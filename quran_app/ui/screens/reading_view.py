"""
Reading View — RTL verse list, verse numbers, tap-to-play per ayah, font slider, translation toggle.
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QScrollArea, QSlider, QCheckBox, QFrame
    )
    from PySide6.QtCore import Qt, Signal
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QScrollArea, QSlider, QCheckBox, QFrame
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal

from quran_app.data.models import Ayah, Surah, Translation
from quran_app.ui.widgets.verse_widget import VerseWidget
from quran_app.theme import DEFAULT_QURAN_FONT_SIZE, MIN_QURAN_FONT_SIZE, MAX_QURAN_FONT_SIZE


class ReadingView(QWidget):
    backRequested = Signal()
    playRequested = Signal(int, int)  # surah, ayah

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._surah: Optional[Surah] = None
        self._ayahs: list[Ayah] = []
        self._translations: dict[tuple[int, int], str] = {}  # (surah,ayah) -> text
        self._show_translation = False
        self._font_size = DEFAULT_QURAN_FONT_SIZE
        self._verse_widgets: list[VerseWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("QFrame { background: white; border-bottom: 1px solid #E5E7EB; }")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)
        self.back_btn = QPushButton("← Surahs")
        self.back_btn.setFlat(True)
        self.back_btn.clicked.connect(self.backRequested.emit)
        hl.addWidget(self.back_btn)
        hl.addStretch()
        self.title_label = QLabel("—")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self.title_label)
        hl.addStretch()
        # Spacer to balance
        hl.addWidget(QLabel(""))
        layout.addWidget(header)

        # Controls bar: font slider + translation toggle
        controls = QFrame()
        controls.setStyleSheet("QFrame { background: #F9FAFB; border-bottom: 1px solid #E5E7EB; }")
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(12, 6, 12, 6)
        cl.addWidget(QLabel("Font:"))
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(MIN_QURAN_FONT_SIZE, MAX_QURAN_FONT_SIZE)
        self.font_slider.setValue(self._font_size)
        self.font_slider.setFixedWidth(140)
        self.font_slider.valueChanged.connect(self._on_font_changed)
        cl.addWidget(self.font_slider)
        self.font_label = QLabel(f"{self._font_size}pt")
        self.font_label.setFixedWidth(36)
        cl.addWidget(self.font_label)
        cl.addSpacing(12)
        self.trans_check = QCheckBox("Translation")
        self.trans_check.toggled.connect(self._on_trans_toggled)
        cl.addWidget(self.trans_check)
        cl.addStretch()
        layout.addWidget(controls)

        # Scrollable verses
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: #FFFEFB; }")
        self.container = QWidget()
        self.verses_layout = QVBoxLayout(self.container)
        self.verses_layout.setContentsMargins(12, 12, 12, 12)
        self.verses_layout.setSpacing(10)
        self.verses_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, stretch=1)

    def set_surah(self, surah: Surah, ayahs: list[Ayah], translations: Optional[dict[tuple[int, int], str]] = None) -> None:
        self._surah = surah
        self._ayahs = ayahs
        if translations is not None:
            self._translations = translations
        self.title_label.setText(f"{surah.name_arabic} — {surah.name_english} ({surah.ayah_count})")
        self._rebuild_verses()
        # Scroll to top
        self.scroll.verticalScrollBar().setValue(0)

    def _rebuild_verses(self) -> None:
        # Clear existing (keep stretch at end)
        while self.verses_layout.count() > 1:
            item = self.verses_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._verse_widgets.clear()

        for ayah in self._ayahs:
            t = self._translations.get((ayah.surah_number, ayah.ayah_number)) if self._show_translation else None
            vw = VerseWidget(
                surah_number=ayah.surah_number,
                ayah_number=ayah.ayah_number,
                text_uthmani=ayah.text_uthmani,
                translation=t,
                font_size_pt=self._font_size,
            )
            vw.playRequested.connect(self.playRequested.emit)
            # Insert before stretch
            self.verses_layout.insertWidget(self.verses_layout.count() - 1, vw)
            self._verse_widgets.append(vw)

    def _on_font_changed(self, v: int) -> None:
        self._font_size = v
        self.font_label.setText(f"{v}pt")
        for w in self._verse_widgets:
            w.set_font_size(v)

    def _on_trans_toggled(self, on: bool) -> None:
        self._show_translation = on
        for w in self._verse_widgets:
            if on:
                t = self._translations.get((w.surah_number, w.ayah_number))
                w.set_translation(t)
            else:
                w.set_translation(None)

    def highlight_ayah(self, ayah_number: int) -> None:
        for w in self._verse_widgets:
            w.set_highlighted(w.ayah_number == ayah_number)
        # Scroll to highlighted
        for w in self._verse_widgets:
            if w.ayah_number == ayah_number:
                self.scroll.ensureWidgetVisible(w)
                break

    def update_translations(self, translations: dict[tuple[int, int], str]) -> None:
        self._translations = translations
        if self._show_translation:
            for w in self._verse_widgets:
                w.set_translation(translations.get((w.surah_number, w.ayah_number)))
