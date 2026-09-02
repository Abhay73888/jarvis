"""Text-to-Speech (TTS) Manager for JARVIS (Feature 2).

Supports:
  1. edge-tts (default, online, high-fidelity neural female voice: en-IN-NeerjaNeural).
  2. pyttsx3 (offline fallback, auto-selects system female voice e.g. Zira).
  3. Honest status reporting (never pretends to speak if engines are unavailable).
"""
from __future__ import annotations

import asyncio
import re
import sys
import tempfile
import threading
from pathlib import Path

from app.core.logging import get_logger

log = get_logger("voice.tts")

FEMALE_HINTS = (
    "zira", "neerja", "swara", "aria", "heera", "female", "hazel",
    "eva", "catherine", "susan", "linda", "jenny", "samantha",
)


def split_text_into_chunks(text: str, max_chars: int = 450) -> list[str]:
    """Split text at sentence boundaries into chunks of at most max_chars."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # Split by sentence-ending punctuation or newlines
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    curr_len = 0

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if curr_len + len(sent) + 1 <= max_chars:
            current.append(sent)
            curr_len += len(sent) + 1
        else:
            if current:
                chunks.append(" ".join(current))
                current = []
                curr_len = 0
            if len(sent) > max_chars:
                # Word-level fallback for unusually long single sentences
                words = sent.split()
                sub: list[str] = []
                sub_len = 0
                for w in words:
                    if sub_len + len(w) + 1 <= max_chars:
                        sub.append(w)
                        sub_len += len(w) + 1
                    else:
                        if sub:
                            chunks.append(" ".join(sub))
                        sub = [w]
                        sub_len = len(w)
                if sub:
                    chunks.append(" ".join(sub))
            else:
                current.append(sent)
                curr_len = len(sent)

    if current:
        chunks.append(" ".join(current))

    return chunks


class TTSManager:
    """Manages real text-to-speech synthesis with edge-tts and pyttsx3 fallback."""

    def __init__(
        self,
        voice: str = "en-IN-NeerjaNeural",
        rate: str = "+8%",
        gender: str = "female",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.gender = gender.lower()
        self._lock = threading.Lock()

    @staticmethod
    def check_availability() -> tuple[bool, str]:
        """Check if at least one real TTS engine is installed."""
        has_edge = False
        has_pyttsx3 = False

        try:
            import edge_tts  # noqa: F401
            has_edge = True
        except ImportError:
            pass

        try:
            import pyttsx3  # noqa: F401
            has_pyttsx3 = True
        except ImportError:
            pass

        if has_edge or has_pyttsx3:
            engines = []
            if has_edge:
                engines.append("edge-tts")
            if has_pyttsx3:
                engines.append("pyttsx3")
            return True, f"TTS available ({', '.join(engines)})"

        return False, (
            "No TTS engine available. Please install dependencies:\n"
            "  pip install edge-tts playsound==1.2.2 pyttsx3"
        )

    async def speak(self, text: str) -> bool:
        """Asynchronously synthesize and play speech. Returns True if speech was produced."""
        clean_text = self._clean_for_speech(text)
        if not clean_text:
            return False

        chunks = split_text_into_chunks(clean_text, max_chars=450)
        if not chunks:
            return False

        # 1. Try edge-tts (Primary online neural voice)
        edge_ok = await self._speak_edge_tts(chunks)
        if edge_ok:
            return True

        # 2. Try pyttsx3 (Offline fallback)
        log.info("edge-tts unavailable, falling back to pyttsx3 offline voice")
        pyttsx_ok = self._speak_pyttsx3(chunks)
        if pyttsx_ok:
            return True

        # 3. Honest failure notification
        available, msg = self.check_availability()
        log.warning("TTS failed: %s", msg)
        print(f"\n[Voice Output Unavailable] {msg}")
        return False

    def speak_sync(self, text: str) -> bool:
        """Synchronous wrapper for speak()."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run_coroutine_threadsafe(self.speak(text), loop).result(timeout=30)
            return loop.run_until_complete(self.speak(text))
        except RuntimeError:
            return asyncio.run(self.speak(text))

    async def _speak_edge_tts(self, chunks: list[str]) -> bool:
        try:
            import edge_tts
        except ImportError:
            return False

        for chunk in chunks:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = Path(f.name)

                communicate = edge_tts.Communicate(chunk, voice=self.voice, rate=self.rate)
                await communicate.save(str(tmp_path))

                if tmp_path.exists() and tmp_path.stat().st_size > 0:
                    played = await self._play_audio(tmp_path)
                    if not played:
                        return False
                else:
                    return False
            except Exception as exc:
                log.debug("edge-tts chunk error: %s", exc)
                return False
            finally:
                if tmp_path and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
        return True

    def _speak_pyttsx3(self, chunks: list[str]) -> bool:
        try:
            import pyttsx3
        except ImportError:
            return False

        with self._lock:
            try:
                engine = pyttsx3.init()
                self._configure_pyttsx3_voice(engine)
                for chunk in chunks:
                    engine.say(chunk)
                engine.runAndWait()
                return True
            except Exception as exc:
                log.debug("pyttsx3 error: %s", exc)
                return False

    def _configure_pyttsx3_voice(self, engine) -> None:
        """Configure female voice hint and ~160 wpm speech rate."""
        try:
            engine.setProperty("rate", 160)
            voices = engine.getProperty("voices")
            if not voices:
                return

            if self.gender == "female":
                for v in voices:
                    v_name = (v.name or "").lower()
                    v_id = (v.id or "").lower()
                    v_gender = str(getattr(v, "gender", "")).lower()
                    if "female" in v_gender or any(hint in v_name or hint in v_id for hint in FEMALE_HINTS):
                        engine.setProperty("voice", v.id)
                        return
        except Exception:
            pass

    async def _play_audio(self, path: Path) -> bool:
        """Play synthesized MP3 file using playsound."""
        loop = asyncio.get_running_loop()

        def _play():
            try:
                import playsound
                playsound.playsound(str(path))
                return True
            except Exception as exc:
                log.debug("playsound playback error: %s", exc)
                # Fallback to PowerShell Windows Media Player
                if sys.platform == "win32":
                    try:
                        import subprocess
                        cmd = [
                            "powershell", "-c",
                            f"(New-Object Media.SoundPlayer '{path}').PlaySync()"
                        ]
                        subprocess.run(cmd, capture_output=True, timeout=10)
                        return True
                    except Exception:
                        pass
                return False

        return await loop.run_in_executor(None, _play)

    @staticmethod
    def _clean_for_speech(text: str) -> str:
        """Strip markdown markers, code blocks, URLs, and asterisks for smooth speech."""
        if not text:
            return ""
        # Remove code blocks
        clean = re.sub(r"```[\s\S]*?```", " [code block omitted] ", text)
        clean = re.sub(r"`[^`]+`", " ", clean)
        # Remove URLs
        clean = re.sub(r"https?://\S+", " link ", clean)
        # Strip bold/italic markdown symbols and bullets
        clean = re.sub(r"[*_~#>-]", " ", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
