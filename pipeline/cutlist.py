#!/usr/bin/env python3
"""Map chosen script lines back onto word timestamps to produce a cut list.

The edit prompt requires exact words from the transcript, so matching is mostly
exact -- but Whisper punctuation, casing and the odd dropped filler mean a
strict string match is too brittle. Matching therefore runs on normalised
tokens, with a similarity floor, and reports its confidence so a poor match can
be caught at the review checkpoint rather than silently producing a bad cut.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Below this token-sequence similarity a line is treated as not found.
MATCH_FLOOR = 0.72


@dataclass
class Word:
    word: str
    start: float
    end: float
    probability: float = 1.0

    @property
    def token(self) -> str:
        return normalise(self.word)


@dataclass
class Segment:
    """One continuous span of the source to keep.

    `start`/`end` include padding, which is what gets cut. `core_start`/
    `core_end` are the unpadded bounds of the matched speech, and exist because
    padding can swallow a short word that lies between two segments: testing a
    padded gap can report it as empty when it is not.
    """

    beat: str
    text: str
    start: float
    end: float
    score: float
    matched_text: str = ""
    core_start: float | None = None
    core_end: float | None = None

    def __post_init__(self) -> None:
        if self.core_start is None:
            self.core_start = self.start
        if self.core_end is None:
            self.core_end = self.end

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


@dataclass
class CutList:
    segments: list[Segment] = field(default_factory=list)
    misses: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return round(sum(segment.duration for segment in self.segments), 3)


def normalise(text: str) -> str:
    """Casefold, strip accents' case sensitivity and drop punctuation.

    Swedish characters are preserved -- only punctuation and case are removed,
    since "formulär" and "formular" are different words.
    """
    lowered = unicodedata.normalize("NFC", text).casefold().strip()
    return re.sub(r"[^\w\s]", "", lowered, flags=re.UNICODE).strip()


def tokenise(text: str) -> list[str]:
    return [token for token in (normalise(part) for part in text.split()) if token]


def plausible_duration(word: str) -> float:
    """Roughly how long a word of this length takes to say, in seconds.

    Floored, because short words carry disproportionate time: a drawn-out "i"
    can easily run half a second without anything being wrong.
    """
    return max(0.35, 0.15 + len(normalise(word)) * 0.09)


def drop_hallucinations(
    words: list[Word], floor: float = 0.05, min_run: int = 2
) -> tuple[list[Word], list[Word]]:
    """Remove runs of words the model had essentially no confidence in.

    Hotword biasing can backfire: the terms fed in as a prompt get emitted as
    transcript text over audio the model cannot read. What identifies them is
    not the low score alone but that they arrive CONSECUTIVELY -- the model
    reads nothing for a stretch and fills it from the prompt, several words at
    a time.

    A run length is required because confidence alone is not enough. On a fast,
    quiet delivery genuine function words score below the floor too, scattered
    one at a time; dropping those silently deletes real speech and breaks the
    line that contained them. That is not hypothetical -- "Det", "för", "se"
    and "att" were dropped from one recording, and the beat they belonged to
    then matched at 0.84 against a line missing its first four words.
    """
    dropped: list[Word] = []
    index = 0
    while index < len(words):
        if words[index].probability > floor:
            index += 1
            continue
        run = index
        while run < len(words) and words[run].probability <= floor:
            run += 1
        if run - index >= min_run:
            dropped.extend(words[index:run])
        index = run

    unwanted = {id(word) for word in dropped}
    return [w for w in words if id(w) not in unwanted], dropped


def clamp_slack(
    words: list[Word],
    factor: float = 2.5,
    allow: float = 1.5,
    min_excess: float = 0.6,
) -> tuple[list[Word], list[Word]]:
    """Trim impossible word durations, exposing swallowed audio as a gap.

    Where speech exists that Whisper does not transcribe -- a false start it
    smooths away -- the neighbouring word absorbs the time instead of leaving a
    gap. In the reference recording the word "short" spans eight seconds,
    thirteen times a plausible length, with the discarded takes inside it.

    Nothing downstream can see that: silence removal looks for gaps between
    words, and there is no gap. Trimming the word back to a plausible length
    while keeping its end -- which the following word anchors -- turns the
    swallowed time into an ordinary gap, which silence removal then cuts like
    any other dead air.
    """
    adjusted: list[Word] = []
    clamped: list[Word] = []
    for index, word in enumerate(words):
        duration = word.end - word.start
        plausible = plausible_duration(word.word)
        # Both tests must fail before trimming: a large ratio on a short word
        # is a rounding artifact, and a large absolute excess on a long word
        # can be ordinary emphasis.
        if duration > plausible * factor and duration - plausible > min_excess:
            floor_time = words[index - 1].end if index > 0 else 0.0
            new_start = max(floor_time, word.end - plausible * allow)
            if new_start > word.start:
                clamped.append(word)
                adjusted.append(
                    Word(word.word, round(new_start, 3), word.end, word.probability)
                )
                continue
        adjusted.append(word)
    return adjusted, clamped


def spelling_variants(phrase: str) -> list[str]:
    """The same phrase written the other plausible ways.

    A hyphen survives into the transcript or does not, depending on the take:
    "prompt-dokument" tokenises to one word, "prompt dokument" to two, and
    neither finds the other. Whisper picks differently within a single
    recording, so a line can match at 0.92 against words that are exactly
    right.
    """
    candidates = [phrase, phrase.replace("-", " "), phrase.replace("-", "")]
    if len(phrase.split()) <= 2:
        # The reverse case, bounded: gluing every word of a long phrase
        # together would match nothing and cost a pass over the transcript.
        candidates.append(phrase.replace(" ", ""))
    seen, out = set(), []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def find_span(words: list[Word], phrase: str) -> tuple[int, int, float] | None:
    """Locate `phrase` in `words`; returns (start index, end index, score).

    Tries an exact normalised-subsequence match first, which is the common case
    and is exact by construction. Falls back to the best-scoring window of
    comparable length, so a line that lost a filler word still lands.
    """
    haystack = [word.token for word in words]
    if not words:
        return None

    # An exact hit under any spelling beats an approximate one under the
    # first, so every variant is tried before falling back.
    for candidate in spelling_variants(phrase):
        needle = tokenise(candidate)
        if not needle:
            continue
        matches = [
            start
            for start in range(len(haystack) - len(needle) + 1)
            if haystack[start : start + len(needle)] == needle
        ]
        if matches:
            start = matches[-1]
            return start, start + len(needle) - 1, 1.0

    needle = tokenise(phrase)
    if not needle:
        return None

    # Taking the LAST match, not the first, is handled above.
    #
    # Raw talking-head footage is mostly retakes: the speaker fluffs a line,
    # stops, and says it again. The good take is therefore almost always the
    # final one, and preferring the first systematically selects the blooper.

    # Best approximate window. Widen slightly so an extra spoken word can be
    # absorbed rather than truncating the line.
    best: tuple[int, int, float] | None = None
    for width in {len(needle), len(needle) + 1, len(needle) + 2, max(1, len(needle) - 1)}:
        for start in range(len(haystack) - width + 1):
            window = haystack[start : start + width]
            score = SequenceMatcher(None, needle, window).ratio()
            # >= so that among equally good windows the latest wins, for the
            # same retake reason as the exact pass above.
            if best is None or score >= best[2]:
                best = (start, start + width - 1, score)

    if best and best[2] >= MATCH_FLOOR:
        return best
    return None


def build_cutlist(
    words: list[Word],
    beats: list[tuple[str, str]],
    pad_start: float = 0.10,
    pad_end: float = 0.22,
) -> CutList:
    """Turn (beat name, line) pairs into timed segments.

    A little padding either side stops a cut clipping the attack of the first
    word or the tail of the last; the end gets more because speech decays.
    Segments are returned in script order, not source order -- the edit may
    deliberately move the landing line to the end.
    """
    result = CutList()
    for beat, line in beats:
        span = find_span(words, line)
        if span is None:
            result.misses.append((beat, line))
            continue
        first, last, score = span

        # Cut in the middle of the silence between words, not at word.end plus
        # padding.
        #
        # Whisper's word-end timestamps systematically under-report: they mark
        # where the acoustic alignment ends, which clips the release of a final
        # consonant. Cutting there chops the word audibly -- "video" becomes
        # "vid", "själv" loses its tail. Padding past it fixes that but risks
        # catching the next word, and clamping to the next word's start brings
        # the clipping straight back when words run together.
        #
        # The midpoint of the gap is right on both counts: it always clears the
        # spoken word, and it never reaches the next one.
        # The midpoint is the ceiling on how far padding may reach, not the
        # target. Aiming at it directly drags in half of any long gap -- a six
        # second pause before a line put three seconds of silence at its head.
        if first > 0:
            midpoint = (words[first - 1].end + words[first].start) / 2
            start = max(midpoint, words[first].start - pad_start)
        else:
            start = words[first].start - pad_start

        if last + 1 < len(words):
            midpoint = (words[last].end + words[last + 1].start) / 2
            end = min(midpoint, words[last].end + pad_end)
        else:
            end = words[last].end + pad_end

        start = max(0.0, start)
        result.segments.append(
            Segment(
                beat=beat,
                text=line,
                start=round(start, 3),
                end=round(end, 3),
                score=round(score, 4),
                matched_text="".join(w.word for w in words[first : last + 1]).strip(),
                core_start=words[first].start,
                core_end=words[last].end,
            )
        )
    return result


def tighten(
    segments: list[Segment],
    words: list[Word],
    max_gap: float = 0.30,
    keep: float = 0.12,
    min_piece: float = 0.20,
) -> list[Segment]:
    """Remove dead air inside segments by splitting at long inter-word gaps.

    Driven by word timestamps rather than an audio threshold: the transcript
    already says exactly when speech starts and stops, whereas silencedetect
    trips on breaths and room tone and needs tuning per recording.

    A pause longer than `max_gap` is collapsed to `keep` rather than to
    nothing. Removing every pause makes delivery sound gabbled and strips the
    beats a listener needs; the aim is tightening, not compression.

    `min_piece` discards slivers too short to read as speech, which otherwise
    produce a stutter at the join.
    """
    tightened: list[Segment] = []

    for segment in segments:
        inside = [
            word for word in words
            if word.start >= segment.start - 0.001 and word.end <= segment.end + 0.001
        ]
        if len(inside) < 2:
            tightened.append(segment)
            continue

        # Split points: the index after which a gap is too long to keep.
        pieces: list[tuple[float, float]] = []
        piece_start = segment.start
        for previous, current in zip(inside, inside[1:]):
            gap = current.start - previous.end
            if gap > max_gap:
                pieces.append((piece_start, previous.end + keep / 2))
                piece_start = current.start - keep / 2
        pieces.append((piece_start, segment.end))

        kept = [(start, end) for start, end in pieces if end - start >= min_piece]
        if not kept:
            tightened.append(segment)
            continue

        for index, (start, end) in enumerate(kept):
            # Recompute the unpadded bounds per piece. Letting them default to
            # the padded span would undo the exclusion guard in merge_adjacent,
            # which is what the guard exists to prevent.
            inner = [w for w in inside if start <= (w.start + w.end) / 2 <= end]
            tightened.append(
                Segment(
                    beat=segment.beat if index == 0 else f"{segment.beat}.{index + 1}",
                    text=segment.text,
                    start=round(max(0.0, start), 3),
                    end=round(end, 3),
                    score=segment.score,
                    matched_text=segment.matched_text,
                    core_start=inner[0].start if inner else round(max(0.0, start), 3),
                    core_end=inner[-1].end if inner else round(end, 3),
                )
            )

    return tightened


def drop_fillers(
    words: list[Word],
    segments: list[Segment],
    fillers: set[str],
    pad: float = 0.04,
) -> list[Segment]:
    """Split segments so listed filler words fall outside them.

    Opt-in and explicit: an aggressive default would cut real words. "liksom"
    and "typ" are fillers in one sentence and load-bearing in the next, so the
    list is the operator's to curate.
    """
    if not fillers:
        return segments

    normalised = {normalise(filler) for filler in fillers}
    result: list[Segment] = []

    for segment in segments:
        inside = [
            word for word in words
            if word.start >= segment.start - 0.001 and word.end <= segment.end + 0.001
        ]
        hits = [word for word in inside if word.token in normalised]
        if not hits:
            result.append(segment)
            continue

        cursor = segment.start
        piece = 0
        for hit in hits:
            if hit.start - pad > cursor:
                piece += 1
                piece_end = round(hit.start - pad, 3)
                inner = [
                    w for w in inside if cursor <= (w.start + w.end) / 2 <= piece_end
                ]
                result.append(
                    Segment(
                        beat=segment.beat if piece == 1 else f"{segment.beat}.{piece}",
                        text=segment.text, start=round(cursor, 3),
                        end=piece_end, score=segment.score,
                        matched_text=segment.matched_text,
                        core_start=inner[0].start if inner else round(cursor, 3),
                        core_end=inner[-1].end if inner else piece_end,
                    )
                )
            cursor = hit.end + pad
        if segment.end - cursor > 0.05:
            piece += 1
            inner = [
                w for w in inside if cursor <= (w.start + w.end) / 2 <= segment.end
            ]
            result.append(
                Segment(
                    beat=segment.beat if piece == 1 else f"{segment.beat}.{piece}",
                    text=segment.text, start=round(cursor, 3), end=segment.end,
                    score=segment.score, matched_text=segment.matched_text,
                    core_start=inner[0].start if inner else round(cursor, 3),
                    core_end=inner[-1].end if inner else segment.end,
                )
            )

    return result


def read_words(path: Path) -> list[Word]:
    """The word list from a transcript file.

    Stated once. brief.py grew its own copy that assumed the file was a bare
    JSON array, which is not what the transcriber writes -- it writes an object
    with the run's settings and a "words" key -- so the director stage died on
    the first real transcript it was pointed at with a TypeError about string
    indices.

    utf-8-sig because a file that has been through PowerShell has a BOM.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return [
        Word(w["word"], float(w["start"]), float(w["end"]),
             float(w.get("probability", 1.0)))
        for w in data["words"]
    ]


def words_between(words: list[Word], start: float, end: float) -> list[Word]:
    """Words falling wholly inside the (start, end) gap, judged by midpoint."""
    return [word for word in words if start < (word.start + word.end) / 2 < end]


def merge_adjacent(
    segments: list[Segment],
    words: list[Word] | None = None,
    gap: float = 0.25,
    overlap: float = 0.4,
) -> list[Segment]:
    """Join segments that are truly contiguous in the source.

    Two beats pulled from consecutive sentences produce a pointless seam if cut
    apart and rejoined, so they merge. Negative gaps up to `overlap` merge too:
    padding makes back-to-back lines overlap slightly, and cutting both would
    duplicate that sliver of speech.

    A time threshold alone is not enough. If the script deliberately excludes
    words between two beats -- a stumble cut out mid-sentence -- those words can
    be short enough to fall under `gap`, and merging would silently put them
    back and reverse the edit. So when `words` is supplied, a gap containing any
    word is never merged: the author dropped that speech on purpose.
    """
    if not segments:
        return []
    merged = [segments[0]]
    for segment in segments[1:]:
        previous = merged[-1]
        distance = segment.start - previous.end
        # Tested between the unpadded speech bounds. Using the padded span can
        # narrow the window past a short word's midpoint and report an empty
        # gap, which silently merges across speech the script dropped.
        excluded = (
            words_between(words, previous.core_end or previous.end,
                          segment.core_start or segment.start)
            if words else []
        )
        if -overlap <= distance <= gap and segment.end > previous.end and not excluded:
            merged[-1] = Segment(
                beat=f"{previous.beat}+{segment.beat}",
                text=f"{previous.text} {segment.text}",
                start=previous.start,
                end=max(previous.end, segment.end),
                score=min(previous.score, segment.score),
                matched_text=f"{previous.matched_text} {segment.matched_text}",
                core_start=previous.core_start,
                core_end=segment.core_end,
            )
        else:
            merged.append(segment)
    return merged
