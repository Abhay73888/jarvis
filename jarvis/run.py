#!/usr/bin/env python3
"""JARVIS launcher.

    python run.py            # start Desktop GUI App + Voice Listener
    python run.py app        # start Desktop GUI App
    python run.py app --tray # start minimized in Windows System Tray
    python run.py cli        # interactive text console
    python run.py doctor     # environment diagnostics
    python run.py init       # write default config files
"""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    args = sys.argv[1:]
    dev = "--dev" in args
    start_in_tray = "--tray" in args
    no_voice = "--no-voice" in args

    command = next((a for a in args if not a.startswith("--")), "app")

    if command == "init":
        return asyncio.run(_init())
    if command == "doctor":
        return asyncio.run(_doctor())
    if command == "cli" or command == "chat" or command == "console":
        from app.cli import cmd_cli
        return asyncio.run(cmd_cli(dev=dev))
    if command == "app" or command == "gui" or command == "ui":
        from app.ui import run_gui_app
        return run_gui_app(start_in_tray=start_in_tray, enable_voice=not no_voice)

    print(__doc__)
    return 2


async def _init() -> int:
    from app.cli import cmd_init
    return await cmd_init()


async def _doctor() -> int:
    from app.cli import cmd_doctor
    return await cmd_doctor()


if __name__ == "__main__":
    raise SystemExit(main())
