"""Holographic AI Lab & Quantum Settings Dialog for JARVIS.

Allows user configuration for:
- AI Brain Model selection (Gemini 3.6 Flash, Gemini 2.0 Flash, Claude, OpenAI).
- Voice Synthesizer & TTS Engine (Indian English, Hindi, British Jarvis, US English).
- Speech Rate & Auto-Speak toggles.
- Live audio voice preview button.
- Language personality mode (Auto / English / Hinglish).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import Settings
from app.ui.theme import (
    COLOR_ACCENT,
    COLOR_ACCENT_GLOW,
    COLOR_AMBER,
    COLOR_BG_CARD,
    COLOR_BG_SURFACE,
    COLOR_BG_VOID,
    COLOR_BORDER,
    COLOR_EMERALD,
    COLOR_PLASMA_BLUE,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    STYLESHEET,
)
from app.voice.synthesizer import VoiceSynthesizer


class SettingsDialog(QDialog):
    """Futuristic Holographic Settings & AI Lab Modal."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        synthesizer: Optional[VoiceSynthesizer] = None,
        async_loop: Optional[asyncio.AbstractEventLoop] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.synthesizer = synthesizer
        self.async_loop = async_loop

        self.setWindowTitle("JARVIS — Quantum AI Lab & Protocol Settings")
        self.setMinimumSize(460, 560)
        self.setStyleSheet(STYLESHEET)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Title Bar
        title = QLabel("⚙️ QUANTUM AI LAB & PROTOCOL CONFIG")
        title.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px; font-weight: 800; letter-spacing: 2px; font-family: 'Consolas', monospace;")
        layout.addWidget(title)

        # -------------------------------------------------------------
        # 1. AI Brain Model Configuration
        # -------------------------------------------------------------
        model_card = QFrame(self)
        model_card.setProperty("class", "ProtocolCard")
        m_layout = QVBoxLayout(model_card)
        m_layout.setSpacing(8)

        m_title = QLabel("🧠 AI NEURAL COGNITIVE MODEL")
        m_title.setStyleSheet(f"color: {COLOR_PLASMA_BLUE}; font-size: 11px; font-weight: 800; font-family: 'Consolas', monospace;")
        m_layout.addWidget(m_title)

        self.model_combo = QComboBox(self)
        self.model_combo.addItems([
            "gemini-3.6-flash (Ultra-Fast / Recommended)",
            "gemini-2.0-flash (High-Speed Multimodal)",
            "gemini-2.5-flash (Balanced)",
            "gemini-3.1-flash-lite (Low-Latency)",
            "gpt-4o (OpenAI Compatible)",
            "claude-3-5-sonnet (Anthropic)",
            "ollama/llama3 (Local Offline)",
        ])
        m_layout.addWidget(self.model_combo)
        layout.addWidget(model_card)

        # -------------------------------------------------------------
        # 2. Voice Synthesizer & Speech Tuning
        # -------------------------------------------------------------
        voice_card = QFrame(self)
        voice_card.setProperty("class", "ProtocolCard")
        v_layout = QVBoxLayout(voice_card)
        v_layout.setSpacing(8)

        v_title = QLabel("🎙️ ACOUSTIC SYNTHESIZER & TTS STUDIO")
        v_title.setStyleSheet(f"color: {COLOR_EMERALD}; font-size: 11px; font-weight: 800; font-family: 'Consolas', monospace;")
        v_layout.addWidget(v_title)

        # Voice Selector
        voice_lbl = QLabel("VOICE PROFILE:")
        voice_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; font-family: 'Consolas', monospace;")
        v_layout.addWidget(voice_lbl)

        self.voice_combo = QComboBox(self)
        self.voice_combo.addItems([
            "en-IN-NeerjaNeural (Indian English - Female)",
            "hi-IN-MadhurNeural (Hindi / Hinglish - Male)",
            "en-GB-RyanNeural (British Jarvis - Male)",
            "en-US-ChristopherNeural (US English - Male)",
            "en-IN-PrabhatNeural (Indian English - Male)",
        ])
        v_layout.addWidget(self.voice_combo)

        # Speech Rate Slider
        rate_box = QHBoxLayout()
        self.rate_lbl = QLabel("SPEECH RATE: +8%")
        self.rate_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px; font-family: 'Consolas', monospace;")
        rate_box.addWidget(self.rate_lbl)

        self.rate_slider = QSlider(Qt.Horizontal, self)
        self.rate_slider.setRange(-30, 40)
        self.rate_slider.setValue(8)
        self.rate_slider.valueChanged.connect(lambda val: self.rate_lbl.setText(f"SPEECH RATE: {val:+d}%"))
        rate_box.addWidget(self.rate_slider)
        v_layout.addLayout(rate_box)

        # Test Audio Button
        test_btn = QPushButton("🔊 TEST VOICE PREVIEW")
        test_btn.setStyleSheet(f"background-color: rgba(0, 255, 163, 0.12); color: {COLOR_EMERALD}; border: 1px solid {COLOR_EMERALD}; font-weight: 700; border-radius: 6px; padding: 6px 12px;")
        test_btn.clicked.connect(self._test_voice)
        v_layout.addWidget(test_btn)

        layout.addWidget(voice_card)

        # -------------------------------------------------------------
        # 3. Personality & Behavior
        # -------------------------------------------------------------
        pref_card = QFrame(self)
        pref_card.setProperty("class", "ProtocolCard")
        p_layout = QVBoxLayout(pref_card)
        p_layout.setSpacing(8)

        p_title = QLabel("🌐 PERSONALITY & LANGUAGE PROTOCOL")
        p_title.setStyleSheet(f"color: {COLOR_AMBER}; font-size: 11px; font-weight: 800; font-family: 'Consolas', monospace;")
        p_layout.addWidget(p_title)

        self.lang_combo = QComboBox(self)
        self.lang_combo.addItems([
            "auto (Auto-detect English / Hindi / Hinglish)",
            "hinglish (Natural Hinglish Roman Hindi)",
            "english (Standard English)",
        ])
        p_layout.addWidget(self.lang_combo)

        self.auto_speak_chk = QCheckBox("Automatically speak all AI text responses aloud")
        self.auto_speak_chk.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px;")
        self.auto_speak_chk.setChecked(True)
        p_layout.addWidget(self.auto_speak_chk)

        layout.addWidget(pref_card)

        # -------------------------------------------------------------
        # Save & Close Buttons
        # -------------------------------------------------------------
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        close_btn = QPushButton("SAVE & APPLY")
        close_btn.setObjectName("PrimaryTransmit")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        layout.addLayout(btn_box)

    def _test_voice(self) -> None:
        if self.synthesizer and self.async_loop:
            voice_choice = self.voice_combo.currentText().split(" ")[0]
            rate_val = f"{self.rate_slider.value():+d}%"
            test_phrase = "Greetings Commander. Voice synthesizer matrix is fully operational."
            asyncio.run_coroutine_threadsafe(
                self.synthesizer.speak(test_phrase, voice=voice_choice, rate=rate_val),
                self.async_loop,
            )
