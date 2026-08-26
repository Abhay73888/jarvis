"""Interactive text console (Phase 2) with Live Streaming & TTS support.
Voice (§5–7) and the PySide6 GUI (§29) share this engine runtime.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import sys

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


async def cmd_cli(dev: bool = False, speak: bool = False, voice: bool = False) -> int:
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
        if state in ("thinking", "working", "listening") and detail and not streaming_state["active"]:
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

    # Voice listener setup if --voice is passed
    voice_listener = None
    if voice or rt.settings.voice.wake_enabled:
        try:
            from app.voice.listener import VoiceListener
            from app.voice.synthesizer import VoiceSynthesizer
            from app.voice.transcriber import VoiceTranscriber

            transcriber = VoiceTranscriber(model_size=rt.settings.voice.stt_model)
            synthesizer = VoiceSynthesizer(
                voice_name=rt.settings.voice.tts_voice,
                rate=rt.settings.voice.tts_rate,
                bus=rt.bus,
            )
            voice_listener = VoiceListener(
                engine=rt.engine,
                bus=rt.bus,
                settings=rt.settings,
                transcriber=transcriber,
                synthesizer=synthesizer,
                on_wake_callback=lambda: print("\n🎙️ [Wake Word Detected] Listening for command..."),
                on_transcript_callback=lambda txt: print(f"\nYou (voice) › {txt}"),
            )
            asyncio.create_task(voice_listener.start())
            print("  🎙️ Hands-free voice active: Say 'Jarvis' or press Ctrl+Space. Ctrl+Shift+Space to Stop.\n")
        except Exception as exc:
            print(f"  ⚠ Voice listener could not be started: {exc}\n")

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
            if voice_listener:
                voice_listener.stop()
            await rt.router.close()
            return 0
        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("  Goodbye.")
            if voice_listener:
                voice_listener.stop()
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


async def cmd_voice_test() -> int:
    """Run comprehensive voice diagnostics, mic test, and STT/TTS check."""
    import numpy as np
    from app.voice.state import AudioProcessor
    from app.voice.synthesizer import VoiceSynthesizer
    from app.voice.transcriber import VoiceTranscriber

    print("\nJARVIS Voice Diagnostics")
    print("=" * 60)

    # 1. Microphone check via sounddevice
    has_mic = False
    dev_name = "None"
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_in = sd.default.device[0] if sd.default.device else -1
        if default_in is not None and default_in >= 0 and default_in < len(devices):
            dev_name = devices[default_in]["name"]
            has_mic = True
            print(f"  [✓] Microphone input device   : {dev_name}")
        else:
            print("  [✗] Microphone input device   : None found")
    except Exception as exc:
        print(f"  [✗] sounddevice / Microphone  : {exc}")

    # 2. Wake word engine check
    has_wake = False
    try:
        import openwakeword
        from openwakeword.model import Model
        openwakeword.utils.download_models()
        model = Model(wakeword_models=["hey_jarvis", "jarvis"], inference_framework="onnx")
        has_wake = True
        print(f"  [✓] openwakeword wake engine  : models ready (jarvis, hey_jarvis)")
    except Exception as exc:
        print(f"  [!] openwakeword wake engine  : {exc}")

    # 3. STT check
    stt_ok, stt_msg = VoiceTranscriber.check_availability()
    print(f"  [{'✓' if stt_ok else '✗'}] faster-whisper STT        : {stt_msg}")

    # 4. TTS check
    synth = VoiceSynthesizer()
    print(f"  [✓] TTS output engine         : {synth.voice_name} (edge-tts + pyttsx3 fallback)")

    # 5. Live Audio Capture & VAD Test
    print("=" * 60)
    if has_mic:
        print("  Recording 3-second audio sample to test mic & STT...")
        try:
            import sounddevice as sd
            sample_rate = 16000
            duration = 3.0
            print("  🎙️ Speak something now into your microphone...")
            raw_audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
            sd.wait()

            audio_data = raw_audio[:, 0]
            raw_rms = AudioProcessor.calculate_rms(audio_data)
            amplified = AudioProcessor.apply_agc(audio_data)
            amp_rms = AudioProcessor.calculate_rms(amplified)

            print(f"  [✓] Audio captured            : {len(audio_data)} samples @ 16kHz")
            print(f"  [✓] Signal energy (RMS)       : Raw={raw_rms:.5f}, AGC Amplified={amp_rms:.5f}")

            if amp_rms < 0.001:
                print("  ⚠ Low audio signal detected. Speak closer to your microphone or check Windows mic volume.")
            else:
                print("  Transcribing test audio...")
                transcriber = VoiceTranscriber(model_size="small")
                text = await transcriber.transcribe(amplified)
                if text:
                    print(f"  [✓] Transcription output      : \"{text}\"")
                else:
                    print("  [i] No speech detected in test audio clip.")
        except Exception as exc:
            print(f"  [✗] Mic recording error       : {exc}")
    else:
        print("  [!] Microphone not available on this machine. Voice listening will fall back gracefully.")

    print("=" * 60)
    print("  Test complete.\n")
    return 0

