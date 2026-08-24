"""System Tray Icon and integration for JARVIS.

Allows JARVIS to stay active in the background, listening for voice commands
even when the main HUD window is minimized or closed.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app.computer.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from app.ui.theme import COLOR_ACCENT, COLOR_BG


def create_tray_icon() -> QIcon:
    """Generate a high-res glowing cyan JARVIS tray icon."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Dark background circle
    painter.setBrush(QColor(COLOR_BG))
    painter.setPen(QColor(COLOR_ACCENT))
    painter.drawEllipse(4, 4, 56, 56)

    # Inner glowing dot
    painter.setBrush(QColor(COLOR_ACCENT))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(20, 20, 24, 24)

    painter.end()
    return QIcon(pixmap)


class JarvisTrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        parent_window: QWidget,
        voice_listener=None,
        on_exit_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        icon = create_tray_icon()
        super().__init__(icon, parent_window)
        self.parent_window = parent_window
        self.voice_listener = voice_listener
        self.on_exit_callback = on_exit_callback

        self.setToolTip("JARVIS — AI Operating Layer")
        self._setup_menu()
        self.activated.connect(self._on_tray_activated)

    def _setup_menu(self) -> None:
        menu = QMenu(self.parent_window)

        self.show_action = QAction("Open JARVIS HUD", menu)
        self.show_action.triggered.connect(self._toggle_show_window)
        menu.addAction(self.show_action)

        menu.addSeparator()

        self.mute_action = QAction("Mute Voice", menu)
        self.mute_action.setCheckable(True)
        self.mute_action.setChecked(False)
        self.mute_action.triggered.connect(self._toggle_voice_mute)
        menu.addAction(self.mute_action)

        self.autostart_action = QAction("Start with Windows", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(is_autostart_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)

        menu.addSeparator()

        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self._handle_exit)
        menu.addAction(exit_action)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_show_window()

    def _toggle_show_window(self) -> None:
        if self.parent_window.isVisible():
            self.parent_window.hide()
            self.show_action.setText("Open JARVIS HUD")
        else:
            self.parent_window.showNormal()
            self.parent_window.activateWindow()
            self.show_action.setText("Hide JARVIS HUD")

    def _toggle_voice_mute(self) -> None:
        if self.voice_listener:
            is_muted = self.mute_action.isChecked()
            self.voice_listener.set_muted(is_muted)

    def _toggle_autostart(self) -> None:
        if self.autostart_action.isChecked():
            enable_autostart(start_in_tray=True)
            self.showMessage("JARVIS", "Auto-start enabled! JARVIS will boot with Windows.", QSystemTrayIcon.Information, 3000)
        else:
            disable_autostart()
            self.showMessage("JARVIS", "Auto-start disabled.", QSystemTrayIcon.Information, 3000)

    def _handle_exit(self) -> None:
        self.hide()
        if self.on_exit_callback:
            self.on_exit_callback()
        if self.voice_listener:
            self.voice_listener.stop()
        self.parent_window.close()
