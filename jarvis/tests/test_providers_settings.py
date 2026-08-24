"""Provider tests via httpx MockTransport: real request building + response
parsing, no network. Also settings/env handling."""
from __future__ import annotations

import json

import httpx
import pytest

from app.brain.providers.anthropic import AnthropicProvider
from app.brain.providers.openai_compat import OpenAICompatibleProvider
from app.brain.provider import ChatMessage
from app.config.settings import ModelEntry, Settings
from app.core.exceptions import ConfigError, ProviderError


def _mock_client_transport(handler):
    real_async_client = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(**kwargs)

    return factory


async def test_openai_payload_and_tool_call_parsing(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization", "")
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "abc", "type": "function",
                        "function": {"name": "create_folder",
                                     "arguments": "{\"path\": \"AI Projects\"}"}},
                    ]}}],
            "model": "gpt-4o-mini"})

    monkeypatch.setattr("app.brain.providers.openai_compat.httpx.AsyncClient",
                        _mock_client_transport(handler))
    entry = ModelEntry(id="gpt-4o-mini", provider="openai_compatible",
                       base_url="http://mock/v1", api_key_env="TEST_KEY")
    monkeypatch.setenv("TEST_KEY", "sk-testtesttest")
    provider = OpenAICompatibleProvider(entry)

    response = await provider.chat(
        [ChatMessage(role="system", content="sys"),
         ChatMessage(role="user", content="make a folder")],
        tools=[{"name": "create_folder", "description": "d",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}])

    assert captured["url"] == "http://mock/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-testtesttest"
    body = captured["json"]
    assert body["model"] == "gpt-4o-mini"
    assert body["tools"][0]["type"] == "function"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert response.wants_tools
    assert response.tool_calls[0].name == "create_folder"
    assert response.tool_calls[0].arguments == {"path": "AI Projects"}


async def test_tool_result_serialization(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("app.brain.providers.openai_compat.httpx.AsyncClient",
                        _mock_client_transport(handler))
    entry = ModelEntry(id="m", provider="openai_compatible", base_url="http://mock/v1",
                       api_key_env="TEST_KEY")
    monkeypatch.setenv("TEST_KEY", "sk-testtesttest")
    provider = OpenAICompatibleProvider(entry)
    from app.brain.provider import ToolCall
    messages = [
        ChatMessage(role="assistant", content="", tool_calls=[
            ToolCall(id="t1", name="system_info", arguments={})]),
        ChatMessage(role="tool", content="{'success': True}", tool_call_id="t1"),
    ]
    await provider.chat(messages)
    sent = captured["json"]["messages"]
    assert sent[0]["tool_calls"][0]["function"]["name"] == "system_info"
    assert sent[1] == {"role": "tool", "tool_call_id": "t1", "content": "{'success': True}"}


async def test_missing_key_friendly_error(monkeypatch):
    monkeypatch.delenv("TEST_KEY_MISSING", raising=False)
    entry = ModelEntry(id="m", provider="openai_compatible",
                       base_url="http://mock/v1", api_key_env="TEST_KEY_MISSING")
    provider = OpenAICompatibleProvider(entry)
    with pytest.raises(ProviderError) as excinfo:
        await provider.chat([ChatMessage(role="user", content="hi")])
    assert "TEST_KEY_MISSING" in excinfo.value.friendly


async def test_auth_rejection_mapped(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    monkeypatch.setattr("app.brain.providers.openai_compat.httpx.AsyncClient",
                        _mock_client_transport(handler))
    entry = ModelEntry(id="m", provider="openai_compatible", base_url="http://mock/v1",
                       api_key_env="TEST_KEY")
    monkeypatch.setenv("TEST_KEY", "sk-wrong")
    provider = OpenAICompatibleProvider(entry)
    with pytest.raises(ProviderError) as excinfo:
        await provider.chat([ChatMessage(role="user", content="hi")])
    assert "rejected" in excinfo.value.friendly.lower()


async def test_anthropic_payload(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "hello"},
                        {"type": "tool_use", "id": "t9", "name": "system_info", "input": {}}],
            "stop_reason": "tool_use"})

    monkeypatch.setattr("app.brain.providers.anthropic.httpx.AsyncClient",
                        _mock_client_transport(handler))
    entry = ModelEntry(id="claude-sonnet", provider="anthropic", api_key_env="TEST_ANTHROPIC")
    monkeypatch.setenv("TEST_ANTHROPIC", "ant-key")
    provider = AnthropicProvider(entry)
    response = await provider.chat(
        [ChatMessage(role="system", content="be brief"),
         ChatMessage(role="user", content="check system")],
        tools=[{"name": "system_info", "description": "d", "parameters": {"type": "object"}}])

    body = captured["json"]
    assert body["system"] == "be brief"
    assert body["tools"][0]["input_schema"]["type"] == "object"
    assert response.content == "hello"
    assert response.tool_calls[0].name == "system_info"


# ------------------------------------------------------------------- settings

def test_default_settings_load(jarvis_home):
    from app.config.settings import load_settings
    settings = load_settings(jarvis_home)
    assert settings.permissions.categories["sensitive"] == "deny"
    assert settings.personality.name == "JARVIS"


def test_yaml_merge_and_env_interpolation(jarvis_home, monkeypatch):
    from app.config.settings import load_settings
    monkeypatch.setenv("JARVIS_TESTER_NAME", "VEDA")
    (jarvis_home / "config").mkdir(parents=True, exist_ok=True)
    (jarvis_home / "config" / "settings.yaml").write_text(
        "personality:\n  name: ${JARVIS_TESTER_NAME:-FALLBACK}\nlog_level: DEBUG\n")
    settings = load_settings(jarvis_home)
    assert settings.personality.name == "VEDA"
    assert settings.log_level == "DEBUG"


def test_invalid_settings_raise_config_error(jarvis_home):
    from app.config.settings import load_settings
    (jarvis_home / "config").mkdir(parents=True, exist_ok=True)
    (jarvis_home / "config" / "settings.yaml").write_text(
        "personality:\n  language_style: klingon\n")
    with pytest.raises(ConfigError):
        load_settings(jarvis_home)


def test_secrets_never_serialize_from_yaml(jarvis_home):
    """API keys belong to env vars; models.yaml only stores the env NAME."""
    from app.config.settings import load_settings
    (jarvis_home / "config").mkdir(parents=True, exist_ok=True)
    (jarvis_home / "config" / "models.yaml").write_text(
        "ai:\n  models:\n    - id: gpt-4o-mini\n      provider: openai_compatible\n"
        "      api_key_env: JARVIS_OPENAI_API_KEY\n      roles: [default]\n")
    settings = load_settings(jarvis_home)
    dumped = settings.model_dump()
    assert "sk-" not in str(dumped)
    assert settings.ai.models[0].api_key_env == "JARVIS_OPENAI_API_KEY"


def test_fresh_install_ships_gemini_defaults(jarvis_home):
    """No models.yaml -> embedded Gemini config applies (user's provider choice)."""
    from app.config.settings import load_settings
    settings = load_settings(jarvis_home)
    assert settings.ai.roles.get("default") in ("gemini-3.7-flash", "gemini-2.5-flash")
    entry = settings.ai.entry_for_role("default")
    assert entry.provider == "gemini"
    assert entry.provider == "gemini"
    assert entry.api_key_env == "JARVIS_GEMINI_API_KEY"


def test_user_models_yaml_overrides_defaults(jarvis_home):
    from app.config.settings import load_settings
    (jarvis_home / "config").mkdir(parents=True, exist_ok=True)
    (jarvis_home / "config" / "models.yaml").write_text(
        "ai:\n  models:\n    - id: my-model\n      provider: ollama\n      roles: [default]\n"
        "  roles:\n    default: my-model\n")
    settings = load_settings(jarvis_home)
    assert settings.ai.entry_for_role("default").id == "my-model"


def test_dotenv_loader(jarvis_home, monkeypatch):
    from app.config.settings import load_dotenv
    monkeypatch.delenv("JARVIS_GEMINI_API_KEY", raising=False)
    (jarvis_home / ".env").write_text(
        '# comment\nJARVIS_GEMINI_API_KEY="AIzaFakeFakeFakeFake"\nBROKEN LINE\n')
    loaded = load_dotenv(jarvis_home)
    assert "JARVIS_GEMINI_API_KEY" in loaded
    import os
    assert os.environ["JARVIS_GEMINI_API_KEY"] == "AIzaFakeFakeFakeFake"
