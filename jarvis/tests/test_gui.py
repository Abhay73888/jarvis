"""Unit tests for Stage 2 PySide6 GUI, System Tray, and Permission Dialogs.

Runs with QT_QPA_PLATFORM=offscreen to verify UI components headlessly in CI.
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.config.settings import Settings
from app.core.events import EventBus, Topics
from app.permissions.manager import PermissionRequest
from app.security.risk import RiskLevel
from app.ui.components import ChatBubble, SystemStatsBar, VoiceVisualizer
from app.ui.dialogs import GuiPermissionBridge, PermissionDialog, SettingsDialog
from app.ui.tray import JarvisTrayIcon
from app.ui.window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for all GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_voice_visualizer_states(qapp):
    vis = VoiceVisualizer()
    assert vis._state == "idle"

    vis.set_state("listening")
    assert vis._state == "listening"

    vis.set_state("thinking")
    assert vis._state == "thinking"

    vis.set_state("speaking")
    assert vis._state == "speaking"


def test_system_stats_bar(qapp):
    bar = SystemStatsBar()
    bar.update_stats()
    assert "CPU" in bar.cpu_label.text()
    assert "RAM" in bar.ram_label.text()


def test_chat_bubble_rendering(qapp):
    # Assistant bubble with action tags
    actions = [{"tool": "open_app", "ok": True, "message": "Opened Chrome"}]
    bubble = ChatBubble(role="assistant", text="Hello Boss, I opened Chrome for you.", actions=actions)
    assert bubble is not None

    # User bubble
    user_bubble = ChatBubble(role="user", text="Chrome kholo")
    assert user_bubble is not None


def test_permission_dialog_choices(qapp):
    req = PermissionRequest(
        subject="tool:delete_file",
        tool_name="delete_file",
        category="files",
        risk=RiskLevel.HIGH,
        reason="User requested file removal",
        args_summary={"path": "C:/test.txt"},
    )
    dlg = PermissionDialog(req)
    assert dlg.choice == "deny"

    dlg._on_allow_once()
    assert dlg.choice == "allow_once"

    dlg._on_allow_always()
    assert dlg.choice == "allow_always"

    dlg._on_deny()
    assert dlg.choice == "deny"


def test_critical_permission_dialog_blocks_always_allow(qapp):
    req = PermissionRequest(
        subject="tool:terminal",
        tool_name="terminal",
        category="terminal",
        risk=RiskLevel.CRITICAL,
        reason="Dangerous disk format command",
        args_summary={"command": "format C:"},
    )
    dlg = PermissionDialog(req)
    # The 'Always Allow' button should be disabled for CRITICAL risk
    for child in dlg.findChildren(object):
        if hasattr(child, "text") and child.text() == "Always Allow":
            assert not child.isEnabled()


def test_settings_dialog(qapp):
    settings = Settings()
    dlg = SettingsDialog(settings)
    dlg.address_edit.setText("Boss")
    dlg.voice_combo.setCurrentText("hi-IN-SwaraNeural")
    dlg.wake_cb.setChecked(True)
    dlg.speak_cb.setChecked(False)

    dlg._save_settings()
    assert settings.greeting.address == "Boss"
    assert settings.voice.tts_voice == "hi-IN-SwaraNeural"
    assert settings.voice.wake_enabled is True
    assert settings.voice.speak_responses is False


def test_main_window_construction_and_events(qapp):
    mock_engine = MagicMock()
    mock_bus = EventBus()
    settings = Settings()

    window = MainWindow(engine=mock_engine, bus=mock_bus, settings=settings)
    assert window.windowTitle() == "JARVIS — AI Operating Layer"

    # Test status update signal
    window.status_updated.emit("listening", "Listening for wake word")
    assert window.visualizer._state == "listening"
    assert window.status_badge.text() == "LISTENING"

    window.status_updated.emit("speaking", "Speaking response")
    assert window.visualizer._state == "speaking"
    assert window.status_badge.text() == "SPEAKING"

    # Test message stream
    window.add_message("user", "Hello Jarvis")
    window.add_message("assistant", "Hello Sir, standing by.")
    assert window.chat_layout.count() >= 2


def test_system_tray_icon_actions(qapp):
    mock_engine = MagicMock()
    mock_bus = EventBus()
    settings = Settings()
    window = MainWindow(engine=mock_engine, bus=mock_bus, settings=settings)

    tray = JarvisTrayIcon(parent_window=window, settings=settings)
    assert tray is not None

    # Toggle show window
    window.hide()
    tray._toggle_show_window()
    assert window.isVisible()

    tray._toggle_show_window()
    assert not window.isVisible()
