"""God-Level Sci-Fi Cybernetic UI Components for JARVIS HUD.

Includes:
- QuantumCoreVisualizer: Futuristic multi-tier Arc Reactor & Quantum Neural Core.
- CyberTelemetryHUD: Real-time telemetry bar (Quantum CPU, Synapse RAM, Battery, Link).
- CyberChatBubble: Holographic message cards with code copy & tool status indicators.
- QuickActionGrid: One-tap futuristic command chips.
"""
from __future__ import annotations

import math
import random
import time
from typing import Callable, Optional

import psutil
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_DIM,
    COLOR_ACCENT_GLOW,
    COLOR_ACCENT_MUTED,
    COLOR_AMBER,
    COLOR_BG_CARD,
    COLOR_BG_CARD_HOVER,
    COLOR_BG_SURFACE,
    COLOR_BG_VOID,
    COLOR_BORDER,
    COLOR_CRIMSON,
    COLOR_EMERALD,
    COLOR_PLASMA_BLUE,
    COLOR_PURPLE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class QuantumCoreVisualizer(QWidget):
    """Futuristic Arc Reactor & Quantum Neural Singularity Core Visualizer.

    Features:
    - Outer Segmented Telemetry Gyro Ring with angle ticks.
    - Intermediate Counter-Rotating Dashed Orbit Ring with orbital nodes.
    - Inner Sacred Geometry Polygon Lattice (Rotating Hex/Octagram).
    - Radiating 360-degree Acoustic Waveform Equalizer (Voice-Reactive).
    - Multi-layer Plasma Glow Core with subatomic energy sparks.
    - 5 Animated Cognitive States:
        * IDLE: Ambient hypnotic slow gyro pulse & plasma breath.
        * LISTENING: Expanding sonar radar rings + active acoustic frequency spikes.
        * THINKING: High-velocity dual-vortex acceleration & quantum bursts.
        * SPEAKING: Voice-reactive multi-band radiating equalizer bars.
        * ALERT: Red plasma flare with emergency strobe.
    - Interactive: Click to trigger voice capture with an expanding shockwave pulse!
    """
    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.setMaximumHeight(220)
        self.setCursor(Qt.PointingHandCursor)

        self._state = "idle"  # idle, listening, thinking, speaking, alert
        self._phase = 0.0
        self._gyro_angle1 = 0.0
        self._gyro_angle2 = 0.0
        self._pulse_scale = 1.0
        self._is_hovered = False
        self._shockwave_radius = 0.0
        self._shockwave_alpha = 0

        # Sub-atomic particle sparks
        self._particles = [
            {
                "angle": random.uniform(0, 2 * math.pi),
                "dist": random.uniform(0.3, 0.9),
                "speed": random.uniform(0.02, 0.06),
                "size": random.uniform(1.5, 3.5),
            }
            for _ in range(16)
        ]

        # 60 FPS smooth rendering loop
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(16)  # ~60 FPS

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.update()

    def _on_tick(self) -> None:
        speed = 0.05
        if self._state == "thinking":
            speed = 0.14
        elif self._state == "speaking":
            speed = 0.08
        elif self._state == "listening":
            speed = 0.07

        self._phase = (self._phase + speed) % (2 * math.pi)
        self._gyro_angle1 = (self._gyro_angle1 + speed * 15.0) % 360.0
        self._gyro_angle2 = (self._gyro_angle2 - speed * 22.0) % 360.0

        # Update sub-atomic particle positions
        for p in self._particles:
            p["angle"] = (p["angle"] + p["speed"] * (2.5 if self._state == "thinking" else 1.0)) % (2 * math.pi)

        # Decay shockwave
        if self._shockwave_alpha > 0:
            self._shockwave_radius += 4.5
            self._shockwave_alpha = max(0, self._shockwave_alpha - 8)

        self.update()

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._shockwave_radius = 20.0
            self._shockwave_alpha = 240
            self.clicked.emit()
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        max_r = min(w, h) * 0.44

        # Primary state colors
        if self._state == "listening":
            primary_color = QColor(COLOR_EMERALD)
            glow_color = QColor(0, 255, 163, 160)
            core_color = QColor(180, 255, 230)
        elif self._state == "thinking":
            primary_color = QColor(COLOR_AMBER)
            glow_color = QColor(255, 183, 0, 180)
            core_color = QColor(255, 240, 200)
        elif self._state == "speaking":
            primary_color = QColor(COLOR_ACCENT)
            glow_color = QColor(0, 240, 255, 200)
            core_color = QColor(200, 250, 255)
        elif self._state == "alert":
            primary_color = QColor(COLOR_CRIMSON)
            glow_color = QColor(255, 42, 85, 200)
            core_color = QColor(255, 200, 210)
        else:
            # Idle cyan / quantum blue
            primary_color = QColor(COLOR_ACCENT)
            glow_color = QColor(0, 240, 255, 120)
            core_color = QColor(220, 250, 255)

        pulse = 1.0 + 0.06 * math.sin(self._phase * 2)

        # -------------------------------------------------------------
        # 1. Outer Background Holographic Grid / Radar Scan
        # -------------------------------------------------------------
        painter.setBrush(Qt.NoBrush)
        pen_grid = QPen(QColor(0, 240, 255, 25 if not self._is_hovered else 45), 1)
        pen_grid.setStyle(Qt.DotLine)
        painter.setPen(pen_grid)
        painter.drawEllipse(QPointF(cx, cy), max_r * 1.05, max_r * 1.05)

        # -------------------------------------------------------------
        # 2. Outer Segmented Calibration Gyro Ring (Clockwise)
        # -------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._gyro_angle1)

        # Draw 4 segmented arcs with gaps
        pen_arc = QPen(QColor(primary_color.red(), primary_color.green(), primary_color.blue(), 180), 2.5)
        painter.setPen(pen_arc)
        r_outer = max_r * 0.92
        rect_outer = QRectF(-r_outer, -r_outer, r_outer * 2, r_outer * 2)

        for seg in range(4):
            start_deg = seg * 90 + 12
            span_deg = 66
            painter.drawArc(rect_outer, int(start_deg * 16), int(span_deg * 16))

        # Calibration tick marks around perimeter
        pen_tick = QPen(QColor(0, 240, 255, 90), 1.5)
        painter.setPen(pen_tick)
        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            x1 = math.cos(rad) * (r_outer - 5)
            y1 = math.sin(rad) * (r_outer - 5)
            x2 = math.cos(rad) * (r_outer + 4)
            y2 = math.sin(rad) * (r_outer + 4)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        painter.restore()

        # -------------------------------------------------------------
        # 3. Intermediate Counter-Rotating Ring with Data Nodes
        # -------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._gyro_angle2)

        r_mid = max_r * 0.76
        pen_dash = QPen(QColor(0, 136, 255, 140), 1.8)
        pen_dash.setStyle(Qt.DashLine)
        painter.setPen(pen_dash)
        painter.drawEllipse(QPointF(0, 0), r_mid, r_mid)

        # Orbital data nodes
        painter.setBrush(QBrush(primary_color))
        painter.setPen(Qt.NoPen)
        for i in range(3):
            angle_rad = i * (2 * math.pi / 3)
            nx = math.cos(angle_rad) * r_mid
            ny = math.sin(angle_rad) * r_mid
            painter.drawEllipse(QPointF(nx, ny), 3.5, 3.5)

        painter.restore()

        # -------------------------------------------------------------
        # 4. Radiating Acoustic Waveform / Equalizer (Voice & Cognitive)
        # -------------------------------------------------------------
        if self._state in ("speaking", "listening", "thinking"):
            num_bars = 24
            r_inner_eq = max_r * 0.48
            for b in range(num_bars):
                bar_angle = (b * (2 * math.pi / num_bars)) + self._phase * 0.5
                if self._state == "speaking":
                    bar_len = (math.sin(self._phase * 5 + b * 1.2) * 0.5 + 0.5) * (max_r * 0.28) + 4
                elif self._state == "listening":
                    bar_len = (math.sin(self._phase * 3 + b * 0.8) * 0.5 + 0.5) * (max_r * 0.20) + 3
                else:
                    bar_len = (math.cos(self._phase * 6 + b * 2.0) * 0.5 + 0.5) * (max_r * 0.22) + 2

                bx1 = cx + math.cos(bar_angle) * r_inner_eq
                by1 = cy + math.sin(bar_angle) * r_inner_eq
                bx2 = cx + math.cos(bar_angle) * (r_inner_eq + bar_len)
                by2 = cy + math.sin(bar_angle) * (r_inner_eq + bar_len)

                pen_bar = QPen(QColor(primary_color.red(), primary_color.green(), primary_color.blue(), 190), 2.0)
                pen_bar.setCapStyle(Qt.RoundCap)
                painter.setPen(pen_bar)
                painter.drawLine(QPointF(bx1, by1), QPointF(bx2, by2))

        # -------------------------------------------------------------
        # 5. Expanding Radar Ripples (When Listening)
        # -------------------------------------------------------------
        if self._state == "listening":
            for i in range(3):
                ripple_p = (self._phase + i * (math.pi * 2 / 3)) % (2 * math.pi)
                r_rip = (max_r * 0.4) + (ripple_p / (2 * math.pi)) * (max_r * 0.65)
                alpha = int(max(0, 180 * (1.0 - ripple_p / (2 * math.pi))))
                pen_rip = QPen(QColor(0, 255, 163, alpha), 1.8)
                painter.setPen(pen_rip)
                painter.drawEllipse(QPointF(cx, cy), r_rip, r_rip)

        # -------------------------------------------------------------
        # 6. Click Shockwave Wavefront
        # -------------------------------------------------------------
        if self._shockwave_alpha > 0:
            pen_shock = QPen(QColor(0, 240, 255, self._shockwave_alpha), 3.0)
            painter.setPen(pen_shock)
            painter.drawEllipse(QPointF(cx, cy), self._shockwave_radius, self._shockwave_radius)

        # -------------------------------------------------------------
        # 7. Sub-atomic Quantum Particle Sparks
        # -------------------------------------------------------------
        painter.setPen(Qt.NoPen)
        for p in self._particles:
            px = cx + math.cos(p["angle"]) * (max_r * p["dist"])
            py = cy + math.sin(p["angle"]) * (max_r * p["dist"])
            p_grad = QRadialGradient(px, py, p["size"] * 2)
            p_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
            p_grad.setColorAt(0.6, primary_color)
            p_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(p_grad))
            painter.drawEllipse(QPointF(px, py), p["size"] * 1.5, p["size"] * 1.5)

        # -------------------------------------------------------------
        # 8. Inner Rotating Hexagonal Sacred Geometry Lattice
        # -------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._gyro_angle1 * 0.7)
        r_hex = max_r * 0.42 * pulse

        hex_path = QPainterPath()
        for i in range(6):
            h_ang = i * (math.pi / 3)
            hx = math.cos(h_ang) * r_hex
            hy = math.sin(h_ang) * r_hex
            if i == 0:
                hex_path.moveTo(hx, hy)
            else:
                hex_path.lineTo(hx, hy)
        hex_path.closeSubpath()

        painter.setPen(QPen(QColor(0, 240, 255, 90), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(hex_path)
        painter.restore()

        # -------------------------------------------------------------
        # 9. Main Central Glowing Plasma Core
        # -------------------------------------------------------------
        core_r = max_r * 0.32 * pulse
        plasma = QRadialGradient(cx, cy, core_r * 1.6)
        plasma.setColorAt(0.0, core_color)
        plasma.setColorAt(0.35, primary_color)
        plasma.setColorAt(0.7, glow_color)
        plasma.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(plasma))
        painter.drawEllipse(QPointF(cx, cy), core_r * 1.6, core_r * 1.6)

        # White-hot singularity center
        center_r = core_r * 0.4
        center_grad = QRadialGradient(cx, cy, center_r)
        center_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        center_grad.setColorAt(0.7, QColor(200, 245, 255, 230))
        center_grad.setColorAt(1.0, primary_color)

        painter.setBrush(QBrush(center_grad))
        painter.drawEllipse(QPointF(cx, cy), center_r, center_r)

        # -------------------------------------------------------------
        # 10. Hover HUD Reticle & State Text
        # -------------------------------------------------------------
        if self._is_hovered:
            painter.setPen(QPen(QColor(0, 240, 255, 160), 1))
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.drawText(
                QRectF(cx - 60, cy + max_r * 0.82, 120, 20),
                Qt.AlignCenter,
                "▶ TAP TO SPEAK ◀",
            )


class CyberTelemetryHUD(QFrame):
    """Futuristic Hardware & Neural Link Telemetry HUD.

    Displays:
    - ⚡ QUANTUM CPU Load (%)
    - 🧠 SYNAPSE MEMORY / RAM (%)
    - 🔋 ZERO-POINT POWER / Battery (%)
    - 🌐 UPLINK: GEMINI-3.6-FLASH // READY
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("TelemetryHUD")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(14)

        # CPU
        self.cpu_lbl = QLabel("⚡ CPU: --%")
        self.cpu_lbl.setProperty("class", "TelemetryLabel")
        layout.addWidget(self.cpu_lbl)

        # RAM
        self.ram_lbl = QLabel("🧠 RAM: --%")
        self.ram_lbl.setProperty("class", "TelemetryLabel")
        layout.addWidget(self.ram_lbl)

        # Battery
        self.bat_lbl = QLabel("🔋 BAT: --%")
        self.bat_lbl.setProperty("class", "TelemetryLabel")
        layout.addWidget(self.bat_lbl)

        layout.addStretch()

        # Neural Link Status
        self.link_lbl = QLabel("● GEMINI-3.6 // ONLINE")
        self.link_lbl.setStyleSheet(f"color: {COLOR_EMERALD}; font-size: 10px; font-weight: 700; font-family: 'Consolas', monospace;")
        layout.addWidget(self.link_lbl)

        # Compatibility attributes
        self.cpu_label = self.cpu_lbl
        self.ram_label = self.ram_lbl
        self.battery_label = self.bat_lbl

        # Update telemetry every 2 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_telemetry)
        self._timer.start(2000)
        self.update_telemetry()

    def update_telemetry(self) -> None:
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            self.cpu_lbl.setText(f"⚡ CPU: {int(cpu)}%")
            self.ram_lbl.setText(f"🧠 RAM: {int(ram)}%")

            battery = psutil.sensors_battery()
            if battery:
                plug = " ⚡" if battery.power_plugged else ""
                self.bat_lbl.setText(f"🔋 BAT: {int(battery.percent)}%{plug}")
                self.bat_lbl.setVisible(True)
            else:
                self.bat_lbl.setVisible(False)
        except Exception:
            pass

    def update_stats(self) -> None:
        self.update_telemetry()



class CyberChatBubble(QFrame):
    """Holographic Sci-Fi Chat Card for Commander (User) & JARVIS (Neural AI)."""

    def __init__(
        self,
        role: str,
        text: str,
        actions: Optional[list] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.role = role
        self.raw_text = text
        self.actions = actions or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # 1. Header Bar with Holographic Badge & Timestamp
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        is_jarvis = role == "assistant"
        role_title = "JARVIS // NEURAL AI" if is_jarvis else "COMMANDER // USER"
        role_color = COLOR_ACCENT if is_jarvis else COLOR_PLASMA_BLUE
        badge_bg = "rgba(0, 240, 255, 0.12)" if is_jarvis else "rgba(0, 136, 255, 0.12)"

        badge = QLabel(f"  {role_title}  ")
        badge.setStyleSheet(f"""
            color: {role_color};
            background-color: {badge_bg};
            border: 1px solid {role_color};
            border-radius: 4px;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 1.5px;
            font-family: 'Consolas', monospace;
            padding: 2px 4px;
        """)
        header.addWidget(badge)

        timestamp_str = time.strftime("%H:%M:%S")
        time_lbl = QLabel(timestamp_str)
        time_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 10px; font-family: 'Consolas', monospace;")
        header.addStretch()
        header.addWidget(time_lbl)
        layout.addLayout(header)

        # 2. Main Content
        self._format_content(text, layout)

        # 3. Executed Actions / Tools
        if self.actions:
            for action in self.actions:
                tool_name = str(action.get("tool", "protocol")).upper()
                ok = action.get("ok", True)
                msg = action.get("message", "")
                status_icon = "✓" if ok else "✗"
                status_color = COLOR_EMERALD if ok else COLOR_CRIMSON

                tool_frame = QFrame(self)
                tool_layout = QHBoxLayout(tool_frame)
                tool_layout.setContentsMargins(8, 4, 8, 4)
                tool_frame.setStyleSheet("background-color: rgba(0, 0, 0, 0.35); border-radius: 4px; border-left: 2px solid " + status_color + ";")

                tool_lbl = QLabel(f"[{status_icon}] {tool_name}: {msg}")
                tool_lbl.setStyleSheet(f"color: {status_color}; font-size: 11px; font-family: 'Consolas', monospace;")
                tool_lbl.setWordWrap(True)
                tool_layout.addWidget(tool_lbl)
                layout.addWidget(tool_frame)

        # Styling
        if is_jarvis:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(10, 18, 36, 0.90);
                    border: 1px solid rgba(0, 240, 255, 0.35);
                    border-left: 3px solid {COLOR_ACCENT};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(14, 24, 46, 0.75);
                    border: 1px solid rgba(0, 136, 255, 0.25);
                    border-right: 3px solid {COLOR_PLASMA_BLUE};
                    border-radius: 10px;
                }}
            """)

    def _format_content(self, text: str, layout: QVBoxLayout) -> None:
        # Check if message contains code blocks (```)
        if "```" in text:
            parts = text.split("```")
            for idx, part in enumerate(parts):
                if idx % 2 == 1:  # Code snippet
                    code_lines = part.strip().split("\n")
                    first_line = code_lines[0].strip() if code_lines else ""
                    code_body = "\n".join(code_lines[1:]) if len(code_lines) > 1 else part.strip()

                    code_box = QFrame(self)
                    code_box.setStyleSheet("background-color: #03060d; border: 1px solid rgba(0, 240, 255, 0.2); border-radius: 6px;")
                    code_layout = QVBoxLayout(code_box)
                    code_layout.setContentsMargins(8, 6, 8, 6)

                    top_bar = QHBoxLayout()
                    lang_tag = QLabel(first_line.upper() or "CODE")
                    lang_tag.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 9px; font-weight: bold; font-family: 'Consolas', monospace;")
                    top_bar.addWidget(lang_tag)
                    top_bar.addStretch()

                    copy_btn = QPushButton("📋 COPY")
                    copy_btn.setStyleSheet(f"background: transparent; color: {COLOR_TEXT_SECONDARY}; font-size: 9px; border: none; padding: 2px 6px;")
                    copy_btn.clicked.connect(lambda _, c=code_body: QApplication.clipboard().setText(c))
                    top_bar.addWidget(copy_btn)
                    code_layout.addLayout(top_bar)

                    code_txt = QLabel(code_body)
                    code_txt.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    code_txt.setStyleSheet("color: #00f0ff; font-size: 12px; font-family: 'Consolas', monospace; line-height: 1.3;")
                    code_layout.addWidget(code_txt)
                    layout.addWidget(code_box)
                else:
                    if part.strip():
                        lbl = QLabel(part.strip())
                        lbl.setWordWrap(True)
                        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                        lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; line-height: 1.4;")
                        layout.addWidget(lbl)
        else:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; line-height: 1.4;")
            layout.addWidget(lbl)


class QuickActionGrid(QWidget):
    """Futuristic Quick Command Chips Grid."""
    chip_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        chips = [
            ("⚡ System Diagnostic", "system status detail"),
            ("📸 Analyze Screen", "analyze screen"),
            ("🎵 Play Music", "youtube pe song play karo"),
            ("💻 Open VS Code", "open vs code"),
            ("🌐 Web Search", "search google"),
            ("🔒 Protocol Zero", "emergency lockdown"),
        ]

        for label, cmd in chips:
            btn = QPushButton(label)
            btn.setProperty("class", "ActionChip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, c=cmd: self.chip_clicked.emit(c))
            layout.addWidget(btn)

        layout.addStretch()


# Compatibility aliases for legacy imports / tests
VoiceVisualizer = QuantumCoreVisualizer
SystemStatsBar = CyberTelemetryHUD
ChatBubble = CyberChatBubble
