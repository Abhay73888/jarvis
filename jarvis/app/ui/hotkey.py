"""Global Hotkey Manager for Windows.

Registers system-wide hotkeys:
- Alt + J (Primary AI toggle)
- Ctrl + Shift + A (Assistant)
- F8 (Single Key toggle)
- Ctrl + Shift + K
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

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
VK_F8 = 0x77


class GlobalHotkeyThread(QThread):
    hotkey_triggered = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = True
        self.registered_ids: list[int] = []

    def run(self) -> None:
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32
        msg = wintypes.MSG()
        # Force message queue initialization on this thread
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        # Free verified shortcuts
        combos = [
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
                    log.debug("global hotkey triggered: %d", msg.wParam)
                    self.hotkey_triggered.emit()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                break

        for hid in self.registered_ids:
            user32.UnregisterHotKey(None, hid)

    def stop(self) -> None:
        self._running = False
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            user32.PostQuitMessage(0)
