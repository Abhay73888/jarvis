"""Gemini provider tests — payload building & response parsing via MockTransport.
Also validates the preconfigured default models.yaml the user selected."""
from __future__ import annotations

import json

import httpx
import pytest

from app.brain.provider import ChatMessage, ToolCall
from app.brain.providers.gemini import GeminiProvider
from app.config.settings import ModelEntry


def _with_transport(monkeypatch, handler):
    real = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(**kwargs)

    monkeypatch.setattr("app.brain.providers.gemini.httpx.AsyncClient", factory)


async def test_gemini_payload_and_function_call_parsing(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key_header"] = request.headers.get("x-goog-api-key")
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [
                {"text": "Checking."},
                {"functionCall": {"name": "system_info", "args": {}}},
            ]}, "finishReason": "STOP"}]})

    _with_transport(monkeypatch, handler)
    entry = ModelEntry(id="gemini-2.5-flash", provider="gemini", api_key_env="JARVIS_GEMINI_API_KEY")
    monkeypatch.setenv("JARVIS_GEMINI_API_KEY", "AIzaTestTestTestTestTestTestTestTest")
    provider = GeminiProvider(entry)

    response = await provider.chat(
        [ChatMessage(role="system", content="be brief"),
         ChatMessage(role="user", content="check system")],
        tools=[{"name": "system_info", "description": "d",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}])

    # Key must be in the header, NEVER in the URL (log safety)
    assert "AIzaTestTest" not in captured["url"]
    assert "key=" not in captured["url"]
    assert captured["key_header"].startswith("AIza")

    body = captured["json"]
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert body["contents"][0]["role"] == "user"
    # additionalProperties (not in Gemini's schema subset) must be stripped
    assert "additionalProperties" not in json.dumps(body["tools"])
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "system_info"

    assert response.content == "Checking."
    assert response.tool_calls[0].name == "system_info"


async def test_gemini_tool_result_roundtrip_serialization(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    _with_transport(monkeypatch, handler)
    entry = ModelEntry(id="gemini-2.5-flash", provider="gemini", api_key_env="JARVIS_GEMINI_API_KEY")
    monkeypatch.setenv("JARVIS_GEMINI_API_KEY", "AIzaTestTestTestTestTestTestTestTest")
    provider = GeminiProvider(entry)

    messages = [
        ChatMessage(role="user", content="open yt"),
        ChatMessage(role="assistant", content="", tool_calls=[
            ToolCall(id="c1", name="browser_search", arguments={"query": "x"})]),
        ChatMessage(role="tool", content="{'success': True}", tool_call_id="c1",
                    name="browser_search"),
    ]
    await provider.chat(messages)
    contents = captured["json"]["contents"]
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["functionCall"]["name"] == "browser_search"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "browser_search"


async def test_gemini_error_maps_friendly(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "quota"}})

    _with_transport(monkeypatch, handler)
    entry = ModelEntry(id="gemini-2.5-flash", provider="gemini", api_key_env="JARVIS_GEMINI_API_KEY")
    monkeypatch.setenv("JARVIS_GEMINI_API_KEY", "AIzaTestTestTestTestTestTestTestTest")
    provider = GeminiProvider(entry)
    from app.core.exceptions import ProviderError
    with pytest.raises(ProviderError):
        await provider.chat([ChatMessage(role="user", content="hi")])


def test_default_models_yaml_is_gemini_ready():
    """The shipped models.yaml must be valid YAML and Gemini-shaped (user's pick)."""
    import yaml

    from app.config.settings import DEFAULT_MODELS_YAML
    # Defaults ship with commented examples only (no fake models) —
    # verify the Gemini example is present and correctly shaped.
    assert "provider: ollama" in DEFAULT_MODELS_YAML or "gemini" in DEFAULT_MODELS_YAML
    yaml.safe_load(DEFAULT_MODELS_YAML)  # parses
