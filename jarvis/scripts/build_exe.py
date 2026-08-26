"""PyInstaller packaging script for JARVIS (Spec Phase 14).

Builds a standalone onedir Windows executable (JARVIS.exe) that runs
without requiring manual python commands. Keeps .env and config/ external.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def build():
    print("=" * 60)
    print("JARVIS Standalone Executable Builder (PyInstaller)")
    print("=" * 60)

    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    dist_dir = root / "dist"
    build_dir = root / "build"
    icon_path = root / "jarvis.ico"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "JARVIS",
        "--paths", str(root),
        "--collect-all", "openwakeword",
        "--collect-all", "faster_whisper",
        "--collect-all", "PySide6",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    cmd.append(str(root / "run.py"))

    print(f"Executing: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(root))

    # Copy external configuration folders to dist/JARVIS
    output_dir = dist_dir / "JARVIS"
    if output_dir.exists():
        for item in ("config", ".env.example"):
            src = root / item
            dst = output_dir / item
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            elif src.is_file():
                shutil.copy2(src, dst)
        print(f"\n[OK] Build complete! Executable located at:\n     {output_dir / 'JARVIS.exe'}")


if __name__ == "__main__":
    build()
