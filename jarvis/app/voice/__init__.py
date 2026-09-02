"""Voice subsystem for JARVIS.

Provides:
- VoiceSynthesizer: Text-to-Speech via edge-tts (neural) & pyttsx3 (offline).
- VoiceTranscriber: Speech-to-Text via faster-whisper (multilingual Hindi/English).
- VoiceListener: Continuous background wake word detection and speech command execution.
"""
from __future__ import annotations

from app.voice.listener import VoiceListener
from app.voice.synthesizer import VoiceSynthesizer
from app.voice.transcriber import VoiceTranscriber

__all__ = ["VoiceListener", "VoiceSynthesizer", "VoiceTranscriber"]
