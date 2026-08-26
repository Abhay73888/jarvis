"""Unit tests for Stage 4 Superpowers: Window Control, Memory Upgrade, Self-Healing, and Proactive Monitoring.
"""
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.brain.provider import ChatMessage, ChatResponse
from app.brain.self_heal import ErrorCategory, ErrorClassifier
from app.computer.proactive import ProactiveMonitor
from app.computer.window_manager import WindowInfo, WindowManager
from app.core.events import EventBus, Topics
from app.memory.preferences import PreferenceManager
from app.memory.projects import ProjectRegistry
from app.memory.summarizer import ConversationSummarizer
from app.tools.base import ToolContext
from app.tools.builtin.windows import ManageWindowTool


# ---------------------------------------------------------------- Window Manager Tests

def test_window_info_dataclass():
    win = WindowInfo(hwnd=12345, title="Google Chrome", process_name="chrome.exe", is_visible=True, is_minimized=False)
    assert win.hwnd == 12345
    assert win.title == "Google Chrome"
    assert win.process_name == "chrome.exe"


def test_window_manager_find_logic():
    mock_windows = [
        WindowInfo(1, "Google Chrome", "chrome.exe", True, False),
        WindowInfo(2, "Visual Studio Code", "code.exe", True, False),
        WindowInfo(3, "Command Prompt", "cmd.exe", True, True),
    ]

    with patch.object(WindowManager, "list_windows", return_value=mock_windows):
        # 1. Exact title match
        assert WindowManager.find_window("Google Chrome").hwnd == 1

        # 2. Substring match
        assert WindowManager.find_window("chrome").hwnd == 1
        assert WindowManager.find_window("studio code").hwnd == 2

        # 3. Process name match
        assert WindowManager.find_window("cmd").hwnd == 3

        # 4. Non-existent
        assert WindowManager.find_window("Photoshop") is None


@pytest.mark.asyncio
async def test_manage_window_tool(tmp_path):
    tool = ManageWindowTool()
    ctx = ToolContext(settings=MagicMock(), workdir=tmp_path, writable_roots=[tmp_path])

    mock_windows = [
        WindowInfo(1, "Notepad - Untitled", "notepad.exe", True, False),
    ]

    with patch.object(WindowManager, "list_windows", return_value=mock_windows):
        res = await tool.execute({"action": "list"}, ctx)
        assert res.success is True
        assert "Notepad" in res.message

    with patch.object(WindowManager, "focus", return_value=(True, "Focused Notepad")):
        res_focus = await tool.execute({"action": "focus", "title": "Notepad"}, ctx)
        assert res_focus.success is True
        assert "Focused Notepad" in res_focus.message


# ---------------------------------------------------------------- Memory & Preferences Tests

def test_preference_manager(tmp_path):
    pref_file = tmp_path / "test_prefs.json"
    pm = PreferenceManager(storage_path=pref_file)

    pm.set("preferred_editor", "VS Code")
    pm.set("window_style", "maximized")

    assert pm.get("preferred_editor") == "VS Code"
    assert pm.get("window_style") == "maximized"

    prompt_snippet = pm.format_for_system_prompt()
    assert "USER PREFERENCES" in prompt_snippet
    assert "preferred_editor: VS Code" in prompt_snippet

    # Reload from disk
    pm2 = PreferenceManager(storage_path=pref_file)
    assert pm2.get("preferred_editor") == "VS Code"


def test_project_registry(tmp_path):
    proj_file = tmp_path / "test_projects.json"
    pr = ProjectRegistry(storage_path=proj_file)

    health_dir = tmp_path / "healthcare_app"
    health_dir.mkdir()

    pr.register("healthcare", health_dir)
    assert pr.find("healthcare") == health_dir
    assert pr.find("health") == health_dir
    assert pr.find("non_existent_project") is None


@pytest.mark.asyncio
async def test_conversation_summarizer():
    cs = ConversationSummarizer(router=None)

    messages = [
        ChatMessage(role="user", content="Hello Jarvis"),
        ChatMessage(role="assistant", content="Hello! How can I help?"),
        ChatMessage(role="user", content="Yaad rakho main VS Code maximized prefer karti hoon"),
    ]

    facts = await cs.extract_facts(messages)
    assert len(facts) >= 1
    assert any("VS Code" in f for f in facts)


# ---------------------------------------------------------------- Self-Healing Error Classifier Tests

def test_error_classifier_missing_dependency():
    err_text = "Traceback (most recent call last):\nModuleNotFoundError: No module named 'fastapi'"
    cat, detail = ErrorClassifier.classify(err_text)
    assert cat == ErrorCategory.MISSING_DEPENDENCY
    assert detail == "fastapi"

    fix = ErrorClassifier.propose_fix(cat, detail)
    assert fix is not None
    assert fix["action"] == "install_package"
    assert "pip install fastapi" in fix["command"]


def test_error_classifier_permission_denied():
    err_text = "PermissionError: [Errno 13] Permission denied: 'C:/Windows/system32/secret'"
    cat, _ = ErrorClassifier.classify(err_text)
    assert cat == ErrorCategory.PERMISSION_DENIED


def test_error_classifier_network_timeout():
    err_text = "ConnectionRefusedError: [WinError 10061] No connection could be made because the target machine actively refused it"
    cat, _ = ErrorClassifier.classify(err_text)
    assert cat == ErrorCategory.NETWORK_TIMEOUT


# ---------------------------------------------------------------- Proactive Monitor Tests

@pytest.mark.asyncio
async def test_proactive_monitor_alerts():
    mock_bus = EventBus()
    monitor = ProactiveMonitor(bus=mock_bus)

    # Mock high disk usage
    mock_disk = MagicMock()
    mock_disk.percent = 92.5
    mock_disk.free = 5 * (1024 ** 3)

    with patch("psutil.disk_usage", return_value=mock_disk):
        alerts = await monitor.check_health()
        assert len(alerts) >= 1
        assert any(a["type"] == "disk_space_warning" for a in alerts)
