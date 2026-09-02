"""Continuous Voice Listener for JARVIS with Automatic Gain Control (AGC).

Captures microphone audio, normalizes quiet laptop microphones dynamically,
monitors for wake word ('Jarvis' / 'Hey Jarvis'), records commands until silence,
and runs them through transcriber -> engine -> synthesizer pipeline.
"""
from __future__ import annotations

import asyncio
import collections
import time
from collections.abc import Callable

import numpy as np

from app.brain.engine import AgentEngine
from app.core.events import EventBus, Topics
from app.core.logging import get_logger
from app.voice.synthesizer import VoiceSynthesizer
from app.voice.transcriber import VoiceTranscriber

log = get_logger("voice.listener")

SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 80  # 80ms chunk = 1280 samples @ 16kHz
CHUNK_SIZE = int(SAMPLE_RATE * (CHUNK_DURATION_MS / 1000.0))
MAX_RECORD_DURATION_S = 14.0
WAKE_THRESHOLD = 0.20   # Sensitive wake threshold


def _apply_agc(chunk: np.ndarray) -> np.ndarray:
    """Automatic Gain Control: amplify quiet microphone signals to standard nominal volume."""
    peak = float(np.max(np.abs(chunk)))
    if peak < 1e-6:
        return chunk
    if peak < 0.25:
        # Boost quiet input up to 80x while preventing clipping
        gain = min(80.0, 0.4 / peak)
        return np.clip(chunk * gain, -1.0, 1.0)
    return chunk


class VoiceListener:
    def __init__(
        self,
        engine: AgentEngine,
        bus: EventBus,
        transcriber: VoiceTranscriber | None = None,
        synthesizer: VoiceSynthesizer | None = None,
        on_wake_callback: Callable[[], None] | None = None,
        on_transcript_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.engine = engine
        self.bus = bus
        self.transcriber = transcriber or VoiceTranscriber()
        self.synthesizer = synthesizer or VoiceSynthesizer()
        self.on_wake_callback = on_wake_callback
        self.on_transcript_callback = on_transcript_callback

        self._running = False
        self._muted = False
        self._is_recording_command = False
        self._manual_trigger = asyncio.Event()
        self._stream = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wakeword_model = None
        self._wakeword_loaded = False
        self._noise_floor = 0.001

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        log.info("voice listener muted: %s", muted)

    def trigger_manual_listen(self) -> None:
        """Manually trigger voice listening immediately (Push-to-Talk)."""
        if self._running and not self._is_recording_command:
            log.info("manual voice trigger requested")
            self._manual_trigger.set()

    def _init_wakeword(self) -> None:
        if not self._wakeword_loaded:
            self._wakeword_loaded = True
            try:
                import openwakeword
                from openwakeword.model import Model
                openwakeword.utils.download_models()
                self._wakeword_model = Model(wakeword_models=["hey_jarvis", "jarvis"], inference_framework="onnx")
                log.info("openwakeword initialized for 'jarvis' wake word")
            except Exception as exc:
                log.info("openwakeword fallback (%s)", exc)
                self._wakeword_model = None

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._loop = asyncio.get_running_loop()
        self._init_wakeword()

        try:
            import sounddevice as sd
        except ImportError:
            log.error("sounddevice is not installed")
            self._running = False
            return

        log.info("starting JARVIS voice listener (sample_rate=%d, chunk=%d)...", SAMPLE_RATE, CHUNK_SIZE)
        await self.bus.publish(Topics.STATUS, {"state": "idle", "detail": "Voice listening active"})

        audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

        def audio_callback(indata: np.ndarray, frames: int, time_info, status):
            if self._running and not self._muted and self._loop:
                raw_chunk = indata[:, 0].copy()
                amplified = _apply_agc(raw_chunk)
                self._loop.call_soon_threadsafe(audio_queue.put_nowait, amplified)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SIZE,
                callback=audio_callback,
            ) as stream:
                self._stream = stream
                await self._process_audio_stream(audio_queue)
        except Exception as exc:
            log.error("voice stream error: %s", exc)
        finally:
            self._running = False
            self._stream = None

    def stop(self) -> None:
        self._running = False
        if self.synthesizer:
            self.synthesizer.stop()

    async def _process_audio_stream(self, queue: asyncio.Queue[np.ndarray]) -> None:
        pre_roll = collections.deque(maxlen=int(2.0 / (CHUNK_DURATION_MS / 1000.0)))

        while self._running:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.15)
            except TimeoutError:
                if self._manual_trigger.is_set():
                    pass
                else:
                    continue

            if self._muted or self.synthesizer.is_speaking:
                continue

            pre_roll.append(chunk)

            # Update adaptive noise floor
            rms = float(np.sqrt(np.mean(chunk**2)))
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * max(0.0001, rms)

            wake_detected = self._check_wake_word(chunk)
            manual_triggered = self._manual_trigger.is_set()

            if wake_detected or manual_triggered:
                self._manual_trigger.clear()
                self._is_recording_command = True
                log.info("Voice trigger activated! Recording command...")

                if self.on_wake_callback:
                    try:
                        self.on_wake_callback()
                    except Exception:
                        pass

                await self.bus.publish(Topics.STATUS, {"state": "listening", "detail": "Listening..."})
                await self._play_wake_chime()

                utterance_audio = await self._record_utterance(queue, pre_roll)
                if utterance_audio is not None and len(utterance_audio) > SAMPLE_RATE * 0.4:
                    await self._handle_utterance(utterance_audio)

                self._is_recording_command = False
                await self.bus.publish(Topics.STATUS, {"state": "idle", "detail": "Ready"})
                pre_roll.clear()

    def _check_wake_word(self, chunk: np.ndarray) -> bool:
        if self._wakeword_model is not None:
            try:
                int16_chunk = (chunk * 32767).astype(np.int16)
                predictions = self._wakeword_model.predict(int16_chunk)
                for model_name, score in predictions.items():
                    if score >= WAKE_THRESHOLD:
                        log.info("WAKE WORD DETECTED: '%s' (score=%.2f)", model_name, score)
                        self._wakeword_model.reset()
                        return True
            except Exception as exc:
                log.debug("wakeword error: %s", exc)
        return False

    async def _record_utterance(self, queue: asyncio.Queue[np.ndarray], pre_roll: collections.deque) -> np.ndarray | None:
        recorded_chunks = list(pre_roll)
        silence_start: float | None = None
        has_spoken = False
        start_time = time.time()
        speech_threshold = max(0.005, self._noise_floor * 2.2)

        while self._running and (time.time() - start_time < MAX_RECORD_DURATION_S):
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.4)
            except TimeoutError:
                break

            recorded_chunks.append(chunk)
            rms = float(np.sqrt(np.mean(chunk**2)))

            if rms > speech_threshold:
                has_spoken = True
                silence_start = None
            else:
                if has_spoken:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= 1.3:
                        log.debug("end of speech detected")
                        break

        if not recorded_chunks:
            return None

        full_audio = np.concatenate(recorded_chunks)
        # Normalize peak to 0.7 for whisper
        peak = float(np.max(np.abs(full_audio)))
        if peak > 1e-5:
            full_audio = (full_audio / peak) * 0.7
        return full_audio

    async def _handle_utterance(self, audio: np.ndarray) -> None:
        await self.bus.publish(Topics.STATUS, {"state": "thinking", "detail": "Transcribing..."})
        text = await self.transcriber.transcribe(audio)

        if not text or not text.strip():
            log.info("no clear speech transcribed")
            return

        clean_text = text.strip()
        for prefix in ("jarvis", "hey jarvis", "hello jarvis", "ok jarvis"):
            if clean_text.lower().startswith(prefix):
                clean_text = clean_text[len(prefix):].lstrip(",.:; ")

        if not clean_text:
            clean_text = "Hello Jarvis"

        log.info("user voice command: '%s'", clean_text)
        if self.on_transcript_callback:
            try:
                self.on_transcript_callback(clean_text)
            except Exception:
                pass

        await self.bus.publish(Topics.STATUS, {"state": "thinking", "detail": "Thinking..."})
        result = await self.engine.turn(clean_text)

        reply_text = result.text if hasattr(result, "text") else str(result)
        log.info("jarvis response: %s", reply_text[:100])

        await self.bus.publish(Topics.STATUS, {"state": "speaking", "detail": "Speaking..."})
        await self.synthesizer.speak(reply_text)

    async def _play_wake_chime(self) -> None:
        try:
            import sounddevice as sd
            t = np.linspace(0, 0.08, int(SAMPLE_RATE * 0.08), False)
            tone1 = 0.15 * np.sin(2 * np.pi * 587.33 * t)  # D5
            tone2 = 0.15 * np.sin(2 * np.pi * 880.00 * t)  # A5
            chime = np.concatenate([tone1, tone2])
            sd.play(chime.astype(np.float32), samplerate=SAMPLE_RATE)
        except Exception:
            pass
