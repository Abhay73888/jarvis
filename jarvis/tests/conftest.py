"""Shared fixtures: a fully wired JARVIS stack against a temp directory."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.brain.engine import AgentEngine
from app.brain.provider import ChatResponse, LLMProvider, ToolCall
from app.brain.router import ModelRouter
from app.config.settings import ModelEntry, Settings
from app.core.events import EventBus
from app.database.db import init_db, make_engine, make_session_factory
from app.memory.manager import ConversationManager
from app.permissions.manager import PermissionManager, PermissionStore
from app.tools import build_tool_manager
from app.tools.base import ToolContext


@pytest.fixture()
def jarvis_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect JARVIS_HOME to a temp dir and confine writes to it."""
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path))
    return tmp_path


class Stack:
    """Builds the full engine graph inside the running test loop."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.settings = Settings()
        self.settings.security.writable_roots = [str(home)]
        self.settings.memory.persist_conversations = True
        self.bus = EventBus()
        self.decisions: list[str] = []
        self.confirm_decision = "allow_once"

    async def build(self, models: list[ModelEntry] | None = None) -> "Stack":
        from app.utils.paths import get_paths
        paths = get_paths()
        engine = make_engine(paths.db_file)
        await init_db(engine)
        self.session_factory = make_session_factory(engine)
        self.permissions = PermissionManager(self.settings, PermissionStore(self.session_factory),
                                             self.bus)
        self.permissions.set_confirm_handler(self._handler)
        self.tools = build_tool_manager(self.settings, self.permissions, self.bus,
                                        self.session_factory)
        self.tools.bind_context(ToolContext(
            settings=self.settings, workdir=self.home,
            writable_roots=[self.home], session_factory=self.session_factory))
        self.conversations = ConversationManager(self.settings, self.session_factory, self.bus)
        if models:
            self.settings.ai.models = models
            self.settings.ai.roles = {"default": models[0].id}
        self.router = ModelRouter(self.settings.ai)
        self.engine = AgentEngine(self.settings, self.router, self.tools,
                                  self.conversations, self.bus)
        return self

    async def _handler(self, request) -> str:
        self.decisions.append(f"{request.tool_name}:{request.risk.label}")
        return self.confirm_decision


@pytest.fixture()
def stack(jarvis_home: Path) -> Stack:
    return Stack(jarvis_home)


class MockProvider(LLMProvider):
    """Scripted provider for testing the tool-calling loop — no network."""

    def __init__(self, entry, script: list[ChatResponse]) -> None:
        super().__init__(entry)
        self.script = list(script)
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, temperature=0.3, max_tokens=1024) -> ChatResponse:
        self.calls.append({"roles": [m.role for m in messages], "tools": tools or []})
        if not self.script:
            return ChatResponse(content="Done.")
        return self.script.pop(0)


def tool_call_response(call_id: str, name: str, arguments: dict) -> ChatResponse:
    return ChatResponse(content="", tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)])
