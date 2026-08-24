"""Desktop GUI + system tray for JARVIS (PySide6).

Provides:
- run_gui_app: Main launcher for the complete Desktop GUI application.
- MainWindow: Modern Glassmorphic HUD window.
- JarvisTrayIcon: Windows system tray icon and background controls.
"""
from __future__ import annotations

from app.ui.app import run_gui_app
from app.ui.tray import JarvisTrayIcon
from app.ui.window import MainWindow

__all__ = ["run_gui_app", "MainWindow", "JarvisTrayIcon"]
