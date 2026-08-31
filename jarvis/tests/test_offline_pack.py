"""Unit tests for Stage O1 — One-Time Offline Pack & Verification."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.offline.manifest import OfflineManifestManager
from app.offline.setup import (
    check_ollama_status,
    ensure_openwakeword_models,
    ensure_piper_voices,
    ensure_tesseract_data,
    ensure_whisper_small_model,
    run_offline_setup,
)
from app.offline.verifier import (
    run_offline_verify,
    verify_manifest,
    verify_offline_brain,
    verify_stt,
    verify_tts,
    verify_wakeword,
)


def test_manifest_manager_defaults_and_ram_sizing(tmp_path: Path):
    manifest_file = tmp_path / "offline-manifest.json"
    mgr = OfflineManifestManager(manifest_path=manifest_file)

    # Test RAM sizing logic
    with patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value = MagicMock(total=8 * (1024 ** 3))
        rec, tier = mgr.get_recommended_model()
        assert rec == "qwen2.5:3b"
        assert "8GB" in tier

        mock_vm.return_value = MagicMock(total=16 * (1024 ** 3))
        rec, tier = mgr.get_recommended_model()
        assert rec == "qwen2.5:7b"
        assert "16GB+" in tier

    # Test manifest persistence
    data = mgr.load()
    assert "components" in data
    assert "whisper" in data["components"]
    assert "piper_tts" in data["components"]
    assert "openwakeword" in data["components"]

    mgr.update_component("whisper", True, model="small")
    assert mgr.is_component_ready("whisper")
    assert manifest_file.exists()


def test_ensure_piper_and_tesseract_assets(tmp_path: Path):
    piper_dir = tmp_path / "piper"
    p_ok, voices = ensure_piper_voices(piper_dir)
    assert p_ok
    assert len(voices) >= 2
    assert (piper_dir / "voices.json").exists()

    tess_dir = tmp_path / "tessdata"
    t_ok, langs = ensure_tesseract_data(tess_dir)
    assert t_ok
    assert "eng" in langs
    assert "hin" in langs
    assert (tess_dir / "eng.traineddata").exists()


@pytest.mark.asyncio
async def test_offline_verifier_checks():
    r_manifest = await verify_manifest()
    assert r_manifest.status in ("PASS", "WARN")

    r_brain = await verify_offline_brain()
    assert r_brain.status == "PASS"

    r_tts = await verify_tts()
    assert r_tts.status == "PASS"

    r_stt = await verify_stt()
    assert r_stt.status in ("PASS", "WARN")

    r_wake = await verify_wakeword()
    assert r_wake.status in ("PASS", "WARN")

    # Full verifier run
    exit_code = await run_offline_verify()
    assert exit_code in (0, 1)


@pytest.mark.asyncio
async def test_run_offline_setup(tmp_path: Path):
    with patch("app.offline.setup.get_paths") as mock_paths:
        mock_paths.return_value = MagicMock(data=tmp_path)
        with patch("app.offline.setup.check_ollama_status", return_value=(True, ["qwen2.5:3b"])):
            with patch("app.offline.setup.ensure_whisper_small_model", return_value=(True, str(tmp_path / "models" / "whisper-small"))):
                exit_code = await run_offline_setup()
                assert exit_code in (0, 1)
                manifest_file = tmp_path / "models" / "offline-manifest.json"
                assert manifest_file.exists()

