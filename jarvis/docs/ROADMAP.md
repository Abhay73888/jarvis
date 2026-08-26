# Roadmap — BUILD → RUN → TEST → DEBUG → VERIFY → DOCUMENT per phase

Legend: ✅ done & tested · 🔶 built, needs real-Windows verification · ⬜ next

## Phase 1 — Core architecture ✅
Config system (typed YAML + env interpolation), EventBus, redacting JSON logs,
exception model, SQLite + migrations, path guards. *74 tests green.*

## Phase 2 — Text assistant ✅
AgentEngine turn loop, conversation persistence, CLI REPL with live status,
permission prompts, `new`/`help`, offline honesty (no fake answers).

## Phase 3 — LLM providers ✅
LLMProvider ABC; OpenAI-compatible (OpenAI/Groq/OpenRouter/LM Studio/vLLM),
Anthropic, Gemini, Ollama; ModelRouter with roles; bounded tool-calling loop;
friendly provider errors; payload/response tests via httpx MockTransport.
**Ships pre-configured for Google Gemini** (user's choice): add
JARVIS_GEMINI_API_KEY to .env and you're live. Gemini key travels in the
x-goog-api-key header, never the URL.

## Phase 4 — Tool system ✅ (foundation; more tools each phase)
BaseTool (schema/risk/validate/execute/rollback), ToolManager pipeline
(validate → permission → execute → verify → log), 24 built-in tools across
system/app/file/terminal/web/memory classes.

## Phase 5 — Windows automation ✅
✅ App discovery (Start Menu `.lnk` scan + PATH + aliases, fuzzy match), open/close with process verification, kill_process, terminal (PowerShell), run_python.
✅ Semantic Win32 window management (`WindowManager` + `ManageWindowTool`): focus, minimize, maximize, restore, move, resize, close by window title substring.

## Phase 6 — Voice ✅
✅ edge-tts + pyttsx3 TTS abstraction (female voice default `en-IN-NeerjaNeural`, rate `+8%`, offline fallback `pyttsx3` with female voice hints).
✅ Time-aware boot greeting with reminder brief (`Good morning/afternoon/evening/Working late, sir`) + Windows Startup batch installation (`python run.py startup install`).
✅ Fast streaming responses (SSE `chat_stream` on Gemini & OpenAI-compatible providers, `Topics.RESPONSE_DELTA`, connection reuse with persistent `httpx.AsyncClient`, non-blocking cpu stats).
✅ faster-whisper STT (`small` model, auto-detect hi/en/Hinglish) + openwakeword local wake word (`jarvis`/`hey jarvis`) + barge-in interrupt (`stop`/`ruk jao`/`abort`) + global push-to-talk (`Ctrl+Space`) and emergency stop (`Ctrl+Shift+Space`). 15 unit tests green.


## Phase 7 — Browser agent ✅ (live-verified with real Chromium)
PlaywrightDriver: semantic DOM snapshots with stable element refs (never
coordinate clicks), verified click/type/navigate, engine-aware search with
redirect-URL decoding (Bing default; DDG/Google/YouTube supported), untrusted
page fencing + injection flags, tabs, page screenshots, honest capability
errors. Fast-path: "X search karo" → numbered results → "first wala kholo"
opens result #1 — the full Spec §67 flow, tested live against the real web and
deterministically against local fixtures (12 browser tests). On Windows the
agent browser runs HEADED so you watch it work. Uploads & persistent login
profiles: Phase 12.

## Phase 8 — Vision ✅
✅ Screen capture via `mss` / Pillow with local file stamping.
✅ Pytesseract OCR with English + Hindi auto-detection and prompt-injection fencing (`fence_untrusted`).
✅ Multimodal vision reasoning (`ScreenAnalyzer`) wired to Google Gemini Vision (`gemini-2.0-flash`), diagnosing active screen errors, stack traces, and suggesting safe remediation steps.
✅ Fast-path intent matching for `"screen pe jo error hai samjho"`, `"ye error samjhao"`, `"screen padho"`, and `"screen par kya likha hai"`. 7 unit tests green.

## Phase 9 — Memory & Preferences ✅
✅ Long-term user preference learning (`PreferenceManager`) injected into LLM system prompts ("always open VS Code maximized", tone, directory preferences).
✅ Project Registry (`ProjectRegistry`) resolving semantic project names ("mera healthcare project kholo") to absolute paths.
✅ End-of-conversation summarizer (`ConversationSummarizer`) extracting memorable facts and preferences into SQLite.

## Phase 10 — Security hardening ⬜
Windows Credential Manager for secrets, privacy mode (local-only routing),
file-content sandboxing review, plugin permission scoping, external audit
of the injection pipeline.

## Phase 11 — GUI + tray ✅
✅ PySide6 dark glass HUD UI (live audio waveform visualizer, streaming chat messages, token-by-token deltas, CPU/RAM telemetry, permission dialogs, settings modal).
✅ System tray icon with open/hide, voice mute toggle, settings, autostart toggle, and clean exit.
✅ Non-blocking async event bridge (`GuiPermissionBridge` & `AsyncWorker`), global Windows hotkey `Ctrl+Shift+J`, offscreen GUI test suite (8 tests).

## Phase 12 — Self-healing & Proactive Monitor ✅
✅ Error classification engine (`ErrorClassifier`): classifies missing dependencies, permission failures, network timeouts, syntax errors, and missing paths.
✅ Automated safe remediation proposals (e.g. `pip install <pkg>`, path verification) with capped retries (max 2).
✅ Proactive background monitor (`ProactiveMonitor`): alerts on disk space (>90%), critical memory (>95%), and due reminders.

## Phase 13 — Testing at scale ✅
✅ 151 automated tests green across the entire repository (core, providers, security, voice loop, offscreen GUI, vision, window control, memory, and self-healing).

## Phase 14 — Standalone Packaging ✅
✅ PyInstaller automated build pipeline (`scripts/build_exe.py`) packaging `dist/JARVIS/JARVIS.exe` with external `.env` and `config/` isolation.

## Phase 15 — Optimization ⬜
Streaming tokens end-to-end, tool-call caching, model router heuristics from
observed latencies, startup time budget.
