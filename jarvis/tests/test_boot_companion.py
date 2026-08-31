"""Unit tests for Stage O4 — Boot Companion & Spoken Daily Brief."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.brain.greeting import build_greeting
from app.brain.intent import IntentRouter
from app.database.models import TaskRecord
from app.tools.base import ToolContext
from app.tools.builtin.tasks_companion import TaskCompanionTool


def test_spoken_daily_brief_offline_structure():
    now = datetime(2026, 8, 31, 9, 0)
    # 1. Standard offline brief with tasks & battery
    brief = build_greeting(
        now=now,
        address="Abhay",
        include_brief=True,
        pending_today=3,
        task_titles=["Team meeting at 10", "Deploy v0.6.0", "Code review"],
        battery_info={"percent": 82, "plugged": True},
        disk_info={"percent": 65},
        is_online=False,
        include_weather=True,
    )
    assert "Good morning, Abhay." in brief
    assert "Today is Monday, August 31." in brief
    assert "Battery 82% (charging)." in brief
    assert "Aaj aapke 3 tasks hain — sabse pehle: 'Team meeting at 10'." in brief
    assert "Sab karein ya details sunaun?" in brief
    assert "Weather ke liye offline hoon." in brief
    assert "Disk warning" not in brief

    # 2. Disk warning when disk > 90%
    brief_disk = build_greeting(
        now=now,
        address="sir",
        include_brief=True,
        disk_info={"percent": 94},
        is_online=False,
    )
    assert "Disk warning: storage 94% full." in brief_disk


@pytest.mark.asyncio
async def test_task_companion_tool_crud():
    tool = TaskCompanionTool()

    # In-memory mock session and repository
    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    ctx = ToolContext(
        settings=MagicMock(),
        workdir=MagicMock(),
        writable_roots=[],
        session_factory=mock_session_factory,
    )

    with patch("app.tools.builtin.tasks_companion.TaskRepo") as MockRepo:
        repo_instance = MockRepo.return_value
        fake_task = TaskRecord(id=1, title="Review PR #42", status="pending")
        repo_instance.create = AsyncMock(return_value=fake_task)
        repo_instance.list = AsyncMock(return_value=[fake_task])
        repo_instance.set_status = AsyncMock(return_value=True)

        # 1. Add task
        r_add = await tool.execute({"action": "add", "title": "Review PR #42"}, ctx)
        assert r_add.success is True
        assert "Naya task add kar diya" in r_add.message

        # 2. List tasks
        r_list = await tool.execute({"action": "list"}, ctx)
        assert r_list.success is True
        assert "Review PR #42" in r_list.message

        # 3. Complete task
        r_done = await tool.execute({"action": "complete", "title": "Review PR"}, ctx)
        assert r_done.success is True
        assert "✓ Task mark done" in r_done.message

        # 4. Snooze task
        r_snooze = await tool.execute({"action": "snooze", "snooze_minutes": 15}, ctx)
        assert r_snooze.success is True
        assert "15 minute" in r_snooze.message

        # 5. Daily review
        r_review = await tool.execute({"action": "daily_review"}, ctx)
        assert r_review.success is True
        assert "End-of-day Review" in r_review.message


def test_task_companion_intent_fast_path():
    router = IntentRouter()

    # List tasks
    i1 = router.parse("mere tasks batao")
    assert i1 is not None
    assert i1.tool == "manage_tasks"
    assert i1.args.get("action") == "list"

    # Add task
    i2 = router.parse("naya task: kal 10 baje team sync")
    assert i2 is not None
    assert i2.tool == "manage_tasks"
    assert i2.args.get("action") == "add"
    assert "team sync" in i2.args.get("title", "")

    # Complete task
    i3 = router.parse("ye complete ho gaya")
    assert i3 is not None
    assert i3.tool == "manage_tasks"
    assert i3.args.get("action") == "complete"

    # Snooze
    i4 = router.parse("20 minute baad yaad dila")
    assert i4 is not None
    assert i4.tool == "manage_tasks"
    assert i4.args.get("action") == "snooze"
    assert i4.args.get("snooze_minutes") == 20

    # End of day review
    i5 = router.parse("aaj kya hua")
    assert i5 is not None
    assert i5.tool == "manage_tasks"
    assert i5.args.get("action") == "daily_review"
