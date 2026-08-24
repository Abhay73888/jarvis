"""Anthropic Messages API provider (tool use)."""
from __future__ import annotations

from typing import Any

import httpx

from app.brain.provider import ChatMessage, ChatResponse, LLMProvider, ToolCall
from app.core.exceptions import ProviderError

_BASE = "https://api.anthropic.com/v1"
_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class AnthropicProvider(LLMProvider):
    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._require_key(), "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"}

    @staticmethod
    def _serialize(messages: list[ChatMessage]) -> tuple[str, list[dict[str, Any]]]:
        system = "\n".join(m.content for m in messages if m.role == "system")
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "tool":
                out.append({"role": "user", "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content}]})
            elif msg.role == "assistant" and msg.tool_calls:
                blocks: list[dict[str, Any]] = ([{"type": "text", "text": msg.content}]
                                                if msg.content else [])
                blocks += [{"type": "tool_use", "id": c.id, "name": c.name,
                            "input": c.arguments} for c in msg.tool_calls]
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": msg.role, "content": msg.content})
        return system, out

    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                   temperature: float = 0.3, max_tokens: int = 1024) -> ChatResponse:
        system, serialized = self._serialize(messages)
        payload: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens, "temperature": temperature,
            "messages": serialized,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [{"name": t["name"], "description": t["description"],
                                 "input_schema": t["parameters"]} for t in tools]
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(f"{_BASE}/messages",
                                         json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProviderError("I couldn't reach Anthropic. Check your connection.",
                                detail=str(exc)) from exc
        if resp.status_code in (401, 403):
            raise ProviderError("Anthropic rejected the API key — check .env.",
                                detail=f"status {resp.status_code}", status_code=resp.status_code)
        if resp.status_code >= 400:
            raise ProviderError(f"Anthropic returned an error ({resp.status_code}).",
                                detail=resp.text[:500], status_code=resp.status_code)

        data = resp.json()
        content = ""
        tool_calls: list[ToolCall] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCall(id=block.get("id", f"call_{len(tool_calls)}"),
                                           name=block.get("name", ""),
                                           arguments=block.get("input") or {}))
        return ChatResponse(content=content, tool_calls=tool_calls, model=data.get("model", self.model),
                            finish_reason=data.get("stop_reason", "stop"))
