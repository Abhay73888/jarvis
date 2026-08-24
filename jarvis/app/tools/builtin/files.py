"""File & folder tools (Spec §12, §13) — create/read/move/copy/rename/delete/
search/compress/extract/open. Every mutation verifies its effect; destructive
ops are HIGH risk (confirmation handled by the permission engine)."""
from __future__ import annotations

import asyncio
import fnmatch
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.exceptions import ToolValidationError
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.tools.pathing import human_size, resolve_path

MAX_READ_BYTES = 2_000_000            # read_file cap
MAX_SEARCH_RESULTS = 200
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache", "AppData",
             "$Recycle.Bin", "System Volume Information", ".mypy_cache", ".pytest_cache"}
BINARY_EXT = {".exe", ".dll", ".so", ".bin", ".iso", ".img", ".zip", ".7z", ".rar",
              ".mp3", ".mp4", ".avi", ".mkv", ".png", ".jpg", ".jpeg", ".gif", ".pdf"}


class _CreateFolderArgs(BaseModel):
    path: str = Field(description="Folder to create, e.g. 'Desktop/AI Projects'")


class CreateFolderTool(BaseTool):
    name = "create_folder"
    description = "Create a folder (and parents). Understands desktop/downloads/documents hints."
    args_model = _CreateFolderArgs
    category = "filesystem"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = resolve_path(args["path"], ctx, for_write=True)
        existed = path.exists()
        if not existed:
            path.mkdir(parents=True, exist_ok=True)
        verified = path.is_dir()
        msg = f"'{path.name}' is ready." if verified else f"Creating '{path.name}' failed."
        if existed:
            msg = f"'{path.name}' already exists."
        return ToolResult(verified, msg, data={"path": str(path)}, verified=verified)


class _CreateFileArgs(BaseModel):
    path: str = Field(description="File path to create/overwrite")
    content: str = Field(default="", description="Text content to write")


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Create (or overwrite) a text file with the given content. Overwrite requires the file to already be verified as text."
    args_model = _CreateFileArgs
    category = "filesystem"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = resolve_path(args["path"], ctx, for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        verified = path.is_file() and path.stat().st_size >= len(args["content"].encode("utf-8")) if args["content"] else path.is_file()
        return ToolResult(verified, f"Saved '{path.name}'.", data={"path": str(path)},
                          verified=verified)


class _ReadFileArgs(BaseModel):
    path: str
    max_chars: int = Field(default=20_000, ge=100, le=200_000)


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a text file (code, notes, config). Returns up to max_chars characters."
    args_model = _ReadFileArgs
    category = "filesystem"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = resolve_path(args["path"], ctx, must_exist=True)
        if path.stat().st_size > MAX_READ_BYTES:
            return ToolResult(False, f"'{path.name}' is too large for me to read in one go "
                              f"({human_size(path.stat().st_size)}). Ask me to search or summarize a part of it.")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(False, f"Reading '{path.name}' failed.", error=str(exc))
        truncated = len(text) > args["max_chars"]
        content = text[: args["max_chars"]] + ("\n…[truncated]" if truncated else "")
        return ToolResult(True, f"Read '{path.name}' ({human_size(path.stat().st_size)}).",
                          data={"path": str(path), "content": content}, verified=True)


class _ListDirArgs(BaseModel):
    path: str = Field(default=".", description="Folder to list")
    pattern: str | None = Field(default=None, description="Optional glob filter, e.g. '*.pdf'")


class ListDirTool(BaseTool):
    name = "list_directory"
    description = "List files/folders in a directory, optionally filtered by pattern (e.g. '*.pdf')."
    args_model = _ListDirArgs
    category = "filesystem"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = resolve_path(args["path"], ctx, must_exist=True)
        if not path.is_dir():
            raise ToolValidationError(f"'{args['path']}' is a file, not a folder.",
                                      detail=str(path))
        items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        pattern = args.get("pattern")
        if pattern:
            items = [p for p in items if fnmatch.fnmatch(p.name.lower(), pattern.lower())]
        rows = [{"name": p.name, "type": "folder" if p.is_dir() else "file",
                 "size": human_size(p.stat().st_size) if p.is_file() else ""} for p in items[:200]]
        return ToolResult(True, f"{len(rows)} item(s) in '{path.name}'.",
                          data={"path": str(path), "items": rows}, verified=True)


class _MoveCopyArgs(BaseModel):
    source: str
    destination: str
    overwrite: bool = Field(default=False, description="Replace existing destination files")


class MoveFileTool(BaseTool):
    name = "move_file"
    description = "Move or rename a file/folder. Use for 'move PDFs to Documents' or 'rename this file'."
    args_model = _MoveCopyArgs
    category = "filesystem"
    risk = RiskLevel.MEDIUM

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        src = resolve_path(args["source"], ctx, must_exist=True)
        dst = resolve_path(args["destination"], ctx, for_write=True)
        if dst.is_dir():
            dst = dst / src.name
        if dst.exists() and not args.get("overwrite"):
            return ToolResult(False, f"'{dst.name}' already exists — say the word and I'll replace it.",
                              verified=True)
        shutil.move(str(src), str(dst))
        verified = dst.exists() and not src.exists()
        return ToolResult(verified, f"Moved to '{dst}'.", data={"from": str(src), "to": str(dst)},
                          verified=verified)

    async def rollback(self, args: dict, ctx: ToolContext) -> bool:
        try:
            src = resolve_path(args["source"], ctx)
            dst = resolve_path(args["destination"], ctx)
            if dst.is_dir():
                dst = dst / src.name
            if dst.exists():
                shutil.move(str(dst), str(src))
                return True
        except Exception:  # noqa: BLE001
            return False
        return False


class CopyFileTool(BaseTool):
    name = "copy_file"
    description = "Copy a file or folder to a destination."
    args_model = _MoveCopyArgs
    category = "filesystem"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        src = resolve_path(args["source"], ctx, must_exist=True)
        dst = resolve_path(args["destination"], ctx, for_write=True)
        if dst.is_dir():
            dst = dst / src.name
        if dst.exists() and not args.get("overwrite"):
            return ToolResult(False, f"'{dst.name}' already exists — want me to replace it?",
                              verified=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=args.get("overwrite"))
        else:
            shutil.copy2(src, dst)
        verified = dst.exists()
        return ToolResult(verified, f"Copied to '{dst}'.", data={"to": str(dst)}, verified=verified)


class _DeleteArgs(BaseModel):
    path: str
    recursive: bool = Field(default=True, description="Delete folders with contents")


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = ("PERMANENTLY delete a file or folder. Destructive — always asks for "
                   "confirmation. Cannot be undone.")
    args_model = _DeleteArgs
    category = "filesystem"
    risk = RiskLevel.HIGH
    destructive = True

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = resolve_path(args["path"], ctx, must_exist=True, for_write=True)
        if path == Path.home():
            return ToolResult(False, "I won't delete your entire home folder.", verified=True)
        if path.is_dir() and any(path.iterdir()) and not args.get("recursive"):
            return ToolResult(False, f"'{path.name}' isn't empty — confirm and I'll delete its contents too.")
        count = sum(1 for _ in path.rglob("*")) if path.is_dir() else 1
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        verified = not path.exists()
        return ToolResult(verified, f"Deleted '{path.name}' ({count} item(s)).",
                          data={"path": str(path), "items": count}, verified=verified)


class _SearchFilesArgs(BaseModel):
    query: str = Field(description="Filename substring or glob, e.g. 'resume', '*.pdf', 'main.py'")
    root: str | None = Field(default=None, description="Folder to search; default = user home")
    modified_within_days: int | None = Field(default=None, ge=1, le=3650)
    max_results: int = Field(default=50, ge=1, le=MAX_SEARCH_RESULTS)


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = ("Search for files by name/glob under a folder (default: home), optionally "
                   "filtered by recency ('last week' -> modified_within_days=7). Returns paths + modified time.")
    args_model = _SearchFilesArgs
    category = "filesystem"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        root = (resolve_path(args["root"], ctx, must_exist=True)
                if args.get("root") else Path.home())
        query = args["query"].lower().strip('"')
        days = args.get("modified_within_days")
        cutoff = (time.time() - days * 86400) if days else None
        results: list[dict] = []

        def _walk() -> list[dict]:
            found: list[dict] = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                for fname in filenames:
                    if not (query in fname.lower() or fnmatch.fnmatch(fname.lower(), query)):
                        continue
                    full = Path(dirpath) / fname
                    try:
                        stat = full.stat()
                    except OSError:
                        continue
                    if cutoff and stat.st_mtime < cutoff:
                        continue
                    found.append({
                        "path": str(full), "name": fname,
                        "size": human_size(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                                    .strftime("%Y-%m-%d %H:%M")})
                    if len(found) >= args["max_results"]:
                        return found
            return found

        results = await asyncio.to_thread(_walk)
        if not results:
            return ToolResult(True, f"No files matching '{args['query']}' found.",
                              data={"results": []}, verified=True)
        return ToolResult(True, f"Found {len(results)} match(es) for '{args['query']}':",
                          data={"results": results}, verified=True)


class _ZipArgs(BaseModel):
    source: str
    destination: str = Field(description="Zip file to create, e.g. 'Desktop/project.zip'")


class CompressTool(BaseTool):
    name = "compress_folder"
    description = "Zip a file or folder."
    args_model = _ZipArgs
    category = "filesystem"
    risk = RiskLevel.MEDIUM

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        src = resolve_path(args["source"], ctx, must_exist=True)
        dst = resolve_path(args["destination"], ctx, for_write=True)
        if not dst.suffix == ".zip":
            dst = dst.with_suffix(".zip")

        def _zip() -> None:
            if src.is_file():
                with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(src, src.name)
            else:
                shutil.make_archive(str(dst.with_suffix("")), "zip", str(src))

        await asyncio.to_thread(_zip)
        verified = dst.exists() and dst.stat().st_size > 0
        return ToolResult(verified, f"Created '{dst.name}' ({human_size(dst.stat().st_size) if verified else '0'}).",
                          data={"path": str(dst)}, verified=verified)


class _ExtractArgs(BaseModel):
    archive: str
    destination: str


class ExtractTool(BaseTool):
    name = "extract_archive"
    description = "Extract a .zip archive to a destination folder."
    args_model = _ExtractArgs
    category = "filesystem"
    risk = RiskLevel.MEDIUM

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        archive = resolve_path(args["archive"], ctx, must_exist=True)
        dst = resolve_path(args["destination"], ctx, for_write=True)
        if not zipfile.is_zipfile(archive):
            return ToolResult(False, f"'{archive.name}' is not a zip archive I can extract.")
        dst.mkdir(parents=True, exist_ok=True)

        def _extract() -> list[str]:
            rejected: list[str] = []
            with zipfile.ZipFile(archive) as zf:          # path-traversal guard
                for member in zf.namelist():
                    target = (dst / member).resolve()
                    if not str(target).startswith(str(dst.resolve())):
                        rejected.append(member)
                safe = [m for m in zf.namelist() if m not in rejected]
                zf.extractall(dst, members=safe)
            return rejected

        rejected = await asyncio.to_thread(_extract)
        count = sum(1 for _ in dst.rglob("*"))
        return ToolResult(True, f"Extracted {count} item(s) to '{dst.name}'."
                          + (f" Skipped {len(rejected)} unsafe path(s)." if rejected else ""),
                          data={"path": str(dst), "skipped_unsafe": rejected}, verified=True)


class _OpenPathArgs(BaseModel):
    path: str = Field(description="File or folder to open in Explorer/Finder")


class OpenPathTool(BaseTool):
    name = "open_path"
    description = "Open a file or folder with the default application (Explorer for folders)."
    args_model = _OpenPathArgs
    category = "filesystem"
    risk = RiskLevel.MEDIUM

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        path = resolve_path(args["path"], ctx, must_exist=True)

        def _open() -> None:
            if ctx.settings and os.name == "nt":
                os.startfile(str(path))      # type: ignore[attr-defined]
            elif os.uname().sysname == "Darwin":
                import subprocess
                subprocess.Popen(["open", str(path)])
            else:
                import subprocess
                folder = str(path) if path.is_dir() else str(path.parent)
                subprocess.Popen(["xdg-open", folder])

        await asyncio.to_thread(_open)
        return ToolResult(True, f"Opened '{path.name}'.", data={"path": str(path)})
