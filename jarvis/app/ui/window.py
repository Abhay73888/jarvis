"""God-Level Sci-Fi Cybernetic Desktop HUD Window for JARVIS.

Integrates:
- Kardashev Type-II Holographic Arc Reactor (Quantum Neural Core Visualizer).
- Live Telemetry HUD (Quantum CPU, Synapse RAM, Zero-Point Power, Neural Link).
- Modular Tabs:
    1. ⚡ NEURAL HUD (Core Reactor + Live Holographic Stream + Quick Chips + Transmit Bar).
    2. 🛠️ PROTOCOL MATRIX (App Launcher, Acoustic Volume Deck, Screen Vision, Lockdown).
    3. 🧠 SYNAPSE MATRIX (Active Memory, Context, Learned Facts, Agent Swarm).
- Non-blocking Thread-Safe Event Loop Bridge for 100% Silky-Smooth 60 FPS Execution.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.brain.engine import AgentEngine, TurnResult
from app.core.events import EventBus, Topics
from app.core.logging import get_logger
from app.ui.components import (
    CyberChatBubble,
    CyberTelemetryHUD,
    QuantumCoreVisualizer,
    QuickActionGrid,
)
from app.ui.protocol_matrix import ProtocolMatrixWidget
from app.ui.settings_dialog import SettingsDialog
from app.ui.synapse_matrix import SynapseMatrixWidget
from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_DIM,
    COLOR_ACCENT_GLOW,
    COLOR_AMBER,
    COLOR_BG_CARD,
    COLOR_BG_SURFACE,
    COLOR_BG_VOID,
    COLOR_BORDER,
    COLOR_CRIMSON,
    COLOR_EMERALD,
    COLOR_PLASMA_BLUE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    STYLESHEET,
)

log = get_logger("ui.window")


class MainWindow(QMainWindow):
    """God-Level Sci-Fi Cybernetic Operating Layer Window."""
    status_updated = Signal(str, str)
    message_received = Signal(str, str, object)
    tool_event = Signal(str, str)

    def __init__(
        self,
        engine: AgentEngine,
        bus: EventBus,
        settings=None,
        voice_listener=None,
        async_loop: Optional[asyncio.AbstractEventLoop] = None,
        on_close_to_tray_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.bus = bus
        self.settings = settings
        self.voice_listener = voice_listener
        if async_loop is not None:
            self.async_loop = async_loop
        else:
            try:
                self.async_loop = asyncio.get_running_loop()
            except RuntimeError:
                self.async_loop = asyncio.new_event_loop()
        self.on_close_to_tray_callback = on_close_to_tray_callback

        self.setWindowTitle("JARVIS — AI Operating Layer")
        self.setMinimumSize(540, 760)
        self.resize(600, 840)
        self.setStyleSheet(STYLESHEET)

        self._drag_pos = QPoint()
        self._speak_responses = True

        self._setup_ui()
        self._connect_events()

    def _setup_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 12, 14, 14)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 1. Holographic Cyber Header Bar
        # -------------------------------------------------------------
        header = QFrame(self)
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(10)

        # Glowing Title & Version
        title_lbl = QLabel("J A R V I S")
        title_lbl.setObjectName("TitleLabel")
        header_layout.addWidget(title_lbl)

        ver_badge = QLabel("V3.6 NEURAL")
        ver_badge.setObjectName("VersionBadge")
        header_layout.addWidget(ver_badge)

        self.status_badge = QLabel("IDLE")
        self.status_badge.setObjectName("StatusBadge")
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        # Voice Mic Toggle Button
        self.mic_btn = QPushButton("🎙️ MIC: ON")
        self.mic_btn.setStyleSheet(f"background-color: {COLOR_BG_CARD}; color: {COLOR_EMERALD}; font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(0,255,163,0.3);")
        self.mic_btn.clicked.connect(self._toggle_voice_mute)
        header_layout.addWidget(self.mic_btn)

        # Speech Output (TTS) Toggle
        self.tts_btn = QPushButton("🔊 AUDIO: ON")
        self.tts_btn.setStyleSheet(f"background-color: {COLOR_BG_CARD}; color: {COLOR_ACCENT}; font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(0,240,255,0.3);")
        self.tts_btn.clicked.connect(self._toggle_tts_audio)
        header_layout.addWidget(self.tts_btn)

        # Settings Button
        settings_btn = QPushButton("⚙️")
        settings_btn.setObjectName("IconButton")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setToolTip("Quantum Settings & AI Lab")
        settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(settings_btn)

        # Minimize Button
        min_btn = QPushButton("—")
        min_btn.setObjectName("IconButton")
        min_btn.setFixedSize(28, 28)
        min_btn.clicked.connect(self.showMinimized)
        header_layout.addWidget(min_btn)

        # Stealth Close to Tray
        close_btn = QPushButton("✕")
        close_btn.setObjectName("IconButton")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._handle_close)
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # -------------------------------------------------------------
        # 2. Live Hardware Telemetry HUD Bar
        # -------------------------------------------------------------
        self.telemetry_hud = CyberTelemetryHUD(self)
        main_layout.addWidget(self.telemetry_hud)

        # -------------------------------------------------------------
        # 3. Futuristic Multi-Deck Tab Navigation
        # -------------------------------------------------------------
        self.tabs = QTabWidget(self)

        # Tab 1: NEURAL HUD (Main Stream & Core)
        self.neural_tab = QWidget()
        neural_layout = QVBoxLayout(self.neural_tab)
        neural_layout.setContentsMargins(4, 6, 4, 4)
        neural_layout.setSpacing(8)

        # Holographic Arc Reactor Visualizer
        self.visualizer = QuantumCoreVisualizer(self)
        self.visualizer.clicked.connect(self._trigger_speak)
        neural_layout.addWidget(self.visualizer)

        # Chat Message Stream (Scroll Area)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        self.chat_layout = QVBoxLayout(self.scroll_content)
        self.chat_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        neural_layout.addWidget(self.scroll_area, stretch=1)

        # Quick Action Protocol Chips
        self.quick_chips = QuickActionGrid(self)
        self.quick_chips.chip_clicked.connect(self._send_command_text)
        neural_layout.addWidget(self.quick_chips)

        # Input Transmit Bar
        input_frame = QFrame(self)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 2, 0, 0)
        input_layout.setSpacing(8)

        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Command JARVIS... (Type, click 🎙️ SPEAK, or say 'Jarvis')")
        self.input_edit.returnPressed.connect(self._on_enter_pressed)
        input_layout.addWidget(self.input_edit, stretch=1)

        self.speak_btn = QPushButton("🎙️ SPEAK")
        self.speak_btn.setObjectName("MicButton")
        self.speak_btn.setCursor(Qt.PointingHandCursor)
        self.speak_btn.clicked.connect(self._trigger_speak)
        input_layout.addWidget(self.speak_btn)

        self.send_btn = QPushButton("➤ TRANSMIT")
        self.send_btn.setObjectName("PrimaryTransmit")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_enter_pressed)
        input_layout.addWidget(self.send_btn)

        neural_layout.addWidget(input_frame)
        self.tabs.addTab(self.neural_tab, "⚡ NEURAL HUD")

        # Tab 2: PROTOCOL MATRIX
        self.protocol_tab = ProtocolMatrixWidget(self)
        self.protocol_tab.command_triggered.connect(self._send_command_text)
        self.tabs.addTab(self.protocol_tab, "🛠️ PROTOCOL MATRIX")

        # Tab 3: SYNAPSE MEMORY
        self.synapse_tab = SynapseMatrixWidget(self.engine, self.async_loop, self)
        self.tabs.addTab(self.synapse_tab, "🧠 SYNAPSE MATRIX")

        main_layout.addWidget(self.tabs, stretch=1)

        # Welcome message
        self.add_message(
            "assistant",
            "Greetings Commander. JARVIS Quantum Neural Core V3.6 is active and synchronized. "
            "All sub-systems, speech recognition, and computer automation protocols are nominal. "
            "How may I serve you today?",
        )

    def _connect_events(self) -> None:
        self.status_updated.connect(self._on_status_updated)
        self.message_received.connect(self._on_message_received)

        # Subscribe to EventBus Status
        async def on_bus_status(topic: str, payload: dict):
            state = payload.get("state", "idle")
            detail = payload.get("detail", "")
            self.status_updated.emit(state, detail)

        self.bus.subscribe(Topics.STATUS, on_bus_status)

        # Voice listener callbacks
        if self.voice_listener:
            self.voice_listener.on_wake_callback = lambda: self.status_updated.emit("listening", "Wake word detected")
            self.voice_listener.on_transcript_callback = lambda txt: self._dispatch_transcript(txt)

    def _dispatch_transcript(self, text: str) -> None:
        self.message_received.emit("user", text, None)
        self._execute_turn_async(text)

    def _on_status_updated(self, state: str, detail: str) -> None:
        self.visualizer.set_state(state)
        self.status_badge.setText(state.upper())
        if state == "listening":
            self.status_badge.setStyleSheet(f"color: {COLOR_EMERALD}; background-color: rgba(0, 255, 163, 0.15); border: 1px solid {COLOR_EMERALD}; border-radius: 12px; padding: 3px 12px;")
        elif state in ("thinking", "working"):
            self.status_badge.setStyleSheet(f"color: {COLOR_AMBER}; background-color: rgba(255, 183, 0, 0.15); border: 1px solid {COLOR_AMBER}; border-radius: 12px; padding: 3px 12px;")
        elif state == "speaking":
            self.status_badge.setStyleSheet(f"color: {COLOR_ACCENT}; background-color: rgba(0, 240, 255, 0.15); border: 1px solid {COLOR_ACCENT}; border-radius: 12px; padding: 3px 12px;")
        elif state == "alert":
            self.status_badge.setStyleSheet(f"color: {COLOR_CRIMSON}; background-color: rgba(255, 42, 85, 0.15); border: 1px solid {COLOR_CRIMSON}; border-radius: 12px; padding: 3px 12px;")
        else:
            self.status_badge.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; background-color: {COLOR_ACCENT_DIM}; border: 1px solid {COLOR_BORDER}; border-radius: 12px; padding: 3px 12px;")

    def _on_message_received(self, role: str, text: str, actions: Optional[list]) -> None:
        self.add_message(role, text, actions)

    def add_message(self, role: str, text: str, actions: Optional[list] = None) -> None:
        bubble = CyberChatBubble(role, text, actions, self.scroll_content)
        count = self.chat_layout.count()
        self.chat_layout.insertWidget(max(0, count - 1), bubble)
        QTimer.singleShot(60, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def _on_enter_pressed(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self._send_command_text(text)

    def _send_command_text(self, text: str) -> None:
        # Switch to main NEURAL HUD tab if not on it
        self.tabs.setCurrentIndex(0)
        self.add_message("user", text)
        self.status_updated.emit("thinking", "Computing response...")
        self._execute_turn_async(text)

    def _execute_turn_async(self, text: str) -> None:
        """Thread-safe non-blocking execution scheduled directly on runtime loop."""
        async def _run():
            try:
                result = await self.engine.turn(text)
                # Dispatch result back to Qt GUI thread safely
                QTimer.singleShot(0, lambda: self._handle_turn_result(result))
            except Exception as exc:
                err_msg = str(exc)
                QTimer.singleShot(0, lambda: self._handle_turn_error(err_msg))

        asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

    def _handle_turn_result(self, result: TurnResult) -> None:
        reply_text = result.text if hasattr(result, "text") else str(result)
        actions = result.actions if hasattr(result, "actions") else None
        self.add_message("assistant", reply_text, actions)
        self.status_updated.emit("idle", "Ready")

        # Vocalize response if speech is enabled
        if self._speak_responses and self.voice_listener and self.voice_listener.synthesizer:
            synthesizer = self.voice_listener.synthesizer
            asyncio.run_coroutine_threadsafe(synthesizer.speak(reply_text), self.async_loop)

    def _handle_turn_error(self, err: str) -> None:
        self.add_message("assistant", f"I encountered a problem processing that command: {err}")
        self.status_updated.emit("idle", "Ready")

    def _trigger_speak(self) -> None:
        if self.voice_listener:
            self.status_updated.emit("listening", "Listening...")
            self.voice_listener.trigger_manual_listen()

    def _toggle_voice_mute(self) -> None:
        if self.voice_listener:
            is_muted = not self.voice_listener.is_muted
            self.voice_listener.set_muted(is_muted)
            if is_muted:
                self.mic_btn.setText("🔇 MIC: OFF")
                self.mic_btn.setStyleSheet(f"background-color: {COLOR_BG_CARD}; color: {COLOR_CRIMSON}; font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(255,42,85,0.3);")
            else:
                self.mic_btn.setText("🎙️ MIC: ON")
                self.mic_btn.setStyleSheet(f"background-color: {COLOR_BG_CARD}; color: {COLOR_EMERALD}; font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(0,255,163,0.3);")

    def _toggle_tts_audio(self) -> None:
        self._speak_responses = not self._speak_responses
        if self._speak_responses:
            self.tts_btn.setText("🔊 AUDIO: ON")
            self.tts_btn.setStyleSheet(f"background-color: {COLOR_BG_CARD}; color: {COLOR_ACCENT}; font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(0,240,255,0.3);")
        else:
            self.tts_btn.setText("🔈 AUDIO: OFF")
            self.tts_btn.setStyleSheet(f"background-color: {COLOR_BG_CARD}; color: {COLOR_TEXT_MUTED}; font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid {COLOR_BORDER};")

    def _open_settings(self) -> None:
        synth = self.voice_listener.synthesizer if self.voice_listener else None
        dlg = SettingsDialog(self.settings, synth, self.async_loop, self)
        dlg.exec()

    def _handle_close(self) -> None:
        if self.on_close_to_tray_callback:
            self.on_close_to_tray_callback()
        else:
            self.hide()
