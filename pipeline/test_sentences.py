"""Tests for sentence splitting and blooper classification.

Built on the real videoautomationsystem.mp4 transcript, where the bloopers are
known by ear.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cutlist import Word  # noqa: E402
from sentences import (  # noqa: E402
    analyse, classify, keepers, split_sentences,
)

REAL = (
    "Jag håller på att bygga ett system som kommer sätta varenda short form "
    "content editor i konkurs. "
    "Och jag kommer använda det här kontot som testkanin. "
    "Det jag ska åstadkomma med systemet är att jag ska bara filma en video "
    "och så skicka in den. "
    "Och sen så kommer det ut en helt edit. "
    "Det jag ska försöka åstadkomma med det här systemet är att jag ska bara "
    "filma en video och sen ska jag skicka in den. "
    "Och så kommer det ut en fullbordad video. "
    "Den ska ha captions, color correction, den ska ha... "
    "Den ska ha klipp, den ska ha captions, color correction, den ska ha "
    "b-roll, den ska ha allting. "
    "Och ingenting ska jag behöva göra själv. "
    "Så inte bara kommer jag... "
    "Så inte bara kommer kvaliteten på min content gå upp. "
    "Så inte bara kommer kvaliteten på min content höjas. "
    "Utan jag kommer också behöva göra mer. "
    "Och mycket mindre för att få ut min content."
)


def make_words(text: str) -> list[Word]:
    words, cursor = [], 0.0
    for token in text.split():
        duration = 0.06 + len(token) * 0.035
        words.append(Word(f" {token}", round(cursor, 3), round(cursor + duration, 3), 0.95))
        cursor += duration + 0.04
    return words


WORDS = make_words(REAL)


# --- splitting --------------------------------------------------------------

def test_splits_on_terminal_punctuation():
    sentences = split_sentences(make_words("Ett. Två! Tre?"))
    assert [s.text for s in sentences] == ["Ett.", "Två!", "Tre?"]


def test_ellipsis_ends_a_sentence():
    sentences = split_sentences(make_words("Den ska ha... Den ska ha klipp."))
    assert len(sentences) == 2
    assert sentences[0].text == "Den ska ha..."


def test_trailing_group_without_punctuation_still_becomes_a_sentence():
    sentences = split_sentences(make_words("Klart. Och sen"))
    assert len(sentences) == 2
    assert sentences[1].text == "Och sen"


def test_sentence_spans_its_words():
    sentences = split_sentences(WORDS)
    first = sentences[0]
    assert first.start == WORDS[0].start
    assert first.end == first.words[-1].end
    assert first.duration > 0


def test_every_word_lands_in_exactly_one_sentence():
    sentences = split_sentences(WORDS)
    assert sum(len(s.words) for s in sentences) == len(WORDS)


# --- classification ---------------------------------------------------------

def test_truncated_sentences_are_flagged():
    sentences = analyse(WORDS)
    truncated = [s.index for s in sentences if s.truncated]
    # "Den ska ha..." and "Så inte bara kommer jag..."
    assert len(truncated) == 2
    for index in truncated:
        assert sentences[index].text.endswith("...")


def test_retaken_lines_are_superseded_by_the_later_take():
    sentences = analyse(WORDS)
    by_text = {s.text: s for s in sentences}
    early = by_text["Det jag ska åstadkomma med systemet är att jag ska bara "
                    "filma en video och så skicka in den."]
    assert early.superseded_by is not None
    later = sentences[early.superseded_by]
    assert "försöka" in later.text, "the fuller take should win"


def test_the_last_take_of_a_group_is_kept():
    sentences = analyse(WORDS)
    kept = [s.text for s in keepers(sentences)]
    assert any("höjas" in t for t in kept)
    assert not any("gå upp" in t for t in kept), "the earlier take must go"


def test_classification_matches_the_bloopers_identified_by_ear():
    """Five bloopers, and the survivors are the manual edit."""
    sentences = analyse(WORDS)
    bloopers = [s.text for s in sentences if s.is_blooper]
    assert len(bloopers) == 5
    assert any("åstadkomma med systemet" in b for b in bloopers)
    assert any("helt edit" in b for b in bloopers)
    assert any(b.endswith("den ska ha...") for b in bloopers)
    assert any(b == "Så inte bara kommer jag..." for b in bloopers)
    assert any("gå upp" in b for b in bloopers)


def test_good_sentences_survive():
    kept = [s.text for s in keepers(analyse(WORDS))]
    assert len(kept) == 9
    assert any("konkurs" in t for t in kept)
    assert any("testkanin" in t for t in kept)
    assert any("fullbordad" in t for t in kept)
    assert any("b-roll" in t for t in kept)


def test_a_short_common_opening_is_not_treated_as_a_retake():
    """'Och sen.' twice should not supersede on two words alone."""
    sentences = analyse(make_words("Och sen. Helt andra ord här. Och sen."))
    assert sentences[0].superseded_by is None


def test_unrelated_sentences_are_not_superseded():
    sentences = analyse(make_words(
        "Katten sover på soffan. Bilen står utanför huset."))
    assert all(s.superseded_by is None for s in sentences)


def test_a_truncated_sentence_does_not_supersede_anything():
    sentences = analyse(make_words("Jag ska bygga ett system. Jag ska bygga ett..."))
    assert sentences[0].superseded_by is None, "a fragment must not win over a full take"
    assert sentences[1].truncated


# --- sentence ranges --------------------------------------------------------

from sentences import (  # noqa: E402
    DEFAULT_END_TAIL, DEFAULT_HEAD, DEFAULT_TAIL, sentence_range,
)


def test_tail_is_added_after_a_sentence():
    words = make_words("Klart. ")
    sentences = split_sentences(words)
    start, end = sentence_range(sentences[0], words, tail=0.5)
    assert end == pytest.approx(sentences[0].end + 0.5, abs=0.001)


def test_tail_never_reaches_the_next_word():
    words = [Word(" Klart.", 1.0, 1.4, 1.0), Word(" Och", 1.5, 1.7, 1.0)]
    sentences = split_sentences(words)
    _, end = sentence_range(sentences[0], words, tail=0.5)
    assert end <= 1.5, "a generous tail must not pull in the next sentence"


def test_head_never_reaches_the_previous_word():
    words = [Word(" Slut.", 1.0, 1.4, 1.0), Word(" Nytt.", 1.45, 1.9, 1.0)]
    sentences = split_sentences(words)
    start, _ = sentence_range(sentences[1], words, head=0.5)
    assert start >= 1.4


def test_default_room_is_the_values_settled_by_ear():
    """0.5 dragged, 0.2 was still loose: 0.15 after a sentence and 0.05 before
    it, with more at the very end where the tail is all there is before black."""
    assert DEFAULT_HEAD == 0.05
    assert DEFAULT_TAIL == 0.15
    assert DEFAULT_END_TAIL == 0.3
    assert DEFAULT_END_TAIL > DEFAULT_TAIL > DEFAULT_HEAD


def test_the_final_sentence_gets_the_longer_tail():
    words = [Word(" Slut.", 1.0, 1.4, 1.0)]
    sentence = analyse(words)[0]
    normal = sentence_ranges(sentence, words, is_final=False)[-1][1]
    final = sentence_ranges(sentence, words, is_final=True)[-1][1]
    assert final > normal
    assert final == pytest.approx(1.4 + DEFAULT_END_TAIL, abs=0.001)


def test_range_is_clamped_at_zero():
    words = [Word(" Start.", 0.05, 0.4, 1.0)]
    start, _ = sentence_range(split_sentences(words)[0], words, head=0.5)
    assert start == 0.0


# --- splitting a sentence at silence inside it ------------------------------

from cutlist import clamp_slack  # noqa: E402
from sentences import sentence_ranges  # noqa: E402

HOOK_RAW = [
    (" Jag", 0.00, 0.74), (" håller", 0.74, 0.98), (" på", 0.98, 1.12),
    (" att", 1.12, 1.16), (" bygga", 1.16, 1.28), (" ett", 1.28, 1.42),
    (" system", 1.42, 1.72), (" som", 1.72, 2.02), (" kommer", 2.02, 2.24),
    (" sätta", 2.24, 2.64), (" varenda", 2.64, 3.34),
    (" short", 3.34, 11.34),          # the discarded takes live in here
    (" form", 11.34, 11.78), (" content", 11.78, 12.20),
    (" editor", 12.20, 12.80), (" i", 12.80, 13.28), (" konkurs.", 13.28, 13.92),
]


def hook_words():
    words = [Word(w, s, e, 0.95) for w, s, e in HOOK_RAW]
    return clamp_slack(words)[0]


def test_a_sentence_splits_at_silence_inside_it():
    words = hook_words()
    sentence = analyse(words)[0]
    pieces = sentence_ranges(sentence, words)
    assert len(pieces) == 2
    assert pieces[0][1] < 4.0 and pieces[1][0] > 10.0


def test_splitting_removes_the_discarded_takes():
    """Fourteen seconds of span, about seven of speech."""
    words = hook_words()
    sentence = analyse(words)[0]
    total = sum(b - a for a, b in sentence_ranges(sentence, words))
    assert 6.5 < total < 8.5, f"expected around 7s, got {total:.1f}s"


def test_a_continuous_sentence_stays_one_piece():
    words = make_words("Och jag kommer använda det här kontot som testkanin.")
    sentence = analyse(words)[0]
    assert len(sentence_ranges(sentence, words)) == 1


def test_only_the_last_piece_gets_the_full_tail():
    """A half second mid-sentence is a hole, not a landing."""
    words = hook_words()
    sentence = analyse(words)[0]
    pieces = sentence_ranges(sentence, words, tail=0.5)
    first_gap = pieces[0][1] - sentence.words[10].end
    assert first_gap < 0.2, "internal break should be tight"
    assert pieces[-1][1] > sentence.end + 0.4, "the sentence still lands"


def test_max_gap_zero_keeps_the_sentence_whole():
    words = hook_words()
    sentence = analyse(words)[0]
    pieces = sentence_ranges(sentence, words, max_gap=1e9)
    assert len(pieces) == 1


def test_pieces_never_overlap_and_stay_ordered():
    words = hook_words()
    pieces = sentence_ranges(analyse(words)[0], words)
    for earlier, later in zip(pieces, pieces[1:]):
        assert earlier[1] <= later[0]


def test_a_one_word_island_is_short_enough_to_warrant_a_warning():
    """Three pieces with a ~1s island is where alignment has gone unreliable.

    The report warns on exactly this shape; the split itself is a guess.
    """
    # The full run: dropping intermediate words would manufacture gaps that
    # are not in the recording and split it further than reality does.
    raw = [
        (" Jag", 0.18, 0.74), (" håller", 0.74, 0.98), (" på", 0.98, 1.12),
        (" att", 1.12, 1.16), (" bygga", 1.16, 1.28), (" ett", 1.28, 1.42),
        (" system", 1.42, 1.72), (" som", 1.72, 2.02), (" kommer", 2.02, 2.24),
        (" sätta", 2.24, 2.64), (" varenda", 2.64, 3.34),
        (" short", 3.30, 10.10),          # clamped, leaving islands either side
        (" form", 11.34, 11.78), (" content", 11.78, 12.20),
        (" editor", 12.20, 12.80), (" i", 12.80, 13.28),
        (" konkurs.", 13.28, 13.92),
    ]
    words = clamp_slack([Word(w, s, e, 0.9) for w, s, e in raw])[0]
    pieces = sentence_ranges(analyse(words)[0], words)
    assert len(pieces) == 3
    assert min(b - a for a, b in pieces) < 1.2, "the island the warning targets"
