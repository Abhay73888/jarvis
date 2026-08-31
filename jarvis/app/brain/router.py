"""Model router (Spec §33): right model for the job, never one hard-coded model.

Roles (config/models.yaml): fast, default, reasoning, vision, coding, local.
Providers are instantiated lazily and cached per model entry.

Hybrid Router Capabilities:
- Seamless Failover: Online -> Gemini/Cloud; Offline/Timeout -> Local Ollama model.
- Privacy Mode: Local-only ALWAYS (zero outbound network requests).
- EventBus Telemetry: Publishes status ("Online" vs "Local brain active").
"""
from __future__ import annotations

from typing import Optional

from app.brain.connectivity import ConnectivityMonitor
from app.brain.provider import LLMProvider, ModelEntry
from app.brain.providers.anthropic import AnthropicProvider
from app.brain.providers.gemini import GeminiProvider
from app.brain.providers.ollama import OllamaProvider
from app.brain.providers.openai_compat import OpenAICompatibleProvider
from app.config.settings import AISettings
from app.core.events import EventBus, Topics
from app.core.logging import get_logger

log = get_logger("router")

_PROVIDER_CLASSES = {
    "openai_compatible": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


class ModelRouter:
    def __init__(
        self,
        ai: AISettings,
        connectivity: Optional[ConnectivityMonitor] = None,
        bus: Optional[EventBus] = None,
        privacy_mode: bool = False,
    ) -> None:
        self._ai = ai
        self._connectivity = connectivity or ConnectivityMonitor(bus=bus)
        self._bus = bus
        self._privacy_mode = privacy_mode
        self._cache: dict[str, LLMProvider] = {}

    @property
    def privacy_mode(self) -> bool:
        return self._privacy_mode

    def set_privacy_mode(self, enabled: bool) -> None:
        """Toggle privacy mode: when True, routes all queries locally with 0 network."""
        self._privacy_mode = enabled
        self._connectivity.set_force_offline(enabled)
        log.info("privacy mode set to: %s", enabled)

    def is_online(self) -> bool:
        """Returns True if online and privacy mode is not active."""
        if self._privacy_mode:
            return False
        return self._connectivity.is_online_cached

    def provider_for_role(self, role: str | None = None) -> LLMProvider | None:
        """Selects provider: if offline or privacy mode, routes to local Ollama model."""
        target_role = role or self._ai.default_role

        # If in privacy mode or offline, route to local model automatically
        if self._privacy_mode or not self.is_online():
            local_entry = self._get_local_entry()
            if local_entry is not None:
                return self._get_or_create_provider(local_entry)

        entry = self._ai.entry_for_role(target_role)
        if entry is None:
            # Fallback to local entry if requested entry doesn't exist
            entry = self._get_local_entry()
            if entry is None:
                return None

        return self._get_or_create_provider(entry)

    def _get_local_entry(self) -> ModelEntry | None:
        """Finds or constructs a local Ollama model entry."""
        if not self._ai.models:
            return None

        # 1. Check if an explicit 'local' role entry exists
        local_entry = self._ai.entry_for_role("local")
        if local_entry is not None:
            return local_entry

        # 2. Check for any configured Ollama model in models list
        for m in self._ai.models:
            if m.provider == "ollama" or "local" in m.roles:
                return m

        # 3. Default fallback local entry if models configured
        from app.offline.manifest import OfflineManifestManager
        rec_model, _ = OfflineManifestManager.get_recommended_model()
        return ModelEntry(
            id=rec_model,
            provider="ollama",
            roles=["local", "fast", "default"],
        )


    def _get_or_create_provider(self, entry: ModelEntry) -> LLMProvider | None:
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

    def is_using_local_brain(self, role: str | None = None) -> bool:
        """Returns True if the active provider for the given role is local Ollama."""
        provider = self.provider_for_role(role)
        if provider is None:
            return True
        return isinstance(provider, OllamaProvider)

    def describe(self) -> dict:
        active = self.provider_for_role()
        return {
            "models": [f"{m.provider}:{m.id} roles={m.roles}" for m in self._ai.models],
            "roles": dict(self._ai.roles),
            "privacy_mode": self._privacy_mode,
            "is_online": self.is_online(),
            "active_default": active.name if active else None,
            "active_is_local": self.is_using_local_brain(),
        }

    async def close(self) -> None:
        """Close all cached provider HTTP clients."""
        for provider in self._cache.values():
            try:
                await provider.close()
            except Exception:
                pass
        self._cache.clear()
