"""Typed settings system.

Sources (deep-merged in order, later wins):
  1. Built-in defaults (this module)
  2. <root>/config/settings.yaml, models.yaml, permissions.yaml, tools.yaml
  3. JARVIS_HOME environment overrides for paths

Secrets: NEVER in YAML. Model entries reference an environment-variable name
(`api_key_env`); the value is read from the environment at call time only.

${VAR} and ${VAR:-default} interpolation is supported in YAML values.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from app.core.exceptions import ConfigError
from app.utils.paths import get_paths

PolicyName = Literal["allow", "confirm", "deny"]

_ENV_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _interpolate(value: Any) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            env_name, default = m.group(1), m.group(2)
            env_val = os.environ.get(env_name)
            if env_val is not None and env_val != "":
                return env_val
            return default if default is not None else m.group(0)
        return _ENV_VAR.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML", detail=str(exc)) from exc
    return _interpolate(data or {})


# ---------------------------------------------------------------- models


class ModelEntry(BaseModel):
    """One pluggable model (Spec §4: no hard-coded provider)."""
    id: str                                  # provider-side model name, e.g. "gpt-4o-mini"
    provider: Literal["openai_compatible", "anthropic", "gemini", "ollama"] = "openai_compatible"
    base_url: str | None = None              # custom OpenAI-compatible endpoint
    api_key_env: str | None = None           # env var holding the key (never the key itself)
    roles: list[str] = Field(default_factory=list)  # e.g. ["fast", "default", "vision"]


class AISettings(BaseModel):
    models: list[ModelEntry] = Field(default_factory=list)
    roles: dict[str, str] = Field(default_factory=dict)   # role -> model.id
    default_role: str = "default"
    temperature: float = 0.3
    max_tokens: int = 1024

    def entry_for_role(self, role: str) -> ModelEntry | None:
        model_id = self.roles.get(role) or self.roles.get(self.default_role)
        if not model_id:
            return None
        return next((m for m in self.models if m.id == model_id), None)


class VoiceSettings(BaseModel):
    wake_words: list[str] = Field(default_factory=lambda: ["jarvis", "hey jarvis"])
    stt_engine: str = "faster-whisper"       # Phase 6
    stt_model: str = "small"
    tts_engine: str = "edge-tts"             # Phase 6
    tts_voice: str = "en-IN-NeerjaNeural"
    voice_gender: str = "female"
    speak_responses: bool = False
    tts_rate: str = "+8%"
    language: str = "auto"                   # auto | en | hi | hinglish


class GreetingSettings(BaseModel):
    enabled: bool = True
    address: str = "sir"
    include_brief: bool = True
    speak: bool = False



class PermissionSettings(BaseModel):
    # Category policy when no standing grant exists (Spec §25).
    categories: dict[str, PolicyName] = Field(default_factory=lambda: {
        "filesystem": "allow",
        "terminal": "allow",
        "applications": "allow",
        "browser": "allow",
        "network": "allow",
        "memory": "allow",
        "diagnostics": "allow",       # read-only: system info, process list, screenshots          # remembering/recalling personal memory
        "system": "confirm",
        "sensitive": "deny",
    })
    # CRITICAL-risk actions always require confirmation, even with a standing grant.
    critical_always_confirms: bool = True
    # Actions on these paths require confirmation regardless of category policy.
    confirm_path_prefixes: list[str] = Field(default_factory=list)


class PersonalitySettings(BaseModel):
    name: str = "JARVIS"
    style: str = (
        "Intelligent, calm, professional, slightly futuristic. Concise and confident. "
        "Do not over-acknowledge (no 'Absolutely!', 'Certainly!'). Speak naturally."
    )
    language_style: Literal["auto", "english", "hinglish"] = "auto"
    verbosity: Literal["concise", "normal"] = "concise"


class MemorySettings(BaseModel):
    history_window: int = 20                 # messages fed to the LLM
    persist_conversations: bool = True


class AgentSettings(BaseModel):
    max_tool_iterations: int = 6
    intent_fast_path: bool = True            # instant local handling of common commands
    terminal_timeout_s: int = 60
    max_terminal_timeout_s: int = 600
    max_retries: int = 2                     # Phase 12: self-healing


class UISettings(BaseModel):
    theme: str = "dark"
    show_waveform: bool = True
    hotkey_activate: str = "ctrl+space"
    hotkey_stop: str = "ctrl+shift+space"


class SecuritySettings(BaseModel):
    # Writes (create/move/delete/compress) are confined to these roots.
    writable_roots: list[str] = Field(default_factory=lambda: ["~"])
    redact_logs: bool = True


class DevSettings(BaseModel):
    enabled: bool = False                    # stack traces, raw tool args, log viewer


class ToolsSettings(BaseModel):
    disabled: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    ai: AISettings = Field(default_factory=AISettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    greeting: GreetingSettings = Field(default_factory=GreetingSettings)
    permissions: PermissionSettings = Field(default_factory=PermissionSettings)
    personality: PersonalitySettings = Field(default_factory=PersonalitySettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    ui: UISettings = Field(default_factory=UISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    dev: DevSettings = Field(default_factory=DevSettings)
    tools: ToolsSettings = Field(default_factory=ToolsSettings)
    log_level: str = "INFO"


    def writable_roots_resolved(self) -> list[Path]:
        roots = []
        for raw in self.security.writable_roots:
            roots.append(Path(os.path.expandvars(raw)).expanduser().resolve())
        return roots


DEFAULT_SETTINGS_YAML = """\
# JARVIS settings — user overrides. Delete the file to restore defaults.
# Secrets NEVER go here: models reference environment variable names.

greeting:
  enabled: true
  address: "sir"
  include_brief: true
  speak: false

voice:
  tts_engine: "edge-tts"
  tts_voice: "en-IN-NeerjaNeural"
  voice_gender: "female"
  tts_rate: "+8%"
  speak_responses: false

personality:
  name: JARVIS
  language_style: auto        # auto | english | hinglish

agent:
  intent_fast_path: true      # instant local handling of "chrome kholo" style commands

log_level: INFO
dev:
  enabled: false
"""


DEFAULT_MODELS_YAML = """\
# Models & roles (Spec §33 model router). PRE-CONFIGURED for Google Gemini —
# just put your key in .env:  JARVIS_GEMINI_API_KEY=AIza...
# Add more providers below; keys always live in .env, referenced by env NAME.
#
# roles: fast | default | reasoning | vision | coding | local
ai:
  models:
    - id: gemini-3.7-flash
      provider: gemini
      api_key_env: JARVIS_GEMINI_API_KEY
      roles: [fast, default, vision, reasoning, coding]
  roles:
    fast: gemini-3.7-flash
    default: gemini-3.7-flash
    reasoning: gemini-3.7-flash
    vision: gemini-3.7-flash
    coding: gemini-3.7-flash
  default_role: default


# --- Other providers (uncomment & edit) ------------------------------
# OpenAI / OpenAI-compatible (Groq, OpenRouter, LM Studio, vLLM...):
#     - id: gpt-4o-mini
#       provider: openai_compatible
#       api_key_env: JARVIS_OPENAI_API_KEY
#       roles: [fast, default]
# Custom endpoint example (Groq):
#     - id: llama-3.3-70b-versatile
#       provider: openai_compatible
#       base_url: https://api.groq.com/openai/v1
#       api_key_env: JARVIS_COMPAT_API_KEY
#       roles: [fast]
# Anthropic:
#     - id: claude-sonnet-4-5
#       provider: anthropic
#       api_key_env: JARVIS_ANTHROPIC_API_KEY
#       roles: [reasoning, coding]
# Ollama (local, no key):
#     - id: llama3.1:8b
#       provider: ollama
#       roles: [local]
"""

DEFAULT_PERMISSIONS_YAML = """\
# Permission policies (Spec §25). Categories: filesystem, terminal, applications,
# browser, network, system, sensitive. Policy: allow | confirm | deny.
# allow   -> LOW-risk actions run instantly; MEDIUM+ still ask once.
# confirm -> every action in this category asks.
# deny    -> blocked entirely.
permissions:
  categories:
    filesystem: allow
    terminal: allow
    applications: allow
    browser: allow
    network: allow
    memory: allow
    diagnostics: allow
    system: confirm
    sensitive: deny
  critical_always_confirms: true
"""

DEFAULT_TOOLS_YAML = """\
# Disable specific tools by name.
tools:
  disabled: []
"""


def load_settings(root: Path | None = None) -> Settings:
    from app.utils.paths import Paths, get_paths  # local import to avoid cycle in tests

    paths: Paths = get_paths() if root is None else Paths(
        root=root, config=root / "config", data=root / "data", logs=root / "logs",
        screenshots=root / "data" / "screenshots", db_file=root / "data" / "jarvis.db",
    ).ensure()

    merged: dict[str, Any] = {}
    merged = _deep_merge(merged, _load_yaml(paths.config / "settings.yaml"))
    # Fresh install: embedded defaults (Gemini pre-configured) apply until the
    # user writes their own models.yaml; their file always wins after that.
    if (paths.config / "models.yaml").exists():
        merged = _deep_merge(merged, _load_yaml(paths.config / "models.yaml"))
    else:
        import yaml as _yaml
        merged = _deep_merge(merged, _interpolate(_yaml.safe_load(DEFAULT_MODELS_YAML) or {}))
    merged = _deep_merge(merged, _load_yaml(paths.config / "permissions.yaml"))
    merged = _deep_merge(merged, _load_yaml(paths.config / "tools.yaml"))
    try:
        return Settings.model_validate(merged)
    except Exception as exc:  # pydantic ValidationError
        raise ConfigError("Invalid settings — see docs/README for the schema", detail=str(exc)) from exc


def write_default_configs(overwrite: bool = False) -> list[Path]:
    """Materialize default YAML files into config/ so users can edit them."""
    paths = get_paths()
    paths.config.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in (
        ("settings.yaml", DEFAULT_SETTINGS_YAML),
        ("models.yaml", DEFAULT_MODELS_YAML),
        ("permissions.yaml", DEFAULT_PERMISSIONS_YAML),
        ("tools.yaml", DEFAULT_TOOLS_YAML),
    ):
        target = paths.config / name
        if overwrite or not target.exists():
            target.write_text(content, encoding="utf-8")
            written.append(target)
    return written


def load_dotenv(root: Path | None = None) -> list[str]:
    """Minimal .env loader (KEY=VALUE lines; # comments; no shell expansion).
    Never overrides variables already present in the environment. Returns loaded keys."""
    from app.utils.paths import get_paths
    paths_root = root or get_paths().root
    env_file = paths_root / ".env"
    if not env_file.exists():
        if (paths_root.parent / ".env").exists():
            env_file = paths_root.parent / ".env"
        elif (Path.cwd() / ".env").exists():
            env_file = Path.cwd() / ".env"
        else:
            return []

    loaded: list[str] = []
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ and value:
                os.environ[key] = value
                loaded.append(key)
    except OSError:
        pass
    return loaded
