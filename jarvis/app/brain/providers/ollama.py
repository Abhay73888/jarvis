"""Ollama provider — local models via the OpenAI-compatible /v1 endpoint.
No API key; base_url defaults to http://localhost:11434/v1 (env OLLAMA_HOST)."""
from __future__ import annotations

import os

from app.brain.providers.openai_compat import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, entry) -> None:
        if not entry.base_url:
            entry = entry.model_copy(update={
                "base_url": os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/v1"})
        super().__init__(entry)
