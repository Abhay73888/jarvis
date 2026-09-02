"""Main PySide6 Desktop HUD Window for JARVIS.

Integrates:
- Modern dark glass visual interface.
- Live animated Voice Visualizer & Status Badge.
- Real-time conversation stream & tool execution updates.
- Text and Voice input controls.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.brain.engine import AgentEngine
from app.core.events import EventBus, Topics
from app.ui.components import ChatBubble, SystemStatsBar, VoiceVisualizer
from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_MUTED,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_SURFACE,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    STYLESHEET,
)


class AsyncWorker(QThread):
    """Executes asynchronous coroutines on a background thread for the GUI."""
    result_signal = Signal(object)
    error_signal = Signal(str)

    def __init__(self, coro_fn, *args, **kwargs) -> None:
        super().__init__()
        self.coro_fn = coro_fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(self.coro_fn(*self.args, **self.kwargs))
            self.result_signal.emit(res)
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            loop.close()


class MainWindow(QMainWindow):
    status_updated = Signal(str, str)
    message_received = Signal(str, str, object)
    tool_event = Signal(str, str)

    def __init__(
        self,
        engine: AgentEngine,
        bus: EventBus,
        voice_listener=None,
        on_close_to_tray_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.bus = bus
        self.voice_listener = voice_listener
        self.on_close_to_tray_callback = on_close_to_tray_callback

        self.setWindowTitle("JARVIS — AI Operating Layer")
        self.setMinimumSize(480, 680)
        self.resize(520, 750)
        self.setStyleSheet(STYLESHEET)

        self._drag_pos = QPoint()
        self._setup_ui()
        self._connect_events()

    def _setup_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Header Bar
        header = QFrame(self)
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 8)

        title_lbl = QLabel("J A R V I S")
        title_lbl.setObjectName("TitleLabel")
        header_layout.addWidget(title_lbl)

        self.status_badge = QLabel("IDLE")
        self.status_badge.setObjectName("StatusBadge")
        header_layout.addWidget(self.status_badge)

        header_layout.addStretch()

        # Voice Mute Button
        self.mic_btn = QPushButton("🎙️ Mic: ON")
        self.mic_btn.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_ACCENT}; font-size: 11px; padding: 4px 8px; border-radius: 6px;")
        self.mic_btn.clicked.connect(self._toggle_voice_mute)
        header_layout.addWidget(self.mic_btn)

        # Minimize & Close
        min_btn = QPushButton("—")
        min_btn.setObjectName("IconButton")
        min_btn.setFixedSize(28, 28)
        min_btn.clicked.connect(self.showMinimized)
        header_layout.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("IconButton")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._handle_close)
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # 2. Glowing Voice Visualizer
        self.visualizer = VoiceVisualizer(self)
        main_layout.addWidget(self.visualizer)

        # 3. System Stats Bar
        self.stats_bar = SystemStatsBar(self)
        main_layout.addWidget(self.stats_bar)

        # 4. Chat Message Stream (Scroll Area)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        self.chat_layout = QVBoxLayout(self.scroll_content)
        self.chat_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 5. Input Bar
        input_frame = QFrame(self)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 4, 0, 0)
        input_layout.setSpacing(8)

        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Type a command, click 🎙️ Speak, or say 'Jarvis'...")
        self.input_edit.returnPressed.connect(self._send_text_command)
        input_layout.addWidget(self.input_edit, stretch=1)

        self.speak_btn = QPushButton("🎙️ Speak")
        self.speak_btn.setStyleSheet(f"background-color: {COLOR_CARD}; color: {COLOR_ACCENT}; border: 1px solid {COLOR_ACCENT_MUTED}; font-weight: bold; border-radius: 8px; padding: 8px 12px;")
        self.speak_btn.clicked.connect(self._trigger_speak)
        input_layout.addWidget(self.speak_btn)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.setFixedWidth(65)
        self.send_btn.clicked.connect(self._send_text_command)
        input_layout.addWidget(self.send_btn)

        main_layout.addWidget(input_frame)

        # Allow clicking visualizer orb to trigger voice listening
        self.visualizer.setCursor(Qt.PointingHandCursor)
        self.visualizer.mousePressEvent = lambda event: self._trigger_speak()

        # Welcome message
        self.add_message("assistant", "Greetings. I am JARVIS. How may I assist you today? You can type, click 🎙️ Speak, or simply say 'Jarvis'.")


    def _connect_events(self) -> None:
        self.status_updated.connect(self._on_status_updated)
        self.message_received.connect(self._on_message_received)

        # Subscribe to EventBus
        async def on_bus_status(topic: str, payload: dict):
            state = payload.get("state", "idle")
            detail = payload.get("detail", "")
            self.status_updated.emit(state, detail)

        self.bus.subscribe(Topics.STATUS, on_bus_status)


        # Voice listener callbacks
        if self.voice_listener:
            self.voice_listener.on_wake_callback = lambda: self.status_updated.emit("listening", "Wake word triggered")
            self.voice_listener.on_transcript_callback = lambda txt: self.message_received.emit("user", txt, None)

    def _on_status_updated(self, state: str, detail: str) -> None:
        self.visualizer.set_state(state)
        self.status_badge.setText(state.upper())
        if state == "listening":
            self.status_badge.setStyleSheet(f"color: {COLOR_SUCCESS}; background-color: rgba(0, 230, 118, 0.15); border: 1px solid {COLOR_SUCCESS}; border-radius: 10px; padding: 2px 10px;")
        elif state == "thinking":
            self.status_badge.setStyleSheet(f"color: {COLOR_WARNING}; background-color: rgba(255, 171, 0, 0.15); border: 1px solid {COLOR_WARNING}; border-radius: 10px; padding: 2px 10px;")
        elif state == "speaking":
            self.status_badge.setStyleSheet(f"color: {COLOR_ACCENT}; background-color: rgba(0, 240, 255, 0.15); border: 1px solid {COLOR_ACCENT}; border-radius: 10px; padding: 2px 10px;")
        else:
            self.status_badge.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; background-color: rgba(255, 255, 255, 0.05); border: 1px solid {COLOR_BORDER}; border-radius: 10px; padding: 2px 10px;")

    def _on_message_received(self, role: str, text: str, actions: list | None) -> None:
        self.add_message(role, text, actions)

    def add_message(self, role: str, text: str, actions: list | None = None) -> None:
        bubble = ChatBubble(role, text, actions, self.scroll_content)
        # Insert before stretch item at the end
        count = self.chat_layout.count()
        self.chat_layout.insertWidget(max(0, count - 1), bubble)

        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        vsb = self.scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def _send_text_command(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return

        self.input_edit.clear()
        self.add_message("user", text)
        self.status_updated.emit("thinking", "Processing...")

        # Run turn in background worker
        worker = AsyncWorker(self.engine.turn, text)
        worker.result_signal.connect(self._on_turn_completed)
        worker.error_signal.connect(self._on_turn_error)
        worker.start()
        # Keep reference so it doesn't get garbage collected
        self._current_worker = worker

    def _on_turn_completed(self, result) -> None:
        reply_text = result.text if hasattr(result, "text") else str(result)
        actions = result.actions if hasattr(result, "actions") else None
        self.add_message("assistant", reply_text, actions)
        self.status_updated.emit("idle", "Ready")

        # Speak the response aloud through VoiceSynthesizer
        if self.voice_listener and not self.voice_listener.is_muted and self.voice_listener.synthesizer:
            tts_worker = AsyncWorker(self.voice_listener.synthesizer.speak, reply_text)
            tts_worker.start()
            self._tts_worker = tts_worker


    def _on_turn_error(self, err: str) -> None:
        self.add_message("assistant", f"I encountered an error: {err}")
        self.status_updated.emit("idle", "Ready")

    def _toggle_voice_mute(self) -> None:
        if self.voice_listener:
            is_muted = not self.voice_listener.is_muted
            self.voice_listener.set_muted(is_muted)
            if is_muted:
                self.mic_btn.setText("🔇 Mic: OFF")
                self.mic_btn.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_DANGER}; font-size: 11px; padding: 4px 8px; border-radius: 6px;")
            else:
                self.mic_btn.setText("🎙️ Mic: ON")
                self.mic_btn.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_ACCENT}; font-size: 11px; padding: 4px 8px; border-radius: 6px;")

    def _trigger_speak(self) -> None:
        if self.voice_listener:
            self.voice_listener.trigger_manual_listen()

    def _handle_close(self) -> None:
        if self.on_close_to_tray_callback:
            self.on_close_to_tray_callback()
        else:
            self.hide()

