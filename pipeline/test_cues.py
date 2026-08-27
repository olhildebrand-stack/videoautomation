"""Tests for resolving overlay cues against the speech.

The rule under test: a cue names a phrase, never a time. A sheet written
against one take has to survive a re-record, a re-cut and a reorder, because
the phrase is still the phrase.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cues import (  # noqa: E402
    DEFAULT_HOLD, Problem, phrase_frames, resolve, strip_authoring_keys,
)
from cutlist import Word  # noqa: E402

FPS = 30


def spoken(text: str, start: float = 0.0, step: float = 0.5) -> list[Word]:
    """One word per step, so a frame can be predicted by counting."""
    return [
        Word(f" {token}", round(start + i * step, 3),
             round(start + i * step + step * 0.8, 3), 1.0)
        for i, token in enumerate(text.split())
    ]


WORDS = spoken(
    "jag bygger ett system som sätter varenda short form content editor i "
    "konkurs den ska ha klipp den ska ha captions color correction den ska ha "
    "b-roll och kvaliteten på min content höjas utan mycket mindre arbete"
)


# --- finding a phrase --------------------------------------------------------

def test_a_phrase_resolves_to_the_frame_it_is_spoken_on():
    found = phrase_frames(WORDS, "short form content editor", FPS)
    assert found is not None
    start, end, score = found
    assert score == 1.0
    # "short" is the 8th word, so it starts at 3.5s.
    assert start == round(3.5 * FPS)
    assert end > start


def test_a_phrase_that_was_never_said_resolves_to_nothing():
    assert phrase_frames(WORDS, "helt andra ord här", FPS) is None


def test_a_single_word_cue_works():
    assert phrase_frames(WORDS, "klipp", FPS) is not None


# --- resolving a sheet -------------------------------------------------------

def test_frames_are_filled_in_and_authoring_keys_are_dropped():
    sheet = [{"kind": "wordStack", "cue": "short form content editor",
              "words": ["SHORT"], "hold": 0.4}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    assert not problems
    entry = resolved[0]
    assert entry["enter"] == round(3.5 * FPS)
    assert entry["leave"] > entry["enter"]
    # The renderer should receive frames and nothing it has to interpret.
    assert "hold" not in entry and "until" not in entry


def test_a_cue_that_does_not_match_is_dropped_and_reported():
    """An overlay in the wrong place is worse than no overlay."""
    sheet = [{"kind": "image", "cue": "orden finns inte", "src": "x.png"}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    assert resolved == []
    assert len(problems) == 1
    assert "not said" in problems[0].reason


def test_each_emoji_lands_on_its_own_word():
    sheet = [{"kind": "emojiRow", "emoji": [
        {"emoji": "1", "cue": "klipp"},
        {"emoji": "2", "cue": "captions"},
        {"emoji": "3", "cue": "color correction"},
        {"emoji": "4", "cue": "b-roll"},
    ]}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    assert not problems
    enters = [e["enter"] for e in resolved[0]["emoji"]]
    assert enters == sorted(enters), "emoji must arrive in the order spoken"
    assert len(set(enters)) == 4, "each lands on its own moment"


def test_the_row_holds_until_the_last_emoji_has_landed():
    """Dropping each as the next appeared would show the list one item at a
    time and never show the list."""
    sheet = [{"kind": "emojiRow", "emoji": [
        {"emoji": "1", "cue": "klipp"},
        {"emoji": "4", "cue": "b-roll"},
    ]}]
    resolved, _ = resolve(sheet, WORDS, FPS, 900)
    row = resolved[0]
    assert row["leave"] > max(e["enter"] for e in row["emoji"])


def test_the_parent_enters_with_its_first_child():
    sheet = [{"kind": "emojiRow", "emoji": [
        {"emoji": "1", "cue": "klipp"},
        {"emoji": "2", "cue": "captions"},
    ]}]
    resolved, _ = resolve(sheet, WORDS, FPS, 900)
    assert resolved[0]["enter"] == min(e["enter"] for e in resolved[0]["emoji"])


def test_until_end_never_leaves():
    """The two crossing lines only make their comparison while both are up."""
    sheet = [{"kind": "dualGraph", "until": "end", "series": [
        {"label": "K", "direction": "rising", "colour": "green",
         "cue": "kvaliteten på min content höjas"},
        {"label": "A", "direction": "falling", "colour": "lightBlue",
         "cue": "mycket mindre arbete"},
    ]}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    assert not problems
    assert resolved[0]["leave"] is None
    k, a = resolved[0]["series"]
    assert a["enter"] > k["enter"], "effort falls after quality rises"


def test_until_a_phrase_hands_the_frame_over():
    sheet = [{"kind": "image", "cue": "short form", "src": "x.png",
              "until": "klipp"}]
    resolved, _ = resolve(sheet, WORDS, FPS, 900)
    klipp = phrase_frames(WORDS, "klipp", FPS)
    assert resolved[0]["leave"] == klipp[0]


def test_until_end_of_a_phrase_stays_through_it():
    """`until` leaves as a phrase begins, which ends an effect a beat into the
    sentence it was supposed to be over before."""
    sheet = [{"kind": "push", "from": "start", "untilEndOf": "klipp"}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    assert not problems
    klipp = phrase_frames(WORDS, "klipp", FPS)
    assert resolved[0]["leave"] == klipp[1]
    assert klipp[1] > klipp[0], "the two are not the same frame"


def test_a_missing_until_end_of_phrase_is_reported():
    sheet = [{"kind": "push", "from": "start", "untilEndOf": "aldrig sagt"}]
    _, problems = resolve(sheet, WORDS, FPS, 900)
    assert any("untilEndOf" in p.reason for p in problems)


def test_until_end_of_never_reaches_the_renderer():
    """The props carry frames alone; a phrase there means one was not resolved."""
    sheet = [{"kind": "push", "from": "start", "untilEndOf": "klipp"}]
    resolved, _ = resolve(sheet, WORDS, FPS, 900)
    assert "untilEndOf" not in resolved[0]


def test_the_chat_beats_hang_on_their_own_phrases():
    sheet = [{"kind": "chat", "cue": "klipp", "prompt": "Redigera min video",
              "typesCue": "captions", "repliesCue": "b-roll"}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    assert not problems
    entry = resolved[0]
    assert entry["enter"] < entry["types"] < entry["replies"]
    assert "typesCue" not in entry


def test_a_hold_never_runs_past_the_end_of_the_video():
    sheet = [{"kind": "image", "cue": "mycket mindre arbete", "src": "x.png",
              "hold": 60}]
    resolved, _ = resolve(sheet, WORDS, FPS, 400)
    assert resolved[0]["leave"] == 400


def test_the_default_hold_is_applied_when_none_is_given():
    sheet = [{"kind": "image", "cue": "klipp", "src": "x.png"}]
    resolved, _ = resolve(sheet, WORDS, FPS, 900)
    span = phrase_frames(WORDS, "klipp", FPS)
    assert resolved[0]["leave"] == span[1] + round(DEFAULT_HOLD * FPS)


def test_a_weak_match_is_reported_but_still_placed():
    """Worth a look at the checkpoint; not worth dropping on its own."""
    sheet = [{"kind": "image", "cue": "system som sätter varenda kotte",
              "src": "x.png"}]
    resolved, problems = resolve(sheet, WORDS, FPS, 900)
    if problems:
        assert "matched at" in problems[0].reason or "not found" in problems[0].reason


def test_strip_leaves_children_clean_too():
    cue = {"kind": "emojiRow", "hold": 1,
           "emoji": [{"emoji": "1", "cue": "k", "enter": 3, "endFrame": 9}]}
    out = strip_authoring_keys(cue)
    assert "hold" not in out
    assert "endFrame" not in out["emoji"][0]
    assert out["emoji"][0]["enter"] == 3


def test_a_sheet_survives_the_clip_being_recut():
    """The point of the whole module: same sheet, footage shifted by a second,
    every cue still lands on its own word."""
    sheet = [{"kind": "emojiRow", "emoji": [
        {"emoji": "1", "cue": "klipp"},
        {"emoji": "2", "cue": "captions"},
    ]}]
    later = spoken(" ".join(w.word.strip() for w in WORDS), start=1.0)
    first, _ = resolve(sheet, WORDS, FPS, 900)
    second, _ = resolve(sheet, later, FPS, 900)
    shift = round(1.0 * FPS)
    assert [e["enter"] for e in second[0]["emoji"]] == [
        e["enter"] + shift for e in first[0]["emoji"]
    ]


def test_fps_matches_the_renderer():
    """Cues resolve to frame numbers on this side and are read as frame numbers
    on the other. If the two ever disagree, every overlay in every video slides
    by a factor nobody would think to look for."""
    import re
    import pipeline as p

    tokens = (Path(__file__).parent.parent / "broll" / "src" / "tokens.ts")
    found = re.search(r"export const fps = (\d+)", tokens.read_text(encoding="utf-8"))
    assert found, "could not find the frame rate in tokens.ts"
    assert p.FPS == int(found.group(1))


# --- a cue that misses has to be actionable ----------------------------------

def test_a_hyphen_matches_a_space_and_the_other_way_round():
    """Whisper picks differently between the raw pass and the re-transcribe of
    the cut, so a cue that matched yesterday can miss today."""
    spaced = spoken("den ska ha b roll och allting")
    assert phrase_frames(spaced, "b-roll", FPS) is not None
    hyphened = spoken("den ska ha b-roll och allting")
    assert phrase_frames(hyphened, "b roll", FPS) is not None


def test_a_miss_reports_what_was_said_instead():
    """'not found in the transcript' is true and useless."""
    from cues import nearest
    sheet = [{"kind": "image", "cue": "color correction", "src": "x.png"}]
    said = spoken("den ska ha färgkorrigering och allting")
    _, problems = resolve(sheet, said, FPS, 900)
    assert problems
    assert "closest is" in problems[0].reason
    assert nearest(said, "color correction")


def test_nearest_survives_an_empty_transcript():
    from cues import nearest
    assert nearest([], "vad som helst") == ""


# --- every kind's children resolve, not just the two that had tests ----------

@pytest.mark.parametrize("key,child", [
    ("emoji", {"emoji": "1", "cue": "klipp"}),
    ("series", {"label": "K", "direction": "rising", "colour": "green",
                "cue": "klipp"}),
    ("chips", {"text": "Klipp", "cue": "klipp"}),
    ("slots", {"tone": "bad", "name": "Klipp", "cue": "klipp"}),
])
def test_children_of_every_kind_get_a_frame(key, child):
    """The child-key list lived in three places. Two kinds were added to only
    one of them, so their children resolved to no timing and never appeared --
    with the whole suite green."""
    resolved, problems = resolve([{"kind": "x", key: [child]}], WORDS, FPS, 900)
    assert not problems
    assert resolved, f"the {key} cue was dropped entirely"
    assert resolved[0][key][0]["enter"] >= 0
    assert resolved[0]["enter"] == resolved[0][key][0]["enter"]


def test_a_parent_with_children_needs_no_phrase_of_its_own():
    resolved, _ = resolve(
        [{"kind": "chipRow", "chips": [{"text": "A", "cue": "captions"}]}],
        WORDS, FPS, 900)
    assert resolved[0]["enter"] > 0


def test_a_clip_can_finish_its_output_before_it_leaves():
    """Pacing to a sentence and holding past it are two different moments: the
    terminal cued on "RAW-file" finishes as that sentence does and stays up
    over the next one."""
    words = []
    at = 0.0
    for token in ("du bara slanger in din RAW-file och gor en edit "
                  "men desto fler jag far den att gora").split():
        words.append(Word(" " + token, at, at + 0.3, 0.9))
        at += 0.35

    sheet = [{"kind": "terminal", "cue": "RAW-file",
              "finishBy": "gor en edit", "until": "men desto fler",
              "lines": ["a", "b", "c"]}]
    resolved, problems = resolve(sheet, words, 30, 3000)
    assert problems == []
    cue = resolved[0]
    assert cue["finishes"] > cue["enter"], "it has to finish after it arrives"
    assert cue["leave"] > cue["finishes"], "and leave after it finishes"
    assert "finishBy" not in cue, "the phrase is not the renderer's business"


def test_finishing_by_a_phrase_that_was_not_said_is_reported():
    words = [Word(" hej", 0.0, 0.4, 0.9), Word(" da", 0.4, 0.8, 0.9)]
    sheet = [{"kind": "terminal", "cue": "hej", "finishBy": "aldrig sagt",
              "lines": ["a"]}]
    resolved, problems = resolve(sheet, words, 30, 300)
    assert any("aldrig sagt" in p.cue for p in problems)
    assert "finishes" not in resolved[0]


def test_a_cue_can_anchor_to_the_first_frame_of_the_clip():
    """The mirror of `until: "end"`. An effect meant to fire the instant the
    video begins cannot hang on a phrase: the first word is said a moment in,
    and cueing on it puts the effect a moment late -- which is exactly what the
    operator saw, half a second of nothing before the zoom."""
    words = [Word(" Min", 0.4, 0.7, 0.9), Word(" Claude", 0.7, 1.2, 0.9),
             Word(" redigerar", 1.2, 1.8, 0.9), Word(" sen", 5.0, 5.4, 0.9)]
    sheet = [{"kind": "push", "from": "start", "until": "sen"}]
    resolved, problems = resolve(sheet, words, 30, 300)
    assert problems == []
    assert resolved[0]["enter"] == 0
    assert resolved[0]["leave"] == 150
    assert "from" not in resolved[0], "the anchor is not the renderer's business"


def test_anchoring_to_the_first_frame_beats_the_first_word():
    """The first word is not frame zero, which is the whole point."""
    words = [Word(" Min", 0.4, 0.7, 0.9), Word(" Claude", 0.7, 1.2, 0.9)]
    by_phrase, _ = resolve([{"kind": "push", "cue": "Min Claude"}], words, 30, 300)
    by_start, _ = resolve([{"kind": "push", "from": "start"}], words, 30, 300)
    assert by_phrase[0]["enter"] > 0
    assert by_start[0]["enter"] == 0
