"""Application discovery (Spec §11) — no hard-coded paths.

Windows: Start Menu shortcut scan + PATH lookup (+ App Paths registry via
pywin32 when available). Linux/dev: .desktop entries + PATH. Fuzzy matching
over the indexed names, with a common-alias table.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

from app.utils.paths import IS_WINDOWS

ALIASES: dict[str, str] = {
    "chrome": "Google Chrome", "google chrome": "Google Chrome",
    "edge": "Microsoft Edge", "msedge": "Microsoft Edge",
    "firefox": "Firefox", "vscode": "Visual Studio Code", "vs code": "Visual Studio Code",
    "code": "Visual Studio Code", "spotify": "Spotify", "discord": "Discord",
    "notepad": "Notepad", "calculator": "Calculator", "paint": "Paint",
    "word": "Word", "excel": "Excel", "powerpoint": "PowerPoint",
    "outlook": "Outlook", "photoshop": "Adobe Photoshop", "terminal": "Terminal",
    "powershell": "PowerShell", "cmd": "Command Prompt", "explorer": "File Explorer",
}


@dataclass
class AppEntry:
    name: str          # display name, e.g. "Google Chrome"
    launch: str        # .lnk path, executable path, or .desktop file
    kind: str          # "shortcut" | "executable" | "desktop"


def _start_menu_dirs() -> list[Path]:
    dirs = []
    if IS_WINDOWS:
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        appdata = os.environ.get("APPDATA", "")
        dirs = [
            Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
    return [d for d in dirs if d and d.is_dir()]


def _desktop_dirs() -> list[Path]:
    if IS_WINDOWS:
        return []
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    dirs = [base / "applications", Path("/usr/share/applications")]
    return [d for d in dirs if d.is_dir()]


def _scan_shortcuts() -> list[AppEntry]:
    entries: list[AppEntry] = []
    for directory in _start_menu_dirs():
        for lnk in directory.rglob("*.lnk"):
            entries.append(AppEntry(name=lnk.stem, launch=str(lnk), kind="shortcut"))
            if len(entries) >= 4000:
                return entries
    return entries


def _scan_desktop_entries() -> list[AppEntry]:
    entries: list[AppEntry] = []
    for directory in _desktop_dirs():
        for desk in directory.glob("*.desktop"):
            try:
                name, exec_cmd = None, None
                for line in desk.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("Name=") and name is None:
                        name = line.split("=", 1)[1].strip()
                    elif line.startswith("Exec=") and exec_cmd is None:
                        exec_cmd = line.split("=", 1)[1].strip()
                if name and exec_cmd:
                    entries.append(AppEntry(name=name, launch=exec_cmd, kind="desktop"))
            except OSError:
                continue
    return entries


def _scan_path_executables() -> list[AppEntry]:
    entries: list[AppEntry] = []
    seen: set[str] = set()
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder or not Path(folder).is_dir():
            continue
        try:
            for exe in Path(folder).glob("*.exe" if IS_WINDOWS else "*"):
                if not exe.is_file():
                    continue
                if exe.stem.lower() in seen:
                    continue
                seen.add(exe.stem.lower())
                entries.append(AppEntry(name=exe.stem, launch=str(exe), kind="executable"))
        except (OSError, PermissionError):
            continue
    return entries


async def build_index() -> list[AppEntry]:
    """Assemble the application registry. Runs scans in a worker thread."""
    def _scan() -> list[AppEntry]:
        merged: dict[str, AppEntry] = {}
        for entry in _scan_shortcuts() + _scan_desktop_entries() + _scan_path_executables():
            key = entry.name.lower()
            # Prefer: shortcut > desktop > bare executable
            rank = {"shortcut": 0, "desktop": 1, "executable": 2}[entry.kind]
            if key not in merged or rank < {"shortcut": 0, "desktop": 1, "executable": 2}[merged[key].kind]:
                merged[key] = entry
        return list(merged.values())

    return await asyncio.to_thread(_scan)


def find_apps(query: str, index: list[AppEntry], limit: int = 5) -> list[AppEntry]:
    """Fuzzy-match a user query against the app index. Empty list = not found."""
    q = query.strip().lower()
    if not q:
        return []
    names = {e.name.lower(): e for e in index}

    if q in ALIASES and ALIASES[q].lower() in names:
        return [names[ALIASES[q].lower()]]
    if q in names:
        return [names[q]]

    # Direct substring matches first
    substr = [e for e in index if q in e.name.lower()]
    if substr:
        substr.sort(key=lambda e: len(e.name))
        return substr[:limit]

    # Fuzzy fallback
    close = get_close_matches(q, list(names.keys()), n=limit, cutoff=0.55)
    return [names[c] for c in close]
