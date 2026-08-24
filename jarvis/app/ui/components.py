"""Reusable UI components for JARVIS Desktop App.

Includes:
- VoiceVisualizer: Animated glowing orb & dynamic waveform renderer.
- SystemStatsBar: Real-time CPU, RAM, Battery telemetry.
- ChatMessageWidget: Rich chat bubbles with markdown & tool action tags.
"""
from __future__ import annotations

import math
from typing import Optional

import psutil
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QTextEdit, QVBoxLayout, QWidget

from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_MUTED,
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
)


class VoiceVisualizer(QWidget):
    """Animated glowing orb visualizer that reflects JARVIS's cognitive and voice states:
    - IDLE: Gentle breathing pulse.
    - LISTENING: Expanding ripple waves (active audio capture).
    - THINKING: Spinning dual-ring orbit.
    - SPEAKING: Dynamic acoustic wave bars.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self.setMaximumHeight(140)

        self._state = "idle"  # idle, listening, thinking, speaking
        self._phase = 0.0

        # Animation timer ~40 FPS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(25)

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.update()

    def _on_tick(self) -> None:
        self._phase = (self._phase + 0.05) % (2 * math.pi)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        base_radius = min(w, h) * 0.28

        # 1. Background Glow / Ripple
        pulse = math.sin(self._phase * 2) * 0.15 + 1.0

        if self._state == "listening":
            # Expanding acoustic ripples
            for i in range(3):
                ripple_phase = (self._phase + i * (math.pi / 1.5)) % (2 * math.pi)
                ripple_r = base_radius * (1.2 + (ripple_phase / (2 * math.pi)) * 0.8)
                alpha = int(max(0, 160 * (1.0 - ripple_phase / (2 * math.pi))))
                pen = QPen(QColor(0, 240, 255, alpha), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), ripple_r, ripple_r)

        elif self._state == "thinking":
            # Dual rotating orbit rings
            painter.setBrush(Qt.NoBrush)
            pen1 = QPen(QColor(0, 240, 255, 180), 2.5)
            painter.setPen(pen1)
            rect1 = QRectF(cx - base_radius * 1.3, cy - base_radius * 1.3, base_radius * 2.6, base_radius * 2.6)
            angle1 = int((self._phase * 180 / math.pi) * 16)
            painter.drawArc(rect1, angle1, 120 * 16)

            pen2 = QPen(QColor(0, 160, 255, 140), 2)
            painter.setPen(pen2)
            rect2 = QRectF(cx - base_radius * 1.5, cy - base_radius * 1.5, base_radius * 3.0, base_radius * 3.0)
            angle2 = int((-self._phase * 140 / math.pi) * 16)
            painter.drawArc(rect2, angle2, 100 * 16)

        elif self._state == "speaking":
            # Pulsing voice waves
            painter.setBrush(Qt.NoBrush)
            for bar in range(-6, 7):
                bx = cx + bar * 7
                dist = abs(bar)
                bar_h = math.sin(self._phase * 4 + bar * 0.5) * (base_radius * 0.5) + (base_radius * 0.4) - dist * 2
                bar_h = max(4, bar_h)
                pen = QPen(QColor(0, 240, 255, 200 - dist * 15), 3)
                painter.setPen(pen)
                painter.drawLine(QPointF(bx, cy - bar_h / 2), QPointF(bx, cy + bar_h / 2))

        # 2. Main Central Glowing Orb
        glow = QRadialGradient(cx, cy, base_radius * pulse)
        if self._state == "listening":
            glow.setColorAt(0.0, QColor(0, 255, 220, 240))
            glow.setColorAt(0.5, QColor(0, 200, 255, 160))
            glow.setColorAt(1.0, QColor(0, 240, 255, 0))
        elif self._state == "thinking":
            glow.setColorAt(0.0, QColor(0, 180, 255, 240))
            glow.setColorAt(0.5, QColor(0, 100, 255, 150))
            glow.setColorAt(1.0, QColor(0, 100, 255, 0))
        elif self._state == "speaking":
            glow.setColorAt(0.0, QColor(50, 255, 200, 250))
            glow.setColorAt(0.5, QColor(0, 220, 255, 180))
            glow.setColorAt(1.0, QColor(0, 240, 255, 0))
        else:
            # Idle gentle breath
            glow.setColorAt(0.0, QColor(0, 240, 255, 200))
            glow.setColorAt(0.4, QColor(0, 160, 220, 100))
            glow.setColorAt(1.0, QColor(0, 100, 180, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), base_radius * pulse, base_radius * pulse)

        # 3. Inner Core Dot
        core_r = base_radius * 0.35
        core = QRadialGradient(cx, cy, core_r)
        core.setColorAt(0.0, QColor(255, 255, 255, 255))
        core.setColorAt(0.7, QColor(200, 250, 255, 220))
        core.setColorAt(1.0, QColor(0, 240, 255, 120))
        painter.setBrush(QBrush(core))
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)


class SystemStatsBar(QFrame):
    """Telemetry bar showing real-time CPU, RAM, and Battery percentages."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatsBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(18)

        self.cpu_label = QLabel("⚡ CPU: --%")
        self.ram_label = QLabel("🧠 RAM: --%")
        self.battery_label = QLabel("🔋 BAT: --%")

        for lbl in (self.cpu_label, self.ram_label, self.battery_label):
            lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 500;")
            layout.addWidget(lbl)

        layout.addStretch()

        # Update telemetry every 2.5s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_stats)
        self._timer.start(2500)
        self.update_stats()

    def update_stats(self) -> None:
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.cpu_label.setText(f"⚡ CPU: {int(cpu)}%")
            self.ram_label.setText(f"🧠 RAM: {int(ram)}%")

            battery = psutil.sensors_battery()
            if battery:
                plugged = " 🔌" if battery.power_plugged else ""
                self.battery_label.setText(f"🔋 BAT: {int(battery.percent)}%{plugged}")
                self.battery_label.setVisible(True)
            else:
                self.battery_label.setVisible(False)
        except Exception:
            pass


class ChatBubble(QFrame):
    """A styled chat bubble for User, JARVIS, or Tool notifications."""

    def __init__(self, role: str, text: str, actions: Optional[list] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatBubble")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        sender_title = "YOU" if role == "user" else "JARVIS"
        title_color = COLOR_ACCENT if role == "assistant" else COLOR_TEXT_SECONDARY

        title_lbl = QLabel(sender_title)
        title_lbl.setStyleSheet(f"color: {title_color}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        content_lbl = QLabel(text)
        content_lbl.setWordWrap(True)
        content_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; line-height: 1.4;")
        layout.addWidget(content_lbl)

        # Show executed tools if any
        if actions:
            for action in actions:
                tool_name = action.get("tool", "tool")
                ok = action.get("ok", True)
                status_icon = "✓" if ok else "✗"
                tool_lbl = QLabel(f"[{status_icon}] {tool_name}: {action.get('message', '')}")
                tool_color = COLOR_SUCCESS if ok else COLOR_DANGER
                tool_lbl.setStyleSheet(f"color: {tool_color}; font-size: 11px; padding: 2px 6px; background-color: rgba(255,255,255,0.04); border-radius: 4px;")
                layout.addWidget(tool_lbl)

        bg_color = "rgba(0, 240, 255, 0.06)" if role == "assistant" else COLOR_SURFACE
        border_color = "rgba(0, 240, 255, 0.25)" if role == "assistant" else COLOR_BORDER

        self.setStyleSheet(f"""
        QFrame#ChatBubble {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 10px;
        }}
        """)
