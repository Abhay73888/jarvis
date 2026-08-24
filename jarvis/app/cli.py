"""Interactive text console (Phase 2). Voice (§5–7) and the PySide6 GUI (§29)
arrive in later phases; everything here is real and shared with them."""
from __future__ import annotations

import asyncio
import sys

from app.core.events import Topics
from app.permissions.manager import PermissionRequest


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


async def cmd_cli(dev: bool = False) -> int:
    from app.main import build_runtime

    def on_status(topic: str, payload: dict) -> None:
        state, detail = payload.get("state"), payload.get("detail")
        icons = {"listening": "🎙", "thinking": "🧠", "working": "⚙️ ", "speaking": "🔊",
                 "idle": "  ", "error": "⚠️ "}
        if state in ("thinking", "working") and detail:
            print(f"\n  {icons.get(state, '')} {detail} …")

    rt = await build_runtime(confirm_handler=_cli_confirm)
    rt.bus.subscribe(Topics.STATUS, on_status)
    rt.bus.subscribe(Topics.TOOL_FINISHED, lambda t, p: print(
        f"  {'✓' if p['success'] else '✗'} {p['tool']} — {p['message']}"
        + (f"  ({p['duration_ms']} ms)" if dev else "")))

    _print_banner()
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
            return 0
        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("  Goodbye.")
            return 0
        if user_input.lower() in ("help", "?"):
            _print_help()
            continue
        if user_input.lower() in ("new", "new conversation"):
            await rt.conversations.new_conversation()
            print("  Started a fresh conversation.")
            continue

        result = await rt.engine.turn(user_input)
        print(f"\nJARVIS › {result.text}" + ("   (fast-path)" if dev and result.used_fast_path else ""))
        for action in result.actions:
            pass  # details already streamed via TOOL_FINISHED events


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
            "sqlalchemy": "SQLAlchemy", "aiosqlite": "aiosqlite", "psutil": "psutil"}
    for module, label in core.items():
        checks.append((f"core: {label}", find_spec(module) is not None, ""))
    optional = {"mss": "screenshots", "pytesseract": "OCR",
                "PySide6": "GUI (Phase 11)", "faster_whisper": "STT (Phase 6)",
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
