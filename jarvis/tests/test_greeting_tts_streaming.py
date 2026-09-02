"""Unit tests for Time-Aware Greeting, TTS Manager, and Provider SSE Streaming."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.brain.greeting import (
    build_greeting,
    get_startup_status,
    install_startup_bat,
    remove_startup_bat,
)
from app.brain.provider import ChatMessage, ModelEntry, StreamEvent
from app.brain.providers.gemini import GeminiProvider
from app.brain.providers.openai_compat import OpenAICompatibleProvider
from app.voice.tts import TTSManager, split_text_into_chunks

# ==============================================================================
# Feature 1: Time-Aware Greeting Tests
# ==============================================================================

def test_greeting_time_buckets():
    # 5am - 12pm: Good morning
    dt_morning = datetime(2026, 8, 24, 8, 30)
    g_m = build_greeting(dt_morning, address="sir", include_brief=False)
    assert g_m == "Good morning, sir."

    # 12pm - 5pm: Good afternoon
    dt_afternoon = datetime(2026, 8, 24, 14, 15)
    g_a = build_greeting(dt_afternoon, address="sir", include_brief=False)
    assert g_a == "Good afternoon, sir."

    # 5pm - 9pm: Good evening
    dt_evening = datetime(2026, 8, 24, 19, 45)
    g_e = build_greeting(dt_evening, address="sir", include_brief=False)
    assert g_e == "Good evening, sir."

    # 9pm - 5am: Working late
    dt_night = datetime(2026, 8, 24, 23, 10)
    g_n = build_greeting(dt_night, address="sir", include_brief=False)
    assert g_n == "Working late, sir."

    dt_early = datetime(2026, 8, 24, 3, 0)
    g_early = build_greeting(dt_early, address="sir", include_brief=False)
    assert g_early == "Working late, sir."


def test_greeting_brief_and_reminders():
    dt = datetime(2026, 8, 24, 9, 0)

    # With 0 reminders
    g0 = build_greeting(dt, address="Abhay", include_brief=True, pending_today=0)
    assert "Good morning, Abhay." in g0
    assert "Today is Monday, August 24." in g0
    assert "reminders" not in g0

    # With 1 reminder
    g1 = build_greeting(dt, address="Abhay", include_brief=True, pending_today=1)
    assert "You have 1 reminder due today." in g1

    # With multiple reminders
    g2 = build_greeting(dt, address="Abhay", include_brief=True, pending_today=3)
    assert "You have 3 reminders due today." in g2


def test_startup_bat_lifecycle(tmp_path: Path):
    project_root = tmp_path / "jarvis_project"
    project_root.mkdir()
    startup_dir = tmp_path / "Startup"

    # Status before install
    st1 = get_startup_status(startup_dir)
    assert not st1["installed"]

    # Install silent bat
    bat_path = install_startup_bat(project_root, speak=True, console=False, target_dir=startup_dir)
    assert bat_path.exists()

    content = bat_path.read_text(encoding="utf-8")
    assert "run.py greet --speak" in content
    assert str(project_root) in content

    # Status after install
    st2 = get_startup_status(startup_dir)
    assert st2["installed"]
    assert "run.py greet" in st2["content"]

    # Remove bat
    removed = remove_startup_bat(startup_dir)
    assert removed
    assert not bat_path.exists()

    # Status after removal
    st3 = get_startup_status(startup_dir)
    assert not st3["installed"]


# ==============================================================================
# Feature 2: TTS Manager Tests
# ==============================================================================

def test_tts_chunking():
    # Empty
    assert split_text_into_chunks("") == []

    # Short sentence
    text = "Hello sir. How are you today?"
    chunks = split_text_into_chunks(text, max_chars=450)
    assert chunks == [text]

    # Long text with sentence splitting
    sentences = [f"Sentence number {i} with some descriptive words." for i in range(25)]
    long_text = " ".join(sentences)
    assert len(long_text) > 800

    split_chunks = split_text_into_chunks(long_text, max_chars=300)
    assert len(split_chunks) > 1
    for chunk in split_chunks:
        assert len(chunk) <= 300


def test_tts_honest_availability():
    # When both libraries are mocked as unavailable
    with patch.dict("sys.modules", {"edge_tts": None, "pyttsx3": None}):
        available, msg = TTSManager.check_availability()
        assert not available
        assert "pip install edge-tts" in msg


def test_tts_female_voice_hints():
    tts = TTSManager(voice="en-IN-NeerjaNeural", gender="female")
    mock_engine = MagicMock()

    class VoiceObj:
        def __init__(self, vid, vname, gender):
            self.id = vid
            self.name = vname
            self.gender = gender

    mock_engine.getProperty.return_value = [
        VoiceObj("id_david", "Microsoft David Desktop", "Male"),
        VoiceObj("id_zira", "Microsoft Zira Desktop", "Female"),
    ]

    tts._configure_pyttsx3_voice(mock_engine)
    mock_engine.setProperty.assert_any_call("rate", 160)
    mock_engine.setProperty.assert_any_call("voice", "id_zira")


# ==============================================================================
# Feature 3: Provider Streaming Tests (In-Memory Fake SSE)
# ==============================================================================

@pytest.mark.asyncio
async def test_gemini_sse_streaming():
    entry = ModelEntry(id="gemini-3.7-flash", provider="gemini", api_key_env="DUMMY_KEY")
    provider = GeminiProvider(entry)
    provider._require_key = MagicMock(return_value="test-key")

    sse_lines = [
        b'data: {"candidates": [{"content": {"parts": [{"text": "Hello "}]}}]}\r\n',
        b'data: {"candidates": [{"content": {"parts": [{"text": "world!"}]}}]}\r\n',
        b'data: {"candidates": [{"content": {"parts": [{"functionCall": {"name": "system_info", "args": {}}}]}}]}\r\n',
    ]

    class FakeAsyncResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line.decode("utf-8")

    mock_client = MagicMock()
    mock_client.is_closed = False
    mock_client.stream = MagicMock(return_value=FakeAsyncResponse())
    provider._client = mock_client

    events: list[StreamEvent] = []
    messages = [ChatMessage(role="user", content="Hi")]
    async for ev in provider.chat_stream(messages):
        events.append(ev)

    # Verify deltas streamed
    text_deltas = [ev.text for ev in events if ev.text]
    assert text_deltas == ["Hello ", "world!"]

    # Verify final response assembled
    final_ev = events[-1]
    assert final_ev.response is not None
    assert final_ev.response.content == "Hello world!"
    assert len(final_ev.response.tool_calls) == 1
    assert final_ev.response.tool_calls[0].name == "system_info"


@pytest.mark.asyncio
async def test_openai_compat_sse_streaming():
    entry = ModelEntry(id="gpt-4o-mini", provider="openai_compatible", api_key_env="DUMMY_KEY")
    provider = OpenAICompatibleProvider(entry)
    provider._require_key = MagicMock(return_value="test-key")

    sse_lines = [
        b'data: {"choices": [{"delta": {"content": "JARVIS "}}]}\r\n',
        b'data: {"choices": [{"delta": {"content": "online."}}]}\r\n',
        b'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "open_app", "arguments": "{\\"app\\": \\"notepad\\"}"}}]}}]}\r\n',
        b'data: [DONE]\r\n',
    ]

    class FakeAsyncResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line.decode("utf-8")

    mock_client = MagicMock()
    mock_client.is_closed = False
    mock_client.stream = MagicMock(return_value=FakeAsyncResponse())
    provider._client = mock_client

    events: list[StreamEvent] = []
    messages = [ChatMessage(role="user", content="Start")]
    async for ev in provider.chat_stream(messages):
        events.append(ev)

    text_deltas = [ev.text for ev in events if ev.text]
    assert text_deltas == ["JARVIS ", "online."]

    final_ev = events[-1]
    assert final_ev.response is not None
    assert final_ev.response.content == "JARVIS online."
    assert len(final_ev.response.tool_calls) == 1
    assert final_ev.response.tool_calls[0].name == "open_app"
    assert final_ev.response.tool_calls[0].arguments == {"app": "notepad"}
