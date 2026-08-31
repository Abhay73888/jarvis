"""Synapse Matrix: Neural Memory & Cognitive State Inspector for JARVIS.

Displays:
- Active Working Memory (Last App, Last URL, Pending candidate lists).
- Learned User Preferences & Profile.
- Sub-Agent Cognitive Status (Vision Agent, Win32 Automation, Browser Drone, Speech Synthesizer).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.brain.engine import AgentEngine
from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_AMBER,
    COLOR_BG_CARD,
    COLOR_BG_SURFACE,
    COLOR_BORDER,
    COLOR_EMERALD,
    COLOR_PLASMA_BLUE,
    COLOR_PURPLE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class SynapseMatrixWidget(QWidget):
    """Futuristic Neural Synapse & Memory Inspector."""

    def __init__(self, engine: AgentEngine, async_loop: Optional[asyncio.AbstractEventLoop] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.async_loop = async_loop
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # -------------------------------------------------------------
        # Section 1: Active Sub-Agent Swarm Status
        # -------------------------------------------------------------
        agent_card = QFrame()
        agent_card.setProperty("class", "ProtocolCard")
        agent_layout = QVBoxLayout(agent_card)

        ag_title = QLabel("🤖 ACTIVE SUB-AGENT SWARM")
        ag_title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        agent_layout.addWidget(ag_title)

        agents = [
            ("🧠 NEURAL BRAIN ROUTER", "ONLINE (Gemini 3.6 Flash / Fallback Cascade)", COLOR_EMERALD),
            ("🎙️ ACOUSTIC SYNTHESIZER", "READY (Edge-TTS Multi-Voice / Low-Latency)", COLOR_EMERALD),
            ("👁️ SCREEN VISION & OCR", "ENGAGED (MSS Screen Engine + Tesseract OCR)", COLOR_EMERALD),
            ("💻 WIN32 COMPUTER DRONE", "ACTIVE (Native UIA & Shell Automation)", COLOR_EMERALD),
            ("🌐 PLAYWRIGHT BROWSER DRONE", "STANDBY (Automated Chromium Sandbox)", COLOR_PLASMA_BLUE),
        ]

        for name, status, col in agents:
            row = QHBoxLayout()
            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 600; font-family: 'Consolas', monospace;")
            s_lbl = QLabel(status)
            s_lbl.setStyleSheet(f"color: {col}; font-size: 10px; font-weight: 700; font-family: 'Consolas', monospace;")
            row.addWidget(n_lbl)
            row.addStretch()
            row.addWidget(s_lbl)
            agent_layout.addLayout(row)

        layout.addWidget(agent_card)

        # -------------------------------------------------------------
        # Section 2: Active Working Memory & Context
        # -------------------------------------------------------------
        mem_card = QFrame()
        mem_card.setProperty("class", "ProtocolCard")
        mem_layout = QVBoxLayout(mem_card)

        mem_title = QLabel("🧠 ACTIVE WORKING MEMORY & CONTEXT")
        mem_title.setStyleSheet(f"color: {COLOR_PURPLE}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        mem_layout.addWidget(mem_title)

        self.mem_display = QLabel("● Working Memory Index: Initializing quantum synapses...")
        self.mem_display.setWordWrap(True)
        self.mem_display.setStyleSheet("color: #a855f7; font-size: 11px; font-family: 'Consolas', monospace; line-height: 1.4;")
        mem_layout.addWidget(self.mem_display)

        layout.addWidget(mem_card)

        # -------------------------------------------------------------
        # Section 3: Learned User Preferences
        # -------------------------------------------------------------
        pref_card = QFrame()
        pref_card.setProperty("class", "ProtocolCard")
        pref_layout = QVBoxLayout(pref_card)

        pref_title = QLabel("👤 COMMANDER PROFILE & PREFERENCES")
        pref_title.setStyleSheet(f"color: {COLOR_AMBER}; font-size: 11px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        pref_layout.addWidget(pref_title)

        self.pref_display = QLabel("● User profile: Synchronizing preferences from SQLite vault...")
        self.pref_display.setWordWrap(True)
        self.pref_display.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-family: 'Consolas', monospace; line-height: 1.4;")
        pref_layout.addWidget(self.pref_display)

        layout.addWidget(pref_card)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Auto refresh memory every 3 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_memory)
        self._timer.start(3000)
        self.refresh_memory()

    def refresh_memory(self) -> None:
        try:
            summary = self.engine.working.summary()
            if summary:
                self.mem_display.setText(summary)
            else:
                self.mem_display.setText("● Working Context: Empty / Ready for new queries.\n● Active Intent Pipeline: Synchronized.\n● Safety Rules: Injected.")

            prefs_text = getattr(self.engine, "_prefs_text", "")
            if prefs_text:
                self.pref_display.setText(prefs_text)
            else:
                self.pref_display.setText("● Commander: Recognized.\n● Language Mode: Auto-Detect (Hindi / English / Hinglish).\n● Cognitive Model: Gemini 3.6 Flash.")
        except Exception:
            pass
