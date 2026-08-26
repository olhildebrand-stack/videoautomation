"""Tests for measuring how a reference video was edited."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from analyse import Report, Shape, analyse, grab_frames, probe, scene_cuts  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH"
)


@pytest.fixture(scope="module")
def reel(tmp_path_factory):
    """Six seconds, three shots of two seconds each, cuts at 2s and 4s."""
    out = tmp_path_factory.mktemp("reel")
    parts = []
    for index, shade in enumerate(("0x202020", "0x808080", "0x404040")):
        part = out / f"{index}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"color=c={shade}:s=540x960:d=2:r=30",
             "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", str(part)], check=True)
        parts.append(part)
    listing = out / "list.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    joined = out / "reel.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(joined)], check=True)
    return joined


@needs_ffmpeg
def test_shape_is_read_from_the_file(reel):
    shape = probe(reel)
    assert (shape.width, shape.height) == (540, 960)
    assert shape.vertical
    assert shape.fps == pytest.approx(30, abs=0.1)
    assert shape.duration == pytest.approx(6.0, abs=0.2)


@needs_ffmpeg
def test_every_cut_is_found(reel):
    """showinfo writes at info level, so running ffmpeg quietly -- the obvious
    thing to do -- returns nothing and looks like a video with no cuts."""
    cuts = scene_cuts(reel)
    assert len(cuts) == 2
    assert cuts[0] == pytest.approx(2.0, abs=0.2)
    assert cuts[1] == pytest.approx(4.0, abs=0.2)


@needs_ffmpeg
def test_shot_lengths_come_out_of_the_cuts(reel):
    report = analyse(reel, None, 0.3)
    assert len(report.shots) == 3
    assert all(s == pytest.approx(2.0, abs=0.2) for s in report.shots)
    assert report.cuts_per_minute == pytest.approx(20, abs=2)


@needs_ffmpeg
def test_the_picture_is_measured(reel):
    report = analyse(reel, None, 0.3)
    assert 0 < report.brightness < 255
    # Three different greys, so there is spread between shots but no colour.
    assert report.contrast > 0
    assert report.saturation == pytest.approx(0, abs=2)


@needs_ffmpeg
def test_a_frame_is_written_for_every_shot(reel, tmp_path):
    shape = probe(reel)
    frames = grab_frames(reel, scene_cuts(reel), tmp_path, shape)
    assert len(frames) == 3, "one per shot, taken just after the cut"
    assert all(f.is_file() and f.stat().st_size > 0 for f in frames)


def test_shot_lengths_survive_a_video_with_no_cuts():
    report = Report(path=Path("x.mp4"), shape=Shape(10.0, 30, 1080, 1920),
                    cuts=[], brightness=0, saturation=0, contrast=0, silence=0)
    assert report.shots == [10.0]
    assert report.cuts_per_minute == 0


def test_an_empty_clip_does_not_divide_by_zero():
    report = Report(path=Path("x.mp4"), shape=Shape(0.0, 30, 1080, 1920),
                    cuts=[], brightness=0, saturation=0, contrast=0, silence=0)
    assert report.cuts_per_minute == 0
    assert report.shots == []
