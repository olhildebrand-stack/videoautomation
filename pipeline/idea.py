#!/usr/bin/env python3
"""The idea stage: what gets recorded, settled before anything is filmed.

    python pipeline/idea.py new   <name>
    python pipeline/idea.py hooks <name>
    python pipeline/idea.py check <name>

`IDEAS.md` is the stage. This is the part of it a machine can check. The stage
turns "I want to post something" into a topic, a hook picked from the bank by
number, and a beat outline -- and every one of those already has a rule
attached that was, until now, only written down.

Two files per idea, both tracked, both outliving the project directory they get
copied into:

    topics/<name>.txt     what the video is ABOUT. `--topic` already reads it.
    outlines/<name>.md    the beats, in the director's vocabulary. Read at the
                          camera by a person and consumed by nothing else --
                          the director re-derives the beats from what was
                          actually said, not from what was planned.

The hook is matched here rather than only at checkpoint 3, because by
checkpoint 3 the video exists. A subject the bank holds no hook for is worth
finding out about before the recording rather than after it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from formats import names as format_names  # noqa: E402
from hookgen import (  # noqa: E402
    SEED_TOPIC, bank_has_nothing, generate, load_bank, parse_topic,
)

HERE = Path(__file__).resolve().parent
BRAND = HERE / "ideas" / "BRAND.md"
TOPICS = HERE / "topics"
OUTLINES = HERE / "outlines"

# The two beats DIRECTOR.md fixes the ends of the video to. Everything between
# them is named for what it is -- `STEP 1`, `THE FIX`, `WHAT CHANGED` -- so
# there is no vocabulary to enforce there, only these two.
FIRST_BEAT = "HOOK"
LAST_BEAT = "LANDING"

# A number followed by a unit of time. The rule this catches is IDEAS.md's:
# the pipeline measures time from the audio, so an outline saying "10 seconds
# on the problem" is guessing at a number the machine will overrule.
#
# Only beat names and header values are searched, never what the beat says. A
# line of spoken content that happens to mention three minutes is the video's
# subject, not a timing, and flagging it would teach the operator to ignore
# this check -- which costs more than the rule is worth.
CLOCK = re.compile(
    r"\b\d+([.,]\d+)?\s*(s|sec|secs|second|seconds|sek|sekund|sekunder"
    r"|min|mins|minute|minutes|minut|minuter)\b|\b\d{1,2}:\d{2}\b",
    re.IGNORECASE,
)

SEED_OUTLINE = """\
# {name}

# needs  : what has to be filmed or captured, honestly -- talking head only,
#          a screen recording, a screenshot, three photographs. This is what
#          decides whether the idea gets made this week or never.
# format : a slide format from pipeline/formats/bank.json, for a story. Leave
#          it as `-` for a talking-head video.
# hook   : a number from pipeline/hooks/bank.json. `idea.py hooks {name}`
#          ranks the bank against topics/{name}.txt.

needs  :
format : -
hook   :

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
    unanswered, question = [], "?"
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

    topic = parse_topic(topic_file.read_text(encoding="utf-8-sig"))
    if not (topic.tools or topic.subject or topic.makes or topic.replaces
            or topic.about):
        found.append(f"{topic_file.name} is still the blank seed, so hook"
                     " matching has nothing to rank against")

    text = outline_file.read_text(encoding="utf-8-sig")
    header, beats = parse_outline(text)

    if not header.get("needs"):
        found.append("the outline does not say what it needs filmed or"
                     " captured, so nobody can tell whether it is makeable")

    fmt = header.get("format", "")
    if fmt and fmt != "-" and fmt not in format_names():
        found.append(f"format {fmt!r} is not in the formats bank -- a sequence"
                     " picks a layout, it does not invent one")

    hook = header.get("hook", "")
    if not hook:
        found.append(f"no hook picked. `idea.py hooks {name}` ranks the bank")
    elif not hook.isdigit():
        found.append(f"hook {hook!r} is not a number -- hooks are matched from"
                     " the bank by number, never written")
    elif int(hook) not in {h["n"] for h in load_bank()}:
        found.append(f"hook {hook} is not in pipeline/hooks/bank.json")

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

    timed = [f"{k}: {v}" for k, v in header.items() if CLOCK.search(v)]
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
    written = []
    for path, seed in ((topic_path(name), SEED_TOPIC),
                       (outline_path(name), SEED_OUTLINE.format(name=name))):
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


def hooks(name: str, count: int = 5) -> int:
    """Rank the bank against the topic alone -- there is no recording yet."""
    path = topic_path(name)
    if not path.is_file():
        print(f"error: no topic at {path}", file=sys.stderr)
        return 2
    topic = parse_topic(path.read_text(encoding="utf-8-sig"))
    candidates = generate("", topic, count=count)

    for c in candidates:
        print(f"\n[{c.source_n}] {c.sv}")
        print(f"     {c.source_en!r}"
              f" -- {c.changed} word{'' if c.changed == 1 else 's'} changed")
        if c.why:
            print(f"     why: {', '.join(c.why)}")

    if bank_has_nothing(candidates):
        print("\nThe bank does not hold a hook for this. Every candidate above"
              "\nscored as noise, so the shortlist is a ranking of nothing."
              "\nEither the topic is about something the bank has never covered"
              "\n-- in which case the bank needs growing with a hook that"
              "\nactually won -- or topics/%s.txt is too thin to rank against."
              % name)
        return 1

    print(f"\nWrite the number into the `hook :` line of"
          f" outlines/{name}.md.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, helptext in [
        ("new", "start an idea: a blank topic and a blank outline"),
        ("hooks", "rank the hooks bank against the topic, before recording"),
        ("check", "every rule IDEAS.md states, enforced"),
    ]:
        p = sub.add_parser(command, help=helptext)
        p.add_argument("name")
        if command == "hooks":
            p.add_argument("--count", type=int, default=5)

    args = parser.parse_args()
    if args.command == "new":
        return new(args.name)
    if args.command == "hooks":
        return hooks(args.name, args.count)
    return check(args.name)


if __name__ == "__main__":
    raise SystemExit(main())
