"""Unit tests for Stage O3 — Offline Brain (Hybrid Router, Failover & Privacy Mode)."""
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.brain.connectivity import ConnectivityMonitor
from app.brain.engine import AgentEngine
from app.brain.providers.ollama import OllamaProvider
from app.brain.router import ModelRouter
from app.config.settings import AISettings, ModelEntry, Settings
from app.core.events import EventBus


@pytest.fixture
def block_network():
    """Socket blocker fixture that blocks all outbound external internet connections."""
    orig_connect = socket.socket.connect

    def blocked_connect(sock, address, *args, **kwargs):
        host = address[0] if isinstance(address, (tuple, list)) and address else address
        if str(host) in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(sock, address, *args, **kwargs)
        raise RuntimeError(f"NETWORK CALL BLOCKED: Attempted external socket connection to {address}!")

    with patch.object(socket.socket, "connect", new=blocked_connect):
        yield


def test_connectivity_monitor_and_caching():
    monitor = ConnectivityMonitor()
    assert monitor.is_online_cached is True

    # Test force offline toggle
    monitor.set_force_offline(True)
    assert monitor.is_online_cached is False
    monitor.set_force_offline(False)


def test_hybrid_router_automatic_failover():
    ai = AISettings(
        models=[
            ModelEntry(id="gemini-3.7-flash", provider="gemini", roles=["default", "fast"], api_key_env="DUMMY"),
            ModelEntry(id="qwen2.5:7b", provider="ollama", roles=["local"]),
        ],
        roles={"default": "gemini-3.7-flash", "local": "qwen2.5:7b"},
    )
    monitor = ConnectivityMonitor()
    router = ModelRouter(ai=ai, connectivity=monitor)

    # 1. When online, default role resolves to Gemini
    assert router.is_online() is True
    prov = router.provider_for_role()
    assert prov.name == "gemini:gemini-3.7-flash"
    assert router.is_using_local_brain() is False

    # 2. When offline, seamlessly fails over to Ollama local model
    monitor.set_force_offline(True)
    assert router.is_online() is False
    local_prov = router.provider_for_role()
    assert isinstance(local_prov, OllamaProvider)
    assert local_prov.name == "ollama:qwen2.5:7b"
    assert router.is_using_local_brain() is True


def test_privacy_mode_forces_local_brain(block_network):
    ai = AISettings(
        models=[
            ModelEntry(id="gemini-3.7-flash", provider="gemini", roles=["default"], api_key_env="DUMMY"),
            ModelEntry(id="qwen2.5:3b", provider="ollama", roles=["local"]),
        ],
        roles={"default": "gemini-3.7-flash", "local": "qwen2.5:3b"},
    )
    router = ModelRouter(ai=ai)
    assert router.privacy_mode is False

    # Enable privacy mode
    router.set_privacy_mode(True)
    assert router.privacy_mode is True
    assert router.is_online() is False

    prov = router.provider_for_role("default")
    assert isinstance(prov, OllamaProvider)
    assert router.is_using_local_brain() is True


def test_compact_system_prompt_for_local_models():
    settings = Settings()
    ai = AISettings(
        models=[ModelEntry(id="qwen2.5:3b", provider="ollama", roles=["local", "default"])],
        roles={"default": "qwen2.5:3b"},
    )
    bus = EventBus()
    router = ModelRouter(ai=ai, bus=bus)
    router.set_privacy_mode(True)

    mock_tools = MagicMock()
    mock_convs = MagicMock()
    mock_convs.preferences = AsyncMock(return_value={})

    engine = AgentEngine(
        settings=settings,
        router=router,
        tools=mock_tools,
        conversations=mock_convs,
        bus=bus,
    )

    prompt = engine._system_prompt()
    assert "offline AI operating layer" in prompt
    assert "Be direct, concise, and helpful." in prompt
