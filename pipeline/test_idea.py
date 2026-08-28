"""Tests for the idea stage.

The rules under test are the ones IDEAS.md states and nothing enforced: both
hooks name a source that is really in their bank, the outline runs HOOK to
LANDING, it says what has to be filmed, and it never writes a timing -- because
the pipeline measures time from the audio.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import idea  # noqa: E402

ANSWERED_BRAND = """\
# Who this is for

## 1. What do you actually do?

**Answer:** Build video automation.

## 2. Who is watching?

**Answer:** People who edit their own reels.
"""

TOPIC = (
    "# what is this about\n"
    "Automating short form video editing end to end with Claude Code and\n"
    "Remotion, so filming is the only step left by hand.\n"
)

# Quoted exactly as their banks have them. That these cannot be paraphrased
# is the point of the check they exercise.
VERBAL = "Can you tell us how to (insert result) in 60 seconds?"
ONSCREEN = "Replaced My Marketing Agency with Claude Code"

OUTLINE = f"""\
# demo

needs         : talking head, plus a screen recording of the render finishing
format        : -
verbal        : Kan du visa hur man klipper en hel video pa en gang?
verbal-from   : {VERBAL}
onscreen      : Ersatte min videoredigerare med Claude
onscreen-from : {ONSCREEN}

## HOOK
One recording in, a finished video out.

## PROBLEM
Every edit is done by hand, and nothing about it accumulates.

## LANDING
I only press record now.
"""


@pytest.fixture
def idea_dir(tmp_path, monkeypatch):
    """A filled-in idea that passes, for each test to break one thing in."""
    brand = tmp_path / "BRAND.md"
    brand.write_text(ANSWERED_BRAND, encoding="utf-8")
    monkeypatch.setattr(idea, "BRAND", brand)
    monkeypatch.setattr(idea, "TOPICS", tmp_path / "topics")
    monkeypatch.setattr(idea, "OUTLINES", tmp_path / "outlines")
    idea.TOPICS.mkdir()
    idea.OUTLINES.mkdir()
    idea.topic_path("demo").write_text(TOPIC, encoding="utf-8")
    idea.outline_path("demo").write_text(OUTLINE, encoding="utf-8")
    return tmp_path


def rewrite(name: str, old: str, new: str) -> None:
    path = idea.outline_path(name)
    path.write_text(path.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8")


def test_a_complete_idea_passes(idea_dir):
    assert idea.problems("demo") == []


def test_unanswered_brand_stops_everything(idea_dir):
    idea.BRAND.write_text(
        ANSWERED_BRAND.replace("**Answer:** Build video automation.",
                               "**Answer:**"),
        encoding="utf-8")
    assert any("What do you actually do" in p for p in idea.problems("demo"))


def test_an_idea_needs_both_hooks(idea_dir):
    """They are different banks doing different jobs; one will not cover."""
    rewrite("demo", f"verbal        : Kan du visa hur man klipper en hel video pa en gang?",
            "verbal        :")
    assert any("no verbal hook" in p for p in idea.problems("demo"))


def test_a_hook_with_no_source_is_not_a_match(idea_dir):
    rewrite("demo", f"onscreen-from : {ONSCREEN}", "onscreen-from :")
    assert any("does not say what it was matched from" in p
               for p in idea.problems("demo"))


@pytest.mark.parametrize("line,fake", [
    (f"verbal-from   : {VERBAL}",
     "verbal-from   : Here is a hook I made up just now"),
    (f"onscreen-from : {ONSCREEN}",
     "onscreen-from : Fired My Video Editor And Hired Claude"),
])
def test_a_source_outside_the_bank_is_an_invented_hook(idea_dir, line, fake):
    """The one failure both banks exist to prevent, and the only part of
    matching a machine can settle."""
    rewrite("demo", line, fake)
    assert any("is not in" in p and "written hook" in p
               for p in idea.problems("demo"))


def test_a_paraphrased_source_is_caught(idea_dir):
    """Near enough is not verbatim -- that is what makes the bank a bank."""
    rewrite("demo", f"onscreen-from : {ONSCREEN}",
            "onscreen-from : Replaced My Video Editor with Claude Code")
    assert any("is not in" in p for p in idea.problems("demo"))


def test_a_hook_on_a_clock_is_not_a_timing(idea_dir):
    """Half the swipe file is built on a clock. Rejecting those would reject
    the bank, so the timing rule stops at the hook fields."""
    assert "60 seconds" in VERBAL
    assert idea.problems("demo") == []


def test_quoting_differences_are_not_worth_rejecting(idea_dir):
    """`in_bank` flattens quotes, so a quoted-caps source matches unquoted."""
    rewrite("demo", f"onscreen-from : {ONSCREEN}",
            'onscreen-from : "IS MY MARKET TOO SMALL?"')
    assert idea.problems("demo") == []


def test_a_sentence_is_not_an_onscreen_card(idea_dir):
    rewrite("demo", "onscreen      : Ersatte min videoredigerare med Claude",
            "onscreen      : Jag ersatte hela min videoredigerare med Claude"
            " Code och det tog en helg")
    assert any("words;" in p for p in idea.problems("demo"))


def test_an_outline_must_start_on_the_hook(idea_dir):
    rewrite("demo", "## HOOK", "## INTRO")
    assert any("not HOOK" in p for p in idea.problems("demo"))


def test_an_outline_must_land(idea_dir):
    rewrite("demo", "## LANDING", "## AND SO ON")
    assert any("no landing" in p for p in idea.problems("demo"))


def test_an_idea_nobody_can_film_is_not_an_idea(idea_dir):
    rewrite("demo", OUTLINE.splitlines()[2], "needs         :")
    assert any("makeable" in p for p in idea.problems("demo"))


def test_a_format_must_come_from_the_bank(idea_dir):
    rewrite("demo", "format        : -", "format        : splitscreen")
    assert any("not in the formats bank" in p for p in idea.problems("demo"))


def test_a_banked_format_is_accepted(idea_dir):
    rewrite("demo", "format        : -", "format        : beforeafter")
    assert idea.problems("demo") == []


@pytest.mark.parametrize("timing", ["## PROBLEM (10s)", "## PROBLEM 0:10"])
def test_a_beat_may_not_carry_a_duration(idea_dir, timing):
    rewrite("demo", "## PROBLEM", timing)
    assert any("writes a timing" in p for p in idea.problems("demo"))


def test_spoken_content_may_mention_time(idea_dir):
    """The rule is about planned durations, not about what the video says."""
    rewrite("demo", "I only press record now.",
            "It used to take 3 hours. Now it takes 2 minutes.")
    assert idea.problems("demo") == []


def test_an_empty_beat_has_nothing_to_say(idea_dir):
    rewrite("demo", "One recording in, a finished video out.", "")
    assert any("beat HOOK is empty" in p for p in idea.problems("demo"))


def test_a_topic_of_only_comments_says_nothing(idea_dir):
    idea.topic_path("demo").write_text(idea.SEED_TOPIC, encoding="utf-8")
    assert any("says nothing about the video" in p
               for p in idea.problems("demo"))


def test_new_writes_a_pair_that_check_then_complains_about(idea_dir):
    idea.new("fresh")
    assert idea.topic_path("fresh").is_file()
    assert idea.outline_path("fresh").is_file()
    # A seed is not an idea, and saying so is the whole job of `check`.
    assert idea.problems("fresh")
