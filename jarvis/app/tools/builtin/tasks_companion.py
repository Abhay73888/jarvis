"""Offline Task & Daily Brief Companion Tool for JARVIS.

Handles voice task management:
- list: 'mere tasks batao', 'kal ke tasks'
- add: 'naya task: kal 10 baje report bhejna'
- complete: 'ye complete ho gaya', 'report task done karo'
- snooze: '10 minute baad yaad dila'
- daily_review: 'aaj kya hua', 'end of day review'
All stored and queried 100% locally from SQLite DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, ClassVar, Literal, Optional, Type

import psutil
from pydantic import BaseModel, Field

from app.database.repo import TaskRepo
from app.security.risk import RiskLevel
from app.tools.base import BaseTool, ToolContext, ToolResult


class TaskCompanionArgs(BaseModel):
    action: Literal["list", "add", "complete", "snooze", "daily_review", "daily_brief"] = Field(
        default="list", description="Action to perform: list, add, complete, snooze, daily_review, daily_brief"
    )
    title: Optional[str] = Field(default=None, description="Task title or description")
    due_at: Optional[str] = Field(default=None, description="Due date/time string, e.g. 'tomorrow 10:00', '10 mins'")
    task_id: Optional[int] = Field(default=None, description="Task ID if known")
    snooze_minutes: Optional[int] = Field(default=10, description="Snooze duration in minutes")


class TaskCompanionTool(BaseTool):
    name: ClassVar[str] = "manage_tasks"
    description: ClassVar[str] = (
        "Offline task and daily brief companion: list tasks, add new task, complete task, "
        "snooze task, or get daily morning brief / end-of-day review from local database."
    )
    args_model: ClassVar[Type[BaseModel]] = TaskCompanionArgs
    category: ClassVar[str] = "memory"
    risk: ClassVar[RiskLevel] = RiskLevel.LOW
    destructive: ClassVar[bool] = False

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        action = args.get("action", "list")
        title = args.get("title")
        task_id = args.get("task_id")
        snooze_min = args.get("snooze_minutes", 10) or 10

        if not ctx.session_factory:
            return ToolResult(False, "Database session factory not initialized in tool context.")

        async with ctx.session_factory() as session:
            repo = TaskRepo(session)

            if action == "add":
                if not title:
                    return ToolResult(False, "Task title is required to add a task.")
                # Compute due_at if provided
                due_dt = None
                if args.get("due_at"):
                    due_dt = self._parse_due_time(args["due_at"])
                task = await repo.create(title=title, due_at=due_dt)
                due_str = f" for {due_dt.strftime('%d %b, %I:%M %p')}" if due_dt else ""
                msg = f"✓ Naya task add kar diya: '{title}'{due_str}."
                return ToolResult(True, msg, data={"task_id": task.id, "title": title}, verified=True)

            elif action == "list":
                tasks = await repo.list(status="pending")
                if not tasks:
                    return ToolResult(True, "Aaj koi pending tasks nahi hain, sab clear hai!", data={"count": 0, "tasks": []})
                count = len(tasks)
                items = [f"{idx+1}. {t.title}" for idx, t in enumerate(tasks[:5])]
                list_str = ", ".join(items)
                msg = f"Aapke {count} pending tasks hain: {list_str}."
                return ToolResult(True, msg, data={"count": count, "tasks": [{"id": t.id, "title": t.title} for t in tasks]})

            elif action == "complete":
                pending = await repo.list(status="pending")
                target = None
                if task_id:
                    target = next((t for t in pending if t.id == task_id), None)
                elif title:
                    # Match by substring
                    target = next((t for t in pending if title.lower() in t.title.lower()), None)
                if not target and pending:
                    target = pending[0]  # Complete latest/top item

                if target:
                    await repo.set_status(target.id, "done")
                    return ToolResult(True, f"✓ Task mark done: '{target.title}'.", data={"task_id": target.id, "title": target.title}, verified=True)
                return ToolResult(False, "Koi matching pending task nahi mila complete karne ke liye.")

            elif action == "snooze":
                pending = await repo.list(status="pending")
                if not pending:
                    return ToolResult(True, "Snooze karne ke liye koi pending task nahi hai.")
                target = pending[0]
                new_due = datetime.now() + timedelta(minutes=snooze_min)
                target.due_at = new_due
                await session.commit()
                return ToolResult(True, f"✓ Task '{target.title}' {snooze_min} minute ke liye snooze kar diya gaya.", data={"task_id": target.id, "snooze_until": new_due.isoformat()})

            elif action in ("daily_review", "daily_brief"):
                pending = await repo.list(status="pending")
                all_tasks = await repo.list()
                completed = [t for t in all_tasks if t.status == "done"]

                # Telemetry
                battery = psutil.sensors_battery()
                bat_str = f"Battery {int(battery.percent)}%" if battery else ""
                disk = psutil.disk_usage("/")
                disk_warn = f" Disk space warning: {int(disk.percent)}% full." if disk.percent > 90 else ""

                if action == "daily_review":
                    msg = (
                        f"End-of-day Review: Aaj aapne {len(completed)} tasks complete kiye hain "
                        f"aur {len(pending)} tasks pending hain.{disk_warn}"
                    )
                else:
                    task_preview = f" Sabse pehle: '{pending[0].title}'." if pending else " Sab clear hai."
                    msg = (
                        f"Daily Brief: {bat_str}. Aaj aapke {len(pending)} pending tasks hain.{task_preview}{disk_warn}"
                    )
                return ToolResult(True, msg, data={"pending": len(pending), "completed": len(completed)})

            return ToolResult(False, f"Unknown action '{action}'")

    def _parse_due_time(self, raw: str) -> datetime:
        now = datetime.now()
        raw_l = raw.lower()
        if "minute" in raw_l or "min" in raw_l:
            import re
            m = re.search(r"\d+", raw_l)
            mins = int(m.group(0)) if m else 10
            return now + timedelta(minutes=mins)
        if "tomorrow" in raw_l or "kal" in raw_l:
            base = now + timedelta(days=1)
            return base.replace(hour=10, minute=0, second=0)
        return now + timedelta(hours=1)
