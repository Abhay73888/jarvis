"""Global Hotkey Manager for Windows.

Registers system-wide hotkeys:
- Ctrl + Shift + J (Primary AI toggle)
- Ctrl + Alt + J (Secondary AI toggle)
- Alt + J (AI quick toggle)
- Ctrl + Shift + A (Assistant toggle)
- F8 (Single Key toggle)
- Ctrl + Shift + K (Terminal toggle)
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
from typing import Optional

from PySide6.QtCore import QThread, Signal

from app.core.logging import get_logger

log = get_logger("ui.hotkey")

# Windows API Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_F8 = 0x77


class GlobalHotkeyThread(QThread):
    hotkey_triggered = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = True
        self._win32_thread_id: int = 0
        self.registered_ids: list[int] = []

    def run(self) -> None:
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._win32_thread_id = kernel32.GetCurrentThreadId()

        msg = wintypes.MSG()
        # Force message queue initialization on this thread
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        # Windows Global Shortcuts for JARVIS HUD Toggle
        combos = [
            (MOD_CONTROL | MOD_SHIFT, ord("J"), 100, "Ctrl + Shift + J"),
            (MOD_CONTROL | MOD_ALT, ord("J"), 105, "Ctrl + Alt + J"),
            (MOD_ALT, ord("J"), 101, "Alt + J"),
            (MOD_CONTROL | MOD_SHIFT, ord("A"), 102, "Ctrl + Shift + A"),
            (0, VK_F8, 103, "F8"),
            (MOD_CONTROL | MOD_SHIFT, ord("K"), 104, "Ctrl + Shift + K"),
        ]

        for mods, vk, hid, name in combos:
            res = user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk)
            if res:
                self.registered_ids.append(hid)
                log.info("Registered Windows global shortcut '%s' (ID=%d)", name, hid)

        if not self.registered_ids:
            log.warning("could not register global hotkeys")
            return

        while self._running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res > 0:
                if msg.message == WM_HOTKEY and msg.wParam in self.registered_ids:
                    log.info("Global hotkey triggered (ID=%d)", msg.wParam)
                    self.hotkey_triggered.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                break

        for hid in self.registered_ids:
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
        self.registered_ids.clear()

    def stop(self) -> None:
        self._running = False
        if sys.platform == "win32" and self._win32_thread_id:
            try:
                user32 = ctypes.windll.user32
                user32.PostThreadMessageW(self._win32_thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
