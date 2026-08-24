"""Speech-to-Text (STT) transcriber for JARVIS using faster-whisper.

Transcribes multilingual audio (English, Hindi, Hinglish) with fast, local inference.
Runs on CPU by default with INT8 quantization for minimal resource usage.
"""
from __future__ import annotations

import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.logging import get_logger
from app.utils.paths import get_paths

log = get_logger("voice.transcriber")


class VoiceTranscriber:
    def __init__(self, model_size: str = "base", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self._model = None
        self._loading = False
        self._model_dir = get_paths().data / "models" / "whisper"

    def _get_model(self):
        """Lazy loader for faster-whisper WhisperModel."""
        if self._model is None and not self._loading:
            self._loading = True
            try:
                from faster_whisper import WhisperModel
                self._model_dir.mkdir(parents=True, exist_ok=True)
                log.info("loading faster-whisper model '%s' (compute=%s)...", self.model_size, self.compute_type)
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type=self.compute_type,
                    download_root=str(self._model_dir),
                )
                log.info("faster-whisper model loaded successfully")
            except Exception as exc:
                log.error("failed to load faster-whisper: %s", exc)
                self._model = None
            finally:
                self._loading = False
        return self._model

    async def transcribe(self, audio_data: np.ndarray | bytes | str | Path, sample_rate: int = 16000) -> str:
        """Transcribe audio asynchronously.

        Args:
            audio_data: 1D numpy array of 16kHz float32 audio, or bytes / file path.
            sample_rate: Sample rate of the audio (default 16000).

        Returns:
            Transcribed text string.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_transcribe, audio_data, sample_rate)

    def _sync_transcribe(self, audio_data: np.ndarray | bytes | str | Path, sample_rate: int = 16000) -> str:
        model = self._get_model()
        if model is None:
            log.warning("whisper model not available for transcription")
            return ""

        try:
            # If numpy array, ensure float32 normalized [-1.0, 1.0]
            if isinstance(audio_data, np.ndarray):
                if audio_data.ndim > 1:
                    audio_data = audio_data.mean(axis=1)  # convert to mono
                if audio_data.dtype == np.int16:
                    audio_data = audio_data.astype(np.float32) / 32768.0
                elif audio_data.dtype != np.float32:
                    audio_data = audio_data.astype(np.float32)

                segments, info = model.transcribe(
                    audio_data,
                    beam_size=3,
                    language=None,  # auto-detect language (Hindi / English)
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                )
            else:
                # File path or stream
                segments, info = model.transcribe(
                    str(audio_data),
                    beam_size=3,
                    vad_filter=True,
                )

            text_parts = [segment.text.strip() for segment in segments]
            full_text = " ".join(text_parts).strip()
            log.debug("transcribed text: '%s' (detected lang: %s, prob: %.2f)",
                      full_text, getattr(info, 'language', 'unknown'), getattr(info, 'language_probability', 0.0))
            return full_text
        except Exception as exc:
            log.warning("transcription error: %s", exc)
            return ""
