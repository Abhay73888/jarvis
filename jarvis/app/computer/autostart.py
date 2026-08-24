"""Windows Startup management for JARVIS.

Allows JARVIS to launch automatically when the user logs in to Windows.
Uses the Windows user Startup folder (shell:startup) with a silent VBS launcher.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from app.core.logging import get_logger
from app.utils.paths import get_paths

log = get_logger("autostart")


def get_windows_startup_dir() -> Path:
    """Returns the current user's Windows Startup folder."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def get_shortcut_path() -> Path:
    """Path to the JARVIS startup script/shortcut in the Startup folder."""
    return get_windows_startup_dir() / "JARVIS.vbs"


def is_autostart_enabled() -> bool:
    """Check if JARVIS is configured to start with Windows."""
    if sys.platform != "win32":
        return False
    return get_shortcut_path().exists()


def enable_autostart(start_in_tray: bool = True) -> bool:
    """Enable JARVIS auto-start on Windows login using a silent VBS script."""
    if sys.platform != "win32":
        log.warning("Autostart is only supported on Windows.")
        return False

    try:
        startup_dir = get_windows_startup_dir()
        startup_dir.mkdir(parents=True, exist_ok=True)
        shortcut = get_shortcut_path()

        root = get_paths().root
        venv_pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
        python_exe = venv_pythonw if venv_pythonw.exists() else Path(sys.executable)

        tray_flag = " --tray" if start_in_tray else ""
        run_py = root / "run.py"

        # VBScript to launch Python invisibly (0 = hide window)
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{root}"
WshShell.Run """{python_exe}"" ""{run_py}"" app{tray_flag}", 0, False
'''
        shortcut.write_text(vbs_content, encoding="utf-8")
        log.info("enabled JARVIS autostart at: %s", shortcut)
        return True
    except Exception as exc:
        log.exception("failed to enable autostart: %s", exc)
        return False


def disable_autostart() -> bool:
    """Disable JARVIS auto-start by removing the startup file."""
    try:
        shortcut = get_shortcut_path()
        if shortcut.exists():
            shortcut.unlink()
            log.info("disabled JARVIS autostart: removed %s", shortcut)
        return True
    except Exception as exc:
        log.exception("failed to disable autostart: %s", exc)
        return False
