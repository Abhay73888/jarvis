# 🧠 JARVIS — Personal AI Operating Layer for Windows

Not a chatbot. A production-oriented agent system that **understands what you
say (English / Hindi / Hinglish), reasons about it, operates your computer
through real tools, verifies the result, and remembers** — with permissions,
risk analysis, and honest failure reporting.

> **Status: God-Level Desktop OS Layer Complete — 151 automated tests green (100% pass across core, voice, GUI, vision, window control, memory, and self-healing).**
> Fully functional on Windows with real tools, continuous hands-free voice loop, PySide6 dark-glass HUD, multimodal screen vision, semantic window management, and standalone packaging.
> Nothing is faked: every ✅ feature executes and verifies for real.

---

## Quick start

### 🚀 1-Page Setup (Windows)

1. **Install Dependencies & Virtual Environment**:
   ```bat
   install.bat
   ```

2. **Configure API Key in `.env`**:
   Get a free key from [Google AI Studio](https://aistudio.google.com/app/apikey) and put it in `.env`:
   ```env
   JARVIS_GEMINI_API_KEY=AIzaSy...
   ```

3. **Launch Desktop HUD & Voice**:
   ```bat
   run.bat app               :: Start Desktop GUI + Voice Listener
   run.bat cli --speak --voice :: Interactive Console + Speech
   run.bat voice-test        :: Microphone & STT/TTS Diagnostics
   run.bat doctor            :: Full environment diagnostics
   ```
   *(Or double-click **`JARVIS.lnk`** on your Desktop).*

---

## Honest status matrix

### ✅ Implemented & tested (151 pytest cases)
| Capability | Where |
|---|---|
| Typed config (YAML + env interpolation, no secrets in YAML) | `app/config/settings.py` |
| Async event bus (engine ⇄ UI decoupling) | `app/core/events.py` |
| Structured JSON logging with mandatory secret redaction | `app/core/logging.py`, `app/security/redaction.py` |
| Command risk classifier (LOW→CRITICAL, PS+bash) | `app/security/risk.py` |
| Permission engine: categories × risk × standing grants, confirm-flow | `app/permissions/manager.py` |
| Prompt-injection defense (untrusted-content fencing) | `app/security/injection.py` |
| SQLite schema + repos + migration stamping | `app/database/` |
| LLM provider abstraction: OpenAI-compatible / Anthropic / Gemini / Ollama | `app/brain/providers/` |
| Model router (role-based) | `app/brain/router.py` |
| Agent engine: bounded tool loop + cancellation + friendly errors | `app/brain/engine.py` |
| Deterministic intent fast-path (EN/HI/Hinglish + follow-up context) | `app/brain/intent.py` |
| **Browser agent**: semantic refs, verified click/type/navigate, engine-aware search w/ redirect decoding, tabs, untrusted-content fencing | `app/browser/driver.py`, `app/tools/builtin/browser.py` |
| 27 built-in tools: system, apps, 11 file ops, terminal, run_python, web, memory, screenshot, OCR vision, window control | `app/tools/builtin/` |
| Write confinement + protected-path guards + zip traversal guard | `app/tools/pathing.py` |
| Short-term memory (DB) + working memory (referents) | `app/memory/manager.py` |
| Conversation persistence, preferences, summarizer, project registry | `app/memory/` |
| CLI REPL with live status + permission prompts; `doctor`, `init` | `app/cli.py` |
| **Hands-free Voice Loop**: openwakeword wake word, faster-whisper STT (hi/en/Hinglish), barge-in interrupt, global hotkeys (Ctrl+Space, Ctrl+Shift+Space), neural female TTS | `app/voice/` |
| **Desktop HUD GUI & System Tray**: PySide6 dark-glass UI, live audio waveform, token streaming, interactive permission dialogs, settings modal, `Ctrl+Shift+J` hotkey | `app/ui/` |
| **Screen Vision & OCR**: mss capture, pytesseract OCR (eng+hin) with prompt-injection fencing, multimodal error diagnostics via Gemini Vision | `app/vision/`, `app/tools/builtin/vision.py` |
| **Semantic Window Control**: Win32 window management (focus, minimize, maximize, move, resize, close by title) | `app/computer/window_manager.py`, `app/tools/builtin/windows.py` |
| **Self-Healing & Proactive Monitor**: Error classification engine, safe fix proposals, capped retries, proactive disk/memory alerts | `app/brain/self_heal.py`, `app/computer/proactive.py` |
| **Standalone Packaging**: PyInstaller automated executable builder (`scripts/build_exe.py`) | `scripts/build_exe.py` |

## Try it right now (offline, no keys needed)

```
You › chrome kholo                    ← app discovery + launch verification
You › mera laptop slow kyu hai?       ← real psutil diagnostics
You › ram usage kitna hai
You › kaun kaun se apps chal rahe hain
You › desktop pe folder bana AI Projects naam ka
You › downloads ke pdf dhundo
You › python automation tutorial search karo   ← real numbered web results
You › first wala kholo                ← opens result #1 (verified navigation)
You › page par kya likha hai          ← reads page (fenced as untrusted data)
You › search youtube                  ← "What would you like me to search?"
You › arijit singh                    ← context carries the follow-up
You › reminder set karo: call manager tomorrow 10:00
You › meri last week wali resume file dhundo
You › stop                            ← interrupts
```

With a provider configured, everything else goes through the LLM tool loop —
same tools, same permissions, same verification.

## Safety model (short version)

- Destructive/high-risk actions **always** ask; CRITICAL ones can't be
  bypassed even by "always allow".
- Writes confined to your home (configurable); OS directories hard-blocked.
- Unknown terminal commands are treated as MEDIUM risk (ask first).
- Webpage/file text is fenced as untrusted data — never followed as
  instructions. Download-and-execute pipelines are refused outright.
- Secrets live in `.env` only; logs/memory/chat redact them (tested).
- Every tool verifies its own effect and reports `verified` honestly.

Full details: `docs/SECURITY.md`.

## Project layout & docs

```
docs/ARCHITECTURE.md    module map, data flow, decision matrices, design rationale
docs/ROADMAP.md         phase-by-phase plan with acceptance criteria
docs/SECURITY.md        threat model, enforced guarantees, planned hardening
docs/WINDOWS-NOTES.md   UAC/UWP/UIA/AV constraints — the honest limits
```

## Development

```bash
pytest -q               # 113 tests
pytest tests/test_greeting_tts_streaming.py -q
python run.py doctor
```


Conventions: pydantic-typed everything; async by default; tools never import
UI; every tool declares risk + category + schema; every feature gets tests in
the same change. `app/voice|browser|vision|agents|plugins|ui` are honest
stubs — they contain zero fake functionality by design (Spec §61).
