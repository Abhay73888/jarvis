"""Model router (Spec §33): right model for the job, never one hard-coded model.

Roles (config/models.yaml): fast, default, reasoning, vision, coding, local.
Providers are instantiated lazily and cached per model entry.
"""
from __future__ import annotations

from app.brain.provider import LLMProvider
from app.brain.providers.anthropic import AnthropicProvider
from app.brain.providers.gemini import GeminiProvider
from app.brain.providers.ollama import OllamaProvider
from app.brain.providers.openai_compat import OpenAICompatibleProvider
from app.config.settings import AISettings
from app.core.logging import get_logger

log = get_logger("router")

_PROVIDER_CLASSES = {
    "openai_compatible": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


class ModelRouter:
    def __init__(self, ai: AISettings) -> None:
        self._ai = ai
        self._cache: dict[str, LLMProvider] = {}

    def provider_for_role(self, role: str | None = None) -> LLMProvider | None:
        entry = self._ai.entry_for_role(role or self._ai.default_role)
        if entry is None:
            return None
        if entry.id not in self._cache:
            cls = _PROVIDER_CLASSES.get(entry.provider)
            if cls is None:
                log.error("unknown provider type: %s", entry.provider)
                return None
            self._cache[entry.id] = cls(entry)
        return self._cache[entry.id]

    @property
    def has_provider(self) -> bool:
        return self.provider_for_role() is not None

    def describe(self) -> dict:
        return {
            "models": [f"{m.provider}:{m.id} roles={m.roles}" for m in self._ai.models],
            "roles": dict(self._ai.roles),
            "active_default": (self.provider_for_role().name if self.has_provider else None),
        }
