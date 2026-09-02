"""OpenAI-compatible provider: OpenAI, Groq, Together, OpenRouter, LM Studio,
vLLM, Ollama's /v1 endpoint, and anything speaking /chat/completions with SSE streaming."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.brain.provider import ChatMessage, ChatResponse, LLMProvider, StreamEvent, ToolCall
from app.core.exceptions import ProviderError

DEFAULT_BASE_URL = "https://api.openai.com/v1"
_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, entry) -> None:
        super().__init__(entry)
        self.base_url = (entry.base_url or DEFAULT_BASE_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

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
                                     "arguments": json.dumps(call.arguments)},
                    } for call in msg.tool_calls],
                })
            else:
                out.append({"role": msg.role, "content": msg.content})
        return out

    def _build_payload(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._serialize(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream"] = True
        if tools:
            payload["tools"] = [{"type": "function",
                                 "function": {"name": t["name"],
                                              "description": t["description"],
                                              "parameters": t["parameters"]}}
                                for t in tools]
        return payload

    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                   temperature: float = 0.3, max_tokens: int = 1024) -> ChatResponse:
        payload = self._build_payload(messages, tools, temperature, max_tokens, stream=False)
        client = self._get_client()
        url = f"{self.base_url}/chat/completions"

        try:
            resp = await client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ProviderError(f"I couldn't reach {self.entry.provider} ({self.base_url}). Check your connection.",
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

    async def chat_stream(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                          temperature: float = 0.3, max_tokens: int = 1024) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(messages, tools, temperature, max_tokens, stream=True)
        client = self._get_client()
        url = f"{self.base_url}/chat/completions"

        try:
            async with client.stream("POST", url, json=payload, headers=self._headers()) as resp:
                if resp.status_code in (401, 403):
                    raise ProviderError("The API key was rejected — check it in .env.",
                                        detail=f"status {resp.status_code}", status_code=resp.status_code)
                if resp.status_code == 429:
                    raise ProviderError("The provider is rate-limiting us. Give it a moment.",
                                        detail="429 rate limited", status_code=429)
                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    raise ProviderError(f"The provider returned an error ({resp.status_code}).",
                                        detail=err_body.decode(errors="replace")[:500], status_code=resp.status_code)

                content = ""
                tool_calls_map: dict[int, dict[str, Any]] = {}
                model_name = self.model
                finish_reason = "stop"

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    if line == "data: [DONE]":
                        break
                    json_str = line[6:].strip()
                    if not json_str:
                        continue
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue

                    model_name = data.get("model", model_name)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta") or {}

                    delta_text = delta.get("content")
                    if delta_text:
                        content += delta_text
                        yield StreamEvent(text=delta_text)

                    if delta.get("tool_calls"):
                        for tc_chunk in delta["tool_calls"]:
                            idx = tc_chunk.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": tc_chunk.get("id") or f"call_{idx}",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc_chunk.get("id"):
                                tool_calls_map[idx]["id"] = tc_chunk["id"]
                            func = tc_chunk.get("function") or {}
                            if func.get("name"):
                                tool_calls_map[idx]["name"] += func["name"]
                            if func.get("arguments"):
                                tool_calls_map[idx]["arguments"] += func["arguments"]

                # Assemble tool calls
                tool_calls: list[ToolCall] = []
                for idx in sorted(tool_calls_map.keys()):
                    tc_data = tool_calls_map[idx]
                    tool_calls.append(ToolCall(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=self._parse_json_arguments(tc_data["arguments"]),
                    ))

                yield StreamEvent(response=ChatResponse(
                    content=content,
                    tool_calls=tool_calls,
                    model=model_name,
                    finish_reason=finish_reason,
                ))

        except httpx.HTTPError as exc:
            raise ProviderError(f"I couldn't reach {self.entry.provider} ({self.base_url}). Check your connection.",
                                detail=str(exc)) from exc

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
