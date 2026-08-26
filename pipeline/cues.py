#!/usr/bin/env python3
"""Turn "when I say X" into a frame number.

An overlay cue names a phrase, never a time. That is the whole reason this
stage exists: a sheet written against one take survives a re-record, a re-cut
and a reorder, because the phrase is still the phrase. A sheet of timestamps
would have to be redone every time the edit moves by a frame -- which, on this
pipeline, it does.

Resolution runs against the CUT transcript, so the times are already in the
finished video's clock and no offset arithmetic is needed downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from difflib import SequenceMatcher

from cutlist import Word, find_span, tokenise

# How long an overlay stays after its phrase finishes, unless it says
# otherwise. Long enough to read, short enough not to outstay the sentence.
DEFAULT_HOLD = 0.5

# Below this, a cue matched something the operator probably did not mean.
WEAK_MATCH = 0.75

# Cue fields holding children that carry their own phrase. Stated once: it was
# listed in three places, and two new kinds were added to only one of them --
# so their children resolved to no timing at all and never appeared.
CHILD_KEYS = ("emoji", "series", "chips", "slots")


@dataclass
class Problem:
    """A cue that could not be placed, for the checkpoint to report."""

    cue: str
    kind: str
    reason: str


def variants(phrase: str) -> list[str]:
    """The same phrase written the other plausible ways.

    A hyphen survives into the transcript or does not, depending on the take:
    "b-roll" tokenises to one word, "b roll" to two, and neither finds the
    other. Whisper picks differently between the raw pass and the re-transcribe
    of the cut, so a cue that matched yesterday can miss today.
    """
    candidates = [phrase, phrase.replace("-", " "), phrase.replace("-", "")]
    # The reverse case -- a cue written "b roll" against a transcript that says
    # "b-roll". Only for a short phrase: gluing every word of a long one
    # together would match nothing and cost a pass over the transcript each
    # time.
    if len(phrase.split()) <= 2:
        candidates.append(phrase.replace(" ", ""))

    seen, out = set(), []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def nearest(words: list[Word], phrase: str, span: int = 6) -> str:
    """The closest thing actually said, for reporting a miss.

    "not found in the transcript" is true and useless. What the operator needs
    is what the transcript says instead, so the cue can be corrected in the one
    edit it takes.
    """
    needle = tokenise(phrase)
    haystack = [w.token for w in words]
    if not needle or not haystack:
        return ""
    width = max(1, min(len(needle), span))
    best, best_score = 0, -1.0
    for start in range(max(1, len(haystack) - width + 1)):
        score = SequenceMatcher(None, needle, haystack[start : start + width]).ratio()
        if score > best_score:
            best, best_score = start, score
    return " ".join(
        w.word.strip() for w in words[best : best + width]
    ).strip()


def phrase_frames(
    words: list[Word], phrase: str, fps: int
) -> tuple[int, int, float] | None:
    """(first frame, last frame, match score) for a spoken phrase."""
    found = None
    for candidate in variants(phrase):
        found = find_span(words, candidate)
        if found is not None:
            break
    if found is None:
        return None
    start, end, score = found
    return (
        int(round(words[start].start * fps)),
        int(round(words[end].end * fps)),
        score,
    )


def resolve(
    sheet: list[dict], words: list[Word], fps: int, duration_frames: int
) -> tuple[list[dict], list[Problem]]:
    """Fill in every frame number a cue sheet needs.

    Returns the resolved sheet and whatever could not be placed. A cue that
    fails is dropped rather than guessed at: an overlay in the wrong place is
    worse than no overlay, and the checkpoint says which ones went.
    """
    resolved: list[dict] = []
    problems: list[Problem] = []

    for entry in sheet:
        kind = entry.get("kind", "?")
        cue = dict(entry)

        # Sub-cues first: an emoji row and a two-line graph each carry several
        # phrases, and the parent's timing is derived from them.
        children_ok = True
        for key in CHILD_KEYS:
            if key not in cue:
                continue
            placed = []
            for child in cue[key]:
                span = phrase_frames(words, child["cue"], fps)
                if span is None:
                    problems.append(
                        Problem(child["cue"], kind,
                                f'not said -- closest is "{nearest(words, child["cue"])}"')
                    )
                    children_ok = False
                    continue
                if span[2] < WEAK_MATCH:
                    problems.append(
                        Problem(child["cue"], kind,
                                f"only matched at {span[2]:.2f}")
                    )
                placed.append({**child, "enter": span[0], "endFrame": span[1]})
            cue[key] = placed
        if not children_ok or (("emoji" in cue or "series" in cue) and not cue.get("emoji", cue.get("series"))):
            continue

        # The parent's own phrase, the first of its children, or the clip's
        # own first frame. `from: "start"` is the mirror of `until: "end"`,
        # and it exists because an effect meant to fire the instant the video
        # begins cannot be anchored to a phrase: the first word is said a
        # moment in, and cueing on it puts the effect a moment late. It is
        # also the only anchor that does not depend on what the transcript
        # says, which for the first frame of every video is worth having.
        if cue.get("from") == "start":
            cue["enter"] = 0
            cue["score"] = 1.0
            # Nothing has been placed yet, so there is no later frame to hold
            # past. A push anchored here names its own `until`.
            last = 0
        elif cue.get("cue"):
            span = phrase_frames(words, cue["cue"], fps)
            if span is None:
                problems.append(
                    Problem(cue["cue"], kind,
                            f'not said -- closest is "{nearest(words, cue["cue"])}"')
                )
                continue
            if span[2] < WEAK_MATCH:
                problems.append(
                    Problem(cue["cue"], kind, f"only matched at {span[2]:.2f}")
                )
            cue["enter"], last = span[0], span[1]
            cue["score"] = round(span[2], 3)
        else:
            children = next(
                (cue[key] for key in CHILD_KEYS if cue.get(key)), []
            )
            cue["enter"] = min(c["enter"] for c in children)
            last = max(c["endFrame"] for c in children)
            cue["score"] = 1.0

        # A row of emoji holds until the LAST one has landed and been read.
        # Dropping each as the next appeared would show the list one item at a
        # time and never show the list.
        for key in CHILD_KEYS:
            for child in cue.get(key, []):
                last = max(last, child["endFrame"])

        # The chat's two later beats hang on their own phrases.
        # A phrase resolved to a frame the component needs, other than its
        # entry and exit. `finishBy` is the one a generated clip wants: pace
        # the output to end HERE, then hold until `until`. Those are two
        # different moments -- the terminal cued on "RAW-file" should finish
        # its output as that sentence does and stay up over the next one.
        for beat, field in (("typesCue", "types"), ("repliesCue", "replies"),
                            ("finishBy", "finishes")):
            if not cue.get(beat):
                continue
            span = phrase_frames(words, cue[beat], fps)
            if span is None:
                problems.append(
                    Problem(cue[beat], kind,
                            f'not said -- closest is "{nearest(words, cue[beat])}"')
                )
                continue
            cue[field] = span[0]
            last = max(last, span[1])

        cue["leave"] = leave_frame(cue, words, fps, last, duration_frames, problems)
        resolved.append(strip_authoring_keys(cue))

    return resolved, problems


def leave_frame(
    cue: dict,
    words: list[Word],
    fps: int,
    last: int,
    duration_frames: int,
    problems: list[Problem],
) -> int | None:
    """When the overlay goes.

    `until: "end"` keeps it up for the rest of the video -- which is what the
    two crossing lines want, since the comparison only exists while both are
    on screen. `until: "<phrase>"` hands the frame over to something else.
    Otherwise it holds for a moment after its own phrase finishes.
    """
    until = cue.get("until")
    if until == "end":
        return None
    if until:
        span = phrase_frames(words, until, fps)
        if span is None:
            problems.append(
                Problem(until, cue.get("kind", "?"), "until-phrase not found")
            )
        else:
            return span[0]
    hold = float(cue.get("hold", DEFAULT_HOLD))
    return min(last + int(round(hold * fps)), duration_frames)


AUTHORING_KEYS = ("hold", "until", "from", "typesCue", "repliesCue",
                  "finishBy", "endFrame")


def strip_authoring_keys(cue: dict) -> dict:
    """Drop what only the resolver needed, so the props carry frames alone."""
    out = {k: v for k, v in cue.items() if k not in AUTHORING_KEYS}
    for key in CHILD_KEYS:
        if key in out:
            out[key] = [
                {k: v for k, v in child.items() if k not in AUTHORING_KEYS}
                for child in out[key]
            ]
    return out


def load_sheet(path: Path) -> list[dict]:
    from jsonfile import read as read_json

    return read_json(path, "overlay sheet")
