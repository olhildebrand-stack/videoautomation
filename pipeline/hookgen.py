#!/usr/bin/env python3
"""Match the on-screen hook bank against a project.

Checkpoint 3 chooses the text card that sits on the frame, so it matches
against `hooks/onscreen-hooks.md`. The other bank, `hooks/winning-hooks.md`,
is verbal hooks -- the sentence spoken over the opening seconds -- which is
chosen before the camera is on, at the idea stage, not here.

Both banks are prose, which is the whole reason this file looks the way it
does. There is nothing in them to score: a hook is matched by reading it and
recognising that it fits, and the only thing here that can do that is Claude.
So this is a judgement stage like the director, called the same way, with the
same shape of answer coming back.

What is NOT judgement, and is enforced below: every hook offered has to quote
a source that appears in the bank, verbatim. That is "only these" written as
code rather than as a paragraph nobody can check.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from director import ask

HERE = Path(__file__).resolve().parent
BANK = HERE / "hooks" / "onscreen-hooks.md"

MODEL = "sonnet"

SYSTEM = (
    "You choose the on-screen hook for a short vertical video: the text card "
    "on the frame, three to eight words. You never write one. You match the "
    "tightest-fitting source from the bank you were given and change as few "
    "words as possible -- usually one noun, leaving the structure around it "
    "alone. You answer only in the JSON schema you were given."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates", "nothing_fits"],
    "properties": {
        "nothing_fits": {
            "type": "boolean",
            "description": "True when no source in the bank fits this video "
                           "without being rewritten into a different hook.",
        },
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "source", "changed"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The card as it renders, in Swedish.",
                    },
                    "source": {
                        "type": "string",
                        "description": "The bank hook this came from, quoted "
                                       "exactly as it appears in the bank.",
                    },
                    "changed": {
                        "type": "string",
                        "description": "What was swapped, in one line. "
                                       "'word-for-word' when nothing was.",
                    },
                },
            },
        },
    },
}

SEED_TOPIC = """\
# What is this video ABOUT? Two or three lines of plain prose.
#
# The hook is matched against this as well as the transcript, because a
# recording can spend ninety seconds on a system without once naming the tools
# it is built from. Say what it does, what it replaces, and who it is for.
"""


@dataclass
class Candidate:
    sv: str        # the card as it renders
    source: str    # the bank hook it came from, untouched
    changed: str   # what was swapped, in one line


class BankUnavailable(RuntimeError):
    pass


def load_topic(project: Path) -> str:
    """<project>/topic.txt as prose. Blank when absent or only comments."""
    path = project / "topic.txt"
    if not path.is_file():
        return ""
    return "\n".join(
        line for line in path.read_text(encoding="utf-8-sig").splitlines()
        if not line.lstrip().startswith("#")
    ).strip()


def bank_text(path: Path = BANK) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def in_bank(source: str, bank: str) -> bool:
    """Is this source actually in the bank, or was it invented?

    Compared with the quotes stripped and whitespace flattened, because a
    quoted-caps hook comes back with its quotes sometimes kept and sometimes
    not, and that is not the difference worth rejecting an answer over.
    """
    def flat(text: str) -> str:
        return " ".join(text.replace('"', "").replace("'", "").split()).casefold()
    return flat(source) in flat(bank)


def prompt(transcript: str, topic: str, count: int, bank: str) -> str:
    return f"""# Pick the on-screen hook

Below is the bank. Every hook in it has run. Match this video to the {count}
tightest-fitting sources and give each as a card.

The method, which the worked examples in the bank demonstrate:

- Swap one noun. Leave the structure around it alone.
- Carry the source's punctuation across. A trailing `...` and QUOTED CAPS are
  what make a card read as a confession or an overheard objection rather than
  a headline. A lowercase source stays lowercase.
- Word-for-word is a normal outcome, not a failure to try.
- Write the card in Swedish; the source stays in whatever language it is in.
- Quote each `source` exactly as it appears in the bank. An answer quoting
  something that is not in the bank is rejected and asked for again.

Set `nothing_fits` when no source fits without being rewritten into a
different hook. Say so rather than bending one -- offering a bent hook as a
match is the one failure this stage exists to prevent.

---

## What the video is about

{topic or "Not filled in. Go on the transcript alone."}

## The cut, as spoken

{transcript.strip() or "Not transcribed yet."}

---

{bank}
"""


def generate(transcript: str, topic: str, count: int = 5,
             model: str = MODEL, bank: str | None = None) -> list[Candidate]:
    """The `count` best-fitting cards for this video, best first."""
    text = bank if bank is not None else bank_text()
    answer = ask(prompt(transcript, topic, count, text), model,
                 schema=SCHEMA, system=SYSTEM)
    if answer.get("nothing_fits"):
        return []
    out = []
    for row in answer.get("candidates", [])[:count]:
        if not in_bank(row["source"], text):
            raise BankUnavailable(
                f"The hook stage answered with a source that is not in the "
                f"bank: {row['source']!r}. The bank is the complete set, so "
                f"that is an invented hook. Try again, or match one yourself "
                f"from {BANK}.")
        out.append(Candidate(row["text"], row["source"], row["changed"]))
    return out


def render_file(candidates: list[Candidate]) -> str:
    """The shortlist as hook.txt: first non-comment line is what renders."""
    out = [
        f"# Matched from {BANK.name} -- none of these were written.",
        "# The FIRST non-comment line renders. Reorder to change it.",
        "#",
    ]
    for i, c in enumerate(candidates):
        out.append(("" if i == 0 else "# ") + c.sv)
        out.append(f"#   ^ from: {c.source}")
        out.append(f"#     changed: {c.changed}")
        out.append("#")
    return "\n".join(out) + "\n"


def as_dicts(candidates: list[Candidate]) -> list[dict]:
    return [{"sv": c.sv, "source": c.source, "changed": c.changed}
            for c in candidates]
