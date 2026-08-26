"""Creates a Windows Desktop and Start Menu shortcut for JARVIS,
and enables auto-start on laptop boot.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.computer.autostart import enable_autostart


def create_jarvis_icon(icon_path: Path) -> None:
    """Generate a high-res glowing cyan JARVIS icon."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark background circle
    draw.ellipse([10, 10, 246, 246], fill=(9, 13, 22, 255), outline=(0, 240, 255, 255), width=8)

    # Middle cyan ring
    draw.ellipse([50, 50, 206, 206], outline=(0, 200, 255, 180), width=4)

    # Core glowing dot
    draw.ellipse([85, 85, 171, 171], fill=(0, 240, 255, 255))
    draw.ellipse([105, 105, 151, 151], fill=(255, 255, 255, 255))

    img.save(str(icon_path), format="ICO", sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])


def create_desktop_shortcut():
    desktop = Path.home() / "Desktop"
    icon_file = root / "jarvis.ico"
    try:
        create_jarvis_icon(icon_file)
    except Exception:
        pass

    pythonw_exe = root / ".venv" / "Scripts" / "pythonw.exe"
    run_py = root / "run.py"

    if sys.platform != "win32":
        print("Desktop shortcuts are only supported on Windows.")
        return

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")

        # 1. Create Desktop Shortcut (.lnk) pointing directly to pythonw.exe
        desktop_lnk = desktop / "JARVIS.lnk"
        shortcut = shell.CreateShortCut(str(desktop_lnk))
        shortcut.TargetPath = str(pythonw_exe if pythonw_exe.exists() else sys.executable)
        shortcut.Arguments = f'"{run_py}" app'
        shortcut.WorkingDirectory = str(root)
        shortcut.Description = "JARVIS - Personal AI Operating Layer"
        shortcut.WindowStyle = 1  # Normal window
        if icon_file.exists():
            shortcut.IconLocation = f"{icon_file},0"
        shortcut.Save()
        print(f"[OK] Created Desktop Shortcut: {desktop_lnk}")

        # 2. Also create a 1-click Batch launcher on Desktop as a secondary direct option
        desktop_bat = desktop / "JARVIS.bat"
        desktop_bat.write_text(f'@echo off\ncd /d "{root}"\ncall run.bat app\n', encoding="utf-8")
        print(f"[OK] Created Desktop Batch Launcher: {desktop_bat}")

        # 3. Create silent background VBS launcher on Desktop
        desktop_vbs = desktop / "JARVIS.vbs"
        vbs_content = (
            'Set WshShell = CreateObject("WScript.Shell")\n'
            'Set FSO = CreateObject("Scripting.FileSystemObject")\n'
            f'ScriptDir = "{root}"\n'
            'WshShell.CurrentDirectory = ScriptDir\n'
            f'VenvPython = ScriptDir & "\\.venv\\Scripts\\pythonw.exe"\n'
            'If Not FSO.FileExists(VenvPython) Then\n'
            '    VenvPython = "pythonw.exe"\n'
            'End If\n'
            'WshShell.Run """" & VenvPython & """ """ & ScriptDir & "\\run.py"" app", 0, False\n'
        )
        desktop_vbs.write_text(vbs_content, encoding="utf-8")
        print(f"[OK] Created Desktop VBS Launcher: {desktop_vbs}")

        # 4. Enable Windows Autostart on Boot
        ok = enable_autostart(start_in_tray=True)
        if ok:
            print("[OK] Enabled Windows Startup: JARVIS will now auto-start when your laptop boots!")

    except Exception as exc:
        print(f"[X] Error: {exc}")


if __name__ == "__main__":
    create_desktop_shortcut()
