"""Tests for measuring speech edges from the audio.

Why this module exists, in one case: the transcript said "video." ended at
49.04. Cutting at 49.04 + 0.15 produced "vi". The same 0.15s tail was clean on
a word thirty seconds earlier. The tail was never the variable -- `word_end`
was, because `vad_filter` strips silence before decoding and the timestamps are
mapped back afterwards, accumulating error in proportion to the silence removed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from edges import (  # noqa: E402
    DEFAULT_MAX_DRIFT, LADDER, edges_from_runs, measure, measure_best,
)
from takes import Run  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH"
)


@pytest.fixture(scope="module")
def tone(tmp_path_factory):
    """Six seconds holding two bursts of speech-loud tone in known places:
    1.0-2.0 and 3.5-4.5. Everything else is digital silence."""
    path = tmp_path_factory.mktemp("audio") / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*300*t)*between(t,1,2)"
         "+0.5*sin(2*PI*300*t)*between(t,3.5,4.5)':d=6:s=44100", str(path)],
        check=True,
    )
    return path


# --- the decision, without audio --------------------------------------------

def test_outer_bounds_of_the_speech_that_overlaps_the_range():
    runs = [Run(0.0, 0.5), Run(1.0, 2.0), Run(2.4, 3.0), Run(5.0, 6.0)]
    e = edges_from_runs(runs, 1.2, 2.6)
    assert (e.start, e.end) == (1.0, 3.0)
    assert e.measured


def test_a_range_holding_no_speech_is_left_alone():
    """Silence where speech was expected means the threshold is wrong, and
    guessing is worse than keeping what was written."""
    e = edges_from_runs([Run(5.0, 6.0)], 1.0, 2.0)
    assert (e.start, e.end) == (1.0, 2.0)
    assert not e.measured


def test_a_measurement_further_out_than_drift_explains_is_pulled_back():
    runs = [Run(0.0, 9.0)]  # a threshold reading room tone as speech
    e = edges_from_runs(runs, 4.0, 5.0)
    assert e.start == pytest.approx(4.0 - DEFAULT_MAX_DRIFT)
    assert e.end == pytest.approx(5.0 + DEFAULT_MAX_DRIFT)
    assert e.clamped


def test_drift_is_reported_signed_against_what_was_stated():
    e = edges_from_runs([Run(1.0, 2.0)], 0.6, 1.6)
    assert e.start_drift == pytest.approx(0.4)
    assert e.end_drift == pytest.approx(0.4)


# --- against real audio ------------------------------------------------------

@needs_ffmpeg
def test_the_true_edges_are_recovered_from_a_range_that_is_early(tone):
    """The bug, reproduced: a range 0.4s early at both ends."""
    e = measure(tone, 0.6, 1.6)
    assert e.measured
    assert e.start == pytest.approx(1.0, abs=0.05)
    assert e.end == pytest.approx(2.0, abs=0.05)


@needs_ffmpeg
def test_a_range_that_is_already_right_is_left_where_it_is(tone):
    e = measure(tone, 1.0, 2.0)
    assert e.start_drift == pytest.approx(0.0, abs=0.05)
    assert e.end_drift == pytest.approx(0.0, abs=0.05)


@needs_ffmpeg
def test_the_next_burst_is_not_swept_in(tone):
    """1.0-2.0 and 3.5-4.5 are 1.5s apart, wider than the search window."""
    e = measure(tone, 1.0, 2.0)
    assert e.end < 3.0


@needs_ffmpeg
def test_silence_reports_no_measurement_rather_than_a_guess(tone):
    e = measure(tone, 2.2, 3.0)
    assert not e.measured
    assert (e.start, e.end) == (2.2, 3.0)


# --- measuring a whole edit script -------------------------------------------

@needs_ffmpeg
def test_a_script_is_measured_beat_by_beat(tone, tmp_path, capsys):
    """The question this answers before a rebuild: does measuring move the cuts
    that already sounded right?"""
    import json
    from edges import report_script

    script = tmp_path / "edit-script.json"
    script.write_text(json.dumps([
        {"beat": "EARLY", "start": 0.6, "end": 1.6},   # 0.4s early both ends
        {"beat": "RIGHT", "start": 3.5, "end": 4.5},   # already correct
    ]), encoding="utf-8")

    class Args:
        search, noise, min_silence = 1.2, -35.0, 0.14

    assert report_script(script, tone, 0.05, 0.15, Args()) == 0
    out = capsys.readouterr().out
    assert "+0.40  +0.40" in out
    assert "+0.00  +0.00" in out


def test_a_script_with_no_stated_ranges_says_so(tmp_path, capsys):
    import json
    from edges import report_script

    script = tmp_path / "edit-script.json"
    script.write_text(json.dumps([{"beat": "A", "line": "some words"}]),
                      encoding="utf-8")

    class Args:
        search, noise, min_silence = 1.2, -35.0, 0.14

    assert report_script(script, Path("unused.mp4"), 0.05, 0.15, Args()) == 1
    assert "no explicit ranges" in capsys.readouterr().out


def test_the_default_threshold_keeps_a_quiet_final_syllable():
    """-35dB was the first attempt and it clipped "content" to "con": a voice
    declines through a sentence, and the last syllable fell below it."""
    from edges import DEFAULT_NOISE_DB
    assert DEFAULT_NOISE_DB <= -45.0


@needs_ffmpeg
def test_a_syllable_20db_down_survives_the_default_but_not_the_old_one(tmp_path):
    """The real failure, built to order: a loud phrase followed by a trailing
    syllable 20dB quieter, the way a sentence actually ends."""
    path = tmp_path / "decline.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         # 0.5 then 0.008: a trailing syllable about 36dB down, which is
         # within the range a voice drops by at the end of a sentence.
         "aevalsrc='0.5*sin(2*PI*300*t)*between(t,1,1.8)"
         "+0.008*sin(2*PI*300*t)*between(t,1.8,2.2)':d=4:s=44100", str(path)],
        check=True,
    )
    deaf = measure(path, 1.0, 1.8, noise_db=-35.0)
    keen = measure(path, 1.0, 1.8, noise_db=-45.0)
    assert deaf.end == pytest.approx(1.8, abs=0.08), "the quiet tail was heard"
    assert keen.end == pytest.approx(2.2, abs=0.08), "the quiet tail was lost"


@needs_ffmpeg
def test_the_sweep_shows_the_edge_at_each_threshold(tone, tmp_path, capsys):
    import json
    from edges import report_sweep

    script = tmp_path / "edit-script.json"
    script.write_text(json.dumps([{"beat": "A", "start": 0.6, "end": 1.6}]),
                      encoding="utf-8")

    class Args:
        search, min_silence = 1.2, 0.14

    assert report_sweep(script, tone, Args()) == 0
    out = capsys.readouterr().out
    assert "-30" in out and "-60" in out
    assert out.count("2.00") >= 3


# --- the two sides fail independently ----------------------------------------

def test_a_runaway_start_does_not_mark_the_end_as_untrustworthy():
    """Reporting one clamp for both made a usable threshold look unusable: a
    start reaching back into the previous take says nothing about the end."""
    e = edges_from_runs([Run(0.0, 5.2)], 4.0, 5.0)
    assert e.start_clamped
    assert not e.end_clamped
    assert e.end == 5.2, "the end was measured cleanly and should stand"


def test_a_runaway_end_is_marked_on_its_own_side():
    e = edges_from_runs([Run(3.9, 9.0)], 4.0, 5.0)
    assert e.end_clamped
    assert not e.start_clamped
    assert e.start == 3.9


def test_clamped_still_reports_either_side():
    assert edges_from_runs([Run(0.0, 9.0)], 4.0, 5.0).clamped
    assert not edges_from_runs([Run(3.9, 5.2)], 4.0, 5.0).clamped


# --- a room louder than the default floor ------------------------------------

@pytest.fixture(scope="module")
def noisy(tmp_path_factory):
    """Speech between 2s and 5s over room tone loud enough to defeat -45dB.

    This is what aieditoradvancing was: at the stated floor the "speech run"
    never ends, because the room itself is above the threshold, so both edges
    land wherever the drift clamp puts them -- 0.6s of silence in front of
    every sentence and 0.6s behind it.
    """
    path = tmp_path_factory.mktemp("audio") / "room.m4a"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=200:duration=10",
         "-f", "lavfi", "-i", "anoisesrc=d=10:c=pink:a=0.06",
         "-filter_complex",
         "[0:a]volume=0:enable='between(t,0,2)+between(t,5,10)'[speech];"
         "[speech][1:a]amix=inputs=2:duration=first:weights='1 1'[out]",
         "-map", "[out]", "-c:a", "aac", str(path)],
        check=True, capture_output=True,
    )
    return path


@needs_ffmpeg
def test_the_stated_floor_alone_reads_the_room_as_speech(noisy):
    """The failure, stated as a test so the fix has something to beat."""
    found = measure(noisy, 2.2, 4.8, noise_db=-45.0)
    assert found.start_clamped and found.end_clamped
    assert found.start < 1.8, "it should have run past the real onset"
    assert found.end > 5.2, "and past the real offset"


@needs_ffmpeg
def test_climbing_finds_the_real_edges(noisy):
    found, used = measure_best(noisy, 2.2, 4.8, floor=-45.0)
    assert not found.clamped
    assert used > -45.0, "it should have had to climb"
    # Not exact -- the noise decays rather than stopping -- but the 0.6s of
    # room tone the clamp left at each end is gone, which is the whole point.
    assert abs(found.start - 2.0) < 0.2, f"start landed at {found.start}"
    assert abs(found.end - 5.0) < 0.2, f"end landed at {found.end}"

    at_floor = measure(noisy, 2.2, 4.8, noise_db=-45.0)
    assert abs(found.start - 2.0) < abs(at_floor.start - 2.0) / 3
    assert abs(found.end - 5.0) < abs(at_floor.end - 5.0) / 3


@needs_ffmpeg
def test_a_quiet_room_is_measured_at_the_floor_and_not_climbed(tone):
    """Climbing is a last resort: a less sensitive threshold misses a quiet
    sentence-final syllable, which is the bug that set the floor at -45."""
    found, used = measure_best(tone, 1.0, 1.9, floor=-45.0)
    assert used == -45.0
    assert not found.clamped


def test_the_ladder_only_ever_climbs():
    assert LADDER == sorted(LADDER), "a ladder that descends is more sensitive"
    assert LADDER[0] <= -45.0, "it has to start at or below the default floor"


# --- silence inside a range already chosen -----------------------------------

@pytest.fixture(scope="module")
def breath(tmp_path_factory):
    """A short blip at 1.0s, then real speech from 2.5s to 5s.

    This is the case that survived every other guard: the blip is a speech run,
    it overlaps the stated range, and it is inside the drift budget -- so
    `measure` takes it as the onset, reports no clamp, and the cut opens on a
    breath with the words arriving a second and a half later.
    """
    path = tmp_path_factory.mktemp("audio") / "breath.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*300*t)*(between(t,1,1.3)+between(t,2.5,5))"
         "':d=7:s=44100", str(path)],
        check=True,
    )
    return path


@needs_ffmpeg
def test_measuring_around_the_range_takes_the_breath_as_the_onset(breath):
    """The failure, so the fix has something to beat."""
    found = measure(breath, 1.1, 5.0)
    assert not found.start_clamped, "nothing flags it -- that is the problem"
    assert found.start < 1.5, f"it opened on the blip at {found.start}"


@needs_ffmpeg
def test_trimming_inside_the_range_finds_where_the_words_start(breath):
    """Even with the blip inside the range: it is a third of a second followed
    by more than a second of nothing, so it is not what the sentence starts
    with."""
    from edges import trim_to_speech
    speaks_at, stops_at = trim_to_speech(breath, 1.0, 5.2)
    assert abs(speaks_at - 2.5) < 0.15, f"speech starts at {speaks_at}"
    assert abs(stops_at - 5.0) < 0.15, f"speech ends at {stops_at}"

    # And from a range that already begins after it, unchanged.
    speaks_at, _ = trim_to_speech(breath, 1.4, 5.2)
    assert abs(speaks_at - 2.5) < 0.15


@needs_ffmpeg
def test_a_range_of_pure_silence_reports_nothing_rather_than_guessing(breath):
    from edges import trim_to_speech
    assert trim_to_speech(breath, 5.5, 6.8) is None


@needs_ffmpeg
def test_trimming_never_reaches_outside_the_range(breath):
    """The asymmetry the whole idea rests on: moving the start later or the end
    earlier can only remove something the range already held."""
    from edges import trim_to_speech
    speaks_at, stops_at = trim_to_speech(breath, 2.8, 4.0)
    assert speaks_at >= 2.8 and stops_at <= 4.0


# --- a sound that is not speech ----------------------------------------------

def run(start, end):
    return Run(start, end)


def test_a_blip_followed_by_a_long_pause_is_dropped():
    from edges import drop_blips
    kept = drop_blips([run(1.0, 1.3), run(2.5, 5.0)])
    assert [r.start for r in kept] == [2.5]


def test_a_short_first_word_is_kept():
    """"Men", a quarter second, then a beat before the sentence. The pause is
    about its own length, not several times it."""
    from edges import drop_blips
    kept = drop_blips([run(1.0, 1.25), run(1.65, 4.0)])
    assert [r.start for r in kept] == [1.0, 1.65]


def test_a_long_run_is_never_dropped_however_isolated():
    from edges import drop_blips
    kept = drop_blips([run(1.0, 2.0), run(6.0, 9.0)])
    assert len(kept) == 2


def test_a_trailing_blip_goes_too():
    from edges import drop_blips
    kept = drop_blips([run(1.0, 4.0), run(6.0, 6.2)])
    assert [r.end for r in kept] == [4.0]


def test_the_last_run_is_never_dropped():
    """Something has to remain, or the range holds nothing at all."""
    from edges import drop_blips
    assert len(drop_blips([run(1.0, 1.1)])) == 1


@needs_ffmpeg
def test_trimming_climbs_when_the_room_hides_the_silence(noisy):
    """The failure the operator reported twice: "still there and the same
    length". At -45dB in a room above -45dB there is no silence to find
    anywhere, so the range comes back as one unbroken run and nothing is
    trimmed -- which is not "no silence here", it is "this threshold cannot
    tell". Speech runs 2.0-5.0; the range starts 1.2s before it.
    """
    from edges import trim_to_speech
    speaks_at, stops_at = trim_to_speech(noisy, 0.8, 5.4)
    assert speaks_at > 1.5, f"the range still opens in silence, at {speaks_at}"
    assert abs(speaks_at - 2.0) < 0.25, f"speech starts at {speaks_at}"
    assert abs(stops_at - 5.0) < 0.25, f"speech ends at {stops_at}"


@needs_ffmpeg
def test_a_tight_range_in_a_quiet_room_is_left_alone(tone):
    """Climbing must not become an excuse to trim a range that is already
    right: it stops at the most sensitive threshold that can tell."""
    from edges import trim_to_speech
    speaks_at, stops_at = trim_to_speech(tone, 0.95, 2.05)
    assert speaks_at <= 1.05 and stops_at >= 1.95
