#!/usr/bin/env python3
"""Everything a director needs to decide the shape of one video.

The pipeline was deterministic everywhere except the one place that matters:
somebody still had to read the transcript and decide what the video *is* --
which takes are keepers, what order the argument runs in, what deserves an
overlay. That job was being done by hand, per video, in a chat window, and
nothing about it accumulated.

This assembles the question. `decision.py` states the answer's shape and checks
it; `director.py` asks Claude and writes the files. Splitting the three means
the expensive, non-deterministic part is a single call in the middle of two
testable halves.

The unit is the **sentence**, referred to by number. A director who names
sentence 14 cannot mis-time it, cannot pick words that span a discarded take,
and cannot quote the transcript slightly wrong -- three failure modes that all
came from asking for exact words back.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cutlist import (  # noqa: E402
    Word, clamp_slack, read_words, words_between,
)
from sentences import Sentence, analyse, sentence_ranges  # noqa: E402
from takes import detect_silences, speech_runs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BROLL = ROOT / "broll"

# Measured across the ten reference reels in howtocutvideo/videoreferences:
# 23, 31, 31, 40, 50, 52, 61, 63, 65, 70 seconds, median 51.
#
# This said 25-60 before it was measured, which would have called four of the
# ten reels too long -- including the two closest in subject to what we make.
# Not a rule the validator enforces; a band the director has to argue past.
TARGET_SECONDS = (23.0, 70.0)
TYPICAL_SECONDS = 51.0


def flag(sentence: Sentence) -> str:
    """What the machine already believes about this sentence.

    Stated so the director can disagree with it. `sentences.py` catches
    truncated and superseded takes by rule, and it is right most of the time
    and confidently wrong at the edges -- a complete sentence that happens to
    restate a later one is flagged, and a fluent, terminated, unique sentence
    that is nonetheless a worse take is not.
    """
    marks = []
    if sentence.truncated:
        marks.append("TRUNCATED")
    if sentence.superseded_by is not None:
        marks.append(f"SUPERSEDED by {sentence.superseded_by}")
    if not marks:
        return "keeper"
    return " + ".join(marks) + (f" ({'; '.join(sentence.notes)})"
                                if sentence.notes else "")


@dataclass
class Take:
    """One continuous run of speech: the atom the cutter actually produces.

    The sentence is the wrong unit to decide with, and vas3 proved it. Whisper
    wrote the hook as a single fourteen-second sentence, six seconds of which
    were false starts with silence between them. A director who kept "that
    sentence" kept the false starts too, because keeping a sentence keeps every
    piece the cutter later splits it into.

    So the thing given a number is the piece. A take is what a person would
    call an attempt, and choosing between attempts is the actual job.
    """

    index: int
    sentence: int
    start: float
    end: float
    text: str
    words: list[Word]
    part: tuple[int, int]        # this piece, of how many in its sentence
    swallowed: bool = False      # untranscribed speech sits inside this range

    @property
    def duration(self) -> float:
        return self.end - self.start


def takes(words: list[Word], sentences: list[Sentence]) -> list[Take]:
    """Every sentence, split where the speaker actually stopped."""
    found: list[Take] = []
    for sentence in sentences:
        pieces = sentence_ranges(sentence, words)
        for number, (start, end) in enumerate(pieces, 1):
            covered = words_between(words, start, end)
            found.append(Take(
                index=len(found),
                sentence=sentence.index,
                start=start,
                end=end,
                text="".join(w.word for w in covered).strip(),
                words=covered,
                part=(number, len(pieces)),
            ))
    return found


def take_list(words: list[Word]) -> list[Take]:
    """Every take in a recording, as the cutter will produce them.

    Clamped, split, and flagged, in that order and in one place. build() used
    to clamp and director.py did not, so the table a director read had more
    takes in it than the validator would accept -- and every number past the
    validator's end came back as "take 27 does not exist" three times in a row
    while the row was sitting in the brief.
    """
    clamped_words, clamped = clamp_slack(words)
    found = takes(clamped_words, analyse(clamped_words))
    for take in found:
        take.swallowed = any(
            take.start <= word.end <= take.end for word in clamped)
    return found


def unseen(words: list[Word], found: list[Take]) -> list[Word]:
    """Words that fell into no take, so the table never shows them.

    `sentence_ranges` drops a piece shorter than a quarter second, which is
    right for cutting -- a 0.2s fragment is a click, not a take -- and wrong
    for a brief. The words went with it, so the director could not decide about
    them, could not quote them in a cue, and could not tell they existed. The
    operator noticed the brief was short before anything else did.
    """
    covered = set()
    for take in found:
        for word in take.words:
            covered.add(id(word))
    return [word for word in words if id(word) not in covered]


def orphan_note(orphans: list[Word]) -> str:
    if not orphans:
        return ""
    listed = " ".join(
        f"`{word.word.strip()}` ({word.start:.1f}s)" for word in orphans)
    return (
        "### Said, but in no take\n\n"
        f"{len(orphans)} word(s) fell into a run of speech too short to cut "
        "from -- under a quarter second -- so they are in no row above and "
        "cannot be kept or quoted in a cue. They are listed because a sentence "
        "that reads as unfinished in the table may simply have continued "
        f"here:\n\n{listed}"
    )


# Where the transcript is unreliable, the audio is not. These match the
# cutter's own threshold rather than takes.py's deafer default, so the runs
# reported here are the runs the cutter would find.
RUN_NOISE_DB = -45.0
RUN_MIN_SILENCE = 0.35
RUN_MIN = 0.4
# How far either side of a smeared stretch to look, so a run that starts
# before the first bad take is still seen whole.
RUN_MARGIN = 6.0


def smeared_windows(found: list[Take],
                    ends: float | None = None) -> list[tuple[float, float]]:
    """The stretches where the transcript cannot be trusted, merged.

    Clamped to the recording: with no silence after the last word, a window
    reaching past the end reports a run that carries on into nothing.
    """
    limit = ends if ends is not None else float("inf")
    windows: list[tuple[float, float]] = []
    for take in found:
        if not take.swallowed:
            continue
        span = (max(0.0, take.start - RUN_MARGIN),
                min(limit, take.end + RUN_MARGIN))
        if windows and span[0] <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], span[1]))
        else:
            windows.append(span)
    return windows


def measured_runs(source: Path, found: list[Take],
                  ends: float | None = None) -> str:
    """What the audio says was said, where the transcript smeared it.

    aieditoradvancing's problem sentence runs 49.5-57.5 in the audio, one
    continuous eight seconds. The transcript wrote down only its last five and
    put the start three seconds late, so the take table showed a fragment and
    the director built a beat out of a stub plus that fragment. Finding the
    real boundaries meant knowing to run takes.py by hand.

    The audio does not care what Whisper wrote, so where a take is flagged, the
    runs go in the brief beside it.
    """
    windows = smeared_windows(found, ends)
    if not windows or not source.is_file():
        return ""

    lines = []
    for start, end in windows:
        start = max(0.0, start)
        try:
            silences = detect_silences(
                source, start, end, RUN_NOISE_DB, RUN_MIN_SILENCE)
        except Exception:                                   # pragma: no cover
            return ""
        for run in speech_runs(start, end, silences, RUN_MIN):
            lines.append(
                f"| {run.start:.2f} | {run.end:.2f} | {run.duration:.1f} |")
    if not lines:
        return ""

    return (
        "### What the audio says, where the transcript smeared it\n\n"
        "Continuous runs of speech measured from the recording, across every "
        "stretch marked **SPEECH NOT TRANSCRIBED HERE** above. These are what "
        "was actually said; the rows above are what Whisper managed to write "
        "down, and in these stretches the two disagree about *where* as well "
        "as *what*.\n\n"
        "A run far longer than any take inside it is one delivery the "
        "transcript broke up or started late. When you keep a take in such a "
        "stretch, say in `risks` which run you believe it belongs to, so the "
        "operator can widen the beat to the run instead of the fragment.\n\n"
        "| start | end | secs |\n| --- | --- | --- |\n" + "\n".join(lines)
    )


def take_table(found: list[Take], sentences: list[Sentence]) -> str:
    by_index = {s.index: s for s in sentences}
    rows = ["| # | s | start | end | secs | machine says | what was said |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for take in found:
        text = take.text.replace("|", "\\|")
        verdict = flag(by_index[take.sentence])
        if take.part[1] > 1:
            verdict += f" [attempt {take.part[0]} of {take.part[1]}]"
        if take.swallowed:
            verdict += " + SPEECH NOT TRANSCRIBED HERE"
        rows.append(f"| {take.index} | {take.sentence} | {take.start:.2f} | "
                    f"{take.end:.2f} | {take.duration:.1f} | {verdict} | {text} |")
    return "\n".join(rows)


def assets(project: Path) -> str:
    """What is actually on disk to cut to.

    A director who does not know what footage exists invents an overlay that
    names a file nobody has, and the cue is dropped at render time with a note
    nobody reads until the video is finished.
    """
    lines = []
    root = project / "assets"
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                lines.append(f"- `{path.relative_to(root).as_posix()}`")
    if not lines:
        return ("Nothing. `<project>/assets/` is empty, so any cue naming a "
                "file will be dropped. Overlays that generate their own "
                "picture -- `wordStack`, `emojiRow`, `chipRow`, `dualGraph`, "
                "`terminal`, `html`, `flash` -- still work.")
    return "\n".join(lines)


def hook_shortlist(state: dict) -> str:
    candidates = state.get("hook_candidates") or []
    if not candidates:
        return ("Not generated yet -- leave `hook.pick` at 0 and the pipeline "
                "will ask separately.")
    rows = []
    for number, candidate in enumerate(candidates, 1):
        text = candidate.get("sv") or candidate.get("text") or ""
        rows.append(f"{number}. {text}")
        if candidate.get("source"):
            rows.append(f"   from: {candidate['source']}")
    return "\n".join(rows)


def vocabulary() -> str:
    """The overlay kinds, read from the renderer's own type file.

    Restating them here would drift from what the renderer accepts, and a
    director working from a stale list writes cues that resolve and then render
    as nothing.
    """
    return (BROLL / "src" / "overlays" / "types.ts").read_text(encoding="utf-8")


LEADING_COMMENT = re.compile(r"/\*\*(.*?)\*/", re.S)


def purposes() -> str:
    """What each overlay is FOR, from the components' own header comments.

    types.ts says what fields a kind takes and nothing about when to reach for
    it. Given only that, the director asked for a red `flash` to emphasise a
    word -- but a flash is a white blowout with no colour, and it exists to
    cover a cut, so that would have rendered as a glitch mid-sentence. The
    components say so in their own docstrings; they just were not being read.
    """
    blocks = []
    for path in sorted((BROLL / "src" / "overlays").glob("*.tsx")):
        if path.stem == "Overlays":
            continue
        found = LEADING_COMMENT.search(path.read_text(encoding="utf-8"))
        if not found:
            continue
        body = "\n".join(
            line.strip().lstrip("*").strip()
            for line in found.group(1).splitlines()
        ).strip()
        blocks.append(f"**{path.stem}**\n\n{body}")
    return "\n\n".join(blocks)


CATALOGUE = Path(__file__).resolve().parent / "animations"


def saved_animations() -> str:
    """The animations that have already been made to work, with their cues.

    A director given only a vocabulary invents a new combination every video,
    and the fifth video stops looking like the first. These are the
    combinations that survived being watched.
    """
    parts = []
    for path in sorted(CATALOGUE.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        cue = json.dumps(entry["cue"], ensure_ascii=False, indent=2)
        parts.append(
            f"**{entry['title']}** (`{path.stem}`)\n\n"
            f"{entry['what']}\n\n"
            f"*Reach for it when:* {entry['when']}\n\n"
            f"```json\n{cue}\n```"
        )
    return "\n\n".join(parts) if parts else "None saved yet."


def build(project: Path, state: dict, rules: str) -> str:
    """The whole brief, as one markdown document."""
    words = read_words(Path(state["raw_transcript"]))
    found = take_list(words)
    # The sentences the table's `s` column and machine verdicts come from, off
    # the same clamped words the takes came from.
    words, clamped = clamp_slack(words)
    sentences = analyse(words)
    orphans = unseen(words, found)
    raw_length = words[-1].end if words else 0.0
    runs = measured_runs(Path(state.get("source", "")), found, raw_length)
    flagged = sum(1 for s in sentences if s.is_blooper)
    split = sum(1 for take in found if take.part[1] > 1)

    topic_path = project / "topic.txt"
    topic = (topic_path.read_text(encoding="utf-8-sig").strip()
             if topic_path.is_file() else "")

    low, high = TARGET_SECONDS
    return f"""# Direct this video

{rules}

---

## This video

- project: `{project.as_posix()}`
- raw recording: {raw_length:.1f}s, {len(sentences)} sentences, {len(found)} takes
- the machine flags {flagged} sentence(s) as bloopers
- {split} take(s) are one attempt among several inside a single sentence
- {len(clamped)} word(s) were impossibly long, meaning speech sits in this
  recording that Whisper never wrote down
- target finished length: {low:.0f}-{high:.0f}s, the range the ten reference
  reels actually run; their median is {TYPICAL_SECONDS:.0f}s

### What it is meant to be about

{topic or "_Not stated. Infer it from the transcript._"}

## The transcript, one row per take

A **take** is one continuous run of speech. Where a sentence was said more than
once with a pause between attempts, each attempt is its own row and its own
number -- that is the level you decide at. The `s` column says which sentence a
take came from, because the machine's verdict is a property of the sentence.

Times are seconds into the raw recording. You never need them: name takes by
number and the pipeline measures the cut points from the audio.

A take marked **SPEECH NOT TRANSCRIBED HERE** sits next to a word so long it
cannot be one word -- discarded attempts Whisper smoothed away without writing
them down. In that region the text below is *not* a reliable account of what
was said, and the words shown may be spread across several attempts rather than
belonging to one. Read the rule about this under Learned rules before deciding
anything there.

{take_table(found, sentences)}

{orphan_note(orphans)}

{runs}

## Footage and files available

{assets(project)}

## Hook shortlist

{hook_shortlist(state)}

## The overlay vocabulary

This is the renderer's own type definition. Anything not in it does not exist.
You write `cue` (a phrase that is said in a sentence you kept), and optionally
`until` or `hold`; the pipeline fills in every frame number.

```ts
{vocabulary()}
```

## Animations that already work

Prefer one of these over assembling a new combination. Each is a cue sheet
entry that was made, watched and kept; the phrases in them are placeholders to
replace with words said in a take you kept. Using a saved one is why the fifth
video looks like the first.

{saved_animations()}

## What each one is for

The fields above say what a kind accepts. These say when to reach for it, in
the words of the component that draws it. An overlay used against its purpose
renders correctly and reads as a mistake.

{purposes()}
"""


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()

    state = json.loads((args.project / "pipeline.json").read_text(encoding="utf-8"))
    rules_path = Path(__file__).parent / "DIRECTOR.md"
    print(build(args.project, state, rules_path.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
