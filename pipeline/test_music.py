"""Tests for picking where in a song to start. No ffmpeg calls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import music  # noqa: E402
from music import median, spread  # noqa: E402


def profile(monkeypatch, values):
    monkeypatch.setattr(music, "levels", lambda track, rate=music.RATE: values)


# A song shape in one-second levels: quiet intro, a buildup climbing through
# the middle, a steady body, a climax, an outro.
INTRO = [-60.0] * 20
BUILD = [-40.0 + i for i in range(12)]
BODY = [-20.0] * 40
CLIMAX = [-6.0] * 15
OUTRO = [-45.0] * 13
SONG = INTRO + BUILD + BODY + CLIMAX + OUTRO


def test_it_lands_in_the_body(monkeypatch):
    """Not the intro, not the drop -- which is the whole instruction."""
    profile(monkeypatch, SONG)
    start, _, _ = music.best_start(Path("x.mp3"), 20)
    assert 32 <= start <= 52, f"started at {start}s"


def test_the_window_it_picks_does_not_move(monkeypatch):
    profile(monkeypatch, SONG)
    _, _, moves = music.best_start(Path("x.mp3"), 20)
    assert moves < 0.5


def test_a_silent_intro_is_steady_and_still_refused(monkeypatch):
    """Silence has no spread at all, so steadiness alone would choose it. The
    distance from the track's median is what rules it out."""
    profile(monkeypatch, SONG)
    start, level, _ = music.best_start(Path("x.mp3"), 15)
    assert start >= 20 and level > -40


def test_a_track_shorter_than_the_video_starts_at_the_top(monkeypatch):
    profile(monkeypatch, [-20.0] * 5)
    assert music.best_start(Path("x.mp3"), 30)[0] == 0.0


def test_a_track_barely_longer_than_the_video_still_finds_a_window(monkeypatch):
    """Skipping a fifth and a tenth can leave no room at all; the clip still
    has to get music rather than an exception."""
    profile(monkeypatch, [-20.0] * 32)
    start, _, _ = music.best_start(Path("x.mp3"), 30)
    assert 0 <= start <= 2


def test_median_and_spread():
    assert median([3.0, 1.0, 2.0]) == 2.0
    assert median([4.0, 1.0, 2.0, 3.0]) == 2.5
    assert spread([5.0, 5.0, 5.0]) == 0.0
    assert spread([1.0, 3.0]) == 1.0


# --- a track that cannot be read --------------------------------------------

def test_a_missing_track_is_a_sentence_not_a_traceback(tmp_path, capsys, monkeypatch):
    """It answered a typo'd filename with a CalledProcessError and forty lines
    of stack, which tells the operator nothing they did not already know."""
    monkeypatch.setattr(music.sys, "argv",
                        ["m", str(tmp_path / "gone.mp3"), "--seconds", "31"])
    assert music.main() == 2
    assert "no such track" in capsys.readouterr().out


def test_a_file_with_no_audio_says_so(tmp_path):
    import pytest
    empty = tmp_path / "notmusic.mp3"
    empty.write_bytes(b"not an mp3")
    with pytest.raises(music.NoTrack):
        music.levels(empty)
