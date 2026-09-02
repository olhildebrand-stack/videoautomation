"""Tests for binary resolution and the filter graph. No ffmpeg calls."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import ffmpeg_ops as fo  # noqa: E402
from cutlist import Segment  # noqa: E402


def test_missing_binary_raises_something_actionable(monkeypatch):
    monkeypatch.setattr(fo.shutil, "which", lambda _: None)
    monkeypatch.delenv("FFMPEG_BINARY", raising=False)
    with pytest.raises(fo.FFmpegMissing) as excinfo:
        fo.binary("ffmpeg")
    message = str(excinfo.value)
    assert "winget install Gyan.FFmpeg" in message
    assert "reopen the terminal" in message
    # Must say why Remotion's bundled build is not a substitute.
    assert "colortemperature" in message


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("FFMPEG_BINARY", r"C:\tools\ffmpeg.exe")
    assert fo.binary("ffmpeg") == r"C:\tools\ffmpeg.exe"


def test_binary_is_resolved_per_call_not_at_import(monkeypatch):
    """A fresh install must be picked up without restarting."""
    monkeypatch.setattr(fo.shutil, "which", lambda _: None)
    monkeypatch.delenv("FFMPEG_BINARY", raising=False)
    with pytest.raises(fo.FFmpegMissing):
        fo.binary("ffmpeg")
    monkeypatch.setattr(fo.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    assert fo.binary("ffmpeg") == "/usr/bin/ffmpeg"


def test_missing_binary_is_an_ffmpeg_error_subclass():
    """So a caller can catch either without knowing which."""
    assert issubclass(fo.FFmpegMissing, fo.FFmpegError)


# --- filter graph -----------------------------------------------------------

def test_trim_filter_covers_every_segment_in_order():
    segments = [Segment("A", "a", 1.0, 3.0, 1.0), Segment("B", "b", 8.0, 10.5, 1.0)]
    graph = fo.build_trim_filter(segments)
    assert "trim=start=1.0:end=3.0" in graph
    assert "trim=start=8.0:end=10.5" in graph
    assert "concat=n=2:v=1:a=1[outv][outa]" in graph
    assert graph.index("start=1.0") < graph.index("start=8.0"), "script order preserved"


def test_trim_filter_rejects_an_empty_cut():
    with pytest.raises(ValueError):
        fo.build_trim_filter([])


def test_grade_filter_defaults_are_restrained():
    chain = fo.Grade().to_filter()
    assert "eq=contrast=1.06" in chain and "colortemperature=6200" in chain
    assert "lut3d" not in chain


def test_lut_is_applied_last_so_it_grades_the_corrected_image():
    chain = fo.Grade(lut=Path("look.cube")).to_filter()
    assert chain.index("eq=") < chain.index("lut3d")
    assert chain.endswith("lut3d='look.cube'")


# --- probing geometry for a join --------------------------------------------

def _ffprobe_saying(payload):
    """Stand in for ffprobe, returning whatever JSON the test wants."""
    class Result:
        returncode = 0
        stdout = payload
    return lambda *a, **k: Result()


def test_geometry_survives_a_stream_that_carries_no_dimensions(monkeypatch):
    """The first version split ffprobe's CSV on 'x' and unpacked exactly three
    fields. A real file came back with four and it raised. An mp4 can hold more
    than one stream ffprobe calls video -- a cover image is one -- so the first
    with real dimensions is the one that decides the join."""
    import ffmpeg_ops
    monkeypatch.setattr(ffmpeg_ops.subprocess, "run", _ffprobe_saying(
        '{"streams":[{"r_frame_rate":"0/0"},'
        '{"width":1080,"height":1920,"r_frame_rate":"30000/1001"}]}'))
    assert ffmpeg_ops.probe_video(Path("x.mp4")) == (1080, 1920, "30000/1001")


def test_a_file_with_no_usable_video_stream_says_so(monkeypatch):
    import ffmpeg_ops
    monkeypatch.setattr(ffmpeg_ops.subprocess, "run",
                        _ffprobe_saying('{"streams":[]}'))
    with pytest.raises(ffmpeg_ops.FFmpegError, match="no video stream"):
        ffmpeg_ops.probe_video(Path("x.mp4"))
