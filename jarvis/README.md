# 🧠 JARVIS — Personal AI Operating Layer for Windows

Not a chatbot. A production-oriented agent system that **understands what you
say (English / Hindi / Hinglish), reasons about it, operates your computer
through real tools, verifies the result, and remembers** — with permissions,
risk analysis, and honest failure reporting.

> **Status: Phases 1–4 + 7 complete — 92 automated tests green, including the
> browser agent live-verified against the real web with headless Chromium.**
> Voice, browser agent, vision, GUI arrive in the next phases (below).
> Nothing is faked: every ✅ feature executes and verifies for real; every 🔶
> feature is real code awaiting verification on an actual Windows machine.

---

## Quick start

**Windows (target platform):**
```bat
install.bat          :: venv + deps + config + database
copy .env.example .env   :: add your API key(s)
run.bat              :: start the console
run.bat doctor       :: environment diagnostics
```

**Any platform (dev):**
```bash
pip install -r requirements.txt
python run.py init
python run.py          # console (works offline via the intent fast-path)
pytest                 # run the test suite
```

### Configure a brain
**Gemini is pre-configured** — just put your key in `.env`:
```
JARVIS_GEMINI_API_KEY=AIza...
```
Any other provider: edit `config/models.yaml` (roles: fast/default/reasoning/vision/coding/local),

```yaml
ai:
  models:
    - id: gpt-4o-mini                       # or any OpenAI-compatible model
      provider: openai_compatible
      api_key_env: JARVIS_OPENAI_API_KEY
      roles: [fast, default]
    - id: llama3.1:8b                       # fully local, no key
      provider: ollama
      roles: [local]
  roles:
    default: gpt-4o-mini
    local: llama3.1:8b
```

Anthropic and Gemini are configured the same way (`provider: anthropic` /
`gemini`). Groq/OpenRouter/LM Studio: `provider: openai_compatible` + their
`base_url`.

Without any provider, JARVIS still runs the **deterministic fast-path**
offline — it just tells you honestly that reasoning is unavailable.

### Browser agent (optional, recommended)
```
pip install playwright && playwright install chromium
```
Then searches return real numbered results JARVIS can act on (agent browser is
headed on Windows so you can watch it work; set JARVIS_BROWSER_HEADLESS=1 to
hide it, JARVIS_NO_AGENT_BROWSER=1 to disable).

---

## Honest status matrix

### ✅ Implemented & tested (74 pytest cases)
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
| 24 tools: system info/processes/kill, app open/close, 11 file ops, terminal, run_python, open_url/web_search/fetch_url, remember/recall, reminders, screenshot | `app/tools/builtin/` |
| Write confinement + protected-path guards + zip traversal guard | `app/tools/pathing.py` |
| Short-term memory (DB) + working memory (referents) | `app/memory/manager.py` |
| Conversation persistence, preferences | `app/database/repo.py` |
| CLI REPL with live status + permission prompts; `doctor`, `init` | `app/cli.py` |

### 🔶 Written for Windows, verified only on Linux equivalents
| Capability | Note |
|---|---|
| App discovery via Start Menu `.lnk` scan | Real implementation; exercised via PATH/.desktop fallbacks in CI |
| `taskkill`-based app close, `os.startfile` launch, PowerShell terminal | Isolated, platform-guarded; needs a real Windows pass |
| PowerShell command classification | Patterns written; classify logic itself fully tested |

### ⬜ Not built yet (honest TODOs — phases in docs/ROADMAP.md)
- **Phase 5+**: pywin32 window management (focus/minimize/move/resize), pywinauto UIA clicking/typing
- **Phase 6**: wake word, STT (faster-whisper hi/en), natural TTS, streaming voice loop
- **Phase 7 leftovers**: file uploads, persistent login profiles, Playwright download interception
- **Phase 8**: OCR + vision-model screen understanding (screenshot tool already live)
- **Phase 9**: memory summarization/ranking, specialized agents
- **Phase 10**: Windows Credential Manager secret store, privacy mode
- **Phase 11**: PySide6 GUI + tray + hotkeys
- **Phase 12**: self-healing retries with error classification, plugin API
- **Phase 14**: JARVIS.exe packaging

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
pytest -q               # 74 tests
pytest tests/test_security.py -q
python run.py doctor
```

Conventions: pydantic-typed everything; async by default; tools never import
UI; every tool declares risk + category + schema; every feature gets tests in
the same change. `app/voice|browser|vision|agents|plugins|ui` are honest
stubs — they contain zero fake functionality by design (Spec §61).
