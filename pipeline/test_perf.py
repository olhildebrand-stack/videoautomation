"""Tests for the performance record.

The rule under test: retention is the measured thing and views are downstream
of it, and a video that went through the pipeline without its numbers being
kept is a video that taught nobody anything.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import perf  # noqa: E402


def record(tmp_path, monkeypatch, posts, scripts=()):
    path = tmp_path / "performance.json"
    path.write_text(json.dumps({"posts": posts}), encoding="utf-8")
    monkeypatch.setattr(perf, "RECORD", path)
    folder = tmp_path / "edit-scripts"
    folder.mkdir()
    monkeypatch.setattr(perf, "SCRIPTS", folder)
    for name, beats in scripts:
        (folder / f"{name}.json").write_text(
            json.dumps([{"beat": b, "line": "..."} for b in beats]),
            encoding="utf-8")
    return path


GOOD = {"name": "good", "length": 26, "watch": 14.0, "views": 1745}
DIED = {"name": "died", "length": 19, "watch": 4.0, "views": 188}


def test_retention_is_watch_over_length(tmp_path, monkeypatch):
    record(tmp_path, monkeypatch, [GOOD, DIED])
    assert perf.retention(GOOD) == pytest.approx(14 / 26)
    assert perf.retention(DIED) == pytest.approx(4 / 19)


def test_the_two_measured_reels_fall_either_side_of_the_line():
    """The threshold is set from real data, so it has to actually split it."""
    assert perf.retention(DIED) < perf.HOOK_FAILED < perf.retention(GOOD)


def test_an_unwatched_video_has_no_retention(tmp_path, monkeypatch):
    """Absent is not zero -- a row awaiting numbers must not read as a flop."""
    assert perf.retention({"name": "x", "length": 30}) is None
    assert perf.retention({"name": "x", "watch": 5}) is None


def test_a_posted_video_with_no_numbers_is_reported(tmp_path, monkeypatch):
    record(tmp_path, monkeypatch, [GOOD],
           scripts=[("good", ["HOOK"]), ("forgotten", ["HOOK", "LANDING"])])
    assert perf.unrecorded() == ["forgotten"]


def test_nothing_unrecorded_when_every_script_has_a_row(tmp_path, monkeypatch):
    record(tmp_path, monkeypatch, [GOOD], scripts=[("good", ["HOOK"])])
    assert perf.unrecorded() == []
    assert perf.check() == 0


def test_a_row_without_a_script_is_not_an_error(tmp_path, monkeypatch):
    """A video posted outside the pipeline still counts as evidence."""
    record(tmp_path, monkeypatch, [GOOD, DIED], scripts=[("good", ["HOOK"])])
    assert perf.unrecorded() == []


def test_the_beats_a_video_was_made_of_are_joined_on(tmp_path, monkeypatch):
    """The join is the point: a number beside the shape that produced it."""
    record(tmp_path, monkeypatch, [GOOD],
           scripts=[("good", ["HOOK", "THE TAKE", "LANDING"])])
    assert perf.beats("good") == ["HOOK", "THE TAKE", "LANDING"]
    assert perf.beats("died") == []
