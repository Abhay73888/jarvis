"""Unit tests for Stage 1 Hands-free Voice Loop pure logic components.

Tests AGC, RMS, VAD, state machine, barge-in detection, TTS text cleaning,
and settings without requiring physical audio hardware.
"""
import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config.settings import Settings, VoiceSettings
from app.core.events import EventBus, Topics
from app.voice.listener import VoiceListener
from app.voice.state import AudioProcessor, BargeInDetector, VoiceState, VoiceStateMachine
from app.voice.synthesizer import VoiceSynthesizer
from app.voice.transcriber import VoiceTranscriber
from app.voice.tts import split_text_into_chunks


# ---------------------------------------------------------------- Audio Math Tests

def test_audio_processor_rms_silence():
    silence = np.zeros(1600, dtype=np.float32)
    rms = AudioProcessor.calculate_rms(silence)
    assert rms == 0.0


def test_audio_processor_rms_sine():
    t = np.linspace(0, 1, 16000, endpoint=False)
    sine = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    rms = AudioProcessor.calculate_rms(sine)
    # Theoretical RMS of 0.5 * sin is 0.5 / sqrt(2) ~= 0.3535
    assert 0.35 < rms < 0.36


def test_audio_processor_agc():
    # Quiet chunk peak ~0.05
    quiet = np.array([0.01, -0.05, 0.03, -0.02], dtype=np.float32)
    amplified = AudioProcessor.apply_agc(quiet, target_peak=0.4, max_gain=20.0)
    assert np.max(np.abs(amplified)) > np.max(np.abs(quiet))
    assert np.isclose(np.max(np.abs(amplified)), 0.4, atol=1e-3)

    # Loud chunk should not be amplified
    loud = np.array([0.6, -0.8, 0.5], dtype=np.float32)
    same = AudioProcessor.apply_agc(loud, target_peak=0.4)
    assert np.array_equal(loud, same)


def test_audio_processor_noise_floor_update():
    floor = 0.01
    # Higher RMS moves floor up smoothly
    new_floor = AudioProcessor.update_noise_floor(floor, chunk_rms=0.05, alpha=0.1)
    assert new_floor > floor
    assert np.isclose(new_floor, 0.9 * 0.01 + 0.1 * 0.05)


def test_audio_processor_vad_is_speech():
    noise_floor = 0.01
    # Under threshold
    assert not AudioProcessor.is_speech(0.015, noise_floor, multiplier=2.2)
    # Over threshold
    assert AudioProcessor.is_speech(0.03, noise_floor, multiplier=2.2)


def test_audio_processor_normalize_audio():
    audio = np.array([0.1, -0.2, 0.3, -0.4], dtype=np.float32)
    norm = AudioProcessor.normalize_audio(audio, target_peak=0.7)
    assert np.isclose(np.max(np.abs(norm)), 0.7)


# ---------------------------------------------------------------- Barge-in Detector Tests

def test_barge_in_detector():
    detector = BargeInDetector()

    # English & Hindi interrupt phrases
    assert detector.is_barge_in("stop")
    assert detector.is_barge_in("Jarvis please stop")
    assert detector.is_barge_in("ruk jao")
    assert detector.is_barge_in("ruk ja bhai")
    assert detector.is_barge_in("abort mission")
    assert detector.is_barge_in("cancel")
    assert detector.is_barge_in("shant ho jao")
    assert detector.is_barge_in("chup ho jao")

    # Regular commands must NOT trigger barge-in
    assert not detector.is_barge_in("open chrome")
    assert not detector.is_barge_in("what is the weather today")
    assert not detector.is_barge_in("kaun se apps chal rahe hain")
    assert not detector.is_barge_in("search google for stop sign")


# ---------------------------------------------------------------- State Machine Tests

def test_voice_state_machine_transitions():
    state_log = []

    def on_change(prev, new):
        state_log.append((prev, new))

    sm = VoiceStateMachine(on_state_change=on_change)
    assert sm.state == VoiceState.IDLE

    # Happy path transition cycle
    assert sm.on_wake_detected()
    assert sm.state == VoiceState.WAKE_DETECTED

    assert sm.on_prompt_start()
    assert sm.state == VoiceState.PROMPTING

    assert sm.on_recording_start()
    assert sm.state == VoiceState.RECORDING

    assert sm.on_transcribe_start()
    assert sm.state == VoiceState.TRANSCRIBING

    assert sm.on_thinking_start()
    assert sm.state == VoiceState.THINKING

    assert sm.on_speaking_start()
    assert sm.state == VoiceState.SPEAKING

    assert sm.on_idle()
    assert sm.state == VoiceState.IDLE

    # Interrupt transition
    assert sm.on_wake_detected()
    assert sm.on_interrupt()
    assert sm.state == VoiceState.INTERRUPTED
    assert len(state_log) > 0


# ---------------------------------------------------------------- Synthesizer & Speech Cleaning

def test_synthesizer_clean_text():
    synth = VoiceSynthesizer()
    raw = "Here is `some code`: ```python\nprint('hello')\n``` and link https://google.com *bold* and _italic_."
    clean = synth._clean_for_speech(raw)
    assert "print('hello')" not in clean
    assert "code block" in clean
    assert "https://" not in clean
    assert "*" not in clean
    assert "_" not in clean


def test_split_text_into_chunks():
    short = "Hello, sir. How are you?"
    chunks = split_text_into_chunks(short, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == short

    long_text = ". ".join([f"Sentence {i} with some descriptive text" for i in range(20)])
    chunks = split_text_into_chunks(long_text, max_chars=100)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 120


# ---------------------------------------------------------------- Settings & Listener Tests

def test_voice_settings_defaults():
    settings = VoiceSettings()
    assert settings.wake_enabled is True
    assert settings.push_to_talk is True
    assert "jarvis" in settings.wake_words
    assert settings.stt_model == "small"
    assert settings.tts_voice == "en-IN-NeerjaNeural"
    assert settings.barge_in_enabled is True


@pytest.mark.asyncio
async def test_voice_listener_mute_and_trigger():
    mock_engine = MagicMock()
    mock_bus = EventBus()
    listener = VoiceListener(engine=mock_engine, bus=mock_bus)

    assert not listener.is_muted
    listener.set_muted(True)
    assert listener.is_muted

    # Test emergency stop event
    mock_engine.interrupt = MagicMock()
    listener.emergency_stop()
    mock_engine.interrupt.assert_called_once()
    assert listener.state_machine.state == VoiceState.INTERRUPTED


def test_transcriber_availability():
    avail, msg = VoiceTranscriber.check_availability()
    assert isinstance(avail, bool)
    assert isinstance(msg, str)
