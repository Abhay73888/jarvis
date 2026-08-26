"""Text-to-Speech (TTS) synthesizer for JARVIS.

Supports:
- High quality natural female neural voice via edge-tts (online, multilingual EN/HI).
- Offline fallback via pyttsx3 (Windows SAPI5 female voice e.g. Zira).
- Non-blocking audio playback with instant interrupt/cancellation via EventBus.
"""
from __future__ import annotations

import asyncio
import io
import re
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

from app.core.events import EventBus, Topics
from app.core.logging import get_logger

log = get_logger("voice.synthesizer")

FEMALE_HINTS = (
    "neerja", "zira", "swara", "aria", "heera", "female", "hazel",
    "eva", "catherine", "susan", "linda", "jenny", "samantha",
)


class VoiceSynthesizer:
    def __init__(
        self,
        voice_name: str = "en-IN-NeerjaNeural",
        rate: str = "+8%",
        bus: Optional[EventBus] = None,
        offline_voice: str | None = None,
    ) -> None:
        self.voice_name = voice_name
        self.rate = rate
        self.offline_voice = offline_voice
        self.bus = bus
        self._is_speaking = False
        self._cancel_requested = False
        self._current_task: Optional[asyncio.Task] = None
        self._pyttsx_lock = threading.Lock()

        if self.bus:
            self.bus.subscribe(Topics.INTERRUPT, self._on_bus_interrupt)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def _on_bus_interrupt(self, topic: str, payload: dict) -> None:
        """Instantly stop speech when interrupt event is received."""
        log.info("interrupt event received on bus -> stopping speech")
        self.stop()

    def stop(self) -> None:
        """Interrupt and cancel any currently playing speech immediately."""
        self._cancel_requested = True
        self._is_speaking = False
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    async def speak(self, text: str) -> bool:
        """Speak the given text asynchronously. Returns True on success."""
        if not text or not text.strip():
            return False

        clean_text = self._clean_for_speech(text)
        if not clean_text:
            return False

        self.stop()
        self._cancel_requested = False
        self._is_speaking = True

        try:
            # 1. Try online neural edge-tts
            success = await self._speak_edge_tts(clean_text)
            if not success and not self._cancel_requested:
                # 2. Fallback to offline pyttsx3
                log.info("falling back to offline TTS (pyttsx3)...")
                success = await self._speak_pyttsx3(clean_text)
            return success
        except asyncio.CancelledError:
            log.info("speech playback cancelled by user interrupt")
            return False
        except Exception as exc:
            log.warning("TTS error: %s", exc)
            return False
        finally:
            self._is_speaking = False

    async def prompt_yes(self) -> None:
        """Brief prompt after wake word detection."""
        await self.speak("Yes?")

    async def _speak_edge_tts(self, text: str) -> bool:
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice_name, rate=self.rate)
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
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(data)

            return await self._play_audio_file(tmp_path)
        except Exception as exc:
            log.debug("error playing audio bytes: %s", exc)
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return False

    async def _play_audio_file(self, path: Path) -> bool:
        try:
            import av
            import numpy as np
            import sounddevice as sd

            container = av.open(str(path))
            stream = container.streams.audio[0]
            sample_rate = stream.rate or 24000

            audio_frames = []
            for frame in container.decode(stream):
                if self._cancel_requested:
                    break
                arr = frame.to_ndarray()
                if arr.ndim == 2:
                    arr = arr.T
                audio_frames.append(arr)

            container.close()
            path.unlink(missing_ok=True)

            if self._cancel_requested or not audio_frames:
                return False

            full_audio = np.vstack(audio_frames)
            if full_audio.dtype != np.float32 and full_audio.dtype != np.int16:
                full_audio = full_audio.astype(np.float32) / 32768.0

            # Start playback
            sd.play(full_audio, samplerate=sample_rate)

            # Non-blocking sleep loop to allow instant barge-in cancellation
            duration = len(full_audio) / float(sample_rate)
            while duration > 0 and not self._cancel_requested:
                await asyncio.sleep(min(0.08, duration))
                duration -= 0.08

            if self._cancel_requested:
                sd.stop()
                return False

            sd.wait()
            return True
        except Exception as exc:
            log.debug("sounddevice playback failed: %s", exc)
            path.unlink(missing_ok=True)
            return False

    async def _speak_pyttsx3(self, text: str) -> bool:
        try:
            import pyttsx3

            def _sync_speak():
                with self._pyttsx_lock:
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 160)
                    try:
                        voices = engine.getProperty("voices")
                        if voices:
                            for v in voices:
                                v_name = (v.name or "").lower()
                                v_id = (v.id or "").lower()
                                if any(h in v_name or h in v_id for h in FEMALE_HINTS):
                                    engine.setProperty("voice", v.id)
                                    break
                    except Exception:
                        pass
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
        """Strip markdown formatting, URLs, code blocks for speech output."""
        t = re.sub(r"```[\s\S]*?```", " [code block] ", text)
        t = re.sub(r"`.*?`", " ", t)
        t = re.sub(r"https?://\S+", "link", t)
        t = re.sub(r"[*_~#\[\]<>]", "", t)
        t = re.sub(r"\n+", " ", t)
        return t.strip()
