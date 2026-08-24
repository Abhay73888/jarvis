"""Repositories — all DB access lives here. Args are redacted before persist."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Conversation, MemoryItem, Message, PermissionGrant, Preference, TaskRecord, ToolUsage
from app.security.redaction import redact_mapping


class ConversationRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_or_create_active(self) -> Conversation:
        result = await self._s.execute(
            select(Conversation).where(Conversation.active).order_by(desc(Conversation.id)).limit(1))
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = Conversation(title="New conversation")
            self._s.add(conv)
            await self._s.commit()
        return conv

    async def start_new(self, title: str = "New conversation") -> Conversation:
        await self._s.execute(update(Conversation).values(active=False))
        conv = Conversation(title=title)
        self._s.add(conv)
        await self._s.commit()
        return conv

    async def append_message(self, conversation_id: int, role: str, content: str,
                             meta: dict | None = None) -> Message:
        msg = Message(conversation_id=conversation_id, role=role, content=content,
                      meta=redact_mapping(meta or {}))
        self._s.add(msg)
        await self._s.commit()
        return msg

    async def recent(self, conversation_id: int, limit: int = 20) -> list[Message]:
        result = await self._s.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.id))
            .limit(limit))
        return list(reversed(result.scalars().all()))


class MemoryRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def remember(self, kind: str, key: str, content: str, source: str = "user",
                       importance: float = 0.5) -> MemoryItem:
        result = await self._s.execute(
            select(MemoryItem).where(MemoryItem.kind == kind, MemoryItem.key == key))
        item = result.scalar_one_or_none()
        if item:
            item.content = content
            item.importance = importance
        else:
            item = MemoryItem(kind=kind, key=key, content=content, source=source, importance=importance)
            self._s.add(item)
        await self._s.commit()
        return item

    async def search(self, query: str, limit: int = 10) -> list[MemoryItem]:
        stmt = select(MemoryItem).order_by(desc(MemoryItem.importance)).limit(limit)
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(or_(
                func.lower(MemoryItem.key).like(like),
                func.lower(MemoryItem.content).like(like)))
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def forget(self, kind: str, key: str) -> bool:
        result = await self._s.execute(
            delete(MemoryItem).where(MemoryItem.kind == kind, MemoryItem.key == key))
        await self._s.commit()
        return bool(result.rowcount)


class PreferenceRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def set(self, key: str, value: dict) -> None:
        result = await self._s.execute(select(Preference).where(Preference.key == key))
        pref = result.scalar_one_or_none()
        if pref:
            pref.value = value
        else:
            self._s.add(Preference(key=key, value=value))
        await self._s.commit()

    async def all(self) -> dict[str, dict]:
        result = await self._s.execute(select(Preference))
        return {p.key: p.value for p in result.scalars().all()}


class PermissionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def grant(self, subject: str, decision: str) -> None:
        result = await self._s.execute(select(PermissionGrant).where(PermissionGrant.subject == subject))
        row = result.scalar_one_or_none()
        if row:
            row.decision = decision
        else:
            self._s.add(PermissionGrant(subject=subject, decision=decision))
        await self._s.commit()

    async def find(self, subject: str) -> str | None:
        result = await self._s.execute(
            select(PermissionGrant).where(PermissionGrant.subject == subject))
        row = result.scalar_one_or_none()
        return row.decision if row else None


class ToolUsageRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def log(self, tool: str, args: dict, risk: str, status: str, duration_ms: int,
                  error: str | None = None) -> None:
        self._s.add(ToolUsage(tool=tool, args=redact_mapping(args), risk=risk, status=status,
                              duration_ms=duration_ms, error=error))
        await self._s.commit()

    async def recent(self, limit: int = 50) -> list[ToolUsage]:
        result = await self._s.execute(select(ToolUsage).order_by(desc(ToolUsage.id)).limit(limit))
        return list(result.scalars().all())


class TaskRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, title: str, due_at: datetime | None = None, payload: dict | None = None) -> TaskRecord:
        task = TaskRecord(title=title, due_at=due_at, payload=payload or {})
        self._s.add(task)
        await self._s.commit()
        return task

    async def list(self, status: str | None = None) -> list[TaskRecord]:
        stmt = select(TaskRecord).order_by(TaskRecord.due_at.nulls_last(), desc(TaskRecord.id))
        if status:
            stmt = stmt.where(TaskRecord.status == status)
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def set_status(self, task_id: int, status: str) -> bool:
        result = await self._s.execute(
            update(TaskRecord).where(TaskRecord.id == task_id).values(status=status))
        await self._s.commit()
        return bool(result.rowcount)
