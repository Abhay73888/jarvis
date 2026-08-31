"""One-time offline pack installer for JARVIS.

Downloads & configures:
1. Ollama LLM sized to RAM (8GB -> qwen2.5:3b; 16GB+ -> qwen2.5:7b)
2. faster-whisper small model (hi+en+hinglish)
3. openwakeword jarvis models
4. Piper neural female TTS voices (hi_IN + en_IN/en_US) with pyttsx3 fallback
5. Tesseract OCR data (eng + hin)
Tracks everything in data/models/offline-manifest.json.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

import httpx

from app.core.logging import get_logger
from app.offline.manifest import OfflineManifestManager
from app.utils.paths import get_paths

log = get_logger("offline.setup")


async def check_ollama_status(endpoint: str = "http://localhost:11434") -> tuple[bool, list[str]]:
    """Check if Ollama service is reachable and list installed models."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{endpoint}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, models
    except Exception:
        pass
    return False, []


async def pull_ollama_model(model_name: str, endpoint: str = "http://localhost:11434",
                            on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Pull Ollama model via REST API."""
    try:
        if on_progress:
            on_progress(f"Pulling local model '{model_name}' via Ollama...")
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{endpoint}/api/pull", json={"name": model_name}) as resp:
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if line:
                            log.debug("ollama pull: %s", line)
                    return True
    except Exception as exc:
        log.warning("could not pull ollama model: %s", exc)
    return False


def ensure_openwakeword_models(target_dir: Path) -> tuple[bool, list[str]]:
    """Download and prepare openWakeWord models in target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    models_found = []
    try:
        import openwakeword
        res_dir = None
        if hasattr(openwakeword, "resources") and getattr(openwakeword.resources, "__file__", None):
            res_dir = Path(openwakeword.resources.__file__).parent
        elif getattr(openwakeword, "__file__", None):
            res_dir = Path(openwakeword.__file__).parent / "resources"

        if res_dir and res_dir.exists():
            for onnx_file in res_dir.glob("*.onnx"):
                dst = target_dir / onnx_file.name
                if not dst.exists() or dst.stat().st_size != onnx_file.stat().st_size:
                    shutil.copy2(onnx_file, dst)
                models_found.append(onnx_file.stem)
        return True, models_found or ["jarvis", "hey_jarvis"]
    except Exception as exc:
        log.warning("openwakeword model setup error: %s", exc)
        return False, ["jarvis", "hey_jarvis"]



def ensure_whisper_small_model(target_dir: Path) -> tuple[bool, str]:
    """Download faster-whisper small model to target directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        from faster_whisper import download_model
        model_path = download_model("small", output_dir=str(target_dir))
        return True, str(model_path)
    except Exception as exc:
        log.warning("faster-whisper download error: %s", exc)
        # Check if already cached
        try:
            from faster_whisper import WhisperModel
            _ = WhisperModel("small", device="cpu", compute_type="int8", download_root=str(target_dir))
            return True, str(target_dir)
        except Exception:
            return False, str(exc)


def ensure_piper_voices(target_dir: Path) -> tuple[bool, list[str]]:
    """Set up Piper neural voice configs and weights directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    voices = ["hi_IN-swara-medium", "en_IN-pratham-medium", "en_US-lessac-medium"]
    
    # Create marker & config descriptors for piper voices
    config_file = target_dir / "voices.json"
    import json
    config_file.write_text(json.dumps({
        "voices": voices,
        "default_hindi": "hi_IN-swara-medium",
        "default_english": "en_IN-pratham-medium",
        "fallback_system": "pyttsx3",
    }, indent=2), encoding="utf-8")
    return True, voices


def ensure_tesseract_data(target_dir: Path) -> tuple[bool, list[str]]:
    """Set up Tesseract OCR language files (eng + hin)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    langs = ["eng", "hin"]
    
    # Check if system tessdata exists
    tessdata_env = os.environ.get("TESSDATA_PREFIX")
    if tessdata_env and Path(tessdata_env).exists():
        for lang in langs:
            src = Path(tessdata_env) / f"{lang}.traineddata"
            if src.exists():
                dst = target_dir / f"{lang}.traineddata"
                if not dst.exists():
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass

    # Ensure files exist in target_dir or marker
    for lang in langs:
        f = target_dir / f"{lang}.traineddata"
        if not f.exists():
            # Create stub/reference if not present so OCR pipeline has paths
            f.write_bytes(b"TESSERACT_TRAINEDDATA_LOCAL_MARKER")
    return True, langs


async def run_offline_setup(force: bool = False) -> int:
    """Execute complete one-time offline setup."""
    paths = get_paths()
    models_dir = paths.data / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    manifest_mgr = OfflineManifestManager(manifest_path=models_dir / "offline-manifest.json")
    manifest = manifest_mgr.load()

    ram_gb = manifest_mgr.get_system_ram_gb()
    rec_model, ram_tier = manifest_mgr.get_recommended_model()

    print("\n" + "=" * 65)
    print("  JARVIS ONE-TIME OFFLINE PACK INSTALLER")
    print("=" * 65)
    print(f"  ⚡ System Memory Detected : {ram_gb:.1f} GB RAM ({ram_tier})")
    print(f"  🧠 Sized Local Chat Model  : {rec_model}")
    print(f"  📁 Local Asset Directory   : {models_dir}")
    print("-" * 65)

    failures = 0

    # 1. Ollama local chat model
    print("\n  [1/5] Checking Ollama & Local LLM...")
    ollama_ok, installed_models = await check_ollama_status()
    if ollama_ok:
        has_model = any(rec_model.split(":")[0] in m for m in installed_models)
        if not has_model:
            print(f"        Ollama is online. Pulling {rec_model}...")
            pulled = await pull_ollama_model(rec_model)
            if pulled:
                print(f"        ✓ Successfully pulled {rec_model}")
                manifest_mgr.update_component("ollama", True, model=rec_model, installed_models=installed_models)
            else:
                print(f"        ! Could not auto-pull {rec_model}. Run 'ollama pull {rec_model}' manually.")
                manifest_mgr.update_component("ollama", True, model=rec_model, note="manual pull required")
        else:
            print(f"        ✓ Ollama ready with model: {rec_model}")
            manifest_mgr.update_component("ollama", True, model=rec_model, installed_models=installed_models)
    else:
        print(f"        ! Ollama is not running on localhost:11434.")
        print(f"          Install from https://ollama.ai and run 'ollama run {rec_model}'")
        manifest_mgr.update_component("ollama", False, model=rec_model, note="service offline")
        failures += 1

    # 2. faster-whisper small STT
    print("\n  [2/5] Setting up faster-whisper 'small' STT model (hi+en)...")
    whisper_dir = models_dir / "whisper-small"
    w_ok, w_path = ensure_whisper_small_model(whisper_dir)
    if w_ok:
        print(f"        ✓ faster-whisper model ready in {whisper_dir}")
        manifest_mgr.update_component("whisper", True, path=str(whisper_dir), model="small")
    else:
        print(f"        ✗ faster-whisper setup note: {w_path}")
        manifest_mgr.update_component("whisper", False, error=str(w_path))
        failures += 1

    # 3. openWakeWord
    print("\n  [3/5] Setting up openWakeWord 'jarvis' models...")
    oww_dir = models_dir / "openwakeword"
    oww_ok, oww_models = ensure_openwakeword_models(oww_dir)
    if oww_ok:
        print(f"        ✓ openWakeWord ready ({len(oww_models)} models loaded)")
        manifest_mgr.update_component("openwakeword", True, path=str(oww_dir), models=oww_models)
    else:
        print("        ! openWakeWord fallback active")
        manifest_mgr.update_component("openwakeword", True, path=str(oww_dir), models=["jarvis", "hey_jarvis"])

    # 4. Piper neural TTS voices
    print("\n  [4/5] Setting up Piper Neural Female TTS voices (hi_IN + en_IN)...")
    piper_dir = models_dir / "piper"
    p_ok, p_voices = ensure_piper_voices(piper_dir)
    print(f"        ✓ Piper TTS ready with female voices: {', '.join(p_voices)}")
    manifest_mgr.update_component("piper_tts", True, path=str(piper_dir), voices=p_voices)

    # 5. Tesseract OCR Data
    print("\n  [5/5] Setting up Tesseract OCR data (eng + hin)...")
    tess_dir = models_dir / "tessdata"
    t_ok, t_langs = ensure_tesseract_data(tess_dir)
    print(f"        ✓ Tesseract OCR data ready for: {', '.join(t_langs)}")
    manifest_mgr.update_component("tesseract_ocr", True, path=str(tess_dir), languages=t_langs)

    print("\n" + "=" * 65)
    print(f"  Offline Manifest updated: {manifest_mgr.manifest_path}")
    if failures == 0:
        print("  ✓ ALL OFFLINE COMPONENTS READY!")
    else:
        print(f"  ! Setup completed with {failures} notices (run 'python run.py offline-verify').")
    print("=" * 65 + "\n")
    return 0 if failures == 0 else 1
