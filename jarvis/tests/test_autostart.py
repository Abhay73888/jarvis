"""Tests for Windows Startup Autostart utilities."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

from app.computer.autostart import (
    disable_autostart,
    enable_autostart,
    get_shortcut_path,
    get_windows_startup_dir,
    is_autostart_enabled,
)


def test_startup_dir_resolution():
    dir_path = get_windows_startup_dir()
    assert isinstance(dir_path, Path)
    assert "Startup" in str(dir_path)


def test_shortcut_path_resolution():
    shortcut = get_shortcut_path()
    assert isinstance(shortcut, Path)
    assert shortcut.name == "JARVIS.vbs"


def test_autostart_enable_and_disable(tmp_path: Path):
    mock_startup_dir = tmp_path / "Startup"
    mock_startup_dir.mkdir()

    with patch("app.computer.autostart.get_windows_startup_dir", return_value=mock_startup_dir), \
         patch("app.computer.autostart.get_shortcut_path", return_value=mock_startup_dir / "JARVIS.vbs"), \
         patch("sys.platform", "win32"):

        assert not is_autostart_enabled()

        # Enable autostart
        ok = enable_autostart(start_in_tray=True)
        assert ok
        assert is_autostart_enabled()
        vbs_text = (mock_startup_dir / "JARVIS.vbs").read_text(encoding="utf-8")
        assert "JARVIS" in vbs_text or "run.py" in vbs_text

        # Disable autostart
        disabled = disable_autostart()
        assert disabled
        assert not is_autostart_enabled()
