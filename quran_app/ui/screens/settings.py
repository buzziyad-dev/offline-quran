"""
Settings screen — font size, reciter, translation, theme, audio path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider,
        QPushButton, QFileDialog, QFrame
    )
    from PySide6.QtCore import Qt, Signal
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider,
        QPushButton, QFileDialog, QFrame
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal

from quran_app.theme import DEFAULT_QURAN_FONT_SIZE, MIN_QURAN_FONT_SIZE, MAX_QURAN_FONT_SIZE
from quran_app.data.models import TranslationSource


class SettingsScreen(QWidget):
    themeChanged = Signal(str)
    fontSizeChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        # Font size
        row = QHBoxLayout()
        row.addWidget(QLabel("Quran font size:"))
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(MIN_QURAN_FONT_SIZE, MAX_QURAN_FONT_SIZE)
        self.font_slider.setValue(DEFAULT_QURAN_FONT_SIZE)
        self.font_slider.setFixedWidth(160)
        self.font_slider.valueChanged.connect(self._on_font)
        row.addWidget(self.font_slider)
        self.font_label = QLabel(f"{DEFAULT_QURAN_FONT_SIZE}pt")
        row.addWidget(self.font_label)
        row.addStretch()
        layout.addLayout(row)

        # Theme
        row = QHBoxLayout()
        row.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.currentTextChanged.connect(self.themeChanged.emit)
        row.addWidget(self.theme_combo)
        row.addStretch()
        layout.addLayout(row)

        # Translation
        row = QHBoxLayout()
        row.addWidget(QLabel("Translation:"))
        self.trans_combo = QComboBox()
        self.trans_combo.addItem("None", None)
        row.addWidget(self.trans_combo)
        row.addStretch()
        layout.addLayout(row)

        # Audio path
        row = QHBoxLayout()
        row.addWidget(QLabel("Audio folder:"))
        self.audio_path_label = QLabel("Not set")
        self.audio_path_label.setStyleSheet("color: #6B7280;")
        row.addWidget(self.audio_path_label, stretch=1)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse_audio)
        row.addWidget(self.browse_btn)
        layout.addLayout(row)

        layout.addStretch()

        note = QLabel("Audio: point to a folder containing reciter subfolders.\nFull Quran audio is ~1GB — bundle only a sample or let the user choose a folder.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6B7280; font-size: 11px; background: #F9FAFB; padding: 8px; border-radius: 6px;")
        layout.addWidget(note)

    def _on_font(self, v: int) -> None:
        self.font_label.setText(f"{v}pt")
        self.fontSizeChanged.emit(v)

    def _browse_audio(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select audio folder")
        if path:
            self.audio_path_label.setText(path)

    def set_translation_sources(self, sources: list[TranslationSource]) -> None:
        self.trans_combo.clear()
        self.trans_combo.addItem("None", None)
        for s in sources:
            self.trans_combo.addItem(f"{s.display_name} ({s.language})", s.id)

    def set_values(self, font_size: int, theme: str, audio_path: Optional[str]) -> None:
        self.font_slider.setValue(font_size)
        self.theme_combo.setCurrentText(theme)
        if audio_path:
            self.audio_path_label.setText(audio_path)

    def get_audio_path(self) -> Optional[str]:
        t = self.audio_path_label.text()
        return None if t in ("Not set", "") else t
