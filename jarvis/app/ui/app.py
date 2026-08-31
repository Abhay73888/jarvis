"""Application launcher for JARVIS Desktop GUI & Voice system.

Initializes PySide6 QApplication, async background runtime, VoiceListener,
Global Windows Hotkey (Ctrl + Shift + J), and System Tray integration.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.core.logging import get_logger
from app.main import build_runtime
from app.ui.dialogs import GuiPermissionBridge
from app.ui.hotkey import GlobalHotkeyThread
from app.ui.tray import JarvisTrayIcon
from app.ui.window import MainWindow
from app.voice.listener import VoiceListener
from app.voice.synthesizer import VoiceSynthesizer
from app.voice.transcriber import VoiceTranscriber

log = get_logger("ui.app")


def _toggle_window(window: MainWindow) -> None:
    """Toggle visibility and force-focus of the main HUD window."""
    if window.isVisible() and window.isActiveWindow() and not window.isMinimized():
        window.hide()
    else:
        window.showNormal()
        window.activateWindow()
        window.raise_()
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(window.winId())
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
            except Exception:
                pass
        if hasattr(window, "input_edit"):
            window.input_edit.setFocus()



def run_gui_app(start_in_tray: bool = False, enable_voice: bool = True) -> int:
    """Entry point for the PySide6 Desktop GUI."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setQuitOnLastWindowClosed(False)

    # 1. Initialize Async Runtime on a dedicated background event loop
    async_loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=async_loop.run_forever, daemon=True)
    loop_thread.start()

    # Pre-create main window dummy container for bridge or full window
    bridge = GuiPermissionBridge(parent_window=None)
    confirm_handler = bridge.create_async_handler(async_loop)

    # Build runtime asynchronously with UI permission confirm handler
    future_runtime = asyncio.run_coroutine_threadsafe(
        build_runtime(confirm_handler=confirm_handler), async_loop
    )
    runtime = future_runtime.result(timeout=15.0)

    # 2. Initialize Voice Subsystem
    voice_listener: Optional[VoiceListener] = None
    if enable_voice:
        try:
            transcriber = VoiceTranscriber()
            synthesizer = VoiceSynthesizer(bus=runtime.bus)
            voice_listener = VoiceListener(
                engine=runtime.engine,
                bus=runtime.bus,
                settings=runtime.settings,
                transcriber=transcriber,
                synthesizer=synthesizer,
            )
            # Start listener on the async background loop
            asyncio.run_coroutine_threadsafe(voice_listener.start(), async_loop)
            log.info("background voice listener started")
        except Exception as exc:
            log.warning("could not start voice listener: %s", exc)

    # 3. Create Main Window & Tray Icon
    window = MainWindow(
        engine=runtime.engine,
        bus=runtime.bus,
        settings=runtime.settings,
        voice_listener=voice_listener,
        async_loop=async_loop,
        on_close_to_tray_callback=lambda: window.hide(),
    )
    bridge.parent_window = window

    # 4. Initialize Windows Global Hotkey (Ctrl + Shift + J)
    hotkey_thread: Optional[GlobalHotkeyThread] = None
    if sys.platform == "win32":
        try:
            hotkey_thread = GlobalHotkeyThread()
            hotkey_thread.hotkey_triggered.connect(lambda: _toggle_window(window))
            hotkey_thread.start()
            log.info("global hotkey listener started (Ctrl + Shift + J)")
        except Exception as exc:
            log.warning("could not register global hotkey: %s", exc)

    tray = JarvisTrayIcon(
        parent_window=window,
        settings=runtime.settings,
        voice_listener=voice_listener,
        on_exit_callback=lambda: _cleanup(async_loop, voice_listener, hotkey_thread, app),
    )
    tray.show()

    if not start_in_tray:
        window.show()
        window.activateWindow()

    log.info("JARVIS GUI application active (tray=%s, voice=%s, hotkey=Ctrl+Shift+J)", start_in_tray, enable_voice)
    return app.exec()


def _cleanup(
    loop: asyncio.AbstractEventLoop,
    listener: Optional[VoiceListener],
    hotkey: Optional[GlobalHotkeyThread],
    app: QApplication,
) -> None:
    log.info("shutting down JARVIS GUI application...")
    if hotkey:
        hotkey.stop()
    if listener:
        listener.stop()
    loop.call_soon_threadsafe(loop.stop)
    app.quit()
