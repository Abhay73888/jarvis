"""God-Level Cybernetic Holographic Sci-Fi Theme for JARVIS HUD.

Inspired by Advanced AI Civilization, Iron Man JARVIS Hologram HUD,
and Quantum Computing Operating Interfaces.
"""
from __future__ import annotations

# ==============================================================================
# COLOR PALETTE (Kardashev Type II / Cyber Obsidian & Holographic Neon)
# ==============================================================================
COLOR_BG_VOID = "#03060f"           # Deep cosmic obsidian
COLOR_BG_SURFACE = "#070d1d"        # Deep glass surface
COLOR_BG_CARD = "#0c152d"           # Elevated cyber panel
COLOR_BG_CARD_HOVER = "#122044"     # Hover state panel

COLOR_ACCENT = "#00f0ff"            # Holographic Laser Cyan (Primary)
COLOR_ACCENT_GLOW = "#38f8ff"       # High energy cyan glow
COLOR_ACCENT_MUTED = "#007a99"      # Deep cyan accent
COLOR_ACCENT_DIM = "rgba(0, 240, 255, 0.12)"
COLOR_ACCENT_BORDER = "rgba(0, 240, 255, 0.28)"

COLOR_PLASMA_BLUE = "#0088ff"       # Deep Quantum Blue
COLOR_EMERALD = "#00ffa3"           # Quantum Emerald (Online / Listening)
COLOR_AMBER = "#ffb700"             # Solar Gold / Thinking
COLOR_CRIMSON = "#ff2a55"           # Protocol Red / Alert
COLOR_PURPLE = "#a855f7"            # Neural Synapse Purple

COLOR_TEXT_PRIMARY = "#f0f8ff"      # Brilliant holographic white
COLOR_TEXT_SECONDARY = "#8da2bf"    # Sleek cyber metallic grey
COLOR_TEXT_MUTED = "#4d607b"        # Muted telemetry text
COLOR_BORDER = "rgba(0, 240, 255, 0.18)"
COLOR_BORDER_FOCUS = "#00f0ff"

# Backward compatibility aliases
COLOR_BG = COLOR_BG_VOID
COLOR_SURFACE = COLOR_BG_SURFACE
COLOR_CARD = COLOR_BG_CARD
COLOR_ACCENT_HOVER = COLOR_ACCENT_GLOW
COLOR_SUCCESS = COLOR_EMERALD
COLOR_WARNING = COLOR_AMBER
COLOR_DANGER = COLOR_CRIMSON

# ==============================================================================
# GLOBAL STYLESHEET (Cybernetic Holographic HUD)
# ==============================================================================
STYLESHEET = f"""
/* Global Reset & Base */
QMainWindow, QDialog {{
    background-color: {COLOR_BG_VOID};
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, -apple-system, sans-serif;
}}

QWidget#CentralWidget {{
    background: qlineargradient(
        spread: pad, x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #03060f, stop: 0.5 #060b18, stop: 1 #040812
    );
}}

/* Header HUD Bar */
QFrame#HeaderBar {{
    background-color: {COLOR_BG_SURFACE};
    border-bottom: 1px solid {COLOR_BORDER};
    border-top: 1px solid rgba(0, 240, 255, 0.35);
}}

QLabel#TitleLabel {{
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 4px;
    color: {COLOR_ACCENT};
}}

QLabel#VersionBadge {{
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {COLOR_PLASMA_BLUE};
    background-color: rgba(0, 136, 255, 0.12);
    border: 1px solid rgba(0, 136, 255, 0.3);
    border-radius: 4px;
    padding: 2px 6px;
}}

QLabel#StatusBadge {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {COLOR_ACCENT};
    background-color: {COLOR_ACCENT_DIM};
    border: 1px solid {COLOR_ACCENT_BORDER};
    border-radius: 12px;
    padding: 3px 12px;
}}

/* Futuristic Tab Bar */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background-color: transparent;
    border-radius: 8px;
}}

QTabBar::tab {{
    background-color: {COLOR_BG_SURFACE};
    color: {COLOR_TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    padding: 8px 16px;
    margin-right: 4px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_ACCENT};
    border-top: 2px solid {COLOR_ACCENT};
    border-left: 1px solid {COLOR_ACCENT_BORDER};
    border-right: 1px solid {COLOR_ACCENT_BORDER};
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLOR_BG_CARD_HOVER};
    color: {COLOR_TEXT_PRIMARY};
}}

/* Telemetry HUD Bar */
QFrame#TelemetryHUD {{
    background-color: rgba(7, 13, 29, 0.85);
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 4px 10px;
}}

QLabel.TelemetryLabel {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
    font-family: 'Consolas', 'Cascadia Code', monospace;
}}

/* Scroll Area */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QWidget#ScrollContent {{
    background-color: transparent;
}}

/* Futuristic Input Controls */
QLineEdit {{
    background-color: {COLOR_BG_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
    selection-background-color: {COLOR_ACCENT_MUTED};
}}

QLineEdit:focus {{
    border: 1px solid {COLOR_ACCENT};
    background-color: {COLOR_BG_CARD};
}}

/* Cyber Buttons */
QPushButton {{
    background-color: {COLOR_BG_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_CARD_HOVER};
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT};
}}

QPushButton:pressed {{
    background-color: rgba(0, 240, 255, 0.25);
}}

QPushButton#PrimaryTransmit {{
    background: qlineargradient(
        spread: pad, x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #00d2ff, stop: 1 #00f0ff
    );
    color: #03060f;
    font-weight: 800;
    letter-spacing: 1px;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
}}

QPushButton#PrimaryTransmit:hover {{
    background: qlineargradient(
        spread: pad, x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #38f8ff, stop: 1 #ffffff
    );
}}

QPushButton#MicButton {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT_BORDER};
    border-radius: 8px;
    font-weight: 700;
    padding: 8px 14px;
}}

QPushButton#MicButton:hover {{
    background-color: rgba(0, 240, 255, 0.18);
    border-color: {COLOR_ACCENT};
}}

QPushButton#IconButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 13px;
}}

QPushButton#IconButton:hover {{
    background-color: rgba(0, 240, 255, 0.15);
    color: {COLOR_ACCENT};
}}

/* Quick Action Chips */
QPushButton.ActionChip {{
    background-color: rgba(12, 21, 45, 0.7);
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid rgba(0, 240, 255, 0.2);
    border-radius: 14px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}

QPushButton.ActionChip:hover {{
    background-color: rgba(0, 240, 255, 0.15);
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT};
}}

/* Cyber Tool & Protocol Cards */
QFrame.ProtocolCard {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 12px;
}}

QFrame.ProtocolCard:hover {{
    border-color: {COLOR_ACCENT};
    background-color: {COLOR_BG_CARD_HOVER};
}}

/* Custom Cyber Scrollbar */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: rgba(0, 240, 255, 0.2);
    border-radius: 3px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background: {COLOR_BG_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {COLOR_ACCENT};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {COLOR_ACCENT_GLOW};
    border: 2px solid #ffffff;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}}

/* Combo Boxes */
QComboBox {{
    background-color: {COLOR_BG_SURFACE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}}

QComboBox:hover {{
    border-color: {COLOR_ACCENT};
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_ACCENT_MUTED};
    border: 1px solid {COLOR_BORDER};
}}
"""
