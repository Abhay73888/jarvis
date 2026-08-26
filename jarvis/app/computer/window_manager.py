"""Semantic Window Management for Windows Desktop (Spec Phase 5+).

Provides:
- Window enumeration with title, handle, and process identification.
- Semantic focus, minimize, maximize, restore, move, and resize actions by title substring.
- Platform-guarded implementation using Win32 API / ctypes.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger

log = get_logger("computer.windows")


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    process_name: str
    is_visible: bool
    is_minimized: bool


class WindowManager:
    """Manages active application windows on Windows."""

    @staticmethod
    def list_windows(visible_only: bool = True) -> list[WindowInfo]:
        """Enumerate top-level desktop windows."""
        if sys.platform != "win32":
            return []

        import ctypes
        from ctypes import wintypes
        import psutil

        user32 = ctypes.windll.user32
        windows: list[WindowInfo] = []

        def enum_proc(hwnd, lParam):
            if visible_only and not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

            if not title:
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            try:
                proc = psutil.Process(pid.value)
                proc_name = proc.name()
            except Exception:
                pass

            is_min = bool(user32.IsIconic(hwnd))
            is_vis = bool(user32.IsWindowVisible(hwnd))

            windows.append(WindowInfo(
                hwnd=hwnd,
                title=title,
                process_name=proc_name,
                is_visible=is_vis,
                is_minimized=is_min,
            ))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
        return windows

    @staticmethod
    def find_window(title_query: str) -> Optional[WindowInfo]:
        """Find the best matching window by case-insensitive title or process substring."""
        query = title_query.strip().lower()
        windows = WindowManager.list_windows(visible_only=False)

        # 1. Exact match on title
        for w in windows:
            if w.title.lower() == query:
                return w

        # 2. Substring match on title
        for w in windows:
            if query in w.title.lower():
                return w

        # 3. Substring match on process name
        for w in windows:
            if query in w.process_name.lower():
                return w

        return None

    @staticmethod
    def focus(title_query: str) -> tuple[bool, str]:
        """Bring window to foreground and focus it."""
        if sys.platform != "win32":
            return False, "Window control is only supported on Windows."

        import ctypes
        w = WindowManager.find_window(title_query)
        if not w:
            return False, f"No window found matching '{title_query}'."

        user32 = ctypes.windll.user32
        # Restore if minimized
        if w.is_minimized:
            user32.ShowWindow(w.hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(w.hwnd)
        return True, f"Focused window: '{w.title}'."

    @staticmethod
    def minimize(title_query: str) -> tuple[bool, str]:
        """Minimize a window by title."""
        if sys.platform != "win32":
            return False, "Window control is only supported on Windows."

        import ctypes
        w = WindowManager.find_window(title_query)
        if not w:
            return False, f"No window found matching '{title_query}'."

        user32 = ctypes.windll.user32
        user32.ShowWindow(w.hwnd, 6)  # SW_MINIMIZE
        return True, f"Minimized window: '{w.title}'."

    @staticmethod
    def maximize(title_query: str) -> tuple[bool, str]:
        """Maximize a window by title."""
        if sys.platform != "win32":
            return False, "Window control is only supported on Windows."

        import ctypes
        w = WindowManager.find_window(title_query)
        if not w:
            return False, f"No window found matching '{title_query}'."

        user32 = ctypes.windll.user32
        user32.ShowWindow(w.hwnd, 3)  # SW_MAXIMIZE
        return True, f"Maximized window: '{w.title}'."

    @staticmethod
    def restore(title_query: str) -> tuple[bool, str]:
        """Restore window to normal position and size."""
        if sys.platform != "win32":
            return False, "Window control is only supported on Windows."

        import ctypes
        w = WindowManager.find_window(title_query)
        if not w:
            return False, f"No window found matching '{title_query}'."

        user32 = ctypes.windll.user32
        user32.ShowWindow(w.hwnd, 9)  # SW_RESTORE
        return True, f"Restored window: '{w.title}'."

    @staticmethod
    def move_resize(title_query: str, x: int, y: int, width: int, height: int) -> tuple[bool, str]:
        """Move and resize a window."""
        if sys.platform != "win32":
            return False, "Window control is only supported on Windows."

        import ctypes
        w = WindowManager.find_window(title_query)
        if not w:
            return False, f"No window found matching '{title_query}'."

        user32 = ctypes.windll.user32
        user32.MoveWindow(w.hwnd, int(x), int(y), int(width), int(height), True)
        return True, f"Moved and resized '{w.title}' to ({x}, {y}, {width}x{height})."

    @staticmethod
    def close(title_query: str) -> tuple[bool, str]:
        """Send close message (WM_CLOSE) to window."""
        if sys.platform != "win32":
            return False, "Window control is only supported on Windows."

        import ctypes
        w = WindowManager.find_window(title_query)
        if not w:
            return False, f"No window found matching '{title_query}'."

        WM_CLOSE = 0x0010
        user32 = ctypes.windll.user32
        user32.PostMessageW(w.hwnd, WM_CLOSE, 0, 0)
        return True, f"Closed window: '{w.title}'."
