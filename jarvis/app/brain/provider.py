"""LLM provider abstraction (Spec §4, §33).

One interface, many backends: openai_compatible (OpenAI/Groq/OpenRouter/LM
Studio/...), anthropic, gemini, ollama. Providers are constructed from config
(ModelEntry) — never hard-coded. Keys are read from the environment at call
time and never logged.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config.settings import ModelEntry
from app.core.exceptions import ProviderError


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    finish_reason: str = "stop"

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class StreamEvent:
    """A streaming chunk from an LLM provider: either live text delta or final response."""
    text: str = ""
    response: ChatResponse | None = None


@dataclass
class ChatMessage:
    """Provider-neutral message. `tool_call_id` set when role == 'tool'."""
    role: str                                  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class LLMProvider(ABC):
    """A chat-capable model backend with optional tool calling."""

    def __init__(self, entry: ModelEntry) -> None:
        self.entry = entry
        self.model = entry.id

    @property
    def name(self) -> str:
        return f"{self.entry.provider}:{self.entry.id}"

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                   temperature: float = 0.3, max_tokens: int = 1024) -> ChatResponse:
        """Send a chat turn. Must raise ProviderError on transport/auth failure."""

    async def chat_stream(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                          temperature: float = 0.3, max_tokens: int = 1024):
        """Stream a chat turn. Default implementation falls back to non-streaming chat()."""
        resp = await self.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)
        if resp.content:
            yield StreamEvent(text=resp.content)
        yield StreamEvent(response=resp)

    async def close(self) -> None:
        """Close persistent HTTP clients/connections."""


    # ---- shared helpers

    def _require_key(self) -> str:
        import os
        if not self.entry.api_key_env:
            raise ProviderError(f"{self.name} needs an api_key_env in models.yaml.")
        key = os.environ.get(self.entry.api_key_env, "")
        if not key:
            raise ProviderError(
                f"The API key for {self.name} isn't set. Put it in .env as "
                f"{self.entry.api_key_env}=... (see .env.example).",
                detail=f"missing env: {self.entry.api_key_env}")
        return key

    @staticmethod
    def _parse_json_arguments(raw: str | dict) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw or not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"_raw": raw}
