"""Google Gemini provider (function calling & SSE streaming via streamGenerateContent)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.brain.provider import ChatMessage, ChatResponse, LLMProvider, StreamEvent, ToolCall
from app.core.exceptions import ProviderError

_BASE = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class GeminiProvider(LLMProvider):
    def __init__(self, entry) -> None:
        super().__init__(entry)
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_payload(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        system_text = "\n".join(m.content for m in messages if m.role == "system")
        contents: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue
            if msg.role == "tool":
                contents.append({"role": "user", "parts": [
                    {"functionResponse": {"name": msg.name or "tool",
                                          "response": {"result": msg.content}}}]})
            elif msg.role == "assistant" and msg.tool_calls:
                parts = ([{"text": msg.content}] if msg.content else []) + [
                    {"functionCall": {"name": c.name, "args": c.arguments}}
                    for c in msg.tool_calls]
                contents.append({"role": "model", "parts": parts})
            else:
                contents.append({"role": "user" if msg.role == "user" else "model",
                                 "parts": [{"text": msg.content or " "}]})

        gen_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if "3.7" in self.model or "thinking" in self.model:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": gen_config,
        }

        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if tools:
            payload["tools"] = [{"functionDeclarations": [
                {"name": t["name"], "description": t["description"],
                 "parameters": _strip_schema(t["parameters"])} for t in tools]}]
        return payload

    async def chat(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                   temperature: float = 0.3, max_tokens: int = 1024) -> ChatResponse:
        key = self._require_key()
        payload = self._build_payload(messages, tools, temperature, max_tokens)
        url = f"{_BASE}/models/{self.model}:generateContent"
        client = self._get_client()

        try:
            resp = await client.post(url, json=payload,
                                     headers={"x-goog-api-key": key,
                                              "Content-Type": "application/json"})
        except httpx.HTTPError as exc:
            raise ProviderError("I couldn't reach Google Gemini. Check your connection.",
                                detail=str(exc)) from exc

        if resp.status_code in (401, 403):
            raise ProviderError("Gemini rejected the API key — check .env.",
                                detail=f"status {resp.status_code}", status_code=resp.status_code)
        if resp.status_code >= 400:
            raise ProviderError(f"Gemini returned an error ({resp.status_code}).",
                                detail=resp.text[:500], status_code=resp.status_code)

        data = resp.json()
        content = ""
        tool_calls: list[ToolCall] = []
        for part in _parts(data):
            if "text" in part:
                content += part["text"]
            elif "functionCall" in part:
                call = part["functionCall"]
                tool_calls.append(ToolCall(id=f"call_{len(tool_calls)}",
                                           name=call.get("name", ""),
                                           arguments=call.get("args") or {}))
        return ChatResponse(content=content, tool_calls=tool_calls, model=self.model)

    async def chat_stream(self, messages: list[ChatMessage], tools: list[dict[str, Any]] | None = None,
                          temperature: float = 0.3, max_tokens: int = 1024) -> AsyncIterator[StreamEvent]:
        key = self._require_key()
        payload = self._build_payload(messages, tools, temperature, max_tokens)
        url = f"{_BASE}/models/{self.model}:streamGenerateContent?alt=sse"
        client = self._get_client()

        try:
            async with client.stream("POST", url, json=payload,
                                     headers={"x-goog-api-key": key,
                                              "Content-Type": "application/json"}) as resp:
                if resp.status_code in (401, 403):
                    raise ProviderError("Gemini rejected the API key — check .env.",
                                        detail=f"status {resp.status_code}", status_code=resp.status_code)
                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    raise ProviderError(f"Gemini returned an error ({resp.status_code}).",
                                        detail=err_body.decode(errors="replace")[:500], status_code=resp.status_code)

                content = ""
                tool_calls: list[ToolCall] = []

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    json_str = line[6:].strip()
                    if not json_str:
                        continue
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue

                    for part in _parts(data):
                        if "text" in part:
                            delta = part["text"]
                            content += delta
                            yield StreamEvent(text=delta)
                        elif "functionCall" in part:
                            call = part["functionCall"]
                            tool_calls.append(ToolCall(id=f"call_{len(tool_calls)}",
                                                       name=call.get("name", ""),
                                                       arguments=call.get("args") or {}))

                yield StreamEvent(response=ChatResponse(content=content, tool_calls=tool_calls, model=self.model))
        except httpx.HTTPError as exc:
            raise ProviderError("I couldn't reach Google Gemini. Check your connection.",
                                detail=str(exc)) from exc


def _parts(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = data.get("candidates") or [{}]
    return ((candidates[0].get("content") or {}).get("parts")) or []


def _strip_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Gemini rejects some JSON-Schema keys; keep the subset it accepts while preserving property definitions."""
    allowed_keys = {"type", "description", "enum", "items", "properties", "required", "format", "nullable"}

    def clean_obj(obj: Any) -> Any:
        if not isinstance(obj, dict):
            if isinstance(obj, list):
                return [clean_obj(x) for x in obj]
            return obj

        if "anyOf" in obj:
            non_null = [x for x in obj["anyOf"] if isinstance(x, dict) and x.get("type") != "null"]
            if non_null:
                chosen = clean_obj(non_null[0])
                if isinstance(chosen, dict):
                    for k in ("description", "title"):
                        if k in obj and k not in chosen:
                            chosen[k] = obj[k]
                    return clean_obj(chosen)

        res: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "properties" and isinstance(v, dict):
                res["properties"] = {prop_name: clean_obj(prop_schema) for prop_name, prop_schema in v.items()}
            elif k in allowed_keys:
                res[k] = clean_obj(v)

        if "required" in res and "properties" in res:
            res["required"] = [r for r in res["required"] if r in res["properties"]]
            if not res["required"]:
                res.pop("required", None)

        return res

    cleaned = clean_obj(schema)
    if isinstance(cleaned, dict) and "type" not in cleaned:
        cleaned["type"] = "object"
    return cleaned
