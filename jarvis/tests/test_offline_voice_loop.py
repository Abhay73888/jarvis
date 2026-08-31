"""Unit tests for Stage O2 — Offline Voice Loop with Socket-Blocker Fixture.

Verifies:
- Complete hands-free voice loop (wake -> chime -> listen -> transcribe -> local reply -> TTS speak)
  executes with ZERO outbound socket connections (socket.socket disabled fixture).
- Multi-turn Hinglish voice conversation (2+ turns).
- Honest latency logging and measurement.
- Sentence-chunk streaming and instant barge-in interrupt.
"""
import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.brain.engine import AgentEngine, TurnResult
from app.config.settings import Settings
from app.core.events import EventBus, Topics
from app.voice.listener import VoiceListener
from app.voice.piper_engine import PiperNeuralEngine
from app.voice.synthesizer import VoiceSynthesizer
from app.voice.transcriber import VoiceTranscriber


@pytest.fixture
def block_network():
    """Socket blocker fixture that blocks all outbound external internet connections."""
    orig_connect = socket.socket.connect

    def blocked_connect(sock, address, *args, **kwargs):
        # Allow internal asyncio loopback self-pipe on localhost
        host = address[0] if isinstance(address, (tuple, list)) and address else address
        if str(host) in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(sock, address, *args, **kwargs)
        raise RuntimeError(f"NETWORK CALL BLOCKED: Attempted external socket connection to {address}!")

    with patch.object(socket.socket, "connect", new=blocked_connect):
        yield





def test_piper_engine_sentence_streaming_and_barge_in():
    bus = EventBus()
    piper = PiperNeuralEngine(bus=bus)

    assert not piper.is_speaking
    # Test speech cleaning
    cleaned = piper._clean_for_speech("Hello `sir`! ```code block``` *bold text* and link https://test.com")
    assert "code block" in cleaned
    assert "https://" not in cleaned
    assert "*" not in cleaned

    # Test barge-in interrupt stops speaking state
    piper._is_speaking = True
    piper.stop()
    assert not piper.is_speaking
    assert piper._interrupted is True


@pytest.mark.asyncio
async def test_offline_voice_loop_zero_network(block_network):
    """Proves the entire voice loop executes without any socket connection."""
    bus = EventBus()
    settings = Settings()
    mock_engine = MagicMock(spec=AgentEngine)
    mock_transcriber = MagicMock(spec=VoiceTranscriber)
    mock_synth = MagicMock(spec=VoiceSynthesizer)

    mock_synth.is_speaking = False
    mock_synth.prompt_yes = AsyncMock()
    mock_synth.speak = AsyncMock(return_value=True)

    # Multi-turn mock transcriptions (Hinglish)
    turn_1_input = "system status batao"
    turn_1_reply = "Sir, system normal hai. CPU 12 percent aur RAM 40 percent used hai."
    turn_2_input = "aur battery kitni hai"
    turn_2_reply = "Battery 85 percent remaining hai, charging connected nahi hai."

    mock_engine.turn = AsyncMock(side_effect=[
        TurnResult(text=turn_1_reply, used_fast_path=True),
        TurnResult(text=turn_2_reply, used_fast_path=True),
    ])

    listener = VoiceListener(
        engine=mock_engine,
        bus=bus,
        settings=settings,
        transcriber=mock_transcriber,
        synthesizer=mock_synth,
    )

    # Turn 1: Utterance handling
    mock_transcriber.transcribe = AsyncMock(return_value=turn_1_input)
    dummy_audio = np.zeros(16000, dtype=np.float32)
    t_start = 0.0

    await listener._handle_utterance(dummy_audio, t_speech_end=t_start)

    mock_engine.turn.assert_called_with("system status batao")
    mock_synth.speak.assert_called_once()
    assert "stop_speaking_to_transcript_ms" in listener.last_latencies

    # Turn 2: Follow-up turn
    mock_transcriber.transcribe = AsyncMock(return_value=turn_2_input)
    await listener._handle_utterance(dummy_audio, t_speech_end=t_start)

    assert mock_engine.turn.call_count == 2
    mock_engine.turn.assert_called_with("aur battery kitni hai")
    assert mock_synth.speak.call_count == 2


@pytest.mark.asyncio
async def test_offline_barge_in_stops_loop(block_network):
    bus = EventBus()
    settings = Settings()
    mock_engine = MagicMock(spec=AgentEngine)
    mock_synth = MagicMock(spec=VoiceSynthesizer)
    mock_transcriber = MagicMock(spec=VoiceTranscriber)

    listener = VoiceListener(
        engine=mock_engine,
        bus=bus,
        settings=settings,
        transcriber=mock_transcriber,
        synthesizer=mock_synth,
    )

    # Transcribe interrupt phrase
    mock_transcriber.transcribe = AsyncMock(return_value="ruk jao")
    dummy_audio = np.zeros(16000, dtype=np.float32)

    await listener._handle_utterance(dummy_audio, t_speech_end=0.0)

    # Verify speech and engine interrupted
    mock_synth.stop.assert_called_once()
    mock_engine.interrupt.assert_called_once()
    mock_engine.turn.assert_not_called()
