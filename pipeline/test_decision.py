"""Tests for checking a director's decision.

Why this exists: putting a brain in the loop is only worth it if there is a
mechanical answer to "did it actually say something workable". Every check here
is one that would otherwise be found by watching the finished video.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cutlist import Word  # noqa: E402
from brief import takes as split_takes  # noqa: E402
from decision import (  # noqa: E402
    SCHEMA, edit_script, overlay_sheet, validate,
)
from sentences import analyse  # noqa: E402


def transcribe(text: str, start: float = 0.0, gap: float = 0.0) -> list[Word]:
    """Words at a steady pace, so a sentence's timing is predictable."""
    words = []
    at = start
    for token in text.split():
        words.append(Word(f" {token}", at, at + 0.3, 0.9))
        at += 0.3 + gap
    return words


RAW = transcribe("Det har ar hooken.") + transcribe(
    "Det forsta steget ar planering.", start=3.0) + transcribe(
    "Och det andra ar struktur.", start=6.0)
SENTENCES = analyse(RAW)
TAKES = split_takes(RAW, SENTENCES)


def decide(keep, drop, overlays=None, pick=1):
    return {"throughline": "t", "keep": keep, "drop": drop,
            "overlays": overlays or [], "hook": {"pick": pick, "why": "w"}}


def beat(name, takes, why="w"):
    return {"beat": name, "takes": takes, "why": why}


# --- every sentence gets a decision ------------------------------------------

def test_a_complete_decision_passes():
    keep = [beat("HOOK", [0]), beat("STEP 1", [1]), beat("STEP 2", [2])]
    assert validate(decide(keep, []), TAKES) == []


def test_an_unmentioned_take_is_the_whole_point():
    """A take full of retakes shipped with every retake intact because nothing
    made anyone decide about them one at a time."""
    problems = validate(decide([beat("HOOK", [0])], []), TAKES)
    assert any("neither `keep` nor `drop`" in p for p in problems)
    assert any("1" in p and "2" in p for p in problems)


def test_dropping_is_a_decision_and_passes():
    keep = [beat("HOOK", [0])]
    drop = [{"takes": [1, 2], "why": "restated better later"}]
    assert validate(decide(keep, drop), TAKES) == []


def test_a_take_kept_and_dropped_is_reported():
    keep = [beat("HOOK", [0]), beat("STEP", [1])]
    drop = [{"takes": [1, 2], "why": "w"}]
    problems = validate(decide(keep, drop), TAKES)
    assert any("listed twice" in p for p in problems)


def test_a_take_that_does_not_exist_says_the_real_range():
    keep = [beat("HOOK", [0]), beat("X", [99])]
    drop = [{"takes": [1, 2], "why": "w"}]
    problems = validate(decide(keep, drop), TAKES)
    assert any("99" in p and f"0-{len(TAKES) - 1}" in p for p in problems)


def test_an_empty_keep_is_not_a_video():
    problems = validate(decide([], [{"takes": [0, 1, 2], "why": "w"}]), TAKES)
    assert any("no video" in p for p in problems)


def test_a_beat_holding_nothing_is_reported():
    keep = [beat("HOOK", [0]), beat("EMPTY", [])]
    drop = [{"takes": [1, 2], "why": "w"}]
    problems = validate(decide(keep, drop), TAKES)
    assert any("keeps no takes" in p for p in problems)


# --- overlays hang on words that survive -------------------------------------

def test_a_cue_quoting_a_kept_take_passes():
    keep = [beat("HOOK", [0]), beat("STEP", [1]), beat("STEP2", [2])]
    overlays = [{"kind": "wordStack", "cue": "planering", "why": "w"}]
    assert validate(decide(keep, [], overlays), TAKES) == []


def test_a_cue_quoting_a_dropped_take_is_caught_before_the_cut():
    """This used to be found at render time, after the edit was committed."""
    keep = [beat("HOOK", [0])]
    drop = [{"takes": [1, 2], "why": "w"}]
    overlays = [{"kind": "wordStack", "cue": "planering", "why": "w"}]
    problems = validate(decide(keep, drop, overlays), TAKES)
    assert any("planering" in p and "kept" in p for p in problems)


def test_a_child_cue_is_checked_too():
    keep = [beat("HOOK", [0]), beat("STEP", [1]), beat("STEP2", [2])]
    overlays = [{"kind": "chipRow", "why": "w", "chips": [
        {"text": "planering", "cue": "planering"},
        {"text": "utforande", "cue": "utforande"}]}]
    problems = validate(decide(keep, [], overlays), TAKES)
    assert any("utforande" in p for p in problems)


# --- the decision becomes files ----------------------------------------------

def test_the_edit_script_is_one_beat_per_take_in_the_chosen_order():
    keep = [beat("LANDING", [2]), beat("HOOK", [0])]
    drop = [{"takes": [1], "why": "w"}]
    beats = edit_script(decide(keep, drop), TAKES)
    assert [b["beat"] for b in beats] == ["LANDING.T2", "HOOK.T0"]
    assert all(b["end"] > b["start"] for b in beats)


def test_the_ranges_come_from_the_transcript_not_from_the_model():
    keep = [beat("HOOK", [0])]
    drop = [{"takes": [1, 2], "why": "w"}]
    beats = edit_script(decide(keep, drop), TAKES)
    assert beats[0]["start"] == TAKES[0].start
    assert beats[0]["end"] == TAKES[0].end


def test_a_take_that_does_not_exist_is_skipped_rather_than_crashing():
    """The validator has already complained; building files must not also
    explode, or the operator never gets to see what it meant."""
    keep = [beat("HOOK", [0]), beat("GHOST", [99])]
    assert len(edit_script(decide(keep, []), TAKES)) == 1


def test_the_reasoning_is_stripped_out_of_the_overlay_sheet():
    sheet = overlay_sheet({"overlays": [
        {"kind": "wordStack", "cue": "planering", "why": "explains it"}]})
    assert sheet == [{"kind": "wordStack", "cue": "planering"}]


# --- the schema is the CLI's contract ----------------------------------------

def test_the_schema_forbids_the_director_writing_frames():
    """A director that writes a frame number has written a timestamp, which is
    the thing this design removes."""
    overlay = SCHEMA["properties"]["overlays"]["items"]
    assert "enter" not in overlay["properties"]
    assert "leave" not in overlay["properties"]
    assert overlay["additionalProperties"] is False


def test_the_schema_forbids_the_director_writing_hook_text():
    assert set(SCHEMA["properties"]["hook"]["properties"]) == {"pick", "why"}


# Kinds the renderer can draw but the director may not name. Each one is here
# because it was watched in a finished video and ruled out, not because it is
# broken -- so the component stays and the permission goes.
RETIRED = {"wordStack"}


def test_every_overlay_kind_the_renderer_knows_is_offered_unless_retired():
    types = (Path(__file__).resolve().parent.parent
             / "broll" / "src" / "overlays" / "types.ts").read_text(encoding="utf-8")
    block = types.split("export type OverlayKind =")[1].split(";")[0]
    declared = {part.strip().strip("|' ") for part in block.split("\n")}
    declared = {d for d in declared if d}
    offered = set(SCHEMA["properties"]["overlays"]["items"]
                  ["properties"]["kind"]["enum"])
    assert declared - RETIRED == offered
    assert RETIRED <= declared, "a retired kind should still exist to draw"


def test_a_retired_kind_cannot_be_named_by_the_director():
    """The operator watched wordStack and ruled it out for good. A kind the
    director cannot name is a kind that cannot come back by accident."""
    offered = SCHEMA["properties"]["overlays"]["items"]["properties"]["kind"]["enum"]
    assert not RETIRED & set(offered)


def test_a_reason_is_required_everywhere_a_choice_is_made():
    """The reasons are what the operator reads when the cut looks wrong."""
    assert "why" in SCHEMA["properties"]["keep"]["items"]["required"]
    assert "why" in SCHEMA["properties"]["drop"]["items"]["required"]
    assert "why" in SCHEMA["properties"]["overlays"]["items"]["required"]
    assert "why" in SCHEMA["properties"]["hook"]["required"]


# --- a push has to say where it ends -----------------------------------------

def full(overlays):
    return decide([beat("ALL", [t.index for t in TAKES])], [], overlays)


def test_a_push_with_no_end_is_rejected():
    """It scales the footage. One that never releases leaves the whole video
    cropped, and nothing in the sheet says it was meant to be a moment."""
    problems = validate(full([{"kind": "push", "from": "start", "why": "w"}]), TAKES)
    assert any("never where it ends" in p for p in problems)


def test_a_push_until_the_end_of_the_clip_is_rejected():
    problems = validate(full([
        {"kind": "push", "from": "start", "until": "end", "why": "w"}]), TAKES)
    assert any("crops the whole" in p for p in problems)


def test_a_push_that_releases_passes():
    assert validate(full([
        {"kind": "push", "from": "start", "until": "planering", "why": "w"}]),
        TAKES) == []


def test_a_hold_counts_as_an_ending():
    assert validate(full([
        {"kind": "push", "from": "start", "hold": 1.5, "why": "w"}]), TAKES) == []


def test_other_kinds_may_stay_to_the_end():
    """Only the push crops the picture; a row of chips holding to the end is
    an ordinary choice."""
    assert validate(full([
        {"kind": "chipRow", "until": "end", "why": "w",
         "chips": [{"text": "P", "cue": "planering"}]}]), TAKES) == []
