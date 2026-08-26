"""Tests for re-applying corrections to an existing transcript."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import recorrect as r  # noqa: E402


def _w(word, start, end):
    return {"word": word, "start": start, "end": end, "probability": 0.99}


def _doc(words):
    return {
        "words": words,
        "word_count": len(words),
        "corrections_applied": {},
        "segments": [{"id": 0, "start": words[0]["start"], "end": words[-1]["end"],
                      "text": "".join(w["word"] for w in words), "words": list(words)}],
    }


PHANTOM = [
    _w(" behöva", 78.92, 79.32), _w(" göra", 79.32, 79.48),
    _w(" mer.", 79.48, 79.71), _w(" Och", 79.69, 79.82),
    _w(" mycket", 79.82, 80.10), _w(" mindre", 80.10, 80.48),
]
RULE = [("göra mer. Och mycket mindre", "göra mycket mindre")]


def test_invented_words_are_removed():
    data, applied = r.recorrect(_doc(PHANTOM), RULE)
    text = "".join(w["word"] for w in data["words"]).strip()
    assert text == "behöva göra mycket mindre"
    assert applied


def test_segment_text_is_rebuilt_to_match():
    data, _ = r.recorrect(_doc(PHANTOM), RULE)
    assert data["segments"][0]["text"].strip() == "behöva göra mycket mindre"
    joined = "".join(w["word"] for w in data["words"])
    assert data["segments"][0]["text"] == joined


def test_word_count_is_updated():
    data, _ = r.recorrect(_doc(PHANTOM), RULE)
    assert data["word_count"] == len(data["words"]) == 4


def test_counts_accumulate_onto_the_original_run():
    doc = _doc(PHANTOM)
    doc["corrections_applied"] = {"bullbordad => fullbordad": 1}
    data, _ = r.recorrect(doc, RULE)
    assert data["corrections_applied"]["bullbordad => fullbordad"] == 1
    assert "göra mer. Och mycket mindre => göra mycket mindre" in data["corrections_applied"]


def test_no_matching_rule_leaves_the_text_alone():
    doc = _doc([_w(" helt", 0.0, 0.4), _w(" andra", 0.4, 0.8)])
    data, applied = r.recorrect(doc, RULE)
    assert applied == {}
    assert "".join(w["word"] for w in data["words"]).strip() == "helt andra"


def test_single_word_rules_still_apply():
    doc = _doc([_w(" en", 0.0, 0.2), _w(" cloud", 0.2, 0.6)])
    data, applied = r.recorrect(doc, [("cloud", "Claude")])
    assert "Claude" in "".join(w["word"] for w in data["words"])
    assert applied


def test_a_transcript_without_segments_still_works():
    """Older files, and anything hand-assembled, have only a words list."""
    data, applied = r.recorrect({"words": list(PHANTOM)}, RULE)
    assert "".join(w["word"] for w in data["words"]).strip() == "behöva göra mycket mindre"
    assert applied


# --- corrections spanning a Whisper segment boundary ------------------------

def test_a_rule_spanning_two_segments_still_matches():
    """Whisper breaks segments at sentence ends, so an invented full stop puts
    the two halves of the run in different segments. Applied per segment the
    rule could never match, which is how a correct rule looked broken."""
    seg_a = [_w(" behöva", 78.92, 79.32), _w(" göra", 79.32, 79.48),
             _w(" mer.", 79.48, 79.71)]
    seg_b = [_w(" Och", 79.69, 79.82), _w(" mycket", 79.82, 80.10),
             _w(" mindre", 80.10, 80.48)]
    doc = {
        "words": seg_a + seg_b,
        "segments": [
            {"id": 0, "start": 78.92, "end": 79.71,
             "text": "".join(w["word"] for w in seg_a), "words": seg_a},
            {"id": 1, "start": 79.69, "end": 80.48,
             "text": "".join(w["word"] for w in seg_b), "words": seg_b},
        ],
    }
    data, applied = r.recorrect(doc, RULE)
    assert applied, "the run spans a boundary and must still be seen"
    assert "".join(w["word"] for w in data["words"]).strip() == "behöva göra mycket mindre"


def test_segments_are_rebuilt_after_a_spanning_correction():
    """The original grouping described text that no longer exists."""
    seg_a = [_w(" göra", 0.0, 0.2), _w(" mer.", 0.2, 0.4)]
    seg_b = [_w(" Och", 0.4, 0.6), _w(" mycket", 0.6, 0.8),
             _w(" mindre", 0.8, 1.0), _w(" nu.", 1.0, 1.2)]
    doc = {"words": seg_a + seg_b,
           "segments": [{"id": 0, "start": 0.0, "end": 0.4, "text": "", "words": seg_a},
                        {"id": 1, "start": 0.4, "end": 1.2, "text": "", "words": seg_b}]}
    data, _ = r.recorrect(doc, RULE)
    assert len(data["segments"]) == 1, "the boundary was the phantom full stop"
    assert data["segments"][0]["text"].strip() == "göra mycket mindre nu."
    assert data["segments"][0]["id"] == 0


def test_rebuilt_segments_cover_every_word():
    data, _ = r.recorrect(_doc(PHANTOM), RULE)
    in_segments = sum(len(s["words"]) for s in data["segments"])
    assert in_segments == len(data["words"])


# --- deletion ---------------------------------------------------------------

def test_a_deletion_rule_removes_the_word_without_retranscribing():
    """The whole point of recorrect: a phantom goes without touching the GPU."""
    words = [_w(" Okej", 0.5, 0.9), _w(" Textning.nu", 1.0, 1.4), _w(" nu", 1.5, 1.7)]
    data, applied = r.recorrect(_doc(words), [("Textning.nu", "")])
    assert [w["word"] for w in data["words"]] == [" Okej", " nu"]
    assert data["word_count"] == 2
    assert applied == {"Textning.nu => ": 1}
    assert "Textning" not in data["segments"][0]["text"]


def test_a_deleted_words_time_goes_to_the_word_before_it():
    words = [_w(" Okej", 0.5, 0.9), _w(" Textning.nu", 1.0, 1.4), _w(" nu", 1.5, 1.7)]
    data, _ = r.recorrect(_doc(words), [("Textning.nu", "")])
    assert data["words"][0]["end"] == 1.4
