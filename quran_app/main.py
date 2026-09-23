#!/usr/bin/env python3
"""
Offline Quran Desktop App - Main Entry Point
Sidebar layout: Quran reading is the home, surah navigation is a sidebar.
"""

import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QStackedWidget, QMessageBox,
        QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QSplitter, QLabel
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontDatabase
    QT_LIB = "PySide6"
except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QStackedWidget, QMessageBox,
        QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QFrame, QSplitter, QLabel
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFontDatabase
    QT_LIB = "PyQt6"

from quran_app.data.db import Database, initialize_database, get_database_path
from quran_app.data.repository import QuranRepository, AudioRepository
from quran_app.audio.audio_service import AudioService
from quran_app.theme import stylesheet


def setup_application() -> QApplication:
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("Offline Quran")
    app.setApplicationDisplayName("Offline Quran")
    app.setOrganizationName("OfflineQuran")
    app.setOrganizationDomain("offlinequran.local")
    return app


def load_fonts() -> None:
    fonts_dir = Path(__file__).parent / "assets" / "fonts"
    if not fonts_dir.exists():
        return
    for pat in ("*.ttf", "*.otf"):
        for font_file in fonts_dir.rglob(pat):
            fid = QFontDatabase.addApplicationFont(str(font_file))
            if fid == -1:
                print(f"Warning: Failed to load font {font_file}")
            else:
                try:
                    fams = QFontDatabase.applicationFontFamilies(fid)
                    print(f"Loaded font: {fams}")
                except Exception:
                    pass


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Offline Quran")
        self.resize(1100, 700)

        assets_dir = Path(__file__).parent / "assets"
        db_path = get_database_path()
        self.db = Database(db_path)
        initialize_database(self.db)
        self._seed_if_empty(assets_dir)

        self.quran_repo = QuranRepository(self.db)
        self.audio_repo = AudioRepository(self.db)
        self.audio_service = AudioService(audio_root=assets_dir / "audio")

        self._current_theme = self.quran_repo.get_setting("theme", "light") or "light"
        self.setStyleSheet(stylesheet(self._current_theme))  # type: ignore

        self._build_ui()
        self._load_initial_data()

    def _seed_if_empty(self, assets_dir: Path) -> None:
        row = self.db.fetchone("SELECT COUNT(*) as c FROM surahs")
        if row and row["c"] > 0:
            return
        data_dir = assets_dir / "data"
        if not (data_dir / "surahs.json").exists():
            print("No bundled data found — run: python -m quran_app.data.ingest")
            return
        import json
        from quran_app.data.models import Surah, Ayah
        from quran_app.data.db import seed_surahs, seed_ayahs
        try:
            surahs = [Surah(**s) for s in json.loads((data_dir / "surahs.json").read_text(encoding="utf-8"))]
            ayahs = [Ayah(**a) for a in json.loads((data_dir / "ayahs.json").read_text(encoding="utf-8"))]
            seed_surahs(self.db, surahs)
            seed_ayahs(self.db, ayahs)
            print(f"Seeded {len(surahs)} surahs, {len(ayahs)} ayahs from bundled assets")
            manifest = assets_dir / "audio_manifest.json"
            if manifest.exists():
                from quran_app.data.db import load_audio_manifest
                load_audio_manifest(self.db, manifest)
        except Exception as e:
            print(f"Seeding failed: {e}")

    def _build_ui(self) -> None:
        from quran_app.ui.screens.home_screen import HomeScreen
        from quran_app.ui.screens.reading_view import ReadingView
        from quran_app.ui.screens.audio_player import AudioPlayerScreen
        from quran_app.ui.screens.settings import SettingsScreen

        # Central splitter: sidebar | main content
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # --- Sidebar: surah navigation + quick actions ---
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        sidebar.setFixedWidth(300)
        sidebar.setStyleSheet("QFrame { background: #FFFFFF; border-right: 1px solid #E5E7EB; }")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Sidebar header
        hdr = QLabel("القرآن الكريم")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet("font-size: 15px; font-weight: 700; color: #0E7A5A; padding: 12px; border-bottom: 1px solid #E5E7EB;")
        sb_layout.addWidget(hdr)

        # Surah list (reused HomeScreen but without its own title)
        self.surah_list = HomeScreen([])
        # Remove HomeScreen's title duplication — keep search + list
        self.surah_list.surahSelected.connect(self.open_surah)
        sb_layout.addWidget(self.surah_list, stretch=1)

        # Bottom actions
        actions = QFrame()
        actions.setStyleSheet("QFrame { border-top: 1px solid #E5E7EB; background: #F9FAFB; }")
        al = QHBoxLayout(actions)
        al.setContentsMargins(8, 8, 8, 8)
        self.btn_audio = QPushButton("Audio")
        self.btn_audio.setFlat(True)
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setFlat(True)
        al.addWidget(self.btn_audio)
        al.addWidget(self.btn_settings)
        sb_layout.addWidget(actions)

        splitter.addWidget(sidebar)

        # --- Main stacked content: Reading is the home ---
        self.stack = QStackedWidget()
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.reading_view = ReadingView()
        # Back now just focuses sidebar
        self.reading_view.backRequested.connect(lambda: self.surah_list.search.setFocus())
        self.reading_view.playRequested.connect(self._play_ayah)
        self.stack.addWidget(self.reading_view)  # idx 0

        self.audio_screen = AudioPlayerScreen(self.audio_service)
        self.audio_screen.playAyahRequested.connect(self.reading_view.highlight_ayah)
        self.stack.addWidget(self.audio_screen)  # idx 1

        self.settings_screen = SettingsScreen()
        self.settings_screen.themeChanged.connect(self._on_theme)
        self.settings_screen.fontSizeChanged.connect(lambda v: [w.set_font_size(v) for w in self.reading_view._verse_widgets])
        self.stack.addWidget(self.settings_screen)  # idx 2

        self.btn_audio.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_settings.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        # Toggle sidebar button in toolbar
        toolbar = self.addToolBar("Nav")
        toolbar.setMovable(False)
        toggle = toolbar.addAction("☰ Surahs")
        toggle.triggered.connect(lambda: sidebar.setVisible(not sidebar.isVisible()))
        toolbar.addAction("📖 Quran").triggered.connect(lambda: self.stack.setCurrentIndex(0))
        toolbar.addAction("🔊 Audio").triggered.connect(lambda: self.stack.setCurrentIndex(1))
        toolbar.addAction("⚙ Settings").triggered.connect(lambda: self.stack.setCurrentIndex(2))

        self.stack.setCurrentIndex(0)

    def _load_initial_data(self) -> None:
        surahs = self.quran_repo.get_all_surahs()
        if not surahs:
            QMessageBox.warning(self, "No data", "No Quran data found. Run: python -m quran_app.data.ingest")
            return
        self.surah_list.update_surahs(surahs)
        sources = self.quran_repo.get_translation_sources()
        self.settings_screen.set_translation_sources(sources)
        reciters = self.audio_repo.get_reciters()
        self.audio_screen.set_data(reciters, surahs, audio_root=Path(__file__).parent / "assets" / "audio")
        # Default to Al-Fatiha (or last position)
        pos = self.quran_repo.get_last_position()
        self.open_surah(pos[0] if pos else 1)

    def open_surah(self, surah_number: int) -> None:
        surah = self.quran_repo.get_surah(surah_number)
        if not surah:
            return
        ayahs = self.quran_repo.get_ayahs(surah_number)
        translations: dict[tuple[int, int], str] = {}
        sources = self.quran_repo.get_translation_sources()
        if sources:
            for t in self.quran_repo.get_translations_for_surah(surah_number, sources[0].id):
                translations[(t.surah_number, t.ayah_number)] = t.text
        self.reading_view.set_surah(surah, ayahs, translations)
        self.stack.setCurrentIndex(0)
        self.quran_repo.set_last_position(surah_number, 1)

    def _play_ayah(self, surah: int, ayah: int) -> None:
        if self.audio_screen.reciter_combo.count() == 0:
            QMessageBox.information(self, "Audio", "No reciter configured — add audio files and manifest.\nPlaying text-only.")
            self.reading_view.highlight_ayah(ayah)
            return
        reciter_id = self.audio_screen.reciter_combo.currentData()
        self.audio_screen.play_surah(reciter_id, surah, ayah)
        self.reading_view.highlight_ayah(ayah)
        self.stack.setCurrentIndex(0)

    def _on_theme(self, theme: str) -> None:
        self._current_theme = theme
        self.setStyleSheet(stylesheet(theme))  # type: ignore
        self.quran_repo.set_setting("theme", theme)

    def closeEvent(self, event) -> None:  # type: ignore
        try:
            self.audio_service.cleanup()
            self.db.close()
        except Exception:
            pass
        super().closeEvent(event)


def main() -> int:
    app = setup_application()
    load_fonts()
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
