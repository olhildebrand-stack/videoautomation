#!/usr/bin/env python3
"""Group words into sentences and identify which are bloopers.

The sentence is the right atomic unit for editing raw talking-head footage.
Matching arbitrary phrase strings against a word list -- the earlier approach --
is fragile precisely where this material is hardest: a phrase can span a
discarded take and a good one, and nothing in the string says so.

At sentence level the two failure modes are simple and checkable:

  truncated   the speaker stopped mid-thought, so the sentence has no terminal
              punctuation, or Whisper wrote an ellipsis
  superseded  a later sentence says nearly the same thing, i.e. the line was
              retaken

Both are properties of the sentence itself, not of a match against a script.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from cutlist import Word, normalise

# Similarity above which two sentences count as takes of the same line.
SUPERSEDE_RATIO = 0.62
# A prefix shorter than this is too generic to call a retake.
MIN_PREFIX_WORDS = 3
# Likewise for similarity: two short phrases can be identical without either
# being a retake of the other. "Och sen." twice, minutes apart, is just speech.
MIN_SIMILARITY_WORDS = 4

TERMINAL = re.compile(r"[.!?]['\")\]]?\s*$")
ELLIPSIS = re.compile(r"(\.\.\.|…)['\")\]]?\s*$")


@dataclass
class Sentence:
    index: int
    words: list[Word]
    truncated: bool = False
    superseded_by: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(w.word for w in self.words).strip()

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    @property
    def is_blooper(self) -> bool:
        return self.truncated or self.superseded_by is not None

    @property
    def verdict(self) -> str:
        if self.truncated:
            return "truncated"
        if self.superseded_by is not None:
            return f"superseded by #{self.superseded_by}"
        return "keep"


def split_sentences(words: list[Word]) -> list[Sentence]:
    """Group words into sentences on terminal punctuation.

    A trailing group with no terminal punctuation still becomes a sentence --
    it is then almost certainly a truncated one, which is exactly what the
    caller needs to see.
    """
    sentences: list[Sentence] = []
    current: list[Word] = []

    for word in words:
        current.append(word)
        if TERMINAL.search(word.word) or ELLIPSIS.search(word.word):
            sentences.append(Sentence(index=len(sentences), words=current))
            current = []

    if current:
        sentences.append(Sentence(index=len(sentences), words=current))

    return sentences


def tokens_of(sentence: Sentence) -> list[str]:
    return [t for t in (normalise(w.word) for w in sentence.words) if t]


def classify(
    sentences: list[Sentence],
    ratio: float = SUPERSEDE_RATIO,
) -> list[Sentence]:
    """Mark truncated and superseded sentences in place."""
    for sentence in sentences:
        raw = sentence.text
        if ELLIPSIS.search(raw) or not TERMINAL.search(raw):
            sentence.truncated = True
            sentence.notes.append("no terminal punctuation" if not ELLIPSIS.search(raw)
                                  else "ends in an ellipsis")

    for i, earlier in enumerate(sentences):
        if earlier.truncated:
            continue
        a = tokens_of(earlier)
        if not a:
            continue
        for later in sentences[i + 1:]:
            if later.truncated:
                continue
            b = tokens_of(later)
            if not b:
                continue
            similarity = SequenceMatcher(None, a, b).ratio()
            long_enough = min(len(a), len(b)) >= MIN_SIMILARITY_WORDS
            is_prefix = len(a) >= MIN_PREFIX_WORDS and b[: len(a)] == a
            if (similarity >= ratio and long_enough) or is_prefix:
                # The later take wins: the speaker restarted for a reason.
                earlier.superseded_by = later.index
                earlier.notes.append(
                    "restated later" if is_prefix else f"similarity {similarity:.2f}"
                )
                break

    return sentences


def keepers(sentences: list[Sentence]) -> list[Sentence]:
    return [s for s in sentences if not s.is_blooper]


def analyse(words: list[Word]) -> list[Sentence]:
    return classify(split_sentences(words))


# --- turning sentences into cuts --------------------------------------------

# Room left after a sentence ends before the cut. Cutting on the last syllable
# clips the delivery and reads as clipped speech, so a sentence is allowed to
# land before the picture changes.
#
# Settled by ear: 0.5 dragged, 0.2 was still loose, 0.15 is where it sits.
DEFAULT_TAIL = 0.15

# The final cut of the video gets more. Everywhere else a tail is a beat
# between sentences; at the very end it is the only thing between the last
# consonant and black, and Whisper's word-end timestamps under-report, so a
# tail measured from them is shorter than it looks. 0.3 measured generously.
DEFAULT_END_TAIL = 0.3
# Room before a sentence, so the first consonant is not clipped. Tightened to
# 0.05 by ear. This is the riskier of the two: Whisper's word-START timestamps
# run late as often as its word-ends run short, and what the head buys is the
# attack of the first consonant. If a cut ever opens on a clipped plosive, this
# is the number to raise -- not the tail.
DEFAULT_HEAD = 0.05


def sentence_range(
    sentence: Sentence,
    words: list[Word],
    head: float = DEFAULT_HEAD,
    tail: float = DEFAULT_TAIL,
) -> tuple[float, float]:
    """Cut points for a sentence, bounded by the neighbouring speech.

    The tail is a maximum, not a promise: where the next sentence follows
    immediately there is no room for it, and taking it anyway would pull the
    next speaker's first word into the cut.
    """
    first_index = words.index(sentence.words[0])
    last_index = words.index(sentence.words[-1])

    previous_end = words[first_index - 1].end if first_index > 0 else 0.0
    next_start = (
        words[last_index + 1].start if last_index + 1 < len(words) else None
    )

    start = max(previous_end, sentence.start - head, 0.0)
    end = sentence.end + tail
    if next_start is not None:
        end = min(end, next_start)
    return round(start, 3), round(end, 3)


def retime_range(
    words: list[Word],
    start: float,
    end: float,
    head: float = DEFAULT_HEAD,
    tail: float = DEFAULT_TAIL,
) -> tuple[float, float]:
    """Re-derive a stated range from the speech it actually contains.

    An explicit range in an edit script is a number someone wrote down, and it
    carries whatever head and tail were current when they wrote it. Changing
    those defaults does not reach a range already committed to a file -- which
    is correct, since a stated range is the operator's call and not a
    suggestion, but it means a retune leaves old cuts untouched.

    This finds the words the range covers and re-measures around them, with the
    same neighbour clamps `sentence_range` uses. What it discards is any
    adjustment made by ear beyond the tails; what it buys is a cut consistent
    with the current settings. Opt in per rebuild, never automatic.
    """
    covered = [w for w in words if w.end > start and w.start < end]
    if not covered:
        return round(start, 3), round(end, 3)

    first_index = words.index(covered[0])
    last_index = words.index(covered[-1])
    previous_end = words[first_index - 1].end if first_index > 0 else 0.0
    next_start = (
        words[last_index + 1].start if last_index + 1 < len(words) else None
    )

    new_start = max(previous_end, covered[0].start - head, 0.0)
    new_end = covered[-1].end + tail
    if next_start is not None:
        new_end = min(new_end, next_start)
    return round(new_start, 3), round(new_end, 3)


def sentence_ranges(
    sentence: Sentence,
    words: list[Word],
    head: float = DEFAULT_HEAD,
    tail: float = DEFAULT_TAIL,
    max_gap: float = 0.30,
    min_piece: float = 0.25,
    is_final: bool = False,
) -> list[tuple[float, float]]:
    """Cut ranges for a sentence, split at silence inside it.

    A sentence is a unit of meaning, not of continuous sound. Clamping exposes
    discarded takes as gaps inside the sentence that contains them -- the hook
    is one sentence spanning fourteen seconds, six of which are false starts.
    Splitting on those gaps is what turns it back into the six seconds actually
    spoken.

    Only the last piece gets the full tail. An internal break is mid-sentence,
    where a half-second of air would be a hole rather than a landing.
    """
    first_index = words.index(sentence.words[0])
    last_index = words.index(sentence.words[-1])

    breaks: list[list[Word]] = [[]]
    for offset, word in enumerate(sentence.words):
        if offset > 0:
            previous = sentence.words[offset - 1]
            if word.start - previous.end > max_gap:
                breaks.append([])
        breaks[-1].append(word)

    pieces: list[tuple[float, float]] = []
    for position, group in enumerate(breaks):
        if not group:
            continue
        is_first = position == 0
        is_last = position == len(breaks) - 1

        if is_first:
            floor_time = words[first_index - 1].end if first_index > 0 else 0.0
            start = max(floor_time, group[0].start - head, 0.0)
        else:
            # Mid-sentence resumption: a light lead-in, not the sentence head.
            start = max(0.0, group[0].start - min(head, 0.08))

        if is_last:
            ceiling = (
                words[last_index + 1].start if last_index + 1 < len(words) else None
            )
            end = group[-1].end + (DEFAULT_END_TAIL if is_final else tail)
            if ceiling is not None:
                end = min(end, ceiling)
        else:
            end = group[-1].end + 0.08

        if end - start >= min_piece:
            pieces.append((round(start, 3), round(end, 3)))

    return pieces or [sentence_range(sentence, words, head, tail)]
