"""Secret hygiene. Single source of truth for scrubbing secrets.

Used by the log formatter, DB persistence layer, and any place untrusted or
sensitive strings may flow. Spec §39/§69: never expose keys, tokens, cookies,
or private keys in logs, chat history, memory, or error reports.
"""
from __future__ import annotations

import os
import re

# Registered secret *values* (e.g. the actual contents of JARVIS_OPENAI_API_KEY).
_DYNAMIC_SECRETS: set[str] = set()

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"ghp_[A-Za-z0-9]{16,}"), "ghp-***"),
    (re.compile(r"gho_[A-Za-z0-9]{16,}"), "gho-***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat-***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "AIza***"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "xox-***"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"), "<jwt-***>"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***"),
    (re.compile(
        r"(?i)((?:api[_\-]?key|apikey|access[_\-]?token|auth[_\-]?token|token|secret|password|passwd|pwd|client[_\-]?secret)"
        r"[\s\"']*[:=][\s\"']*)[^\s\"',;]{4,}"), r"\1***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "<private-key>"),
)

_SECRETISH_NAME = re.compile(r"(?i)(api.?key|token|secret|password|passwd|credential)")


def register_secret(value: str) -> None:
    """Register a raw secret value so it is redacted wherever it appears."""
    if value and len(value) >= 8:
        _DYNAMIC_SECRETS.add(value)


def register_environment_secrets() -> None:
    """Auto-register values of environment variables with secret-ish names."""
    for name, value in os.environ.items():
        if _SECRETISH_NAME.search(name) and value and len(value) >= 8:
            register_secret(value)


def redact(text: str) -> str:
    """Return text with known secret shapes and registered values removed."""
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    for secret in _DYNAMIC_SECRETS:
        if secret in text:
            text = text.replace(secret, "***")
    return text


def redact_mapping(mapping: dict) -> dict:
    """Recursively redact all string values in a JSON-able structure."""
    out: dict = {}
    for key, value in mapping.items():
        if isinstance(value, str):
            out[key] = redact(value)
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        elif isinstance(value, (list, tuple)):
            out[key] = [redact(v) if isinstance(v, str) else redact_mapping(v) if isinstance(v, dict) else v
                        for v in value]
        else:
            out[key] = value
    return out
