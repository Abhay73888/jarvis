"""Engine tests: fast-path execution, LLM tool loop (mocked provider),
persistence, offline honesty, and memory round-trips."""
from __future__ import annotations

from pathlib import Path

from app.brain.provider import ChatResponse
from app.config.settings import ModelEntry
from tests.conftest import MockProvider, tool_call_response


async def test_fast_path_system_info(jarvis_home: Path, stack):
    await stack.build()
    result = await stack.engine.turn("system info batao")
    assert result.used_fast_path
    assert result.actions and result.actions[0]["tool"] == "system_info"
    assert "system" in result.text.lower()


async def test_offline_mode_is_honest_not_fake(jarvis_home: Path, stack):
    await stack.build()          # no models configured
    result = await stack.engine.turn("write me a poem about mars")
    assert result.used_fast_path is False
    assert "offline" in result.text.lower()      # says it can't, doesn't pretend


async def test_conversation_persisted(jarvis_home: Path, stack):
    await stack.build()
    await stack.engine.turn("system info batao")
    history = await stack.conversations.history()
    roles = [m.role for m in history]
    assert "user" in roles and "assistant" in roles


async def test_llm_tool_loop_executes_real_tool(jarvis_home: Path, stack):
    entry = ModelEntry(id="mock-model", provider="openai_compatible")
    await stack.build(models=[entry])
    mock = MockProvider(entry, script=[
        tool_call_response("c1", "system_info", {}),
        tool_call_response("c2", "create_folder", {"path": "FromLLM"}),
        ChatResponse(content="Created the folder and checked the system."),
    ])
    stack.router._cache["mock-model"] = mock

    result = await stack.engine.turn("check the system and make a folder called FromLLM")
    assert result.text == "Created the folder and checked the system."
    assert {a["tool"] for a in result.actions} == {"system_info", "create_folder"}
    assert (jarvis_home / "FromLLM").is_dir(), "LLM tool call must have real effect"
    # the provider saw the tool result come back as a 'tool' message
    assert "tool" in mock.calls[-1]["roles"]


async def test_llm_loop_respects_denial(jarvis_home: Path, stack):
    entry = ModelEntry(id="mock-model", provider="openai_compatible")
    await stack.build(models=[entry])
    stack.confirm_decision = "deny"
    victim = jarvis_home / "important.txt"
    victim.write_text("do not lose me")
    mock = MockProvider(entry, script=[
        tool_call_response("c1", "delete_file", {"path": str(victim)}),
        ChatResponse(content="Okay, I skipped the deletion."),
    ])
    stack.router._cache["mock-model"] = mock
    result = await stack.engine.turn("delete important.txt")
    assert victim.exists(), "denied LLM tool call must have no effect"
    assert result.actions[0]["ok"] is False


async def test_working_memory_tracks_last_app(jarvis_home: Path, stack):
    stack.engine = None  # built below
    await stack.build()
    stack.engine.working.last_app = "chrome"
    summary = stack.engine.working.summary()
    assert "chrome" in summary.lower()


async def test_memory_tools_roundtrip(jarvis_home: Path, stack):
    await stack.build()
    remembered = await stack.tools.execute("remember",
                                           {"kind": "preference", "key": "preferred-editor",
                                            "content": "VS Code, maximized"})
    assert remembered.success

    refused = await stack.tools.execute("remember",
                                        {"kind": "fact", "key": "leak",
                                         "content": "my api key is sk-AbCdEfGh12345678"})
    assert not refused.success and "secret" in refused.message.lower()

    recalled = await stack.tools.execute("recall_memories", {"query": "editor"})
    assert recalled.success
    assert any("VS Code" in r["content"] for r in recalled.data["results"])


async def test_reminder_natural_language_times(jarvis_home: Path, stack):
    from datetime import datetime

    from app.tools.builtin.memory_tools import parse_due_at

    now = datetime(2026, 8, 24, 11, 0)
    assert parse_due_at("tomorrow 10:00", now).hour == 10
    assert parse_due_at("tonight", now).hour == 20
    assert parse_due_at("18:30", now).strftime("%H:%M") == "18:30"
    assert parse_due_at("2026-08-25T09:00:00", now) is not None
    assert parse_due_at("gibberish-time", now) is None


async def test_reminder_tool_persists(jarvis_home: Path, stack):
    await stack.build()
    result = await stack.tools.execute("set_reminder",
                                       {"title": "Call manager", "due_at": "tomorrow 10:00"})
    assert result.success and result.verified

    listed = await stack.tools.execute("list_reminders", {})
    assert any(t["title"] == "Call manager" for t in listed.data["tasks"])
