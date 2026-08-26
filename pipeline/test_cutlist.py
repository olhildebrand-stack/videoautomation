"""Tests for cut-list matching. Built on the real transcript text."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cutlist import (  # noqa: E402
    CutList, Word, build_cutlist, clamp_slack, drop_hallucinations, find_span,
    merge_adjacent, normalise, tokenise,
)

# The actual transcript from Formulär är bra för kundkontakt.mp4.
REAL = (
    "Min Claude kan nu göra custom formulär med designen av min brand consistently. "
    "Och allt jag behöver göra är att skicka den frågor som jag behöver få svar på "
    "av min kund och så skapa den ett formulär. Det är faktiskt jättelätt att sätta "
    "upp det också. Ni kan ta den här videon, ta transcripten och bara skicka den "
    "till Claude direkt. Alla svaren hamnar i Google Sheets."
)


def make_words(text: str, rate: float = 0.4) -> list[Word]:
    words = []
    cursor = 0.0
    for token in text.split():
        words.append(Word(word=f" {token}", start=round(cursor, 3), end=round(cursor + rate - 0.05, 3)))
        cursor += rate
    return words


WORDS = make_words(REAL)


# --- normalisation ----------------------------------------------------------

def test_normalise_strips_punctuation_and_case():
    assert normalise(" Claude.") == "claude"
    assert normalise("Formulär,") == "formulär"


def test_normalise_preserves_swedish_letters():
    """'formulär' and 'formular' are different words; do not fold accents away."""
    assert normalise("formulär") != normalise("formular")


def test_tokenise_drops_empties():
    assert tokenise("  Hej   och  ") == ["hej", "och"]


# --- exact matching ---------------------------------------------------------

def test_exact_line_matches_with_full_score():
    span = find_span(WORDS, "Det är faktiskt jättelätt att sätta upp det också")
    assert span is not None
    _, _, score = span
    assert score == 1.0


def test_match_is_punctuation_and_case_insensitive():
    span = find_span(WORDS, "alla svaren hamnar i google sheets.")
    assert span is not None
    assert span[2] == 1.0


def test_span_maps_to_correct_timestamps():
    span = find_span(WORDS, "Alla svaren hamnar i Google Sheets")
    assert span is not None
    first, last, _ = span
    assert WORDS[first].word.strip() == "Alla"
    assert WORDS[last].word.strip() == "Sheets."


# --- approximate matching ---------------------------------------------------

def test_line_missing_a_filler_word_still_matches():
    span = find_span(WORDS, "Det är jättelätt att sätta upp det också")
    assert span is not None
    assert span[2] < 1.0, "not exact"
    assert span[2] >= 0.72, "but above the floor"


def test_unrelated_line_does_not_match():
    assert find_span(WORDS, "helt andra ord som inte finns i transkriptet alls") is None


def test_empty_phrase_returns_none():
    assert find_span(WORDS, "") is None


def test_empty_words_returns_none():
    assert find_span([], "någonting") is None


# --- cut list ---------------------------------------------------------------

def test_build_cutlist_orders_by_script_not_source():
    """The landing line is deliberately moved to the end."""
    beats = [
        ("HOOK", "Det är faktiskt jättelätt att sätta upp det också"),
        ("LANDING", "Min Claude kan nu göra custom formulär"),
    ]
    cuts = build_cutlist(WORDS, beats)
    assert [s.beat for s in cuts.segments] == ["HOOK", "LANDING"]
    assert cuts.segments[0].start > cuts.segments[1].start, "script order, not source order"


def test_cutlist_records_misses_rather_than_guessing():
    beats = [("HOOK", "Alla svaren hamnar i Google Sheets"), ("X", "ord som inte finns här alls")]
    cuts = build_cutlist(WORDS, beats)
    assert len(cuts.segments) == 1
    assert cuts.misses == [("X", "ord som inte finns här alls")]


def test_padding_is_applied_and_clamped_at_zero():
    beats = [("HOOK", "Min Claude kan nu göra")]
    cuts = build_cutlist(WORDS, beats, pad_start=0.5, pad_end=0.2)
    assert cuts.segments[0].start == 0.0, "cannot pad before the start of the file"


def test_total_duration_sums_segments():
    beats = [
        ("A", "Min Claude kan nu göra custom formulär"),
        ("B", "Alla svaren hamnar i Google Sheets"),
    ]
    cuts = build_cutlist(WORDS, beats)
    assert cuts.total_duration == pytest.approx(
        sum(s.duration for s in cuts.segments), abs=0.001
    )


def test_matched_text_is_recorded_for_review():
    cuts = build_cutlist(WORDS, [("HOOK", "alla svaren hamnar i google sheets")])
    assert "Google Sheets" in cuts.segments[0].matched_text


# --- merging ----------------------------------------------------------------

def test_adjacent_segments_merge():
    segs = [
        __import__("cutlist").Segment("A", "a", 0.0, 1.0, 1.0),
        __import__("cutlist").Segment("B", "b", 1.1, 2.0, 1.0),
    ]
    merged = merge_adjacent(segs, gap=0.25)
    assert len(merged) == 1
    assert merged[0].start == 0.0 and merged[0].end == 2.0
    assert merged[0].beat == "A+B"


def test_distant_segments_do_not_merge():
    segs = [
        __import__("cutlist").Segment("A", "a", 0.0, 1.0, 1.0),
        __import__("cutlist").Segment("B", "b", 9.0, 10.0, 1.0),
    ]
    assert len(merge_adjacent(segs)) == 2


def test_out_of_order_segments_do_not_merge():
    """A landing line moved to the end must not silently rejoin its neighbour."""
    segs = [
        __import__("cutlist").Segment("A", "a", 9.0, 10.0, 1.0),
        __import__("cutlist").Segment("B", "b", 0.0, 1.0, 1.0),
    ]
    assert len(merge_adjacent(segs)) == 2


def test_merge_of_empty_list():
    assert merge_adjacent([]) == []


def test_overlapping_segments_merge_rather_than_duplicating():
    """Padding makes back-to-back lines overlap; cutting both duplicates speech."""
    Segment = __import__("cutlist").Segment
    segs = [Segment("HOOK", "a", 5.88, 9.79, 1.0), Segment("FIX", "b", 9.66, 15.25, 1.0)]
    merged = merge_adjacent(segs)
    assert len(merged) == 1
    assert merged[0].start == 5.88 and merged[0].end == 15.25


def test_a_fully_contained_segment_does_not_shrink_the_merge():
    Segment = __import__("cutlist").Segment
    segs = [Segment("A", "a", 0.0, 10.0, 1.0), Segment("B", "b", 2.0, 3.0, 1.0)]
    merged = merge_adjacent(segs)
    assert len(merged) == 2, "a contained repeat is a deliberate re-use, not a seam"


def test_large_overlap_is_not_treated_as_a_seam():
    Segment = __import__("cutlist").Segment
    segs = [Segment("A", "a", 0.0, 10.0, 1.0), Segment("B", "b", 8.0, 12.0, 1.0)]
    assert len(merge_adjacent(segs, overlap=0.4)) == 2


# --- silence removal --------------------------------------------------------

from cutlist import Segment, drop_fillers, tighten  # noqa: E402


def _words(spec: list[tuple[str, float, float]]) -> list[Word]:
    return [Word(f" {t}", s, e) for t, s, e in spec]


def test_tighten_splits_at_a_long_pause():
    words = _words([("ett", 0.0, 0.4), ("två", 0.5, 0.9), ("tre", 3.0, 3.4)])
    out = tighten([Segment("A", "x", 0.0, 3.4, 1.0)], words, max_gap=0.3)
    assert len(out) == 2, "the 2.1s pause must be cut out"
    assert out[0].end < 1.1 and out[1].start > 2.8


def test_tighten_leaves_natural_pauses_alone():
    words = _words([("ett", 0.0, 0.4), ("två", 0.55, 0.9), ("tre", 1.05, 1.4)])
    out = tighten([Segment("A", "x", 0.0, 1.4, 1.0)], words, max_gap=0.3)
    assert len(out) == 1, "gaps under max_gap are speech rhythm, not dead air"


def test_tighten_keeps_a_breath_rather_than_butt_joining():
    words = _words([("ett", 0.0, 0.4), ("två", 3.0, 3.4)])
    out = tighten([Segment("A", "x", 0.0, 3.4, 1.0)], words, max_gap=0.3, keep=0.12)
    assert out[0].end > 0.4, "a sliver of pause is kept so delivery is not gabbled"
    assert out[1].start < 3.0


def test_tighten_removes_real_time():
    words = _words([("ett", 0.0, 0.4), ("två", 5.0, 5.4)])
    original = Segment("A", "x", 0.0, 5.4, 1.0)
    out = tighten([original], words, max_gap=0.3)
    assert sum(s.duration for s in out) < original.duration - 4.0


def test_tighten_discards_unreadable_slivers():
    words = _words([("a", 0.0, 0.05), ("b", 4.0, 4.5)])
    out = tighten([Segment("A", "x", 0.0, 4.5, 1.0)], words, max_gap=0.3, min_piece=0.2)
    assert all(s.duration >= 0.2 for s in out)


def test_tighten_passes_through_a_single_word_segment():
    words = _words([("ett", 0.0, 0.4)])
    out = tighten([Segment("A", "x", 0.0, 0.4, 1.0)], words)
    assert len(out) == 1 and out[0].duration == pytest.approx(0.4, abs=0.001)


def test_tighten_never_starts_before_zero():
    words = _words([("ett", 0.0, 0.1), ("två", 2.0, 2.4)])
    out = tighten([Segment("A", "x", 0.0, 2.4, 1.0)], words, max_gap=0.3)
    assert all(s.start >= 0.0 for s in out)


# --- filler removal ---------------------------------------------------------

def test_fillers_are_cut_out_of_a_segment():
    words = _words([("och", 0.0, 0.3), ("öh", 0.4, 0.7), ("sen", 0.8, 1.2)])
    out = drop_fillers(words, [Segment("A", "x", 0.0, 1.2, 1.0)], {"öh"})
    assert len(out) == 2
    assert out[0].end <= 0.4 and out[1].start >= 0.7


def test_filler_removal_is_off_by_default():
    words = _words([("öh", 0.0, 0.3), ("sen", 0.4, 0.8)])
    out = drop_fillers(words, [Segment("A", "x", 0.0, 0.8, 1.0)], set())
    assert len(out) == 1, "an empty list must be a no-op"


def test_filler_matching_ignores_punctuation_and_case():
    words = _words([("Öh,", 0.0, 0.3), ("sen", 0.4, 0.8)])
    out = drop_fillers(words, [Segment("A", "x", 0.0, 0.8, 1.0)], {"öh"})
    assert out[0].start >= 0.3, "leading filler removed despite case and comma"


def test_non_filler_words_survive():
    words = _words([("liksom", 0.0, 0.4), ("bra", 0.5, 0.9)])
    out = drop_fillers(words, [Segment("A", "x", 0.0, 0.9, 1.0)], {"öh"})
    assert len(out) == 1


# --- a deliberate mid-sentence cut must survive merging ---------------------

def test_merge_never_reinstates_deliberately_excluded_words():
    """The exact case from videoautomationsystem.mp4.

    The recorded line is "...behöva göra mer. Och mycket mindre...", where the
    stumble inverts the meaning. The edit cuts "mer. Och" out. Those two words
    are short, so the resulting gap falls under the merge threshold -- merging
    on time alone would put them back and reverse the edit.
    """
    Segment = __import__("cutlist").Segment
    words = [
        Word(" göra", 0.0, 0.30),
        Word(" mer.", 0.34, 0.52),     # excluded
        Word(" Och", 0.55, 0.70),      # excluded
        Word(" mycket", 0.74, 1.05),
    ]
    segs = [Segment("T2", "…göra", 0.0, 0.42, 1.0), Segment("T3", "mycket…", 0.66, 1.05, 1.0)]
    assert segs[1].start - segs[0].end < 0.25, "gap is under the time threshold"

    merged = merge_adjacent(segs, words)
    assert len(merged) == 2, "must stay split: the words between were dropped on purpose"


def test_merge_still_joins_when_nothing_lies_between():
    Segment = __import__("cutlist").Segment
    words = [Word(" ett", 0.0, 0.4), Word(" två", 0.5, 0.9)]
    segs = [Segment("A", "a", 0.0, 0.45, 1.0), Segment("B", "b", 0.46, 0.9, 1.0)]
    merged = merge_adjacent(segs, words)
    assert len(merged) == 1, "consecutive words with nothing dropped should rejoin"


def test_merge_without_words_falls_back_to_the_time_rule():
    Segment = __import__("cutlist").Segment
    segs = [Segment("A", "a", 0.0, 1.0, 1.0), Segment("B", "b", 1.1, 2.0, 1.0)]
    assert len(merge_adjacent(segs)) == 1


def test_merge_sees_excluded_words_hidden_by_padding():
    """The real failure from videoautomationsystem.mp4.

    "mer." and "Och" are spoken fast enough that padding narrows the gap past
    both midpoints. Testing the padded span reports an empty gap and merges,
    reinstating the stumble and inverting the meaning; the unpadded speech
    bounds see them.
    """
    words = [Word(" göra", 78.10, 78.40), Word(" mer.", 78.43, 78.55),
             Word(" Och", 78.57, 78.65), Word(" mycket", 78.68, 79.04)]
    cuts = build_cutlist(words, [("T2", "göra"), ("T3", "mycket")])
    a, b = cuts.segments

    # Padding is clamped to the neighbouring words, so the gap stays open at the
    # true speech boundary rather than closing over the dropped words.
    assert a.end <= words[1].start, "must not reach forward into 'mer.'"
    assert b.start >= words[2].end, "must not reach back into 'Och'"

    # And the guard, testing unpadded cores, keeps them apart.
    assert len(merge_adjacent(cuts.segments, words)) == 2


def test_segment_records_unpadded_speech_bounds():
    words = [Word(" ett", 1.00, 1.40)]
    seg = build_cutlist(words, [("A", "ett")], pad_start=0.5, pad_end=0.5).segments[0]
    assert seg.core_start == 1.00 and seg.core_end == 1.40
    assert seg.start < seg.core_start and seg.end > seg.core_end


def test_merged_segment_spans_both_cores():
    words = [Word(" ett", 0.0, 0.4), Word(" två", 0.45, 0.9)]
    merged = merge_adjacent(build_cutlist(words, [("A","ett"),("B","två")]).segments, words)
    assert len(merged) == 1
    assert merged[0].core_start == 0.0 and merged[0].core_end == 0.9


# --- the full sequence, as the pipeline actually runs it --------------------
#
# Merging was tested in isolation twice and passed twice while the real
# pipeline still reinstated the dropped words. These tests run the same order
# the pipeline does: merge -> tighten -> merge.

STUMBLE_WORDS = [
    Word(" höjas.", 75.70, 76.10), Word(" Utan", 76.20, 76.45),
    Word(" jag", 76.50, 76.68), Word(" kommer", 76.72, 77.10),
    Word(" också", 77.15, 77.50), Word(" behöva", 77.55, 77.95),
    Word(" göra", 78.10, 78.40),
    Word(" mer.", 78.43, 78.55),        # dropped by the script
    Word(" Och", 78.57, 78.65),         # dropped by the script
    Word(" mycket", 78.68, 79.04), Word(" mindre", 79.10, 79.50),
]
STUMBLE_BEATS = [("T2", "Utan jag kommer också behöva göra"), ("T3", "mycket mindre")]


def _run_pipeline_sequence(words, beats, max_gap=0.30):
    segs = merge_adjacent(build_cutlist(words, beats).segments, words)
    segs = tighten(segs, words, max_gap=max_gap)
    return merge_adjacent(segs, words)


def _words_in(segments, words):
    kept = []
    for segment in segments:
        kept += [
            w.word.strip() for w in words
            if segment.start <= (w.start + w.end) / 2 <= segment.end
        ]
    return kept


def test_full_sequence_excludes_the_dropped_stumble():
    kept = _words_in(_run_pipeline_sequence(STUMBLE_WORDS, STUMBLE_BEATS), STUMBLE_WORDS)
    assert "mer." not in kept and "Och" not in kept
    assert " ".join(kept) == "Utan jag kommer också behöva göra mycket mindre"


def test_full_sequence_excludes_the_stumble_with_silence_removal_off():
    kept = _words_in(
        _run_pipeline_sequence(STUMBLE_WORDS, STUMBLE_BEATS, max_gap=0), STUMBLE_WORDS
    )
    assert "mer." not in kept and "Och" not in kept


def test_tighten_preserves_unpadded_core_bounds():
    """Losing these across tighten defeats the exclusion guard on the next merge."""
    segs = merge_adjacent(build_cutlist(STUMBLE_WORDS, STUMBLE_BEATS).segments, STUMBLE_WORDS)
    after = tighten(segs, STUMBLE_WORDS, max_gap=0.30)
    for segment in after:
        assert segment.core_start >= segment.start
        assert segment.core_end <= segment.end
        assert (segment.core_start, segment.core_end) != (segment.start, segment.end), \
            "cores must be real speech bounds, not the padded span"


# --- padding must never reach into a neighbouring word ----------------------

def test_padding_is_clamped_to_the_previous_word():
    words = [Word(" ett", 1.00, 1.40), Word(" två", 1.45, 1.90)]
    seg = build_cutlist(words, [("A", "två")], pad_start=0.5, pad_end=0.1).segments[0]
    assert seg.start >= 1.40, "must not reach back into 'ett'"


def test_padding_is_clamped_to_the_next_word():
    words = [Word(" ett", 1.00, 1.40), Word(" två", 1.45, 1.90)]
    seg = build_cutlist(words, [("A", "ett")], pad_start=0.1, pad_end=0.5).segments[0]
    assert seg.end <= 1.45, "must not reach forward into 'två'"


def test_padding_still_applies_where_there_is_room():
    words = [Word(" ensam", 5.00, 5.40)]
    seg = build_cutlist(words, [("A", "ensam")], pad_start=0.08, pad_end=0.12).segments[0]
    assert seg.start == pytest.approx(4.92, abs=0.001)
    assert seg.end == pytest.approx(5.52, abs=0.001)


# --- retakes: the good take is the last one ---------------------------------

RETAKE = (
    "Jag håller på att sätta varenda "                       # false start
    "Jag håller på att bygga ett system som kommer lägg "     # false start
    "Jag håller på att bygga ett system som kommer sätta varenda "
    "short form content editor i konkurs"                     # the good take
)


def test_exact_match_prefers_the_last_take():
    """Raw footage is mostly retakes; the first match is the blooper."""
    words, cursor = [], 0.0
    for token in RETAKE.split():
        words.append(Word(f" {token}", round(cursor, 3), round(cursor + 0.3, 3)))
        cursor += 0.4

    span = find_span(words, "Jag håller på att bygga ett system som kommer")
    assert span is not None
    first, _, score = span
    assert score == 1.0
    # There are two exact runs; the later one must win.
    assert first > 5, f"selected the early false start at index {first}"


def test_single_occurrence_is_unaffected():
    words = [Word(f" {t}", i * 0.4, i * 0.4 + 0.3)
             for i, t in enumerate("bara en gång i hela transkriptet".split())]
    span = find_span(words, "bara en gång")
    assert span is not None and span[0] == 0


def test_full_hook_line_selects_the_complete_take():
    words, cursor = [], 0.0
    for token in RETAKE.split():
        words.append(Word(f" {token}", round(cursor, 3), round(cursor + 0.3, 3)))
        cursor += 0.4
    span = find_span(
        words,
        "Jag håller på att bygga ett system som kommer sätta varenda "
        "short form content editor i konkurs",
    )
    assert span is not None
    first, last, score = span
    assert score == 1.0
    matched = " ".join(w.word.strip() for w in words[first:last + 1])
    assert matched.startswith("Jag håller")
    assert matched.endswith("konkurs")
    assert "lägg" not in matched, "the false start must not be inside the span"


# --- hallucinated hotwords and swallowed audio ------------------------------
#
# Both from the real videoautomationsystem.mp4 transcript.

def test_hallucinated_hotwords_are_dropped():
    """Vocabulary terms emitted as transcript text, at probability 0.00."""
    words = [
        Word(" konkurs.", 13.28, 13.92, 1.00),
        Word(" TypeScript", 25.58, 26.98, 0.00),
        Word(" React", 26.98, 27.00, 0.00),
        Word(" Cyan", 27.02, 30.10, 0.00),
        Word(" Void", 30.10, 37.98, 0.03),
        Word(" Systemet", 44.10, 44.46, 0.50),
    ]
    kept, dropped = drop_hallucinations(words)
    assert [w.word.strip() for w in dropped] == ["TypeScript", "React", "Cyan", "Void"]
    assert [w.word.strip() for w in kept] == ["konkurs.", "Systemet"]


def test_genuine_low_confidence_words_survive():
    """The weakest real word in the reference scores 0.37; the floor is 0.05."""
    words = [Word(" är", 44.46, 44.54, 0.37), Word(" short", 3.34, 11.34, 0.47)]
    kept, dropped = drop_hallucinations(words)
    assert dropped == [] and len(kept) == 2


def test_swallowed_audio_becomes_a_visible_gap():
    """'short' spans 8s with the discarded takes inside it."""
    words = [
        Word(" varenda", 2.64, 3.34, 0.98),
        Word(" short", 3.34, 11.34, 0.47),
        Word(" form", 11.34, 11.78, 0.82),
    ]
    adjusted, clamped = clamp_slack(words)
    assert [w.word.strip() for w in clamped] == ["short"]
    short = adjusted[1]
    assert short.end == 11.34, "the end is anchored by the next word and must not move"
    assert short.start > 10.0, "the start moves forward to a plausible length"
    assert short.start - adjusted[0].end > 6.0, "the swallowed time is now a gap"


def test_normal_words_are_not_clamped():
    words = [
        Word(" Jag", 0.00, 0.74, 0.95),
        Word(" fullbordad", 47.76, 48.82, 0.91),
        Word(" varenda", 2.64, 3.34, 0.98),
    ]
    _, clamped = clamp_slack(words)
    assert clamped == []


def test_clamping_never_crosses_the_previous_word():
    words = [Word(" a", 5.00, 5.90, 1.0), Word(" bcdefgh", 5.90, 12.00, 1.0)]
    adjusted, _ = clamp_slack(words)
    assert adjusted[1].start >= 5.90


def test_hook_region_collapses_to_a_realistic_length():
    """End to end on the real hook: 13.8s of span, ~7s of actual speech."""
    raw = [(" Jag",0.00,0.74,.95),(" håller",0.74,0.98,1.),(" på",0.98,1.12,1.),
           (" att",1.12,1.16,.77),(" bygga",1.16,1.28,1.),(" ett",1.28,1.42,.99),
           (" system",1.42,1.72,1.),(" som",1.72,2.02,.98),(" kommer",2.02,2.24,1.),
           (" sätta",2.24,2.64,.86),(" varenda",2.64,3.34,.98),
           (" short",3.34,11.34,.47),(" form",11.34,11.78,.82),
           (" content",11.78,12.20,.99),(" editor",12.20,12.80,1.),
           (" i",12.80,13.28,1.),(" konkurs.",13.28,13.92,1.)]
    words = [Word(w, s, e, p) for w, s, e, p in raw]
    words, _ = clamp_slack(words)
    line = ("Jag håller på att bygga ett system som kommer sätta varenda "
            "short form content editor i konkurs")
    segs = merge_adjacent(
        tighten(merge_adjacent(build_cutlist(words, [("HOOK", line)]).segments, words),
                words, max_gap=0.30),
        words)
    total = sum(s.duration for s in segs)
    assert total < 8.5, f"hook should land near 7s, got {total:.1f}s"
    assert len(segs) == 2, "the false-start region should split the line"


# --- what identifies a hallucination is the run, not the score ---------------

def _w(token, probability):
    return Word(f" {token}", 0.0, 1.0, probability)


def test_a_run_of_zero_confidence_words_is_dropped():
    """Hotword biasing emits prompt terms over audio the model cannot read,
    several words at a time."""
    words = [_w("och", 0.9), _w("TypeScript", 0.0), _w("React", 0.0),
             _w("GitHub", 0.0), _w("sen", 0.8)]
    kept, dropped = drop_hallucinations(words)
    assert [w.word.strip() for w in dropped] == ["TypeScript", "React", "GitHub"]
    assert [w.word.strip() for w in kept] == ["och", "sen"]


def test_scattered_low_confidence_words_are_real_speech():
    """On a fast, quiet delivery genuine function words score below the floor
    one at a time. Dropping those deleted "Det", "för", "se" and "att" from a
    recording, and the beat that contained them then matched at 0.84 against a
    line missing its first four words."""
    words = [_w("Det", 0.02), _w("är", 0.9), _w("för", 0.03),
             _w("att", 0.9), _w("se", 0.01), _w("till", 0.9)]
    kept, dropped = drop_hallucinations(words)
    assert dropped == []
    assert len(kept) == 6


def test_a_pair_is_enough_to_count_as_a_run():
    words = [_w("och", 0.9), _w("Cyan", 0.0), _w("Void", 0.0), _w("sen", 0.9)]
    _, dropped = drop_hallucinations(words)
    assert len(dropped) == 2


def test_a_run_at_the_very_end_is_still_caught():
    words = [_w("och", 0.9), _w("Cyan", 0.0), _w("Void", 0.0)]
    kept, dropped = drop_hallucinations(words)
    assert len(dropped) == 2 and len(kept) == 1


def test_nothing_low_means_nothing_dropped():
    words = [_w("helt", 0.9), _w("normalt", 0.8)]
    assert drop_hallucinations(words)[1] == []


def test_a_hyphen_split_by_whisper_still_matches_the_line():
    """"prompt-dokument" tokenises to one word and "prompt dokument" to two.
    Whisper picks differently within one recording, so a line matched at 0.92
    against words that were exactly right."""
    words = [Word(f" {w}", i * 0.4, i * 0.4 + 0.3, 1.0)
             for i, w in enumerate("Och så bygger du upp ett prompt- dokument.".split())]
    found = find_span(words, "Och så bygger du upp ett prompt-dokument.")
    assert found is not None
    assert found[2] == 1.0, "an exact hit under another spelling is still exact"


def test_the_last_take_still_wins_across_spellings():
    words = [Word(f" {w}", i * 0.4, i * 0.4 + 0.3, 1.0)
             for i, w in enumerate("ett prompt-dokument och ett prompt-dokument".split())]
    start, _, score = find_span(words, "ett prompt-dokument")
    assert score == 1.0
    assert start == 3, "the retake, not the first attempt"
