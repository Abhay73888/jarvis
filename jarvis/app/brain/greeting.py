"""Time-aware greeting generator and startup helper (Feature 1).

Generates context-aware greetings based on time-of-day, day/date, and pending reminders.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def build_greeting(
    now: datetime,
    address: str = "sir",
    include_brief: bool = True,
    pending_today: int = 0,
) -> str:
    """Build a time-aware greeting string.

    Time buckets:
      - 5am - 12pm:  "Good morning, {address}."
      - 12pm - 5pm:  "Good afternoon, {address}."
      - 5pm - 9pm:   "Good evening, {address}."
      - 9pm - 5am:   "Working late, {address}."

    If include_brief is True:
      - Appends "Today is {Day}, {Month} {Day_Number}."
      - Appends "You have {N} reminder(s) due today." if pending_today > 0.
    """
    hour = now.hour
    if 5 <= hour < 12:
        salutation = f"Good morning, {address}."
    elif 12 <= hour < 17:
        salutation = f"Good afternoon, {address}."
    elif 17 <= hour < 21:
        salutation = f"Good evening, {address}."
    else:
        salutation = f"Working late, {address}."

    if not include_brief:
        return salutation

    day_str = now.strftime("%A, %B %d").replace(" 0", " ")
    brief = f" Today is {day_str}."

    if pending_today > 0:
        rem_text = "1 reminder" if pending_today == 1 else f"{pending_today} reminders"
        brief += f" You have {rem_text} due today."

    return salutation + brief


def get_windows_startup_dir() -> Path:
    """Resolve the Windows per-user Startup folder (shell:startup)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if p.exists() or sys.platform == "win32":
            return p
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def get_startup_bat_path(target_dir: Optional[Path] = None) -> Path:
    """Return the path to JARVIS-Greeting.bat."""
    base_dir = target_dir or get_windows_startup_dir()
    return base_dir / "JARVIS-Greeting.bat"


def install_startup_bat(
    project_root: Path,
    speak: bool = False,
    console: bool = False,
    target_dir: Optional[Path] = None,
) -> Path:
    """Install JARVIS-Greeting.bat into the user's Startup folder.

    Explicit opt-in only.
    """
    bat_path = get_startup_bat_path(target_dir)
    bat_path.parent.mkdir(parents=True, exist_ok=True)

    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    venv_pythonw = project_root / ".venv" / "Scripts" / "pythonw.exe"

    py_exe = venv_python if console else venv_pythonw
    if not py_exe.exists():
        py_exe = Path("python.exe" if console else "pythonw.exe")

    speak_flag = " --speak" if speak else ""
    lines = [
        "@echo off",
        f'cd /d "{project_root}"',
        f'start "" "{py_exe}" run.py greet{speak_flag}',
    ]

    bat_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return bat_path


def remove_startup_bat(target_dir: Optional[Path] = None) -> bool:
    """Remove JARVIS-Greeting.bat from the user's Startup folder."""
    bat_path = get_startup_bat_path(target_dir)
    if bat_path.exists():
        bat_path.unlink()
        return True
    return False


def get_startup_status(target_dir: Optional[Path] = None) -> dict[str, Any]:
    """Check whether JARVIS startup greeting is installed."""
    bat_path = get_startup_bat_path(target_dir)
    installed = bat_path.exists()
    content = bat_path.read_text(encoding="utf-8") if installed else ""
    return {
        "installed": installed,
        "path": str(bat_path),
        "content": content,
    }
