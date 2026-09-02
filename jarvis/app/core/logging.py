"""Structured logging with mandatory secret redaction.

Every record passes through `redact()` before formatting. JSON lines go to
logs/jarvis.log; a human-friendly line goes to the console.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.security.redaction import redact, register_environment_secrets

_CONFIGURED = False


class RedactingJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc"] = redact(self.formatException(record.exc_info))
        for key in ("tool", "risk", "duration_ms", "topic", "detail"):
            if hasattr(record, key):
                entry[key] = redact(str(getattr(record, key)))
        return json.dumps(entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = f"{record.levelname[:1]} {record.name}: {redact(record.getMessage())}"
        return line


def setup_logging(logs_dir: Path, level: str = "INFO", dev_mode: bool = False) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    register_environment_secrets()

    root = logging.getLogger("jarvis")
    root.setLevel(logging.DEBUG if dev_mode else level.upper())
    root.handlers.clear()

    file_handler = logging.FileHandler(logs_dir / "jarvis.log", encoding="utf-8")
    file_handler.setFormatter(RedactingJsonFormatter())
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(ConsoleFormatter())
    console.setLevel(logging.DEBUG if dev_mode else logging.WARNING)
    root.addHandler(console)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")
