"""Tests for measuring where the composition actually drew.

Why this exists: two placement bugs got through code review, typechecking and
a full test suite. A chat window grew as messages arrived until it sat in the
caption band, and a row pinned to the top of frame centred itself instead,
because a flex row takes its vertical alignment from alignItems and the pin was
on justifyContent. Both were invisible in the source and obvious in the pixels.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cues import CHILD_KEYS  # noqa: E402
from verify import (  # noqa: E402
    Placement, check, dimensions, moments, reason, report, safe_zone,
)

ZONE = {"top": 220, "bottom": 450, "side": 100}
W, H = 1080, 1920


def placed(top, bottom, left=200, right=800):
    p = Placement(1.0, 30, top, bottom, left, right, W, H)
    check(p, ZONE)
    return p


# --- the check itself --------------------------------------------------------

def test_content_inside_the_band_passes():
    assert placed(300, 1400).problems == []


def test_the_top_band_is_reported_with_how_far_in():
    problems = placed(180, 1400).problems
    assert len(problems) == 1
    assert "40px into the top band" in problems[0]


def test_the_bottom_band_is_reported():
    """The caption band. This is where the chat window ended up."""
    problems = placed(300, 1500).problems
    assert any("into the bottom band" in p for p in problems)
    assert any("30px" in p for p in problems)


def test_touching_the_boundary_exactly_is_allowed():
    """220 is the first usable row, not the last forbidden one."""
    assert placed(220, H - 450).problems == []


def test_both_margins_are_checked_independently():
    problems = placed(300, 1400, left=40, right=1050).problems
    assert any("left margin" in p for p in problems)
    assert any("right margin" in p for p in problems)


def test_a_full_frame_element_breaches_everything():
    """A terminal clip paints edge to edge by design, which is the loudest
    possible case and has to be caught rather than rounded away."""
    assert len(placed(0, H - 1, left=0, right=W - 1).problems) == 4


def test_an_empty_frame_is_not_a_breach():
    """Nothing drawn is a legitimate moment -- between two cues."""
    p = Placement(1.0, 30, None, None, None, None, W, H)
    check(p, ZONE)
    assert p.empty
    assert p.problems == []


# --- what gets sampled -------------------------------------------------------

def test_every_cue_contributes_its_midpoint():
    cues = [{"enter": 30, "leave": 90}, {"enter": 150, "leave": 210}]
    found = moments(cues, 30, 20.0)
    assert 2.0 in found and 6.0 in found


def test_a_child_cue_is_sampled_just_after_it_lands():
    """An emoji row is only wrong once the last emoji has arrived."""
    cues = [{"enter": 30, "leave": 300,
             "emoji": [{"enter": 30}, {"enter": 120}]}]
    found = moments(cues, 30, 20.0)
    assert 4.4 in found, "the second emoji's moment is missing"


@pytest.mark.parametrize("kind", CHILD_KEYS)
def test_every_kind_of_child_is_sampled(kind):
    """The chip row was invisible here: the kinds were spelled out by hand, and
    the two added later were never added to the list."""
    cues = [{"enter": 30, "leave": 300, kind: [{"enter": 120}]}]
    assert 4.4 in moments(cues, 30, 20.0), f"{kind} children are not sampled"


def test_a_child_with_no_timing_is_skipped_rather_than_crashing():
    """An unresolved phrase leaves enter null; that is a cue-sheet problem to
    report, not a reason for the layout check to die."""
    cues = [{"enter": 30, "leave": 300, "chips": [{"enter": None}]}]
    assert moments(cues, 30, 20.0)


def test_a_video_with_no_cues_is_still_sampled_for_captions():
    assert len(moments([], 30, 20.0)) >= 3


def test_nothing_is_sampled_past_the_end():
    cues = [{"enter": 30, "leave": None}]
    assert all(t < 10.0 for t in moments(cues, 30, 10.0))


# --- the definitions come from one place -------------------------------------

def test_the_safe_zone_is_read_from_tokens_not_restated():
    """Two copies of the insets would drift, and the check would pass against
    numbers the renderer no longer uses."""
    assert safe_zone() == ZONE


def test_the_frame_size_is_read_from_tokens():
    assert dimensions() == (W, H)


# --- a frame that never rendered is not a frame that passed ------------------

def test_a_failed_render_is_reported_and_fails_the_run(capsys):
    """It used to be skipped, leaving the run saying every sampled frame was
    inside the safe zone -- about the subset that happened to render."""
    good = Placement(1.0, 30, 300, 1400, 200, 800, W, H)
    code = report([good], ZONE, "verify", [(4.5, "highest frame is 89")])
    out = capsys.readouterr().out
    assert "did not render" in out and "highest frame is 89" in out
    assert code == 2, "an unchecked frame cannot be a pass"


def test_a_breach_outranks_a_failed_render(capsys):
    bad = Placement(1.0, 30, 100, 1400, 200, 800, W, H)
    check(bad, ZONE)
    assert report([bad], ZONE, "verify", [(4.5, "boom")]) == 1


def test_a_clean_run_still_passes(capsys):
    good = Placement(1.0, 30, 300, 1400, 200, 800, W, H)
    assert report([good], ZONE, "verify", []) == 0


def test_the_error_line_is_shown_not_the_stack_frame():
    """Remotion's last stderr line is a call site inside its own dist/; the
    line that says what went wrong is the one naming the error."""
    stderr = (
        "RangeError: Cannot use frame 135: Duration of composition is 90\n"
        "    at Object.validateFrame (/broll/node_modules/remotion/dist/x.js:21:15)\n"
        "    at process.processTicksAndRejections (node:internal/process:103:5)\n")
    assert reason(stderr, 1).startswith("RangeError: Cannot use frame 135")


def test_a_silent_failure_still_says_something():
    assert "exited 7" in reason("", 7)
