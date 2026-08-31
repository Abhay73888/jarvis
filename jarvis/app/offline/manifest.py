"""Offline Manifest tracking for JARVIS models and offline assets.

Persists component statuses and file paths in data/models/offline-manifest.json
so that resources are downloaded once and verified offline forever.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psutil

from app.core.logging import get_logger
from app.utils.paths import get_paths

log = get_logger("offline.manifest")


class OfflineManifestManager:
    """Manages data/models/offline-manifest.json."""

    def __init__(self, manifest_path: Optional[Path] = None) -> None:
        if manifest_path is None:
            models_dir = get_paths().data / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            self.manifest_path = models_dir / "offline-manifest.json"
        else:
            self.manifest_path = manifest_path

    @staticmethod
    def get_system_ram_gb() -> float:
        """Returns total physical system RAM in GB rounded to 1 decimal."""
        try:
            return round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except Exception:
            return 8.0

    @classmethod
    def get_recommended_model(cls) -> tuple[str, str]:
        """Returns (model_name, ram_tier) based on system RAM."""
        ram = cls.get_system_ram_gb()
        if ram < 12.0:
            return ("qwen2.5:3b", "8GB (low/mid RAM)")
        return ("qwen2.5:7b", "16GB+ (high RAM)")

    def load(self) -> dict[str, Any]:
        """Loads existing manifest or initializes a default template."""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log.warning("could not read offline-manifest.json: %s", exc)

        model_id, tier = self.get_recommended_model()
        ram_gb = self.get_system_ram_gb()
        default_manifest: dict[str, Any] = {
            "version": "1.0.0",
            "system_ram_gb": ram_gb,
            "ram_tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "components": {
                "ollama": {
                    "provider": "ollama",
                    "model": model_id,
                    "endpoint": "http://localhost:11434",
                    "ready": False,
                    "details": "Local LLM chat reasoning",
                },
                "whisper": {
                    "model": "small",
                    "languages": ["hi", "en", "hinglish"],
                    "path": str(get_paths().data / "models" / "whisper-small"),
                    "ready": False,
                    "details": "Offline faster-whisper STT int8 CPU",
                },
                "openwakeword": {
                    "models": ["jarvis", "hey_jarvis"],
                    "path": str(get_paths().data / "models" / "openwakeword"),
                    "ready": False,
                    "details": "Continuous offline wake word listener",
                },
                "piper_tts": {
                    "voices": ["hi_IN-swara", "en_IN-pratham", "en_US-lessac"],
                    "fallback": "pyttsx3 (Zira/David)",
                    "path": str(get_paths().data / "models" / "piper"),
                    "ready": False,
                    "details": "Piper neural female TTS voice synthesis",
                },
                "tesseract_ocr": {
                    "languages": ["eng", "hin"],
                    "path": str(get_paths().data / "models" / "tessdata"),
                    "ready": False,
                    "details": "Local Tesseract OCR data for screen reading",
                },
            },
        }
        return default_manifest

    def save(self, data: dict[str, Any]) -> None:
        """Saves manifest dictionary to disk atomically."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.manifest_path)
        log.info("saved offline manifest to %s", self.manifest_path)

    def update_component(self, name: str, ready: bool, **kwargs: Any) -> None:
        """Update status and attributes of a component in the manifest."""
        data = self.load()
        if "components" not in data:
            data["components"] = {}
        if name not in data["components"]:
            data["components"][name] = {}
        data["components"][name]["ready"] = ready
        for k, v in kwargs.items():
            data["components"][name][k] = v
        self.save(data)

    def is_component_ready(self, name: str) -> bool:
        data = self.load()
        return bool(data.get("components", {}).get(name, {}).get("ready", False))

    def all_ready(self) -> bool:
        data = self.load()
        comps = data.get("components", {})
        return bool(comps) and all(c.get("ready", False) for c in comps.values())
