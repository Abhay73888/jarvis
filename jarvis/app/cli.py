"""Interactive text console (Phase 2) with Live Streaming & TTS support.
Voice (§5–7) and the PySide6 GUI (§29) share this engine runtime.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from app.brain.greeting import (
    build_greeting,
    get_startup_status,
    install_startup_bat,
    remove_startup_bat,
)
from app.core.events import Topics
from app.permissions.manager import PermissionRequest
from app.voice.tts import TTSManager


def _print_banner() -> None:
    print(
        "\n  ┌─────────────────────────────────────────────┐\n"
        "  │            J A R V I S   v0.1                │\n"
        "  │   personal AI operating layer  ·  console    │\n"
        "  └─────────────────────────────────────────────┘\n"
        "  Type naturally. 'help' for commands, 'exit' to quit.\n")


async def _cli_confirm(request: PermissionRequest) -> str:
    print("\n  ⚠  PERMISSION REQUESTED")
    print(f"     action : {request.tool_name}")
    print(f"     risk   : {request.risk.label}")
    print(f"     why    : {request.reason}")
    if request.args_summary:
        shown = ", ".join(f"{k}={v}" for k, v in list(request.args_summary.items())[:4])
        print(f"     args   : {shown}")
    while True:
        answer = input("     [1] Allow once   [2] Always allow   [3] Deny  → ").strip()
        if answer in ("1", ""):
            return "allow_once"
        if answer == "2":
            return "allow_always"
        if answer in ("3", "n", "no"):
            return "deny"
        print("     Enter 1, 2 or 3.")


async def cmd_cli(dev: bool = False, speak: bool = False) -> int:
    from app.main import build_runtime

    rt = await build_runtime(confirm_handler=_cli_confirm)

    should_speak = speak or rt.settings.voice.speak_responses
    tts = TTSManager(
        voice=rt.settings.voice.tts_voice,
        rate=rt.settings.voice.tts_rate,
        gender=rt.settings.voice.voice_gender,
    )

    streaming_state = {"active": False, "printed_header": False}

    def on_status(topic: str, payload: dict) -> None:
        state, detail = payload.get("state"), payload.get("detail")
        icons = {"listening": "🎙", "thinking": "🧠", "working": "⚙️ ", "speaking": "🔊",
                 "idle": "  ", "error": "⚠️ "}
        if state in ("thinking", "working") and detail and not streaming_state["active"]:
            print(f"\n  {icons.get(state, '')} {detail} …")

    def on_response_delta(topic: str, payload: dict) -> None:
        delta = payload.get("delta", "")
        if delta:
            if not streaming_state["printed_header"]:
                print("\nJARVIS › ", end="", flush=True)
                streaming_state["printed_header"] = True
                streaming_state["active"] = True
            print(delta, end="", flush=True)

    rt.bus.subscribe(Topics.STATUS, on_status)
    rt.bus.subscribe(Topics.RESPONSE_DELTA, on_response_delta)
    rt.bus.subscribe(Topics.TOOL_FINISHED, lambda t, p: print(
        f"  {'✓' if p['success'] else '✗'} {p['tool']} — {p['message']}"
        + (f"  ({p['duration_ms']} ms)" if dev else "")))

    _print_banner()

    # Time-aware startup greeting
    if rt.settings.greeting.enabled:
        pending_count = 0
        try:
            pending_tasks = await rt.tasks.list("pending")
            today = datetime.now().date()
            pending_count = sum(1 for t in pending_tasks if t.due_at and t.due_at.date() <= today)
        except Exception:
            pass

        greeting = build_greeting(
            now=datetime.now(),
            address=rt.settings.greeting.address,
            include_brief=rt.settings.greeting.include_brief,
            pending_today=pending_count,
        )
        print(f"  {greeting}\n")
        if should_speak or rt.settings.greeting.speak:
            await tts.speak(greeting)

    if not rt.router.has_provider:
        print("  ℹ  No AI model configured — offline fast-path active "
              "(open/close apps, files, system, searches, reminders).\n"
              "     Add a provider in config/models.yaml + .env for full reasoning.\n")

    loop = asyncio.get_running_loop()
    while True:
        try:
            user_input = await loop.run_in_executor(None, lambda: input("\nYou › "))
        except (EOFError, KeyboardInterrupt):
            print("\n  JARVIS shutting down. Goodbye.")
            await rt.router.close()
            return 0
        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("  Goodbye.")
            await rt.router.close()
            return 0
        if user_input.lower() in ("help", "?"):
            _print_help()
            continue
        if user_input.lower() in ("new", "new conversation"):
            await rt.conversations.new_conversation()
            print("  Started a fresh conversation.")
            continue

        streaming_state["active"] = False
        streaming_state["printed_header"] = False

        result = await rt.engine.turn(user_input)

        if not streaming_state["printed_header"]:
            print(f"\nJARVIS › {result.text}" + ("   (fast-path)" if dev and result.used_fast_path else ""))
        else:
            print()  # newline after live streaming

        if should_speak and result.text:
            await tts.speak(result.text)


async def cmd_greet(speak: bool = False) -> int:
    """One-shot time-aware greeting command (used at boot)."""
    from app.main import build_runtime

    rt = await build_runtime()
    pending_count = 0
    try:
        pending_tasks = await rt.tasks.list("pending")
        today = datetime.now().date()
        pending_count = sum(1 for t in pending_tasks if t.due_at and t.due_at.date() <= today)
    except Exception:
        pass

    greeting = build_greeting(
        now=datetime.now(),
        address=rt.settings.greeting.address,
        include_brief=rt.settings.greeting.include_brief,
        pending_today=pending_count,
    )
    print(greeting)

    should_speak = speak or rt.settings.greeting.speak or rt.settings.voice.speak_responses
    if should_speak:
        tts = TTSManager(
            voice=rt.settings.voice.tts_voice,
            rate=rt.settings.voice.tts_rate,
            gender=rt.settings.voice.voice_gender,
        )
        await tts.speak(greeting)

    await rt.router.close()
    return 0


async def cmd_startup(action: str = "status", speak: bool = False, console: bool = False) -> int:
    """Manage Windows Startup folder integration for greeting at boot."""
    from app.utils.paths import get_paths
    root = get_paths().root

    if action == "install":
        bat_path = install_startup_bat(root, speak=speak, console=console)
        print(f"[OK] Installed startup greeting into:\n     {bat_path}")
        print(f"     Mode: {'Console' if console else 'Silent (pythonw.exe)'}, Speak: {speak}")
        return 0

    if action == "remove":
        removed = remove_startup_bat()
        if removed:
            print("[OK] Removed startup greeting from Windows Startup folder.")
        else:
            print("[INFO] Startup greeting was not installed.")
        return 0

    if action == "status":
        info = get_startup_status()
        print("\nJARVIS Startup Greeting Status")
        print("=" * 50)
        print(f"  Installed : {'YES' if info['installed'] else 'NO'}")
        print(f"  Location  : {info['path']}")
        if info["installed"]:
            print("\n  --- File Content ---")
            print("  " + "\n  ".join(info["content"].splitlines()))
        print("=" * 50)
        return 0

    print(f"Unknown startup action: '{action}'. Choose from: install, remove, status")
    return 2


def _print_help() -> None:
    print(
        "\n  Examples (English / Hindi / Hinglish):\n"
        "    chrome kholo · open vs code · spotify chalao\n"
        "    downloads folder kholo · files dhundo resume\n"
        "    youtube pe arijit singh search karo · google kholo\n"
        "    system info · ram usage kitna hai · kaun se apps chal rahe hain\n"
        "    chrome band karo · screenshot lo\n"
        "    reminder set karo: call manager tomorrow 10:00\n"
        "    explain this error (paste it)\n"
        "  Commands: help · new (conversation) · exit\n"
        "  Config:   config/models.yaml (providers), .env (keys)")


async def cmd_doctor() -> int:
    from importlib.util import find_spec

    from app.config.settings import load_dotenv, load_settings
    from app.utils.paths import get_paths

    paths = get_paths()
    load_dotenv(paths.root)
    settings = load_settings(paths.root)
    checks: list[tuple[str, bool, str]] = []

    checks.append(("Python ≥ 3.12", sys.version_info >= (3, 12), sys.version.split()[0]))
    core = {"pydantic": "pydantic", "yaml": "PyYAML", "httpx": "httpx",
            "sqlalchemy": "SQLAlchemy", "aiosqlite": "aiosqlite", "psutil": "psutil",
            "edge_tts": "edge-tts (TTS)"}
    for module, label in core.items():
        checks.append((f"core: {label}", find_spec(module) is not None, ""))
    optional = {"mss": "screenshots", "pytesseract": "OCR",
                "PySide6": "GUI (Phase 11)", "faster_whisper": "STT (Phase 6)",
                "playsound": "audio playback (Phase 6)",
                "pyttsx3": "offline TTS (Phase 6)",
                "playwright": "browser agent (Phase 7)"}
    for module, label in optional.items():
        checks.append((f"optional: {label}", find_spec(module) is not None,
                       "not installed" if find_spec(module) is None else "ok"))

    providers = settings.ai.models
    checks.append(("models configured", bool(providers), str(len(providers))))
    if providers:
        import os
        for m in providers:
            has_key = (not m.api_key_env) or bool(os.environ.get(m.api_key_env))
            checks.append((f"key: {m.api_key_env or '(none needed)'}", has_key,
                           m.provider))
    checks.append(("config dir writable", _dir_writable(paths.config), str(paths.config)))
    checks.append(("data dir writable", _dir_writable(paths.data), str(paths.data)))

    print("\nJARVIS doctor\n" + "=" * 60)
    failures = 0
    for label, ok, note in checks:
        failures += not ok
        print(f"  [{'✓' if ok else '✗'}] {label:<28} {note}")
    print("=" * 60)
    print("  Platform note: full computer control (Win32/UIA, tray, wake word)\n"
          "  activates on Windows with requirements-windows.txt installed.\n")
    return 1 if failures else 0


def _dir_writable(path) -> bool:
    try:
        probe = path / ".probe"
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


async def cmd_init() -> int:
    from app.config.settings import write_default_configs
    written = write_default_configs()
    if written:
        print("Created:\n  " + "\n  ".join(str(p) for p in written))
    else:
        print("Config files already exist — nothing overwritten.")
    print("Next: copy .env.example to .env and add your API key(s),\n"
          "then edit config/models.yaml to point at your provider.")
    return 0
