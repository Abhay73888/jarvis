"""Learned User Preferences and Long-Term Memory Injection (Spec Phase 9).

Stores and manages explicit and implicit user habits/preferences:
- Preferred apps & launch styles ("always open VS Code maximized")
- Preferred language styles & communication tone
- Default download / project directories
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.utils.paths import get_paths


class PreferenceManager:
    """Manages persistent user preferences saved to data/preferences.json."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path or (get_paths().data / "preferences.json")
        self._preferences: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                self._preferences = json.loads(self.storage_path.read_text(encoding="utf-8"))
            except Exception:
                self._preferences = {}
        else:
            self._preferences = {}

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(self._preferences, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self._preferences.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._preferences[key] = value
        self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._preferences)

    def format_for_system_prompt(self) -> str:
        """Format learned user preferences into a concise block for LLM system prompt injection."""
        if not self._preferences:
            return ""

        lines = ["USER PREFERENCES & HABITS:"]
        for k, v in self._preferences.items():
            lines.append(f"• {k}: {v}")
        return "\n".join(lines)
