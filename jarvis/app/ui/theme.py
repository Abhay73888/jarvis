"""Theme and Stylesheet definitions for JARVIS PySide6 Desktop GUI.

Curated dark glassmorphism aesthetic with cyber-cyan glowing accents.
"""
from __future__ import annotations

# Color Palette
COLOR_BG = "#090d16"
COLOR_SURFACE = "#111726"
COLOR_CARD = "#172033"
COLOR_ACCENT = "#00f0ff"
COLOR_ACCENT_HOVER = "#33f3ff"
COLOR_ACCENT_MUTED = "#008899"
COLOR_TEXT_PRIMARY = "#f0f6fc"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_TEXT_MUTED = "#566070"
COLOR_BORDER = "#1f2a3f"
COLOR_BORDER_FOCUS = "#00f0ff"
COLOR_SUCCESS = "#00e676"
COLOR_WARNING = "#ffab00"
COLOR_DANGER = "#ff5252"

STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}}

QWidget#CentralWidget {{
    background-color: {COLOR_BG};
}}

QFrame#HeaderBar {{
    background-color: {COLOR_SURFACE};
    border-bottom: 1px solid {COLOR_BORDER};
}}

QFrame#StatsBar {{
    background-color: {COLOR_SURFACE};
    border-radius: 8px;
    border: 1px solid {COLOR_BORDER};
    padding: 6px 12px;
}}

QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QLabel#TitleLabel {{
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 2px;
    color: {COLOR_ACCENT};
}}

QLabel#StatusBadge {{
    font-size: 11px;
    font-weight: 600;
    color: {COLOR_ACCENT};
    background-color: rgba(0, 240, 255, 0.12);
    border: 1px solid {COLOR_ACCENT_MUTED};
    border-radius: 10px;
    padding: 2px 10px;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QWidget#ScrollContent {{
    background-color: transparent;
}}

QLineEdit {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: {COLOR_ACCENT_MUTED};
}}

QLineEdit:focus {{
    border: 1px solid {COLOR_BORDER_FOCUS};
    background-color: {COLOR_CARD};
}}

QPushButton {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLOR_CARD};
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT};
}}

QPushButton:pressed {{
    background-color: rgba(0, 240, 255, 0.2);
}}

QPushButton#PrimaryButton {{
    background-color: {COLOR_ACCENT};
    color: #000000;
    font-weight: 600;
    border: none;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}

QPushButton#IconButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
    color: {COLOR_TEXT_SECONDARY};
}}

QPushButton#IconButton:hover {{
    background-color: {COLOR_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_ACCENT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
"""
