"""Protocol Matrix: Sci-Fi Command Deck & Tools Panel for JARVIS.

Provides direct interactive widgets for:
- One-touch App Launcher with [OFFLINE] badges.
- Acoustic & Media Matrix (Live volume slider, mute, play/pause).
- Offline Productivity & Tasks Deck (Tasks list, pomodoro, dictation, unit converter).
- Vision Matrix & Security Deck (Instant Screen OCR & Error Diagnostic, Protocol Zero).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_DIM,
    COLOR_AMBER,
    COLOR_BG_CARD,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_CRIMSON,
    COLOR_EMERALD,
    COLOR_PLASMA_BLUE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class ProtocolMatrixWidget(QWidget):
    """Futuristic Protocol & Tool Command Center with Offline Capabilities Badges."""
    command_triggered = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(14)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        # -------------------------------------------------------------
        # Section 1: Offline Productivity & Tasks Superpowers
        # -------------------------------------------------------------
        prod_card = QFrame()
        prod_card.setProperty("class", "ProtocolCard")
        prod_layout = QVBoxLayout(prod_card)

        prod_title = QLabel("🚀 OFFLINE SUPERPOWERS & PRODUCTIVITY")
        prod_title.setStyleSheet(f"color: {COLOR_EMERALD}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        prod_layout.addWidget(prod_title)

        prod_grid = QGridLayout()
        prod_grid.setSpacing(8)

        prod_items = [
            ("📋 [OFFLINE] Mere Tasks Batao", "mere tasks batao"),
            ("🍅 [OFFLINE] Start Pomodoro (25m)", "start pomodoro"),
            ("🎙️ [OFFLINE] Dictation Mode ON", "dictation on"),
            ("📖 [OFFLINE] Daily Brief / Review", "daily brief"),
            ("📐 [OFFLINE] Unit Converter", "convert 5 km to miles"),
            ("📝 [OFFLINE] View Local Notes", "list my notes"),
        ]

        for i, (name, cmd) in enumerate(prod_items):
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_BG_SURFACE};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                    padding: 8px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    text-align: left;
                }}
                QPushButton:hover {{
                    border-color: {COLOR_EMERALD};
                    background-color: rgba(0, 255, 159, 0.12);
                    color: {COLOR_EMERALD};
                }}
            """)
            btn.clicked.connect(lambda _, c=cmd: self.command_triggered.emit(c))
            row = i // 2
            col = i % 2
            prod_grid.addWidget(btn, row, col)

        prod_layout.addLayout(prod_grid)
        layout.addWidget(prod_card)

        # -------------------------------------------------------------
        # Section 2: Application Launch Matrix
        # -------------------------------------------------------------
        app_card = QFrame()
        app_card.setProperty("class", "ProtocolCard")
        app_layout = QVBoxLayout(app_card)

        app_title = QLabel("⚡ APPLICATION LAUNCH MATRIX [OFFLINE]")
        app_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        app_layout.addWidget(app_title)

        grid = QGridLayout()
        grid.setSpacing(8)

        apps = [
            ("💻 [OFFLINE] VS Code", "open vs code"),
            ("🌐 Google Chrome", "open chrome"),
            ("📟 [OFFLINE] Terminal", "open powershell"),
            ("📊 [OFFLINE] Task Manager", "open task manager"),
            ("📝 [OFFLINE] Notepad", "open notepad"),
            ("🧮 [OFFLINE] Calculator", "open calculator"),
            ("🎵 Spotify", "open spotify"),
            ("📁 [OFFLINE] Explorer", "open explorer"),
        ]

        for i, (name, cmd) in enumerate(apps):
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_BG_SURFACE};
                    color: {COLOR_TEXT_PRIMARY};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 6px;
                    padding: 8px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    text-align: left;
                }}
                QPushButton:hover {{
                    border-color: {COLOR_ACCENT};
                    background-color: rgba(0, 240, 255, 0.12);
                    color: {COLOR_ACCENT};
                }}
            """)
            btn.clicked.connect(lambda _, c=cmd: self.command_triggered.emit(c))
            row = i // 2
            col = i % 2
            grid.addWidget(btn, row, col)

        app_layout.addLayout(grid)
        layout.addWidget(app_card)

        # -------------------------------------------------------------
        # Section 3: Acoustic & Media Matrix
        # -------------------------------------------------------------
        media_card = QFrame()
        media_card.setProperty("class", "ProtocolCard")
        media_layout = QVBoxLayout(media_card)

        media_title = QLabel("🔊 ACOUSTIC & MEDIA CONTROLLER [OFFLINE]")
        media_title.setStyleSheet(f"color: {COLOR_PLASMA_BLUE}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        media_layout.addWidget(media_title)

        vol_box = QHBoxLayout()
        vol_lbl = QLabel("VOLUME MATRIX:")
        vol_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-family: 'Consolas', monospace;")
        vol_box.addWidget(vol_lbl)

        for v_txt, v_cmd in [("25%", "set volume to 25"), ("50%", "set volume to 50"), ("75%", "set volume to 75"), ("100%", "set volume to 100"), ("🔇 MUTE", "mute volume")]:
            v_btn = QPushButton(v_txt)
            v_btn.setCursor(Qt.PointingHandCursor)
            v_btn.setStyleSheet("font-size: 10px; padding: 4px 8px; border-radius: 4px;")
            v_btn.clicked.connect(lambda _, c=v_cmd: self.command_triggered.emit(c))
            vol_box.addWidget(v_btn)

        media_layout.addLayout(vol_box)

        play_box = QHBoxLayout()
        for p_txt, p_cmd in [("⏮ Prev", "previous track"), ("⏯ Play / Pause", "media play pause"), ("⏭ Next", "next track")]:
            p_btn = QPushButton(p_txt)
            p_btn.setCursor(Qt.PointingHandCursor)
            p_btn.clicked.connect(lambda _, c=p_cmd: self.command_triggered.emit(c))
            play_box.addWidget(p_btn)
        media_layout.addLayout(play_box)
        layout.addWidget(media_card)

        # -------------------------------------------------------------
        # Section 4: Vision & System Security Deck
        # -------------------------------------------------------------
        sec_card = QFrame()
        sec_card.setProperty("class", "ProtocolCard")
        sec_layout = QVBoxLayout(sec_card)

        sec_title = QLabel("🛡️ VISION SCAN & SECURITY PROTOCOLS [OFFLINE]")
        sec_title.setStyleSheet(f"color: {COLOR_AMBER}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        sec_layout.addWidget(sec_title)

        sec_grid = QGridLayout()
        sec_actions = [
            ("📸 Capture Screen OCR", "read screen", COLOR_ACCENT),
            ("🔍 Diagnose Screen Error", "analyze screen", COLOR_AMBER),
            ("⚡ Deep System Diagnostic", "system status report", COLOR_PLASMA_BLUE),
            ("🚨 Protocol Zero (Lockdown)", "emergency lockdown", COLOR_CRIMSON),
        ]

        for i, (name, cmd, col) in enumerate(sec_actions):
            s_btn = QPushButton(name)
            s_btn.setCursor(Qt.PointingHandCursor)
            s_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(0, 0, 0, 0.4);
                    color: {col};
                    border: 1px solid {col};
                    border-radius: 6px;
                    padding: 8px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {col};
                    color: #03060f;
                }}
            """)
            s_btn.clicked.connect(lambda _, c=cmd: self.command_triggered.emit(c))
            r = i // 2
            c = i % 2
            sec_grid.addWidget(s_btn, r, c)

        sec_layout.addLayout(sec_grid)
        layout.addWidget(sec_card)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
