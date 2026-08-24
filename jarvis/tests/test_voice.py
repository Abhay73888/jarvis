"""Tests for Voice Synthesizer and Listener components."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.events import EventBus
from app.voice.listener import VoiceListener
from app.voice.synthesizer import VoiceSynthesizer


def test_synthesizer_clean_for_speech():
    synth = VoiceSynthesizer()
    raw = "Here is `some code`: ```python\nprint('hello')\n``` and a link https://google.com *bold* text."
    cleaned = synth._clean_for_speech(raw)
    assert "print('hello')" not in cleaned
    assert "https://" not in cleaned
    assert "*" not in cleaned
    assert "bold text" in cleaned


def test_voice_listener_mute_toggle():
    mock_engine = MagicMock()
    bus = EventBus()
    listener = VoiceListener(engine=mock_engine, bus=bus)

    assert not listener.is_muted
    listener.set_muted(True)
    assert listener.is_muted
    listener.set_muted(False)
    assert not listener.is_muted
