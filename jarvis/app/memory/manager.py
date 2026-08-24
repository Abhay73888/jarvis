"""Memory system (Spec §22, §23): three levels.

Short-term  — conversation messages (DB-backed) fed to the LLM as a window.
Working     — volatile task state ("what does 'it' refer to?"), injected into
              every prompt so references resolve naturally.
Long-term   — MemoryRepo/PreferenceRepo (facts, preferences, project locations).

Secrets are redacted before anything is persisted.
"""
from __future__ import annotations

from typing import Any

from app.brain.provider import ChatMessage
from app.config.settings import Settings
from app.core.events import EventBus
from app.database.repo import ConversationRepo, PreferenceRepo
from app.security.redaction import redact


class WorkingMemory:
    """Volatile state for the current task & referent tracking."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self.candidates: list[str] = []
        self.last_app: str | None = None
        self.last_path: str | None = None
        self.last_tool: str | None = None
        self.task: str | None = None        # e.g. "opening Chrome"

    def summary(self) -> str:
        parts = []
        if self.task:
            parts.append(f"Current task: {self.task}")
        if self.last_app:
            parts.append(f"Last app discussed: {self.last_app}")
        if self.last_path:
            parts.append(f"Last file/folder discussed: {self.last_path}")
        if self.candidates:
            parts.append(f"Awaiting choice among: {', '.join(self.candidates[:5])}")
        return "\n".join(parts)

    def observe_result(self, tool: str, result_data: dict[str, Any]) -> None:
        self.last_tool = tool
        if tool == "open_application" and result_data.get("app"):
            self.last_app = result_data["app"]
        if result_data.get("ambiguous") and result_data.get("candidates"):
            self.candidates = result_data["candidates"]
        elif tool != "open_application":
            self.candidates = []
        for key in ("path",):
            if isinstance(result_data.get(key), str):
                self.last_path = result_data[key]
        if tool == "open_application" and not result_data.get("ambiguous"):
            self.candidates = []


class ConversationManager:
    def __init__(self, settings: Settings, session_factory, bus: EventBus) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._bus = bus
        self._active_id: int | None = None

    async def active_id(self) -> int:
        if self._active_id is None:
            async with self._session_factory() as session:
                conv = await ConversationRepo(session).get_or_create_active()
                self._active_id = conv.id
        return self._active_id

    async def new_conversation(self, title: str = "New conversation") -> int:
        async with self._session_factory() as session:
            conv = await ConversationRepo(session).start_new(title)
            self._active_id = conv.id
        return conv.id

    async def append(self, role: str, content: str, meta: dict | None = None) -> None:
        if not self._settings.memory.persist_conversations and role == "user":
            return
        content = redact(content)
        async with self._session_factory() as session:
            await ConversationRepo(session).append_message(
                await self.active_id(), role, content, meta)

    async def history(self, limit: int | None = None) -> list[ChatMessage]:
        """Recent messages as provider-neutral ChatMessages."""
        window = limit or self._settings.memory.history_window
        async with self._session_factory() as session:
            rows = await ConversationRepo(session).recent(await self.active_id(), limit=window)
        return [ChatMessage(role=r.role, content=r.content) for r in rows if r.role in ("user", "assistant")]

    async def preferences(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            return await PreferenceRepo(session).all()
