# Security Model

## Threat model
JARVIS executes real actions on the user's machine with the user's authority.
Primary risks: destructive commands, credential leakage, prompt injection from
external content, and privilege-confusion (assistant acting beyond intent).

## Enforced today (code + tests)

1. **Secret hygiene** (`app/security/redaction.py`)
   - Known secret shapes (sk-, ghp_, AKIA, AIza, xox-, JWTs, Bearer, private
     keys, key=value pairs incl. `token=`) scrubbed everywhere text is logged
     or persisted.
   - Values of secret-named env vars auto-registered at startup.
   - `remember` tool refuses content that redaction changes (looks like a
     secret) — tested.
2. **Secrets never in config** — models.yaml stores env-var *names* only;
   `.env` is the sole secret store; `.gitignore` blocks it.
3. **Risk classification** (`app/security/risk.py`) — CRITICAL/HIGH/MEDIUM/LOW
   with Hinglish-aware command surface (PowerShell + bash); unknown commands
   default to MEDIUM (caution).
4. **Permission matrix** (`app/permissions/manager.py`) — categories × risk ×
   standing grants; CRITICAL always confirms; deny-by-default when no UI
   handler is connected. Standing grants stored per tool/category.
5. **Write confinement** — file mutations restricted to
   `security.writable_roots` (default: home); OS directories hard-blocked;
   zip extraction path-traversal guard; `delete_file` can never touch the
   home root itself.
6. **Prompt-injection defense** (`app/security/injection.py`) — external text
   is fenced as untrusted data inside tool messages; system prompt forbids
   following it; classic injection phrasing flagged to logs (tested).
7. **Download-and-execute refusal** — `curl|sh`, `irm|iex` pipelines are
   refused even with user confirmation, with an explanation.
8. **Bounded autonomy** — max tool iterations, per-command timeouts,
   cancellation token, emergency stop intent ("stop"/"ruk jao"/hotkey Phase 11).
9. **Structured logs** — JSON with timestamp/tool/risk/duration; redaction
   filter on every record; no secrets in `tool_usage` rows (tested).

## Planned (Phase 10)
- Windows Credential Manager / DPAPI-backed secret store.
- Privacy mode: route to local models only, disable non-local network tools.
- Plugin permission scoping (a Spotify plugin cannot read the filesystem).
- Optional per-tool allowlists for corporate deployments.
