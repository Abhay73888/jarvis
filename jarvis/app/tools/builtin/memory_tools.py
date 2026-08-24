"""Memory & reminder tools (Spec §22, §24, §56) — remember/recall, preferences,
reminders. All content passes through secret redaction before storage."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult


class _RememberArgs(BaseModel):
    kind: Literal["fact", "preference", "project", "episodic"] = "fact"
    key: str = Field(description="Short lookup key, e.g. 'preferred-editor'")
    content: str = Field(description="What to remember")


class RememberTool(BaseTool):
    name = "remember"
    description = ("Store a long-term memory (fact/preference/project). Never store passwords "
                   "or API keys — they are refused and redacted, not saved.")
    args_model = _RememberArgs
    category = "memory"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        from app.security.redaction import redact
        content = redact(args["content"])
        if content != args["content"]:
            return ToolResult(False,
                              "That looked like it contained a secret — I don't store those.",
                              verified=True)
        if ctx.session_factory is None:
            return ToolResult(False, "Memory storage isn't available.", error="no session factory")
        from app.database.repo import MemoryRepo
        async with ctx.session_factory() as session:
            await MemoryRepo(session).remember(kind=args["kind"], key=args["key"], content=content)
        return ToolResult(True, f"Noted: {args['key']}.", data={"key": args["key"]}, verified=True)


class _RecallArgs(BaseModel):
    query: str = Field(default="", description="What to recall; empty = most important memories")


class RecallTool(BaseTool):
    name = "recall_memories"
    description = "Search long-term memory for earlier facts, preferences, and project notes."
    args_model = _RecallArgs
    category = "memory"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        if ctx.session_factory is None:
            return ToolResult(False, "Memory storage isn't available.", error="no session factory")
        from app.database.repo import MemoryRepo
        async with ctx.session_factory() as session:
            items = await MemoryRepo(session).search(args["query"], limit=10)
        if not items:
            return ToolResult(True, "Nothing in memory matches that yet.", data={"results": []},
                              verified=True)
        results = [{"kind": i.kind, "key": i.key, "content": i.content} for i in items]
        return ToolResult(True, f"{len(results)} memory item(s) found.",
                          data={"results": results}, verified=True)


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_DAY_RE = re.compile(r"^(today|tonight|tomorrow|day after tomorrow)$", re.I)


def parse_due_at(raw: str | None, now: datetime | None = None) -> datetime | None:
    """Best-effort natural datetime parsing: ISO strings, 'tomorrow 18:30',
    'tonight', 'HH:MM' (today or tomorrow). Returns timezone-aware local time."""
    if not raw:
        return None
    now = now or datetime.now().astimezone()
    text = raw.strip().lower()

    if text in ("today", "tonight", "tomorrow", "day after tomorrow"):
        base = now + timedelta(days={"today": 0, "tonight": 0, "tomorrow": 1,
                                     "day after tomorrow": 2}[text])
        hour = 20 if text == "tonight" else 9
        return base.replace(hour=hour, minute=0, second=0, microsecond=0)

    if " " in text:
        day_part, time_part = text.rsplit(" ", 1)
        if _DAY_RE.match(day_part) and _TIME_RE.match(time_part):
            day = parse_due_at(day_part, now)
            assert day is not None
            hour, minute = int(time_part.split(":")[0]), int(time_part.split(":")[1])
            return day.replace(hour=hour, minute=minute)

    if _TIME_RE.match(text):
        hour, minute = int(text.split(":")[0]), int(text.split(":")[1])
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    try:  # ISO format
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        return parsed
    except ValueError:
        return None


class _ReminderArgs(BaseModel):
    title: str
    due_at: str | None = Field(default=None,
                               description="When to remind: ISO datetime or 'tomorrow 10:00' / 'tonight' / '18:30'")


class SetReminderTool(BaseTool):
    name = "set_reminder"
    description = ("Create a persistent reminder with a due time "
                   "('tomorrow 10:00', 'tonight', '18:30', or ISO datetime).")
    args_model = _ReminderArgs
    category = "memory"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        due = parse_due_at(args.get("due_at"))
        if args["due_at"] and due is None:
            return ToolResult(False, f"I couldn't understand the time '{args['due_at']}'. "
                              "Try 'tomorrow 10:00' or an ISO datetime.", verified=True)
        if ctx.session_factory is None:
            return ToolResult(False, "Task storage isn't available.", error="no session factory")
        from app.database.repo import TaskRepo
        async with ctx.session_factory() as session:
            task = await TaskRepo(session).create(title=args["title"], due_at=due)
        when = due.strftime("%a %d %b, %H:%M") if due else "no specific time"
        return ToolResult(True, f"Reminder set for {when}: {args['title']}.",
                          data={"id": task.id, "due_at": due.isoformat() if due else None},
                          verified=True)


class _ListTasksArgs(BaseModel):
    status: Literal["pending", "done", "failed", "scheduled"] | None = None


class ListTasksTool(BaseTool):
    name = "list_reminders"
    description = "List saved reminders/tasks, optionally filtered by status."
    args_model = _ListTasksArgs
    category = "memory"
    risk = RiskLevel.LOW

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        if ctx.session_factory is None:
            return ToolResult(False, "Task storage isn't available.", error="no session factory")
        from app.database.repo import TaskRepo
        async with ctx.session_factory() as session:
            tasks = await TaskRepo(session).list(status=args.get("status"))
        if not tasks:
            return ToolResult(True, "No reminders yet.", data={"tasks": []}, verified=True)
        rows = [{"id": t.id, "title": t.title, "status": t.status,
                 "due_at": t.due_at.isoformat() if t.due_at else None} for t in tasks]
        return ToolResult(True, f"{len(rows)} reminder(s).", data={"tasks": rows}, verified=True)
