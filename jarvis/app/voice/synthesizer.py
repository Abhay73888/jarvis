"""Text-to-Speech (TTS) synthesizer for JARVIS.

Supports:
- High quality natural neural voices via edge-tts (online, multilingual EN/HI).
- Offline fallback via pyttsx3 (Windows SAPI5 voices).
- Non-blocking audio playback and immediate cancellation.
"""
from __future__ import annotations

import asyncio
import io
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger

log = get_logger("voice.synthesizer")


class VoiceSynthesizer:
    def __init__(self, voice_name: str = "en-IN-PrabhatNeural", offline_voice: str | None = None) -> None:
        self.voice_name = voice_name
        self.offline_voice = offline_voice
        self._is_speaking = False
        self._cancel_requested = False
        self._current_task: Optional[asyncio.Task] = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self) -> None:
        """Interrupt and cancel any currently playing speech."""
        self._cancel_requested = True
        self._is_speaking = False
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    async def speak(self, text: str) -> bool:
        """Speak the given text asynchronously. Returns True on success."""
        if not text or not text.strip():
            return False

        # Clean markdown symbols, asterisks, links, code blocks for clean speech
        clean_text = self._clean_for_speech(text)
        if not clean_text:
            return False

        self.stop()
        self._cancel_requested = False
        self._is_speaking = True

        try:
            # Try online edge-tts first
            success = await self._speak_edge_tts(clean_text)
            if not success and not self._cancel_requested:
                # Fallback to offline pyttsx3
                log.info("falling back to offline TTS (pyttsx3)...")
                success = await self._speak_pyttsx3(clean_text)
            return success
        except asyncio.CancelledError:
            log.info("speech playback cancelled")
            return False
        except Exception as exc:
            log.warning("TTS error: %s", exc)
            return False
        finally:
            self._is_speaking = False

    async def _speak_edge_tts(self, text: str) -> bool:
        """Synthesize using edge-tts and play via temporary audio stream."""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice_name)
            mp3_bytes = bytearray()
            async for chunk in communicate.stream():
                if self._cancel_requested:
                    return False
                if chunk["type"] == "audio":
                    mp3_bytes.extend(chunk["data"])

            if not mp3_bytes or self._cancel_requested:
                return False

            return await self._play_mp3_bytes(bytes(mp3_bytes))
        except Exception as exc:
            log.debug("edge-tts synthesis failed: %s", exc)
            return False

    async def _play_mp3_bytes(self, data: bytes) -> bool:
        """Play mp3 bytes via av / sounddevice or a lightweight audio playback."""
        try:
            # Decode mp3 using av or play via PySide6 / temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(data)

            return await self._play_audio_file(tmp_path)
        except Exception as exc:
            log.debug("error playing audio bytes: %s", exc)
            return False

    async def _play_audio_file(self, path: Path) -> bool:
        """Play an audio file using av + sounddevice or system media player."""
        try:
            import av
            import numpy as np
            import sounddevice as sd

            container = av.open(str(path))
            stream = container.streams.audio[0]
            sample_rate = stream.rate or 24000
            channels = stream.channels or 1

            audio_frames = []
            for frame in container.decode(stream):
                if self._cancel_requested:
                    break
                arr = frame.to_ndarray()
                if arr.ndim == 2:
                    arr = arr.T  # sounddevice expects (samples, channels)
                audio_frames.append(arr)

            container.close()
            path.unlink(missing_ok=True)

            if self._cancel_requested or not audio_frames:
                return False

            full_audio = np.vstack(audio_frames)
            # Normalize to float32 or int16
            if full_audio.dtype != np.float32 and full_audio.dtype != np.int16:
                full_audio = full_audio.astype(np.float32) / 32768.0

            loop = asyncio.get_running_loop()
            finished_event = asyncio.Event()

            def callback_done():
                loop.call_soon_threadsafe(finished_event.set)

            # Play asynchronously
            sd.play(full_audio, samplerate=sample_rate)

            # Wait for playback or cancellation
            duration = len(full_audio) / float(sample_rate)
            while duration > 0 and not self._cancel_requested:
                await asyncio.sleep(min(0.1, duration))
                duration -= 0.1

            if self._cancel_requested:
                sd.stop()
                return False

            sd.wait()
            return True
        except Exception as exc:
            log.debug("sounddevice playback failed: %s, trying system fallback", exc)
            path.unlink(missing_ok=True)
            return False

    async def _speak_pyttsx3(self, text: str) -> bool:
        """Offline fallback using pyttsx3."""
        try:
            import pyttsx3

            def _sync_speak():
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                engine.say(text)
                engine.runAndWait()
                engine.stop()

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _sync_speak)
            return True
        except Exception as exc:
            log.warning("pyttsx3 offline speech failed: %s", exc)
            return False

    def _clean_for_speech(self, text: str) -> str:
        """Strip markdown syntax, code blocks, URLs, and formatting for natural speech."""
        t = re.sub(r"```[\s\S]*?```", "", text)  # remove code blocks
        t = re.sub(r"`.*?`", "", t)              # remove inline code
        t = re.sub(r"https?://\S+", "link", t)   # replace URLs
        t = re.sub(r"[*_~#\[\]<>]", "", t)       # remove markdown symbols
        t = re.sub(r"\n+", " ", t)               # replace newlines with space
        return t.strip()
