#!/usr/bin/env python3
"""The idea stage: what gets recorded, settled before anything is filmed.

    python pipeline/idea.py new   <name>
    python pipeline/idea.py check <name>

`IDEAS.md` is the stage. This is the part of it a machine can check. The stage
turns "I want to post something" into a topic, both hooks, and a beat outline
-- and every one of those already has a rule attached that was, until now,
only written down.

Two tracked files per idea, both outliving the gitignored `projects/`
directory they get copied into:

    topics/<name>.txt     what the video is ABOUT. `--topic` already reads it.
    outlines/<name>.md    the beats, in the director's vocabulary. Read at the
                          camera by a person and consumed by nothing else --
                          the director re-derives the beats from what was
                          actually said, not from what was planned.

Matching a hook is judgement and stays in the conversation; there is no
matcher here. What is checkable is the accounting: every hook names the source
it was matched from, and that source has to appear in its bank verbatim. That
is `hookgen.py`'s own check, applied to the half of the work that happens
before the camera is on.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from formats import names as format_names  # noqa: E402
from hookgen import SEED_TOPIC, bank_text, in_bank  # noqa: E402

HERE = Path(__file__).resolve().parent
BRAND = HERE / "ideas" / "BRAND.md"
TOPICS = HERE / "topics"
OUTLINES = HERE / "outlines"

# The two banks, and which header field is matched from which. They are not
# interchangeable: a verbal hook is the full sentence spoken over the opening
# seconds, an on-screen hook is the three-to-eight-word card on the frame.
BANKS = {
    "verbal": HERE / "hooks" / "winning-hooks.md",
    "onscreen": HERE / "hooks" / "onscreen-hooks.md",
}

# What the on-screen bank says a card is. The verbal bank has no such limit --
# its entries are whole sentences.
ONSCREEN_WORDS = (3, 8)

# The two beats DIRECTOR.md fixes the ends of the video to. Everything between
# them is named for what it is -- `STEP 1`, `THE FIX`, `WHAT CHANGED` -- so
# there is no vocabulary to enforce there, only these two.
FIRST_BEAT = "HOOK"
LAST_BEAT = "LANDING"

# A number followed by a unit of time. The rule this catches is IDEAS.md's:
# the pipeline measures time from the audio, so an outline saying "10 seconds
# on the problem" is guessing at a number the machine will overrule.
#
# Only beat names and the non-hook header values are searched. What a beat
# says is exempt -- a line of spoken content mentioning three minutes is the
# video's subject, not a timing. So are the hook fields, and that is not a
# nicety: the swipe file is full of proven hooks built on a clock, "Can you
# tell us how to (insert result) in 60 seconds?" among them, and a check that
# rejected those would reject most of the bank. Flagging either would teach
# the operator to ignore this check, which costs more than the rule is worth.
CLOCK = re.compile(
    r"\b\d+([.,]\d+)?\s*(s|sec|secs|second|seconds|sek|sekund|sekunder"
    r"|min|mins|minute|minutes|minut|minuter)\b|\b\d{1,2}:\d{2}\b",
    re.IGNORECASE,
)

SEED_OUTLINE = """\
# {name}

# needs    : what has to be filmed or captured, honestly -- talking head only,
#            a screen recording, a screenshot, three photographs. This is what
#            decides whether the idea gets made this week or never.
# format   : a slide format from pipeline/formats/bank.json, for a story.
#            Leave it as `-` for a talking-head video.
# verbal   : the sentence spoken over the opening seconds, matched from
#            hooks/winning-hooks.md. Never written.
# onscreen : the {lo}-to-{hi}-word card on the frame, matched from
#            hooks/onscreen-hooks.md. A different bank and a different job.
#
# Each hook carries the source it was matched from, quoted exactly as that
# bank has it. Change as few words as possible -- usually one noun -- and
# carry the source's punctuation across. Word-for-word is a normal outcome.

needs         :
format        : -
verbal        :
verbal-from   :
onscreen      :
onscreen-from :

## HOOK

## PROBLEM

## LANDING
"""


def topic_path(name: str) -> Path:
    return TOPICS / f"{name}.txt"


def outline_path(name: str) -> Path:
    return OUTLINES / f"{name}.md"


def brand_unanswered(text: str) -> list[str]:
    """The BRAND.md questions still sitting on an empty **Answer:**.

    Every idea this stage produces before these are answered is a guess about
    somebody generic, which is the one thing that reliably does not get
    watched. So it is a gate, not a warning.
    """
    unanswered = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        question = block.splitlines()[0].strip()
        _, _, answer = block.partition("**Answer:**")
        if not answer.strip():
            unanswered.append(question)
    return unanswered


def parse_outline(text: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """The header fields, and the beats in the order they are recorded in."""
    header: dict[str, str] = {}
    beats: list[tuple[str, str]] = []
    current: str | None = None
    body: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            if current is not None:
                beats.append((current, "\n".join(body).strip()))
            current, body = line[3:].strip(), []
        elif current is not None:
            body.append(raw)
        elif not line.startswith("#") and ":" in line:
            key, _, value = line.partition(":")
            header[key.strip().casefold()] = value.strip()
    if current is not None:
        beats.append((current, "\n".join(body).strip()))
    return header, beats


def hook_problems(header: dict[str, str], name: str) -> list[str]:
    """Both hooks present, and both matched from a source that really exists.

    The verbatim check is the one that matters. A hook the model liked the
    sound of, presented with a source that is not in the bank, is an invented
    hook -- which is the single failure both banks exist to prevent, and the
    only part of matching a machine can settle.
    """
    found = []
    for field, bank in BANKS.items():
        text, source = header.get(field, ""), header.get(f"{field}-from", "")
        if not text:
            found.append(f"no {field} hook. Match one from {bank.name}")
            continue
        if not source:
            found.append(f"the {field} hook does not say what it was matched"
                         f" from. Without a `{field}-from` line naming a"
                         f" source in {bank.name}, nothing distinguishes a"
                         f" match from an invention")
            continue
        if not in_bank(source, bank_text(bank)):
            found.append(f"the {field} hook is matched from {source!r}, which"
                         f" is not in {bank.name}. That bank is the complete"
                         f" set, so this is a written hook, not a matched one")
    card = header.get("onscreen", "")
    lo, hi = ONSCREEN_WORDS
    if card and not lo <= len(card.split()) <= hi:
        found.append(f"the on-screen hook is {len(card.split())} words;"
                     f" {outline_path(name).name} needs {lo}-{hi}. A whole"
                     f" sentence is a verbal hook, which is the other bank")
    return found


def problems(name: str) -> list[str]:
    """Everything wrong with this idea that can be established mechanically."""
    found = []

    for question in brand_unanswered(BRAND.read_text(encoding="utf-8")):
        found.append(f"ideas/BRAND.md is unanswered: {question}")

    topic_file, outline_file = topic_path(name), outline_path(name)
    if not topic_file.is_file():
        return found + [f"no topic at {topic_file}"]
    if not outline_file.is_file():
        return found + [f"no outline at {outline_file}"]

    topic = "\n".join(
        line for line in topic_file.read_text(encoding="utf-8-sig").splitlines()
        if not line.lstrip().startswith("#")
    ).strip()
    if not topic:
        found.append(f"{topic_file.name} says nothing about the video, so a"
                     " hook cannot be matched against it")

    text = outline_file.read_text(encoding="utf-8-sig")
    header, beats = parse_outline(text)

    if not header.get("needs"):
        found.append("the outline does not say what it needs filmed or"
                     " captured, so nobody can tell whether it is makeable")

    fmt = header.get("format", "")
    if fmt and fmt != "-" and fmt not in format_names():
        found.append(f"format {fmt!r} is not in the formats bank -- a sequence"
                     " picks a layout, it does not invent one")

    found += hook_problems(header, name)

    if not beats:
        found.append("the outline has no beats, which is the whole point of it")
    else:
        if beats[0][0] != FIRST_BEAT:
            found.append(f"the first beat is {beats[0][0]!r}, not {FIRST_BEAT}")
        if beats[-1][0] != LAST_BEAT:
            found.append(f"the last beat is {beats[-1][0]!r}, not {LAST_BEAT}"
                         " -- a video that trails off has no landing")
        for beat, body in beats:
            if not body:
                found.append(f"beat {beat} is empty, so there is nothing to say")

    exempt = set(BANKS) | {f"{field}-from" for field in BANKS}
    timed = [f"{k}: {v}" for k, v in header.items()
             if k not in exempt and CLOCK.search(v)]
    timed += [beat for beat, _ in beats if CLOCK.search(beat)]
    for where in timed:
        found.append(f"the outline writes a timing: {where!r}. The pipeline"
                     " measures time from the audio, so a planned duration is"
                     " a number it will overrule")

    return found


def check(name: str) -> int:
    found = problems(name)
    for problem in found:
        print(f"error: {problem}", file=sys.stderr)
    if found:
        return 1
    print(f"{name}: ready to record. Film it, then:\n"
          f"  python pipeline\\pipeline.py init <video> --project projects\\{name}\n"
          f"  python pipeline\\pipeline.py run --project projects\\{name}"
          f" --topic pipeline\\topics\\{name}.txt")
    return 0


def new(name: str) -> int:
    lo, hi = ONSCREEN_WORDS
    written = []
    for path, seed in ((topic_path(name), SEED_TOPIC),
                       (outline_path(name),
                        SEED_OUTLINE.format(name=name, lo=lo, hi=hi))):
        if path.is_file():
            print(f"{path} already exists, left alone")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(seed, encoding="utf-8")
        written.append(path)
    for path in written:
        print(f"wrote {path}")
    print(f"\nFill both, then: python pipeline\\idea.py check {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, helptext in [
        ("new", "start an idea: a blank topic and a blank outline"),
        ("check", "every rule IDEAS.md states, enforced"),
    ]:
        sub.add_parser(command, help=helptext).add_argument("name")

    args = parser.parse_args()
    return new(args.name) if args.command == "new" else check(args.name)


if __name__ == "__main__":
    raise SystemExit(main())
