"""Shared helpers for file tools: path safety + natural-language path parsing.

Writes are confined to configured writable roots (default: user home) and are
refused inside OS-protected directories (Spec §12, §69).
"""
from __future__ import annotations

from pathlib import Path

from app.core.exceptions import ToolValidationError
from app.tools.base import ToolContext
from app.utils.paths import is_protected_write_target

_HOME_HINTS = {
    "desktop": "Desktop", "downloads": "Downloads", "documents": "Documents",
    "pictures": "Pictures", "videos": "Videos", "music": "Music",
}


def resolve_path(raw: str, ctx: ToolContext, must_exist: bool = False,
                 for_write: bool = False) -> Path:
    """Resolve a user-supplied path against the working directory.

    Accepts absolute paths, home-folder hints ("desktop"), and relative paths.
    Enforces write confinement and OS-protected directories.
    """
    raw = (raw or "").strip().strip('"').strip("'")
    if not raw:
        raise ToolValidationError("A path is required.", detail="empty path")

    lowered = raw.lower().rstrip("\\/").replace("\\", "/")
    if "/" not in lowered and lowered in _HOME_HINTS:
        path = Path.home() / _HOME_HINTS[lowered]
    else:
        candidate = Path(raw.replace("\\", "/") if raw.startswith("/") else raw)
        path = candidate if candidate.is_absolute() else (ctx.workdir / candidate)
    path = path.expanduser().resolve()

    if must_exist and not path.exists():
        raise ToolValidationError(
            f"I couldn't find '{raw}'.", detail=f"path does not exist: {path}")

    if is_protected_write_target(path):
        raise ToolValidationError(
            "That location is a protected system area — I won't modify it.",
            detail=f"protected write target: {path}")

    if for_write and not _is_writable(path, ctx):
        raise ToolValidationError(
            "That location is outside the folders I'm allowed to modify "
            "(see security.writable_roots in settings).",
            detail=f"outside writable roots: {path}")
    return path


def _is_writable(path: Path, ctx: ToolContext) -> bool:
    for root in ctx.writable_roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"
