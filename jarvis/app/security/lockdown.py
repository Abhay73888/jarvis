"""Emergency Protocol Zero & Workstation Lockdown (Spec §59).

Executes an instantaneous hard security lockdown:
1. Immediately cancels active agent tasks and tool runs.
2. Terminates any running subprocesses and browser instances.
3. Clears sensitive clipboard data and working memory.
4. Locks the Windows workstation using native OS security API (LockWorkStation).
"""
from __future__ import annotations

import ctypes
import os
import sys

import psutil

from app.core.logging import get_logger

log = get_logger("security.lockdown")


def execute_emergency_lockdown(engine=None) -> dict[str, str]:
    """Trigger Emergency Protocol Zero / Code Red."""
    log.critical("EMERGENCY PROTOCOL ZERO TRIGGERED - LOCKING DOWN SYSTEM")
    results = {}

    # 1. Interrupt engine turn
    if engine and hasattr(engine, "interrupt"):
        try:
            engine.interrupt()
            results["engine"] = "Active turns cancelled"
        except Exception as exc:
            results["engine"] = f"Error: {exc}"

    # 2. Terminate spawned child worker processes
    killed_processes = 0
    try:
        current_proc = psutil.Process(os.getpid())
        for child in current_proc.children(recursive=True):
            try:
                child.kill()
                killed_processes += 1
            except Exception:
                pass
        results["processes"] = f"Terminated {killed_processes} child processes"
    except Exception as exc:
        results["processes"] = f"Process cleanup: {exc}"

    # 3. Clear sensitive Windows clipboard data
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.OpenClipboard(None)
            ctypes.windll.user32.EmptyClipboard()
            ctypes.windll.user32.CloseClipboard()
            results["clipboard"] = "Clipboard memory cleared"
        except Exception as exc:
            results["clipboard"] = f"Clipboard clear failed: {exc}"

    # 4. Lock Windows Workstation
    if sys.platform == "win32":
        try:
            locked = ctypes.windll.user32.LockWorkStation()
            results["workstation"] = "Workstation locked successfully" if locked else "LockWorkStation returned False"
        except Exception as exc:
            results["workstation"] = f"LockWorkStation error: {exc}"
    else:
        results["workstation"] = "Non-Windows OS (Lock skipped)"

    return results
