"""Permission and Settings dialogs for JARVIS Desktop GUI.

Provides:
- PermissionDialog: Futuristic dark-glass prompt for High/Critical actions
  (Allow once, Always allow, Deny).
- SettingsDialog: Configuration for Voice, Wake Words, Models, and Greetings.
- GuiPermissionBridge: Thread-safe bridge connecting background engine confirm requests
  to the Qt UI main thread.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.permissions.manager import PermissionRequest
from app.security.risk import RiskLevel
from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_SURFACE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    STYLESHEET,
)


class PermissionDialog(QDialog):
    """Futuristic modal dialog requesting user confirmation for High/Critical actions."""

    def __init__(self, request: PermissionRequest, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.request = request
        self.choice = "deny"

        self.setWindowTitle(f"Permission Required — {request.tool_name}")
        self.setFixedWidth(460)
        self.setStyleSheet(STYLESHEET)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with Risk Pill
        header_layout = QHBoxLayout()
        title_lbl = QLabel(f"JARVIS requests permission:")
        title_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 15px; font-weight: bold;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        risk_color = COLOR_DANGER if self.request.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) else COLOR_WARNING
        risk_badge = QLabel(f"{self.request.risk.label.upper()} RISK")
        risk_badge.setStyleSheet(
            f"color: {risk_color}; background-color: rgba(255,255,255,0.06); "
            f"border: 1px solid {risk_color}; border-radius: 8px; padding: 3px 8px; "
            f"font-size: 11px; font-weight: bold;"
        )
        header_layout.addWidget(risk_badge)
        layout.addLayout(header_layout)

        # Action Card
        card = QFrame(self)
        card.setStyleSheet(f"background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 10px; padding: 12px;")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        tool_lbl = QLabel(f"🔧 Tool: <b>{self.request.tool_name}</b> ({self.request.category})")
        tool_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px;")
        card_layout.addWidget(tool_lbl)

        if self.request.reason:
            reason_lbl = QLabel(f"Reason: {self.request.reason}")
            reason_lbl.setWordWrap(True)
            reason_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
            card_layout.addWidget(reason_lbl)

        if self.request.args_summary:
            args_str = ", ".join(f"{k}='{v}'" for k, v in self.request.args_summary.items())
            args_lbl = QLabel(f"Arguments: <code>{args_str}</code>")
            args_lbl.setWordWrap(True)
            args_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
            card_layout.addWidget(args_lbl)

        layout.addWidget(card)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        deny_btn = QPushButton("Deny")
        deny_btn.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_DANGER}; border: 1px solid {COLOR_DANGER}; border-radius: 8px; padding: 8px 16px; font-weight: bold;")
        deny_btn.clicked.connect(self._on_deny)
        btn_layout.addWidget(deny_btn)

        btn_layout.addStretch()

        allow_once_btn = QPushButton("Allow Once")
        allow_once_btn.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; border-radius: 8px; padding: 8px 16px;")
        allow_once_btn.clicked.connect(self._on_allow_once)
        btn_layout.addWidget(allow_once_btn)

        allow_always_btn = QPushButton("Always Allow")
        allow_always_btn.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: #000; font-weight: bold; border-radius: 8px; padding: 8px 16px;")
        allow_always_btn.clicked.connect(self._on_allow_always)
        if self.request.risk == RiskLevel.CRITICAL:
            allow_always_btn.setEnabled(False)
            allow_always_btn.setToolTip("CRITICAL risk actions cannot be granted permanent standing approval.")
        btn_layout.addWidget(allow_always_btn)

        layout.addLayout(btn_layout)

    def _on_deny(self) -> None:
        self.choice = "deny"
        self.reject()

    def _on_allow_once(self) -> None:
        self.choice = "allow_once"
        self.accept()

    def _on_allow_always(self) -> None:
        self.choice = "allow_always"
        self.accept()


class SettingsDialog(QDialog):
    """Settings dialog for customizing JARVIS preferences."""

    def __init__(self, settings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("JARVIS Settings")
        self.setFixedWidth(440)
        self.setStyleSheet(STYLESHEET)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("System Configuration")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        # 1. Master Address
        self.address_edit = QLineEdit(self.settings.greeting.address)
        self.address_edit.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 6px;")
        form.addRow("Address Style:", self.address_edit)

        # 2. TTS Voice
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(["en-IN-NeerjaNeural", "hi-IN-SwaraNeural", "en-US-AriaNeural"])
        self.voice_combo.setCurrentText(self.settings.voice.tts_voice)
        self.voice_combo.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_BORDER}; border-radius: 6px; padding: 6px;")
        form.addRow("TTS Voice:", self.voice_combo)

        # 3. Wake word enabled
        self.wake_cb = QCheckBox("Enable Hands-free Wake Word ('Jarvis')")
        self.wake_cb.setChecked(self.settings.voice.wake_enabled)
        form.addRow("", self.wake_cb)

        # 4. Speak responses
        self.speak_cb = QCheckBox("Speak Responses Aloud (TTS)")
        self.speak_cb.setChecked(self.settings.voice.speak_responses)
        form.addRow("", self.speak_cb)

        layout.addLayout(form)

        # Save Button
        save_btn = QPushButton("Save & Close")
        save_btn.setStyleSheet(f"background-color: {COLOR_ACCENT}; color: #000; font-weight: bold; border-radius: 8px; padding: 8px 16px;")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)

    def _save_settings(self) -> None:
        self.settings.greeting.address = self.address_edit.text().strip() or "Sir"
        self.settings.voice.tts_voice = self.voice_combo.currentText()
        self.settings.voice.wake_enabled = self.wake_cb.isChecked()
        self.settings.voice.speak_responses = self.speak_cb.isChecked()
        self.accept()


class GuiPermissionBridge(QObject):
    """Bridge for triggering permission dialogs from background async worker thread."""

    request_permission_signal = Signal(object, object)  # (PermissionRequest, (asyncio.Future, loop))

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__()
        self.parent_window = parent_window
        self.request_permission_signal.connect(self._show_dialog)

    def _show_dialog(self, request: PermissionRequest, future_loop_tuple: tuple) -> None:
        future, loop = future_loop_tuple
        dlg = PermissionDialog(request, self.parent_window)
        dlg.exec()
        choice = dlg.choice
        loop.call_soon_threadsafe(future.set_result, choice)

    def create_async_handler(self, async_loop: asyncio.AbstractEventLoop):
        async def handler(request: PermissionRequest) -> str:
            future = async_loop.create_future()
            self.request_permission_signal.emit(request, (future, async_loop))
            return await future

        return handler
