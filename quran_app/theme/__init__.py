"""
Theme definitions — light/dark, font handling.
"""

from typing import Literal

ThemeName = Literal["light", "dark"]

LIGHT = {
    "bg": "#FFFEFB",
    "card": "#FFFFFF",
    "text": "#1A1A1A",
    "text_muted": "#6B7280",
    "primary": "#0E7A5A",
    "primary_hover": "#0A5E45",
    "border": "#E5E7EB",
    "highlight_bg": "#FEF3C7",
    "highlight_border": "#F59E0B",
}

DARK = {
    "bg": "#121212",
    "card": "#1E1E1E",
    "text": "#E5E7EB",
    "text_muted": "#9CA3AF",
    "primary": "#10B981",
    "primary_hover": "#059669",
    "border": "#374151",
    "highlight_bg": "#422006",
    "highlight_border": "#F59E0B",
}

# Quran font stack — Scheherazade New primary, Amiri Quran fallback (both OFL, Quran-tuned)
# Per review: Amiri Quran is distinct from plain Amiri — don't include plain Amiri, it would lose Quran shaping
QURAN_FONT_FAMILY = "'Scheherazade New', 'Amiri Quran', serif"
UI_FONT_FAMILY = "'Inter', 'Segoe UI', system-ui, sans-serif"

# Default sizes (pt)
DEFAULT_QURAN_FONT_SIZE = 22
MIN_QURAN_FONT_SIZE = 14
MAX_QURAN_FONT_SIZE = 40


def get_palette(name: ThemeName) -> dict[str, str]:
    return DARK if name == "dark" else LIGHT


def stylesheet(theme: ThemeName = "light") -> str:
    p = get_palette(theme)
    return f"""
    QWidget {{
        background-color: {p['bg']};
        color: {p['text']};
        font-family: {UI_FONT_FAMILY};
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QPushButton {{
        background-color: {p['primary']};
        color: white;
        border: none;
        padding: 6px 14px;
        border-radius: 6px;
    }}
    QPushButton:hover {{ background-color: {p['primary_hover']}; }}
    QPushButton:flat {{
        background: transparent;
        color: {p['primary']};
    }}
    QLineEdit, QTextEdit {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    QListWidget {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: 8px;
    }}
    QListWidget::item {{
        padding: 10px 12px;
        border-bottom: 1px solid {p['border']};
    }}
    QListWidget::item:selected {{
        background: {p['highlight_bg']};
        color: {p['text']};
        border-left: 3px solid {p['highlight_border']};
    }}
    QSlider::groove:horizontal {{
        height: 6px; background: {p['border']}; border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 16px; height: 16px; margin: -5px 0;
        background: {p['primary']}; border-radius: 8px;
    }}
    """
