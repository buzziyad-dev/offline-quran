"""
Audio Player screen — reciter/surah selector, playback controls, repeat, speed, seek.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QSlider, QSpinBox, QFrame, QMessageBox
    )
    from PySide6.QtCore import Qt, Signal, QTimer
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
        QSlider, QSpinBox, QFrame, QMessageBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer

from quran_app.data.models import Reciter, Surah
from quran_app.audio.audio_service import AudioService


class AudioPlayerScreen(QWidget):
    playAyahRequested = Signal(int, int)  # surah, ayah — for highlighting

    def __init__(self, audio_service: AudioService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.svc = audio_service
        self._reciters: list[Reciter] = []
        self._surahs: list[Surah] = []
        self._current_surah = 1
        self._current_ayah = 1
        self._audio_root: Optional[Path] = None

        # Hook service callbacks
        self.svc.on_state_changed = self._on_state_changed
        self.svc.on_error = self._on_error
        self.svc.on_finished = self._on_finished

        self._build_ui()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(250)
        self._poll_timer.timeout.connect(self._poll_position)
        self._seek_dragging = False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Audio Player")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        # Selectors
        row = QHBoxLayout()
        row.addWidget(QLabel("Reciter:"))
        self.reciter_combo = QComboBox()
        self.reciter_combo.setMinimumWidth(200)
        row.addWidget(self.reciter_combo)
        row.addSpacing(12)
        row.addWidget(QLabel("Surah:"))
        self.surah_combo = QComboBox()
        self.surah_combo.setMinimumWidth(160)
        row.addWidget(self.surah_combo)
        row.addStretch()
        layout.addLayout(row)

        self.status_label = QLabel("No audio loaded")
        self.status_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Seek
        seek_row = QHBoxLayout()
        self.pos_label = QLabel("0:00")
        self.pos_label.setFixedWidth(40)
        seek_row.addWidget(self.pos_label)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, "_seek_dragging", True))
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        seek_row.addWidget(self.seek_slider)
        self.dur_label = QLabel("0:00")
        self.dur_label.setFixedWidth(40)
        seek_row.addWidget(self.dur_label)
        layout.addLayout(seek_row)

        # Controls
        ctr = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._on_play_pause)
        ctr.addWidget(self.play_btn)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        ctr.addWidget(self.stop_btn)
        ctr.addSpacing(12)
        ctr.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        for s in ["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"]:
            self.speed_combo.addItem(s)
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self._on_speed)
        ctr.addWidget(self.speed_combo)
        ctr.addSpacing(12)
        ctr.addWidget(QLabel("Repeat ayah:"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(0, 20)
        self.repeat_spin.setValue(0)
        self.repeat_spin.setSuffix(" ×")
        self.repeat_spin.valueChanged.connect(lambda v: self.svc.set_repeat(v))
        ctr.addWidget(self.repeat_spin)
        ctr.addStretch()
        layout.addLayout(ctr)

        if not self.svc.is_available():
            warn = QLabel("⚠ Audio backend not available — install VLC and python-vlc. Playback disabled.")
            warn.setStyleSheet("color: #B45309; background: #FEF3C7; padding: 8px; border-radius: 6px;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        layout.addStretch()

    def set_data(self, reciters: list[Reciter], surahs: list[Surah], audio_root: Optional[Path] = None) -> None:
        self._reciters = reciters
        self._surahs = surahs
        self._audio_root = audio_root
        if audio_root:
            self.svc.audio_root = audio_root
        self.reciter_combo.clear()
        for r in reciters:
            self.reciter_combo.addItem(f"{r.name} ({r.audio_format})", r.id)
        self.surah_combo.clear()
        for s in surahs:
            self.surah_combo.addItem(f"{s.surah_number}. {s.name_arabic} — {s.name_english}", s.surah_number)
        if surahs:
            self._current_surah = surahs[0].surah_number
        self.status_label.setText(f"{len(reciters)} reciter(s) loaded" if reciters else "No reciters — add audio_manifest.json")

    def _fmt(self, ms: int) -> str:
        s = max(0, ms) // 1000
        return f"{s // 60}:{s % 60:02d}"

    def _on_play_pause(self) -> None:
        from quran_app.data.repository import AudioRepository  # lazy

        if self.svc.state.value == "playing":
            self.svc.pause()
            return
        if self.svc.state.value == "paused":
            self.svc.resume()
            return
        # Start playback for selected reciter/surah (first ayah)
        if self.reciter_combo.count() == 0:
            QMessageBox.information(self, "No audio", "No reciter configured. Add audio files and manifest.")
            return
        reciter_id = self.reciter_combo.currentData()
        surah_num = self.surah_combo.currentData()
        if surah_num is None:
            return
        self.play_surah(reciter_id, int(surah_num))

    def play_surah(self, reciter_id: str, surah_number: int, ayah_number: int = 1) -> None:
        # Resolve file via DB or direct AudioService — keep simple: find file relative to audio_root
        # Try repository lookup if available via parent, else scan reciter files
        reciter = next((r for r in self._reciters if r.id == reciter_id), None)
        if not reciter:
            self._on_error(f"Reciter not found: {reciter_id}")
            return
        af = reciter.find_audio_for(surah_number, ayah_number)
        if not af:
            self._on_error(f"No audio for {surah_number}:{ayah_number} (reciter {reciter_id}) — text-only mode")
            return
        self._current_surah = surah_number
        self._current_ayah = ayah_number
        ok = self.svc.play_file(af.relative_path, repeat=self.repeat_spin.value())
        if ok:
            self._poll_timer.start()
            self.status_label.setText(f"Playing {af.relative_path}")
            self.playAyahRequested.emit(surah_number, ayah_number)

    def _on_stop(self) -> None:
        self.svc.stop()
        self._poll_timer.stop()
        self.seek_slider.setValue(0)

    def _on_speed(self, text: str) -> None:
        try:
            v = float(text.replace("x", ""))
            self.svc.set_speed(v)
        except ValueError:
            pass

    def _on_seek_released(self) -> None:
        self._seek_dragging = False
        dur = self.svc.get_duration_ms()
        if dur > 0:
            ms = int(self.seek_slider.value() / 1000 * dur)
            self.svc.seek_ms(ms)

    def _poll_position(self) -> None:
        if self._seek_dragging:
            return
        pos = self.svc.get_time_ms()
        dur = self.svc.get_duration_ms()
        self.pos_label.setText(self._fmt(pos))
        self.dur_label.setText(self._fmt(dur))
        if dur > 0:
            self.seek_slider.setValue(int(pos / dur * 1000))

    def _on_state_changed(self, state) -> None:
        # Called from service (may be VLC thread) — ensure UI thread via QTimer
        QTimer.singleShot(0, lambda: self._update_play_btn(state))

    def _update_play_btn(self, state) -> None:
        if state.value == "playing":
            self.play_btn.setText("⏸ Pause")
        else:
            self.play_btn.setText("▶ Play")
            if state.value == "stopped":
                self._poll_timer.stop()

    def _on_error(self, msg: str) -> None:
        QTimer.singleShot(0, lambda: self.status_label.setText(f"⚠ {msg}"))

    def _on_finished(self) -> None:
        QTimer.singleShot(0, lambda: self.status_label.setText("Finished"))
