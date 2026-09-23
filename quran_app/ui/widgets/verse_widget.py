"""
Verse rendering widget — uses QTextDocument (HTML) for correct Arabic shaping.

Spec §3.1: QTextDocument with rich text shapes complex Arabic ligatures more
reliably than plain QLabel. Force RTL, render Uthmani with diacritics,
pause marks, and verse-end marker ۝ + Arabic-Indic numerals.
"""

from __future__ import annotations

import html
from typing import Optional

try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QSizePolicy
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont
    QT_LIB = "PySide6"
except ImportError:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QSizePolicy
    from PyQt6.QtCore import Qt, pyqtSignal as Signal
    from PyQt6.QtGui import QFont
    QT_LIB = "PyQt6"

from quran_app.theme import QURAN_FONT_FAMILY


def _escape(s: str) -> str:
    return html.escape(s)


class VerseWidget(QWidget):
    """Single ayah display: Arabic (Uthmani), translation, play button, highlight."""

    playRequested = Signal(int, int)  # surah, ayah

    def __init__(
        self,
        surah_number: int,
        ayah_number: int,
        text_uthmani: str,
        translation: Optional[str] = None,
        font_size_pt: int = 22,
        highlighted: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.surah_number = surah_number
        self.ayah_number = ayah_number
        self.text_uthmani = text_uthmani
        self.translation = translation
        self.font_size_pt = font_size_pt
        self.highlighted = highlighted
        self._build_ui()
        self._apply_highlight()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Top row: ayah number + play button
        top = QHBoxLayout()
        self.badge = QLabel(f"{self.surah_number}:{self.ayah_number}")
        self.badge.setStyleSheet("color: #6B7280; font-size: 11px;")
        top.addWidget(self.badge)
        top.addStretch()
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(28, 28)
        self.play_btn.setToolTip("Play this ayah")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("QPushButton { border-radius: 14px; font-size: 10px; padding: 0; }")
        self.play_btn.clicked.connect(lambda: self.playRequested.emit(self.surah_number, self.ayah_number))
        top.addWidget(self.play_btn)
        layout.addLayout(top)

        # Arabic text — QLabel with rich text (uses QTextDocument internally, correct shaping)
        # Using QLabel instead of QTextBrowser avoids fixed-height miscalculation (width 0 at construction)
        self.arabic_label = QLabel()
        self.arabic_label.setWordWrap(True)
        self.arabic_label.setTextFormat(Qt.TextFormat.RichText)
        self.arabic_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.arabic_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.arabic_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.arabic_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.arabic_label.setStyleSheet("QLabel { border: none; background: transparent; }")
        layout.addWidget(self.arabic_label)

        # Translation (optional, LTR)
        self.trans_label = QLabel()
        self.trans_label.setWordWrap(True)
        self.trans_label.setTextFormat(Qt.TextFormat.PlainText)
        self.trans_label.setStyleSheet("color: #4B5563; font-size: 13px; padding-top: 4px;")
        self.trans_label.setVisible(bool(self.translation))
        if self.translation:
            self.trans_label.setText(self.translation)
        layout.addWidget(self.trans_label)

        self.setLayout(layout)
        self._render_arabic()

    def _render_arabic(self) -> None:
        from quran_app.data.text_utils import verse_end_marker

        marker = verse_end_marker(self.ayah_number)
        body = f"{_escape(self.text_uthmani)} <span style='color:#0E7A5A; font-weight:600;'>{_escape(marker)}</span>"
        html_doc = (
            f"<div dir='rtl' style=\"text-align:right; font-family:{QURAN_FONT_FAMILY}; "
            f"font-size:{self.font_size_pt}pt; line-height:180%;\">{body}</div>"
        )
        self.arabic_label.setText(html_doc)

    def _apply_highlight(self) -> None:
        if self.highlighted:
            self.setStyleSheet(
                "VerseWidget { background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 8px; }"
            )
        else:
            self.setStyleSheet(
                "VerseWidget { background: white; border: 1px solid #E5E7EB; border-radius: 8px; }"
            )

    # -- Public API --

    def set_highlighted(self, on: bool) -> None:
        self.highlighted = on
        self._apply_highlight()

    def set_font_size(self, pt: int) -> None:
        self.font_size_pt = pt
        self._render_arabic()

    def set_translation(self, text: Optional[str]) -> None:
        self.translation = text
        self.trans_label.setText(text or "")
        self.trans_label.setVisible(bool(text))
