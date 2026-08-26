"""Continuous Voice Listener for JARVIS with Automatic Gain Control (AGC) & Barge-in.

Captures microphone audio locally (16kHz mono), monitors for local wake words
('Jarvis' / 'Hey Jarvis' via openwakeword), plays chime + 'Yes?' prompt, records
user commands until silence (VAD), and runs them through:
  transcriber (faster-whisper) -> AgentEngine.turn() -> synthesizer (TTS).

Supports:
- Local wake word & Push-to-Talk (Ctrl + Space)
- Emergency Stop (Ctrl + Shift + Space)
- Spoken Barge-in Interrupts ('stop' / 'ruk jao' / 'abort')
- Adaptive noise floor and AGC for quiet laptop microphones.
"""
from __future__ import annotations

import asyncio
import collections
import time
from typing import Callable, Optional

import numpy as np

from app.brain.engine import AgentEngine
from app.config.settings import Settings
from app.core.events import EventBus, Topics
from app.core.logging import get_logger
from app.voice.hotkey import GlobalHotkeyManager
from app.voice.state import AudioProcessor, BargeInDetector, VoiceState, VoiceStateMachine
from app.voice.synthesizer import VoiceSynthesizer
from app.voice.transcriber import VoiceTranscriber

log = get_logger("voice.listener")

SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 80  # 80ms chunk = 1280 samples @ 16kHz
CHUNK_SIZE = int(SAMPLE_RATE * (CHUNK_DURATION_MS / 1000.0))
MAX_RECORD_DURATION_S = 10.0
DEFAULT_WAKE_THRESHOLD = 0.15


class VoiceListener:
    """Production-grade hands-free voice loop for JARVIS."""

    def __init__(
        self,
        engine: AgentEngine,
        bus: EventBus,
        settings: Optional[Settings] = None,
        transcriber: Optional[VoiceTranscriber] = None,
        synthesizer: Optional[VoiceSynthesizer] = None,
        on_wake_callback: Optional[Callable[[], None]] = None,
        on_transcript_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.engine = engine
        self.bus = bus
        self.settings = settings
        self.transcriber = transcriber or VoiceTranscriber()
        self.synthesizer = synthesizer or VoiceSynthesizer(bus=bus)
        self.on_wake_callback = on_wake_callback
        self.on_transcript_callback = on_transcript_callback

        self._running = False
        self._muted = False
        self._is_recording_command = False
        self._manual_trigger = asyncio.Event()
        self._stream = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._wakeword_model = None
        self._wakeword_loaded = False
        self._noise_floor = 0.001

        self.state_machine = VoiceStateMachine(self._on_state_change)
        self.barge_in = BargeInDetector()
        self.hotkeys: Optional[GlobalHotkeyManager] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_muted(self) -> bool:
        return self._muted

    def _on_state_change(self, prev: VoiceState, new_state: VoiceState) -> None:
        log.debug("voice state changed: %s -> %s", prev.value, new_state.value)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        log.info("voice listener muted: %s", muted)

    def trigger_manual_listen(self) -> None:
        """Manually trigger voice listening immediately (Push-to-Talk)."""
        if self._running and not self._is_recording_command:
            log.info("manual voice trigger requested (Push-to-Talk)")
            self._manual_trigger.set()

    def emergency_stop(self) -> None:
        """Emergency stop: cancel speech and active tasks immediately."""
        log.info("emergency stop triggered via hotkey/barge-in")
        self.synthesizer.stop()
        self.engine.interrupt()
        self.state_machine.on_interrupt()
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.bus.publish(Topics.STATUS, {"state": "idle", "detail": "Stopped"}),
                self._loop,
            )

    def _init_wakeword(self) -> None:
        if not self._wakeword_loaded:
            self._wakeword_loaded = True
            try:
                import openwakeword
                from openwakeword.model import Model
                openwakeword.utils.download_models()
                wake_words = ["hey_jarvis", "jarvis"]
                if self.settings and self.settings.voice.wake_words:
                    wake_words = [w.lower().replace(" ", "_") for w in self.settings.voice.wake_words]
                self._wakeword_model = Model(wakeword_models=wake_words, inference_framework="onnx")
                log.info("openwakeword initialized for wake words: %s", wake_words)
            except Exception as exc:
                log.info("openwakeword fallback / unavailable: %s", exc)
                self._wakeword_model = None

    def _init_hotkeys(self) -> None:
        try:
            self.hotkeys = GlobalHotkeyManager(
                on_push_to_talk=self.trigger_manual_listen,
                on_emergency_stop=self.emergency_stop,
            )
            self.hotkeys.start()
        except Exception as exc:
            log.warning("could not initialize global hotkeys: %s", exc)

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._loop = asyncio.get_running_loop()
        self._init_wakeword()
        self._init_hotkeys()

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
                amplified = AudioProcessor.apply_agc(raw_chunk)
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
            await self.bus.publish(Topics.STATUS, {"state": "error", "detail": f"Mic error: {exc}"})
        finally:
            self._running = False
            self._stream = None
            if self.hotkeys:
                self.hotkeys.stop()

    def stop(self) -> None:
        self._running = False
        if self.synthesizer:
            self.synthesizer.stop()
        if self.hotkeys:
            self.hotkeys.stop()

    async def _process_audio_stream(self, queue: asyncio.Queue[np.ndarray]) -> None:
        pre_roll = collections.deque(maxlen=int(2.0 / (CHUNK_DURATION_MS / 1000.0)))

        while self._running:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.15)
            except asyncio.TimeoutError:
                if self._manual_trigger.is_set():
                    pass
                else:
                    continue

            # Check for spoken barge-in if synthesizer is speaking
            if self.synthesizer.is_speaking:
                rms = AudioProcessor.calculate_rms(chunk)
                if AudioProcessor.is_speech(rms, self._noise_floor, multiplier=2.5, min_threshold=0.01):
                    # Spoken activity detected during speech -> sample and test barge-in
                    pass

            if self._muted:
                continue

            pre_roll.append(chunk)

            # Update adaptive background noise floor
            rms = AudioProcessor.calculate_rms(chunk)
            self._noise_floor = AudioProcessor.update_noise_floor(self._noise_floor, rms)

            wake_detected = self._check_wake_word(chunk)
            manual_triggered = self._manual_trigger.is_set()

            if wake_detected or manual_triggered:
                self._manual_trigger.clear()
                self._is_recording_command = True
                self.state_machine.on_wake_detected()
                log.info("Voice trigger activated (wake=%s, manual=%s). Prompting 'Yes?'...", wake_detected, manual_triggered)

                if self.on_wake_callback:
                    try:
                        self.on_wake_callback()
                    except Exception:
                        pass

                await self.bus.publish(Topics.STATUS, {"state": "listening", "detail": "Listening..."})
                await self._play_wake_chime()

                # Prompt 'Yes?'
                self.state_machine.on_prompt_start()
                if self.settings and self.settings.voice.speak_responses:
                    await self.synthesizer.prompt_yes()

                # Record user command
                self.state_machine.on_recording_start()
                utterance_audio = await self._record_utterance(queue, pre_roll)
                if utterance_audio is not None and len(utterance_audio) > SAMPLE_RATE * 0.4:
                    await self._handle_utterance(utterance_audio)

                self._is_recording_command = False
                self.state_machine.on_idle()
                await self.bus.publish(Topics.STATUS, {"state": "idle", "detail": "Ready"})
                pre_roll.clear()

    def _check_wake_word(self, chunk: np.ndarray) -> bool:
        if self._wakeword_model is not None and (not self.settings or self.settings.voice.wake_enabled):
            try:
                int16_chunk = (chunk * 32767).astype(np.int16)
                predictions = self._wakeword_model.predict(int16_chunk)
                thresh = self.settings.voice.wake_threshold if self.settings else DEFAULT_WAKE_THRESHOLD
                for model_name, score in predictions.items():
                    if score >= thresh:
                        log.info("WAKE WORD DETECTED: '%s' (score=%.2f >= %.2f)", model_name, score, thresh)
                        self._wakeword_model.reset()
                        return True
            except Exception as exc:
                log.debug("wakeword error: %s", exc)
        return False

    async def _record_utterance(
        self,
        queue: asyncio.Queue[np.ndarray],
        pre_roll: collections.deque,
    ) -> Optional[np.ndarray]:
        recorded_chunks = list(pre_roll)
        silence_start: Optional[float] = None
        has_spoken = False
        start_time = time.time()
        max_duration = self.settings.voice.max_record_duration_s if self.settings else MAX_RECORD_DURATION_S
        silence_limit = self.settings.voice.silence_duration_s if self.settings else 1.2

        while self._running and (time.time() - start_time < max_duration):
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.35)
            except asyncio.TimeoutError:
                break

            recorded_chunks.append(chunk)
            rms = AudioProcessor.calculate_rms(chunk)

            if AudioProcessor.is_speech(rms, self._noise_floor, multiplier=1.8, min_threshold=0.0003):
                has_spoken = True
                silence_start = None
            else:
                if has_spoken:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start >= silence_limit:
                        log.debug("end of speech detected (silence duration >= %.1fs)", silence_limit)
                        break

        if not recorded_chunks:
            return None

        full_audio = np.concatenate(recorded_chunks)
        return AudioProcessor.normalize_audio(full_audio, target_peak=0.7)

    async def _handle_utterance(self, audio: np.ndarray) -> None:
        self.state_machine.on_transcribe_start()
        await self.bus.publish(Topics.STATUS, {"state": "thinking", "detail": "Transcribing..."})
        text = await self.transcriber.transcribe(audio)

        if not text or not text.strip():
            log.info("no clear speech transcribed")
            return

        clean_text = text.strip()

        # Check for barge-in / interrupt commands
        if self.barge_in.is_barge_in(clean_text):
            log.info("barge-in interrupt command detected: '%s'", clean_text)
            self.emergency_stop()
            return

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

        self.state_machine.on_thinking_start()
        await self.bus.publish(Topics.STATUS, {"state": "thinking", "detail": "Thinking..."})
        result = await self.engine.turn(clean_text)

        reply_text = result.text if hasattr(result, "text") else str(result)
        log.info("jarvis response: %s", reply_text[:100])

        self.state_machine.on_speaking_start()
        await self.bus.publish(Topics.STATUS, {"state": "speaking", "detail": "Speaking..."})
        if not self.settings or self.settings.voice.speak_responses:
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
