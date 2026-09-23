"""
Home / Surah List screen — searchable, shows number, Arabic name, English name, ayah count.
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QHBoxLayout
    from PySide6.QtCore import Qt, Signal
except ImportError:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QHBoxLayout
    from PyQt6.QtCore import Qt, pyqtSignal as Signal

from quran_app.data.models import Surah


class HomeScreen(QWidget):
    surahSelected = Signal(int)  # surah_number

    def __init__(self, surahs: list[Surah], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._all_surahs = surahs
        self._filtered = list(surahs)
        self._build_ui()
        self._populate(surahs)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("القرآن الكريم — Offline Quran")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0E7A5A; padding: 6px;")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search surah (e.g. البقرة, Baqara, Fatiha) …")
        self.search.textChanged.connect(self._on_search)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemClicked.connect(self._on_clicked)
        layout.addWidget(self.list, stretch=1)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

    def _populate(self, surahs: list[Surah]) -> None:
        self.list.clear()
        for s in surahs:
            # Display: "1 — الفاتحة — Al-Fatiha (7 ayahs) — Meccan"
            text = f"{s.surah_number:3d}  {s.name_arabic}  —  {s.name_english}  ({s.ayah_count})  ·  {s.revelation_type.value}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, s.surah_number)
            self.list.addItem(item)
        self.count_label.setText(f"{len(surahs)} surahs" if len(surahs) != 114 else "114 surahs")

    def _on_search(self, q: str) -> None:
        q = q.strip()
        if not q:
            self._populate(self._all_surahs)
            return
        q_lower = q.lower()
        filtered = [
            s for s in self._all_surahs
            if q in s.name_arabic or q_lower in s.name_english.lower()
            or (s.name_transliteration and q_lower in s.name_transliteration.lower())
            or q == str(s.surah_number)
        ]
        self._populate(filtered)

    def _on_clicked(self, item: QListWidgetItem) -> None:
        surah_num = int(item.data(Qt.ItemDataRole.UserRole))
        self.surahSelected.emit(surah_num)

    def update_surahs(self, surahs: list[Surah]) -> None:
        self._all_surahs = surahs
        self._populate(surahs)
        self.search.clear()
