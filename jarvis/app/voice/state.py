"""Pure logic and state machine for JARVIS voice processing.

Decouples audio math, VAD thresholds, barge-in detection, and state transitions
from physical hardware, enabling 100% deterministic unit testing.
"""
from __future__ import annotations

from enum import Enum
import re
from typing import Callable, Optional
import numpy as np


class VoiceState(str, Enum):
    IDLE = "idle"
    WAKE_DETECTED = "wake_detected"
    PROMPTING = "prompting"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class AudioProcessor:
    """Audio signal processing utilities (AGC, RMS, VAD, Normalization)."""

    SAMPLE_RATE = 16000
    CHUNK_DURATION_MS = 80  # 80ms chunk = 1280 samples @ 16kHz
    CHUNK_SIZE = int(SAMPLE_RATE * (CHUNK_DURATION_MS / 1000.0))

    @staticmethod
    def calculate_rms(chunk: np.ndarray) -> float:
        """Calculate Root Mean Square energy of an audio frame."""
        if chunk is None or len(chunk) == 0:
            return 0.0
        return float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

    @staticmethod
    def apply_agc(
        chunk: np.ndarray,
        target_peak: float = 0.5,
        max_gain: float = 150.0,
        min_signal: float = 1e-7,
    ) -> np.ndarray:
        """Automatic Gain Control: amplify quiet microphone signals to standard volume."""
        if chunk is None or len(chunk) == 0:
            return chunk
        peak = float(np.max(np.abs(chunk)))
        if peak < min_signal:
            return chunk
        if peak < target_peak:
            gain = min(max_gain, target_peak / peak)
            return np.clip(chunk * gain, -1.0, 1.0)
        return chunk

    @staticmethod
    def update_noise_floor(current_floor: float, chunk_rms: float, alpha: float = 0.05) -> float:
        """Smoothly update adaptive background noise floor estimate."""
        clamped_rms = max(0.00005, chunk_rms)
        return (1.0 - alpha) * current_floor + alpha * clamped_rms

    @staticmethod
    def is_speech(
        chunk_rms: float,
        noise_floor: float,
        multiplier: float = 1.8,
        min_threshold: float = 0.0003,
    ) -> bool:
        """Energy-based Voice Activity Detection (VAD)."""
        threshold = max(min_threshold, noise_floor * multiplier)
        return chunk_rms > threshold

    @staticmethod
    def normalize_audio(audio: np.ndarray, target_peak: float = 0.7) -> np.ndarray:
        """Normalize peak amplitude to target level for optimal Whisper transcription."""
        if audio is None or len(audio) == 0:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak > 1e-5:
            return (audio / peak) * target_peak
        return audio


class BargeInDetector:
    """Detects spoken interrupt commands to cancel speech and active tasks."""

    DEFAULT_KEYWORDS = [
        "stop",
        "ruk jao",
        "ruk ja",
        "abort",
        "cancel",
        "shant ho jao",
        "shant ho ja",
        "chup ho jao",
        "chup",
        "pause",
        "terminate",
        "quit",
        "halt",
        "emergency stop",
    ]

    def __init__(self, keywords: Optional[list[str]] = None) -> None:
        self.keywords = keywords or self.DEFAULT_KEYWORDS

    def is_barge_in(self, text: str) -> bool:
        """Return True if text is primarily an interrupt/barge-in trigger."""
        if not text:
            return False
        clean = text.strip().lower()
        clean = re.sub(r"[,.!?]+$", "", clean).strip()

        # Remove leading and trailing filler words repeatedly
        prev = None
        while prev != clean:
            prev = clean
            clean = re.sub(r"^(jarvis|hey jarvis|hello jarvis|ok jarvis|please|bhai)\s+", "", clean, flags=re.IGNORECASE).strip()
            clean = re.sub(r"\s+(please|now|bhai|sir|mission)$", "", clean, flags=re.IGNORECASE).strip()

        for kw in self.keywords:
            if clean == kw:
                return True
            if clean.startswith(kw + " ") and len(clean.split()) <= 3:
                return True
        return False


class VoiceStateMachine:
    """State machine governing voice workflow transitions."""

    def __init__(
        self,
        on_state_change: Optional[Callable[[VoiceState, VoiceState], None]] = None,
    ) -> None:
        self._state = VoiceState.IDLE
        self._on_state_change = on_state_change

    @property
    def state(self) -> VoiceState:
        return self._state

    def transition_to(self, new_state: VoiceState) -> bool:
        """Transition to a new state and fire callback."""
        if self._state == new_state:
            return False
        prev = self._state
        self._state = new_state
        if self._on_state_change:
            try:
                self._on_state_change(prev, new_state)
            except Exception:
                pass
        return True

    def on_wake_detected(self) -> bool:
        if self._state in (VoiceState.IDLE, VoiceState.SPEAKING, VoiceState.INTERRUPTED):
            return self.transition_to(VoiceState.WAKE_DETECTED)
        return False

    def on_prompt_start(self) -> bool:
        return self.transition_to(VoiceState.PROMPTING)

    def on_recording_start(self) -> bool:
        return self.transition_to(VoiceState.RECORDING)

    def on_transcribe_start(self) -> bool:
        return self.transition_to(VoiceState.TRANSCRIBING)

    def on_thinking_start(self) -> bool:
        return self.transition_to(VoiceState.THINKING)

    def on_speaking_start(self) -> bool:
        return self.transition_to(VoiceState.SPEAKING)

    def on_interrupt(self) -> bool:
        return self.transition_to(VoiceState.INTERRUPTED)

    def on_idle(self) -> bool:
        return self.transition_to(VoiceState.IDLE)
