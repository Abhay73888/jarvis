# AGENTS.md — JARVIS Project Instructions

This file gives any coding agent (Google Antigravity / Gemini, Claude Code,
Cursor, etc.) the context needed to work on this repository safely.

## What this project is

JARVIS is a personal AI operating layer for Windows: text/voice assistant +
LLM reasoning + real computer control (apps, files, terminal, browser agent) +
memory + permissions + verification. Built phase-by-phase per the original
spec in `docs/ARCHITECTURE.md` and `docs/ROADMAP.md`.

**Current state: Phases 1–4 + 7 complete, 95 pytest tests green.**

## Ground rules (non-negotiable)

1. **Never fake functionality.** No placeholder functions pretending to work,
   no hard-coded fake responses, no simulated tool execution. If a capability
   can't be implemented yet, mark it `TODO` and explain what's required.
2. **Every feature ships with tests.** Run `pytest -q` before declaring done.
   The suite must stay at 100% pass. Do not weaken or skip tests to go green.
3. **Never commit secrets.** API keys live in `.env` only (git-ignored).
   Models reference env-var NAMES (`api_key_env`), never key values.
   `app/security/redaction.py` must keep scrubbing logs/DB — don't bypass it.
4. **Destructive actions always confirm.** The permission matrix in
   `app/permissions/manager.py` is a safety system, not an inconvenience.
   CRITICAL-risk actions can never be auto-approved. Don't "fix" this.
5. **External content is untrusted data.** Webpage/file text goes through
   `fence_untrusted()` and is never followed as instructions (prompt-injection
   defense). Preserve this in every tool that ingests external text.
6. **Tools verify their own effects** and report `verified` honestly.
   Never claim success without checking the real world (process exists, file
   exists, exit code 0, URL changed...).
7. **No blind coordinate clicking.** Browser actions use semantic element
   refs from DOM snapshots (`app/browser/driver.py`).

## Setup & verification (do this first)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py init          # writes config/*.yaml + .env template guidance
python run.py doctor        # environment diagnostics
pytest -q                   # MUST end with "95 passed" (or more if you added)
```

Optional (browser agent): `pip install playwright && playwright install chromium`
On Windows additionally: `pip install -r requirements-windows.txt`

To talk to JARVIS: `python run.py` (console REPL). Without a provider key it
runs the offline fast-path honestly; add `JARVIS_GEMINI_API_KEY=...` to `.env`
for full reasoning (Gemini is pre-configured in `config/models.yaml`).

## Architecture map (where things live)

```
run.py                 launcher (cli | init | doctor)
app/main.py            composition root — build_runtime()
app/core/              EventBus, redacting JSON logs, exceptions
app/config/settings.py typed settings; YAML + ${ENV} interpolation; .env loader
app/security/          risk classifier, secret redaction, injection defense
app/permissions/       decision matrix + confirm flow (UI installs a handler)
app/brain/             providers (OpenAI-compat/Anthropic/Gemini/Ollama),
                       ModelRouter, intent fast-path (EN/HI/Hinglish), AgentEngine
app/tools/             BaseTool + ToolManager pipeline + builtin/ tools
app/browser/           PlaywrightDriver — semantic refs, verified actions
app/computer/          app discovery (Start Menu / PATH / aliases)
app/memory/            short-term (DB) + working memory (referents)
app/database/          SQLAlchemy async models + repos (SQLite)
app/voice|vision|ui|agents|plugins/   honest stubs — future phases
tests/                 pytest suite incl. real-Chromium browser tests
docs/                  ARCHITECTURE / ROADMAP / SECURITY / WINDOWS-NOTES
```

Key invariants:
- Tool pipeline order is fixed: validate → permission → (confirm) → execute →
  self-verify → redact → persist `tool_usage`. All tools flow through
  `ToolManager.execute()` — never call tool internals directly.
- Engine tool loop is bounded by `agent.max_tool_iterations`; cancellation via
  the interrupt intent ("stop"/"ruk jao"). Keep both.
- UI is a pure EventBus subscriber; core never imports UI.

## Conventions

- Python 3.12+, async by default, pydantic models for all tool args.
- Tool optional args: read with `args.get("key")` — validation dumps with
  `exclude_none=True`, so `args["key"]` KeyErrors on optional fields.
- Friendly errors: raise `app.core.exceptions.*` with `friendly=` + `detail=`;
  no raw stack traces to users (dev mode shows detail).
- Tests: deterministic only. Browser tests run against local fixtures in
  `tests/fixtures/` via an ephemeral HTTP server (see `tests/test_browser.py`).
  Live-web checks are for manual smoke tests, not the suite.

## What to build next (priority order)

1. **Phase 6 — Voice**: openwakeword (local wake word), faster-whisper STT
   (hi/en/Hinglish auto-detect), TTS abstraction (edge-tts + pyttsx3 offline
   fallback), streaming responses, barge-in interrupt. Audio code is
   Windows/WASAPI — write it platform-guarded, test the non-audio logic
   (chunking, state machine, config), mark hardware paths for on-device
   verification.
2. **Phase 11 — GUI + tray** (PySide6): subscribe to existing EventBus topics
   (status, tool.finished, permission.requested); permission dialogs install
   the confirm handler. Dark glass theme, waveform, task status, CPU/RAM.
3. **Phase 8 — Vision**: mss screenshots (tool exists) + pytesseract OCR +
   vision-model reasoning via the `vision` model role.
4. **Phase 12 — Self-healing + plugins**: error classification → safe-fix
   proposals → capped retries; plugin `register(registry)` API.

Update `docs/ROADMAP.md` and the README status matrix when a phase lands.

## Windows verification backlog (needs a real Windows PC)

Items marked 🔶 in README: Start Menu `.lnk` scan, `os.startfile` launch,
`taskkill` close, PowerShell terminal tool, headed Playwright browser.
Verify manually, then flip 🔶 → ✅ in README with evidence.
