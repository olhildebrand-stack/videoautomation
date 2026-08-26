"""Tests for locating takes from silence. Pure logic; no ffmpeg needed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from takes import Run, pick_take, speech_runs  # noqa: E402


# --- speech runs ------------------------------------------------------------

def test_runs_are_the_complement_of_the_silences():
    runs = speech_runs(0.0, 11.2, [(1.5, 2.3), (4.5, 5.4)], min_run=0.4)
    assert [(r.start, r.end) for r in runs] == [(0.0, 1.5), (2.3, 4.5), (5.4, 11.2)]


def test_no_silence_means_one_run():
    runs = speech_runs(0.0, 6.0, [], min_run=0.4)
    assert len(runs) == 1 and runs[0].duration == 6.0


def test_runs_shorter_than_min_run_are_dropped():
    """A 0.2s blip between two pauses is a breath, not a take."""
    runs = speech_runs(0.0, 5.0, [(0.5, 1.0), (1.2, 2.0)], min_run=0.4)
    assert all(r.duration >= 0.4 for r in runs)
    assert not any(abs(r.start - 1.0) < 0.01 for r in runs)


def test_silence_running_to_the_end_leaves_no_trailing_run():
    runs = speech_runs(0.0, 5.0, [(3.0, 5.0)], min_run=0.4)
    assert [(r.start, r.end) for r in runs] == [(0.0, 3.0)]


def test_leading_silence_is_skipped():
    runs = speech_runs(0.0, 5.0, [(0.0, 2.0)], min_run=0.4)
    assert runs[0].start == 2.0


def test_overlapping_silences_do_not_produce_negative_runs():
    runs = speech_runs(0.0, 5.0, [(1.0, 3.0), (2.0, 4.0)], min_run=0.4)
    assert all(r.end > r.start for r in runs)


# --- choosing the take ------------------------------------------------------

def test_the_last_long_enough_run_wins():
    """A speaker who restarts does so because the last attempt failed."""
    runs = [Run(0.0, 1.5), Run(2.3, 4.5), Run(5.4, 11.2)]
    assert pick_take(runs, expect=6.0) == runs[2]


def test_a_later_but_too_short_run_does_not_win():
    """A cough after the good take should not be mistaken for it."""
    runs = [Run(0.0, 1.5), Run(2.0, 8.0), Run(9.0, 9.5)]
    assert pick_take(runs, expect=6.0) == runs[1]


def test_without_an_expected_length_the_longest_wins():
    runs = [Run(0.0, 1.5), Run(2.0, 8.0), Run(9.0, 9.5)]
    assert pick_take(runs, expect=None) == runs[1]


def test_all_runs_short_falls_back_to_the_longest():
    runs = [Run(0.0, 1.0), Run(2.0, 3.2)]
    assert pick_take(runs, expect=6.0) == runs[1]


def test_no_runs_gives_nothing():
    assert pick_take([], expect=6.0) is None


def test_threshold_is_generous_enough_for_a_brisk_take():
    """A take slightly shorter than expected is still the take."""
    runs = [Run(0.0, 2.0), Run(3.0, 7.6)]      # 4.6s against an expected 6
    assert pick_take(runs, expect=6.0) == runs[1]
