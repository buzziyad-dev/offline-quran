"""
Audio playback service.

Primary backend: python-vlc (libVLC). Falls back gracefully if unavailable.
Handles play/pause/stop, auto-advance, repeat-ayah, speed, and seek (spec §3.3).

Design: lightweight, no Qt dependency inside core logic; UI connects via callbacks/signals.
For Qt integration, wrap with QTimer polling or use AudioServiceQt below.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import vlc  # type: ignore

    HAS_VLC = True
except ImportError:
    vlc = None  # type: ignore
    HAS_VLC = False


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class PlaybackQueueItem:
    file_path: Path
    surah_number: int
    ayah_start: int
    ayah_end: int
    start_ms: int = 0  # offset for per-ayah seek within multi-ayah file


class AudioService:
    """
    Audio playback controller.

    Usage:
        svc = AudioService(audio_root=Path("assets/audio"))
        svc.play_file(Path("mishary_alafasy/001.mp3"))
        svc.set_speed(1.25)
        svc.seek_ms(5000)
    """

    def __init__(self, audio_root: Optional[Path] = None) -> None:
        self.audio_root = audio_root
        self.state: PlaybackState = PlaybackState.STOPPED
        self.current_file: Optional[Path] = None
        self.repeat_count: int = 0  # 0 = no repeat, N = repeat N times
        self._repeat_done: int = 0
        self._auto_advance: bool = True
        self._speed: float = 1.0

        # Callbacks
        self.on_state_changed: Optional[Callable[[PlaybackState], None]] = None
        self.on_finished: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # VLC internals
        self._instance: Optional[object] = None
        self._player: Optional[object] = None
        self._init_vlc()

    def _init_vlc(self) -> None:
        if not HAS_VLC:
            logger.warning("python-vlc not available — audio playback disabled. Install VLC / python-vlc.")
            return
        try:
            self._instance = vlc.Instance("--no-video")  # type: ignore
            self._player = self._instance.media_player_new()  # type: ignore
            # Listen for end-of-media via event manager
            em = self._player.event_manager()  # type: ignore
            em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end)  # type: ignore
        except Exception as e:
            logger.warning("Failed to init VLC: %s", e)
            self._instance = None
            self._player = None
            if self.on_error:
                self.on_error(f"Audio backend init failed: {e}")

    def _on_vlc_end(self, event: object) -> None:
        """Called on VLC thread when media ends."""
        self._handle_finished()

    def _handle_finished(self) -> None:
        # Repeat logic
        if self.repeat_count > 0 and self._repeat_done < self.repeat_count - 1:
            self._repeat_done += 1
            self._vlc_play(self.current_file)  # type: ignore
            return
        self._repeat_done = 0
        self.state = PlaybackState.STOPPED
        if self.on_state_changed:
            self.on_state_changed(self.state)
        if self.on_finished:
            self.on_finished()
        # Auto-advance is handled by UI (queue next file) via on_finished

    # -- Public API --

    def is_available(self) -> bool:
        return HAS_VLC and self._player is not None

    def play_file(
        self,
        file_path: Path | str,
        start_ms: int = 0,
        repeat: int = 0,
        auto_advance: bool = True,
    ) -> bool:
        """
        Play an audio file. file_path may be absolute or relative to audio_root.
        Returns False if file missing or backend unavailable.
        """
        path = Path(file_path)
        if not path.is_absolute() and self.audio_root:
            path = self.audio_root / path

        if not path.exists():
            msg = f"Audio file not found: {path}"
            logger.warning(msg)
            if self.on_error:
                self.on_error(msg)
            return False

        if not self.is_available():
            msg = "Audio backend not available (VLC missing)"
            logger.warning(msg)
            if self.on_error:
                self.on_error(msg)
            return False

        self.current_file = path
        self.repeat_count = max(0, repeat)
        self._repeat_done = 0
        self._auto_advance = auto_advance
        return self._vlc_play(path, start_ms)

    def _vlc_play(self, path: Path, start_ms: int = 0) -> bool:
        assert self._player is not None and self._instance is not None
        try:
            media = self._instance.media_new(str(path))  # type: ignore
            self._player.set_media(media)  # type: ignore
            if start_ms > 0:
                # Seek after play starts; VLC requires slight delay — caller can also seek after
                pass
            self._player.set_rate(self._speed)  # type: ignore
            self._player.play()  # type: ignore
            if start_ms > 0:
                # Best-effort immediate seek
                try:
                    self._player.set_time(start_ms)  # type: ignore
                except Exception:
                    pass
            self.state = PlaybackState.PLAYING
            if self.on_state_changed:
                self.on_state_changed(self.state)
            return True
        except Exception as e:
            logger.error("VLC play failed: %s", e)
            if self.on_error:
                self.on_error(str(e))
            return False

    def pause(self) -> None:
        if self._player and self.state == PlaybackState.PLAYING:
            try:
                self._player.pause()  # type: ignore
                self.state = PlaybackState.PAUSED
                if self.on_state_changed:
                    self.on_state_changed(self.state)
            except Exception as e:
                logger.error("Pause failed: %s", e)

    def resume(self) -> None:
        if self._player and self.state == PlaybackState.PAUSED:
            try:
                self._player.play()  # type: ignore
                self.state = PlaybackState.PLAYING
                if self.on_state_changed:
                    self.on_state_changed(self.state)
            except Exception as e:
                logger.error("Resume failed: %s", e)

    def stop(self) -> None:
        if self._player:
            try:
                self._player.stop()  # type: ignore
            except Exception:
                pass
        self.state = PlaybackState.STOPPED
        self._repeat_done = 0
        if self.on_state_changed:
            self.on_state_changed(self.state)

    def set_speed(self, speed: float) -> None:
        """Set playback speed 0.5–2.0 (spec §3.3)."""
        self._speed = max(0.5, min(2.0, speed))
        if self._player:
            try:
                self._player.set_rate(self._speed)  # type: ignore
            except Exception as e:
                logger.warning("set_rate failed: %s", e)

    def get_speed(self) -> float:
        return self._speed

    def seek_ms(self, ms: int) -> None:
        if self._player:
            try:
                self._player.set_time(max(0, ms))  # type: ignore
            except Exception as e:
                logger.warning("seek failed: %s", e)

    def get_time_ms(self) -> int:
        if self._player:
            try:
                return int(self._player.get_time())  # type: ignore
            except Exception:
                return 0
        return 0

    def get_duration_ms(self) -> int:
        if self._player:
            try:
                return int(self._player.get_length())  # type: ignore
            except Exception:
                return 0
        return 0

    def set_repeat(self, count: int) -> None:
        """Repeat current ayah N times (0 = no repeat)."""
        self.repeat_count = max(0, count)

    def cleanup(self) -> None:
        try:
            if self._player:
                self._player.stop()  # type: ignore
        except Exception:
            pass
