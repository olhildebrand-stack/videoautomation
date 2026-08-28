"""Tests for the idea stage.

The rules under test are the ones IDEAS.md states and nothing enforced: the
hook is a number from the bank rather than text, the outline runs HOOK to
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
    "tools    : Claude Code, Remotion\n"
    "subject  : videoredigering | video editing\n"
    "about    : automating short form video editing end to end\n"
)

OUTLINE = """\
# demo

needs  : talking head, plus a screen recording of the render finishing
format : -
hook   : 36

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


def test_a_written_hook_is_not_a_matched_one(idea_dir):
    rewrite("demo", "hook   : 36", "hook   : stop editing your own videos")
    assert any("never written" in p for p in idea.problems("demo"))


def test_a_hook_number_outside_the_bank_is_caught(idea_dir):
    rewrite("demo", "hook   : 36", "hook   : 9999")
    assert any("not in pipeline/hooks/bank.json" in p
               for p in idea.problems("demo"))


def test_an_outline_must_start_on_the_hook(idea_dir):
    rewrite("demo", "## HOOK", "## INTRO")
    assert any("not HOOK" in p for p in idea.problems("demo"))


def test_an_outline_must_land(idea_dir):
    rewrite("demo", "## LANDING", "## AND SO ON")
    assert any("no landing" in p for p in idea.problems("demo"))


def test_an_idea_nobody_can_film_is_not_an_idea(idea_dir):
    rewrite("demo", OUTLINE.splitlines()[2], "needs  :")
    assert any("makeable" in p for p in idea.problems("demo"))


def test_a_format_must_come_from_the_bank(idea_dir):
    rewrite("demo", "format : -", "format : splitscreen")
    assert any("not in the formats bank" in p for p in idea.problems("demo"))


def test_a_banked_format_is_accepted(idea_dir):
    rewrite("demo", "format : -", "format : beforeafter")
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


def test_the_blank_seed_cannot_be_ranked_against(idea_dir):
    idea.topic_path("demo").write_text(idea.SEED_TOPIC, encoding="utf-8")
    assert any("blank seed" in p for p in idea.problems("demo"))


def test_hooks_rank_without_a_recording(idea_dir):
    """The whole point of matching here: there is no transcript yet."""
    topic = idea.parse_topic(TOPIC)
    candidates = idea.generate("", topic)
    assert candidates and not idea.bank_has_nothing(candidates)


def test_new_writes_a_pair_that_check_then_complains_about(idea_dir):
    idea.new("fresh")
    assert idea.topic_path("fresh").is_file()
    assert idea.outline_path("fresh").is_file()
    # A seed is not an idea, and saying so is the whole job of `check`.
    assert idea.problems("fresh")
