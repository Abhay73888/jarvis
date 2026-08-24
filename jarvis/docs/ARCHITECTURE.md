# JARVIS Architecture

**What this is:** a personal AI operating layer for Windows — voice + text in,
reasoning, real tool execution on the machine, verified results, memory,
permissions, and a GUI — built as a modular agent system, not a chatbot.

**Status:** Phases 1–3 implemented and tested (core, text assistant, LLM
providers, tool system + OS/file/terminal/web tools, permissions, memory
foundation). See `README.md` for the honest status matrix and `ROADMAP.md` for
what comes next.

---

## 1. The hardest engineering problems (and how this design answers them)

| # | Problem | Approach taken |
|---|---------|----------------|
| 1 | **Reliable computer control on Windows** — every app is different | Least-fragile ladder (Spec §2): API/CLI → native shell (PowerShell/taskkill/os.startfile) → semantic UI Automation → vision, in that order. Implemented now: shell-level app control with Start-Menu discovery + process verification. pywinauto/UIA is Phase 5, vision is Phase 8. |
| 2 | **Agent reliability** — LLMs hallucinate success | Tools *verify their own effects* (`ToolResult.verified`) — e.g. open_application polls the process table; file ops check the filesystem; terminal checks exit codes. The engine reports verification state, never assumes. |
| 3 | **Safety without annoying the user** | Risk-level × permission-category matrix (below). Read-only actions run instantly; mutations confirm once; destructive actions always confirm; CRITICAL (disk format, download-and-execute) can never be bypassed by standing grants. |
| 4 | **Prompt injection from web/files** | External content is wrapped in `<untrusted-external-content>` fences inside *tool* messages, never the system prompt; system prompt carries a hard security clause; `detect_injection()` flags classic patterns for logs. |
| 5 | **Latency** — must feel instant | Deterministic intent fast-path answers common commands (EN/HI/Hinglish) in ~0ms with zero network; streaming STT→LLM→TTS pipelining arrives with Phase 6. |
| 6 | **Provider lock-in** | `LLMProvider` abstraction: OpenAI-compatible (OpenAI/Groq/OpenRouter/LM Studio), Anthropic, Gemini, Ollama. `ModelRouter` maps roles (fast/default/reasoning/vision/coding/local) to configured models. |
| 7 | **Unbounded autonomy** | Hard iteration cap on the tool loop, per-command timeouts, cancellation token + emergency stop, CRITICAL-risk refusals. |
| 8 | **Testing GUI/OS automation honestly** | All business logic is loop-free pure async Python — tested with pytest (74 tests). Providers tested via httpx MockTransport. Windows-only surfaces are thin, isolated adapters pending real-Windows verification. |

## 2. Module map

```
jarvis/
├── run.py                    # launcher: cli | init | doctor
├── app/
│   ├── main.py               # composition root (build_runtime)
│   ├── cli.py                # interactive console (Phase 2 UI)
│   ├── core/
│   │   ├── events.py         # async EventBus — engine ⇄ UI decoupling
│   │   ├── exceptions.py     # friendly + detail error model
│   │   └── logging.py        # JSON logs w/ mandatory secret redaction
│   ├── config/settings.py    # typed settings, YAML + ${ENV} interpolation
│   ├── security/
│   │   ├── risk.py           # command risk classifier (LOW→CRITICAL)
│   │   ├── redaction.py      # secret scrubbing (patterns + registered values)
│   │   └── injection.py      # untrusted-content fencing + detection
│   ├── permissions/manager.py# decision matrix, standing grants, confirmations
│   ├── brain/
│   │   ├── provider.py       # LLMProvider ABC, ChatMessage/ToolCall types
│   │   ├── providers/        # openai_compat, anthropic, gemini, ollama
│   │   ├── router.py         # role → model routing
│   │   ├── intent.py         # deterministic EN/HI/Hinglish fast-path NLU
│   │   └── engine.py         # AgentEngine: fast-path + LLM tool loop
│   ├── tools/
│   │   ├── base.py           # BaseTool (schema, risk, validate/execute/rollback)
│   │   ├── manager.py        # registry + permission+verify+log pipeline
│   │   ├── pathing.py        # write confinement, home-folder hints
│   │   └── builtin/          # system, apps, files, terminal, web, memory, screenshot
│   ├── computer/discovery.py # Start Menu / .desktop / PATH app registry
│   ├── memory/manager.py     # short-term (DB) + working (volatile) memory
│   ├── database/             # SQLAlchemy async models, migrations, repos
│   ├── voice/ browser/ vision/ agents/ plugins/ ui/   # phases 5–12 (honest stubs)
│   └── utils/paths.py        # JARVIS_HOME layout, protected-path guards
├── config/                   # user-editable YAML (written by `run.py init`)
├── data/ logs/               # SQLite DB, screenshots, JSON logs
└── tests/                    # 74 pytest cases across security/engine/tools
```

## 3. Communication between modules

- **EventBus** (`app/core/events.py`) is the only channel engine → UI. Topics:
  `status` (thinking/working/speaking/idle), `tool.started`, `tool.finished`,
  `permission.requested`, `interrupt`, `notification`. The console subscribes
  today; the PySide6 GUI (Phase 11) subscribes to the same topics — UI is a
  pure view, never imported by core.
- **ToolContext** carries services into tools (settings, workdir, writable
  roots, session factory) — tools never import global state.
- **PermissionManager.confirm()** delegates to a handler installed by the
  active frontend (CLI prompt today; dialog in Phase 11). Headless ⇒ deny.
- **LLM tool loop**: system prompt (personality + preferences + working memory
  + injection clause) → provider.chat(tools=schemas) → tool_calls →
  ToolManager.execute (validate → permission → run → verify → log) → tool
  result messages → repeat ≤ `agent.max_tool_iterations`.

## 4. Turn lifecycle (one user utterance)

```
user text
  └─ append to conversation (redacted)
  ├─ Intent fast-path matches? ── yes ──► tool pipeline ──► verified reply
  └─ no ──► LLM loop (bounded) ──► tool calls through same pipeline
                                        │
        ┌───────────────────────────────┘
        ▼
   ToolManager.execute
   1. validate args (pydantic)
   2. permission evaluate (risk × category × grants)
   3. confirm via UI handler if required   ← user can deny
   4. execute (real OS/files/terminal/web action)
   5. self-verify effect
   6. publish events + persist redacted tool_usage row
        ▼
   engine formats reply ──► conversation + status events ──► UI/voice
```

## 5. Permission decision matrix

| Risk / flags | policy `allow` | policy `confirm` | policy `deny` |
|---|---|---|---|
| LOW, non-destructive | auto | confirm | block |
| MEDIUM | confirm | confirm | block |
| HIGH or destructive | confirm | confirm | block |
| CRITICAL | **confirm, always — standing grants cannot bypass** | confirm | block |
| standing `allow_always` | auto (except CRITICAL) | auto (except CRITICAL) | — |
| standing `deny` | block | block | block |

Defaults: filesystem/terminal/applications/browser/network/memory/diagnostics
= allow; system = confirm; sensitive = deny. Writes are additionally confined
to `security.writable_roots` (default: user home) and refused inside OS
directories (C:\Windows, Program Files, /etc, ...).

## 6. Database schema (SQLite)

`conversations`, `messages`, `preferences`, `memory_items`, `permission_grants`,
`tool_usage`, `tasks`, `schema_version`. All persisted args/content pass through
`redact()` first — a `sk-...` key typed by a user is stored (and logged) as
`sk-***`.

## 7. Key design decisions worth knowing

1. **Fast-path is a real subsystem, not a toy** — deterministic NLU for the
   ~20 most frequent commands (open/close app, files, diagnostics, searches,
   reminders) in English/Hindi/Hinglish, with one turn of context ("Search
   YouTube." → "What should I search?" → "Arijit Singh"). Keeps JARVIS useful
   with zero API keys and instant for common asks.
2. **open_application is LOW risk by design** — explicit user intent, and the
   friction-free "Chrome kholo → Opening Chrome" UX is the product's soul.
   Stricter users flip `applications: confirm`.
3. **download-and-execute pipelines are refused outright** even with consent
   (classic malware pattern); the user is told to download + inspect + run
   deliberately.
4. **Errors are vocabulary, not stack traces** — every exception carries
   `friendly` (user) + `detail` (dev mode/logs).
5. **No secrets in YAML ever** — models reference env-var *names*; `.env` is
   the only secret store today (Windows Credential Manager arrives with the
   security phase).
