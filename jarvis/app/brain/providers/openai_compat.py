"""OpenAI-compatible provider: OpenAI, Groq, Together, OpenRouter, LM Studio,
vLLM, Ollama's /v1 endpoint, and anything speaking /chat/completions."""
from __future__ import annotations

from typing import Any

import httpx

from app.brain.provider import ChatMessage, ChatResponse, LLMProvider, ToolCall
from app.core.exceptions import ProviderError

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, entry) -> None:
        super().__init__(entry)
        self.base_url = (entry.base_url or DEFAULT_BASE_URL).rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.entry.api_key_env:
            headers["Authorization"] = f"Bearer {self._require_key()}"
        return headers

    @staticmethod
    def _serialize(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool":
                out.append({"role": "tool", "tool_call_id": msg.tool_call_id,
                            "content": msg.content})
            elif msg.role == "assistant" and msg.tool_calls:
                out.append({
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": [{
                        "id": call.id, "type": "function",
                        "function": {"name": call.name,
                                     "arguments": __import__("json").dumps(call.arguments)},
                    } for call in msg.tool_calls],
                })
            else:
                out.append({"role": msg.role, "content": msg.content})
        return out

    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                   temperature: float = 0.3, max_tokens: int = 1024) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._serialize(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = [{"type": "function",
                                 "function": {"name": t["name"],
                                              "description": t["description"],
                                              "parameters": t["parameters"]}}
                                for t in tools]
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{self.base_url}/chat/completions",
                                         json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProviderError(f"I couldn't reach {self.entry.provider} "
                                f"({self.base_url}). Check your connection.",
                                detail=str(exc)) from exc
        if resp.status_code in (401, 403):
            raise ProviderError("The API key was rejected — check it in .env.",
                                detail=f"status {resp.status_code}", status_code=resp.status_code)
        if resp.status_code == 429:
            raise ProviderError("The provider is rate-limiting us. Give it a moment.",
                                detail="429 rate limited", status_code=429)
        if resp.status_code >= 400:
            raise ProviderError(f"The provider returned an error ({resp.status_code}).",
                                detail=resp.text[:500], status_code=resp.status_code)
        return self._parse_response(resp.json())

    def _parse_response(self, data: dict[str, Any]) -> ChatResponse:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            tool_calls.append(ToolCall(
                id=raw.get("id") or f"call_{len(tool_calls)}",
                name=function.get("name", ""),
                arguments=self._parse_json_arguments(function.get("arguments", "{}"))))
        return ChatResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            model=data.get("model", self.model),
            finish_reason=choice.get("finish_reason", "stop"))
