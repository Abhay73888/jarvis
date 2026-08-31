"""Unit tests for Stage O5 — Maximum Offline Superpowers & Tool Audit."""
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.settings import Settings
from app.core.events import EventBus
from app.permissions.manager import PermissionManager
from app.tools import build_tool_manager
from app.tools.base import ToolContext
from app.tools.builtin.dictation import DictationTool, is_dictation_active
from app.tools.builtin.knowledge import KnowledgeTool
from app.tools.builtin.productivity import ProductivityTool
from app.tools.builtin.system_control import SystemControlTool


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


def test_tool_offline_attribute_audit():
    settings = Settings()
    bus = EventBus()
    perms = MagicMock(spec=PermissionManager)
    perms.check = AsyncMock(return_value=True)

    manager = build_tool_manager(settings, perms, bus, None)

    # Verify every registered tool has the 'offline' attribute in its schema
    schemas = manager.schemas()
    assert len(schemas) > 0
    for schema in schemas:
        assert "offline" in schema
        assert isinstance(schema["offline"], bool)



@pytest.mark.asyncio
async def test_productivity_tool_superpowers(tmp_path):
    tool = ProductivityTool()
    ctx = ToolContext(settings=MagicMock(), workdir=tmp_path, writable_roots=[tmp_path])

    # 1. Calculator
    r_calc = await tool.execute({"action": "calculate", "expression": "14 * 25 + (100 / 4)"}, ctx)
    assert r_calc.success is True
    assert r_calc.data["result"] == 375

    # 2. Unit Conversions
    r_km = await tool.execute({"action": "unit_convert", "value": 5, "from_unit": "km", "to_unit": "miles"}, ctx)
    assert r_km.success is True
    assert round(r_km.data["result"], 2) == 3.11

    r_c = await tool.execute({"action": "unit_convert", "value": 100, "from_unit": "c", "to_unit": "f"}, ctx)
    assert r_c.success is True
    assert r_c.data["result"] == 212.0

    # 3. Pomodoro
    r_pomo = await tool.execute({"action": "pomodoro", "minutes": 25}, ctx)
    assert r_pomo.success is True
    assert "Pomodoro session" in r_pomo.message

    # 4. Notes save, list, read
    with patch("app.tools.builtin.productivity.get_paths") as mock_paths:
        mock_paths.return_value.data = tmp_path
        r_save = await tool.execute({"action": "note_save", "note_title": "DailyPlan", "note_content": "1. Deploy 2. Verify"}, ctx)
        assert r_save.success is True

        r_list = await tool.execute({"action": "note_list"}, ctx)
        assert r_list.success is True
        assert "DailyPlan" in r_list.data["notes"]

        r_read = await tool.execute({"action": "note_read", "note_title": "DailyPlan"}, ctx)
        assert r_read.success is True
        assert "Deploy" in r_read.data["content"]


@pytest.mark.asyncio
async def test_dictation_mode_toggle():
    tool = DictationTool()
    ctx = ToolContext(settings=MagicMock(), workdir=MagicMock(), writable_roots=[])

    r_on = await tool.execute({"action": "on"}, ctx)
    assert r_on.success is True
    assert is_dictation_active() is True

    r_off = await tool.execute({"action": "off"}, ctx)
    assert r_off.success is True
    assert is_dictation_active() is False


@pytest.mark.asyncio
async def test_knowledge_offline_and_local_kb(tmp_path):
    tool = KnowledgeTool()
    ctx = ToolContext(settings=MagicMock(), workdir=tmp_path, writable_roots=[tmp_path])

    # 1. Definition
    r_def = await tool.execute({"action": "define", "query": "algorithm"}, ctx)
    assert r_def.success is True
    assert "step-by-step procedure" in r_def.data["definition"]

    # 2. Local KB search
    with patch("app.tools.builtin.knowledge.get_paths") as mock_paths:
        kb_dir = tmp_path / "knowledge"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "project_alpha.txt").write_text("Project Alpha architecture uses offline LLM.", encoding="utf-8")
        mock_paths.return_value.data = tmp_path

        r_search = await tool.execute({"action": "kb_search", "query": "Alpha"}, ctx)
        assert r_search.success is True
        assert len(r_search.data["matches"]) >= 1

    # 3. Summarize
    r_sum = await tool.execute({"action": "summarize", "query": "Antigravity is powerful. It runs locally. JARVIS is an operating layer."}, ctx)
    assert r_sum.success is True
    assert "Antigravity is powerful." in r_sum.data["summary"]


@pytest.mark.asyncio
async def test_system_control_offline():
    tool = SystemControlTool()
    ctx = ToolContext(settings=MagicMock(), workdir=MagicMock(), writable_roots=[])

    with patch.object(tool, "_run_ps", return_value=""):
        r_vol = await tool.execute({"action": "volume_set", "value": 60}, ctx)
        assert r_vol.success is True
        assert r_vol.data["volume"] == 60

        r_media = await tool.execute({"action": "media_play_pause"}, ctx)
        assert r_media.success is True


@pytest.mark.asyncio
async def test_offline_10_commands_transcript_zero_network(block_network, tmp_path):
    """Executes 10 varied offline commands under strict network isolation fixture."""
    ctx = ToolContext(settings=MagicMock(), workdir=tmp_path, writable_roots=[tmp_path])

    prod = ProductivityTool()
    know = KnowledgeTool()
    dictation = DictationTool()

    # 1. Math eval
    assert (await prod.execute({"action": "calculate", "expression": "25 * 4"}, ctx)).success is True
    # 2. KM to Miles
    assert (await prod.execute({"action": "unit_convert", "value": 10, "from_unit": "km", "to_unit": "miles"}, ctx)).success is True
    # 3. Celsius to Fahrenheit
    assert (await prod.execute({"action": "unit_convert", "value": 37, "from_unit": "c", "to_unit": "f"}, ctx)).success is True
    # 4. Define 'latency'
    assert (await know.execute({"action": "define", "query": "latency"}, ctx)).success is True
    # 5. Define 'jarvis'
    assert (await know.execute({"action": "define", "query": "jarvis"}, ctx)).success is True
    # 6. Dictation ON
    assert (await dictation.execute({"action": "on"}, ctx)).success is True
    # 7. Dictation OFF
    assert (await dictation.execute({"action": "off"}, ctx)).success is True
    # 8. Start pomodoro
    assert (await prod.execute({"action": "pomodoro", "minutes": 25}, ctx)).success is True
    # 9. Summarize
    assert (await know.execute({"action": "summarize", "query": "Offline first architecture. Zero network required."}, ctx)).success is True
    # 10. Math power
    assert (await prod.execute({"action": "calculate", "expression": "2 ** 8"}, ctx)).data["result"] == 256
