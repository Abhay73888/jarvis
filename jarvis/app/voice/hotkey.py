"""Global Hotkey Manager for Windows & Desktop Environments.

Registers system-wide hotkeys:
- Ctrl + Space: Push-to-Talk alternative (triggers voice listening)
- Ctrl + Shift + Space: Emergency Stop (instantly aborts active tasks & speech)
"""
from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

from app.core.logging import get_logger

log = get_logger("voice.hotkey")

# Windows Win32 API Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
VK_SPACE = 0x20


class GlobalHotkeyManager:
    """Manages system-wide hotkeys on a background worker thread."""

    HOTKEY_PTT_ID = 201
    HOTKEY_EMERGENCY_STOP_ID = 202

    def __init__(
        self,
        on_push_to_talk: Optional[Callable[[], None]] = None,
        on_emergency_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_push_to_talk = on_push_to_talk
        self.on_emergency_stop = on_emergency_stop
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._registered_ids: list[int] = []

    def start(self) -> bool:
        """Start listening for global hotkeys in the background."""
        if self._running or sys.platform != "win32":
            return False

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop listening and unregister hotkeys."""
        self._running = False
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.PostQuitMessage(0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        msg = wintypes.MSG()

        # Force message queue creation
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        # 1. Ctrl + Space -> Push to Talk
        res_ptt = user32.RegisterHotKey(
            None,
            self.HOTKEY_PTT_ID,
            MOD_CONTROL | MOD_NOREPEAT,
            VK_SPACE,
        )
        if res_ptt:
            self._registered_ids.append(self.HOTKEY_PTT_ID)
            log.info("Registered global hotkey: Ctrl+Space (Push-to-Talk)")
        else:
            log.warning("Could not register global hotkey Ctrl+Space (ID=%d)", self.HOTKEY_PTT_ID)

        # 2. Ctrl + Shift + Space -> Emergency Stop
        res_stop = user32.RegisterHotKey(
            None,
            self.HOTKEY_EMERGENCY_STOP_ID,
            MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT,
            VK_SPACE,
        )
        if res_stop:
            self._registered_ids.append(self.HOTKEY_EMERGENCY_STOP_ID)
            log.info("Registered global hotkey: Ctrl+Shift+Space (Emergency Stop)")
        else:
            log.warning("Could not register global hotkey Ctrl+Shift+Space (ID=%d)", self.HOTKEY_EMERGENCY_STOP_ID)

        while self._running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res > 0:
                if msg.message == WM_HOTKEY:
                    hotkey_id = msg.wParam
                    if hotkey_id == self.HOTKEY_PTT_ID:
                        log.info("Hotkey triggered: Push-to-Talk (Ctrl+Space)")
                        if self.on_push_to_talk:
                            try:
                                self.on_push_to_talk()
                            except Exception as exc:
                                log.warning("PTT callback error: %s", exc)

                    elif hotkey_id == self.HOTKEY_EMERGENCY_STOP_ID:
                        log.info("Hotkey triggered: Emergency Stop (Ctrl+Shift+Space)")
                        if self.on_emergency_stop:
                            try:
                                self.on_emergency_stop()
                            except Exception as exc:
                                log.warning("Emergency stop callback error: %s", exc)

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                break

        # Cleanup
        for hid in self._registered_ids:
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
        self._registered_ids.clear()
