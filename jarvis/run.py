#!/usr/bin/env python3
"""JARVIS launcher.

    python run.py                     # start Desktop GUI App + Voice Listener
    python run.py --voice             # start Interactive Text Console + Voice Loop
    python run.py voice-test          # run Voice & Microphone diagnostics
    python run.py app                 # start Desktop GUI App
    python run.py app --tray          # start minimized in Windows System Tray
    python run.py cli [--speak] [--voice] # interactive text console (with live streaming & TTS)
    python run.py greet [--speak]     # time-aware greeting (used at boot)
    python run.py startup install [--speak] [--console] # install greeting into Windows Startup folder
    python run.py startup remove      # remove startup greeting
    python run.py startup status      # check startup greeting status
    python run.py doctor              # environment diagnostics
    python run.py init                # write default config files
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
    voice = "--voice" in args
    speak = "--speak" in args
    console = "--console" in args

    non_flags = [a for a in args if not a.startswith("--")]
    
    if voice and not non_flags:
        command = "cli"
    else:
        command = non_flags[0] if non_flags else ("cli" if (speak or voice) else "app")

    if command == "init":
        from app.cli import cmd_init
        return asyncio.run(cmd_init())

    if command == "doctor":
        from app.cli import cmd_doctor
        return asyncio.run(cmd_doctor())

    if command in ("voice-test", "voicetest"):
        from app.cli import cmd_voice_test
        return asyncio.run(cmd_voice_test())

    if command == "greet":
        from app.cli import cmd_greet
        return asyncio.run(cmd_greet(speak=speak))

    if command == "startup":
        from app.cli import cmd_startup
        subaction = non_flags[1] if len(non_flags) > 1 else "status"
        return asyncio.run(cmd_startup(subaction, speak=speak, console=console))

    if command in ("cli", "chat", "console"):
        from app.cli import cmd_cli
        return asyncio.run(cmd_cli(dev=dev, speak=speak, voice=voice))

    if command in ("app", "gui", "ui"):
        from app.ui import run_gui_app
        return run_gui_app(start_in_tray=start_in_tray, enable_voice=not no_voice)

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
