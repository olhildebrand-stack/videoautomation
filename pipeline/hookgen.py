#!/usr/bin/env python3
"""Match hooks from `hooks/bank.json` against a project.

SUPERSEDED. The hook rules now live in `hooks/winning-hooks.md`, which is the
complete, intentional set -- all hooks in it have equal weight, matching is
against any category, and the budget is "as few words as possible" rather than
the three this file counts. That file is prose, so nothing here can score it:
the match is made by reading it and putting the chosen line in the project's
`hook.txt`, then `pipeline.py hook 0`. What remains below still runs, against
the thirty-eight structured hooks in `bank.json` only.

The rule it enforced: never write a new hook. The bank holds hooks that already
worked; this ranks them against what the video is actually about and, where a
hook names the wrong subject, swaps that one phrase for the project's own. A
swap costs words, and more than three is not allowed -- so the best candidates
are almost always the ones offered verbatim.

Two inputs decide the ranking:

  the transcript   what was said, in Swedish. Scored against tag lexicons.
  topic.txt        what the video is ABOUT. A recording can spend ninety
                   seconds on a system without once naming the tools it is
                   built from, so the transcript alone is not enough.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BANK = Path(__file__).resolve().parent / "hooks" / "bank.json"

# Words that put a video on a topic. Swedish first -- that is what the
# transcript is in -- plus the English loanwords Swedish creators actually
# use ("content", "captions", "b-roll") rather than their Swedish equivalents.
LEXICON: dict[str, list[str]] = {
    "automation": ["automat", "pipeline", "skript", "script", "av sig själv",
                   "göra själv", "system", "automatiskt", "helt själv"],
    "video": ["video", "klipp", "filma", "filmar", "film", "redigera",
              "redigering", "editor", "edit", "captions", "undertext",
              "b-roll", "color correction", "färgkorr", "kamera"],
    "content": ["content", "innehåll", "posta", "publicera", "konto",
                "short form", "reels", "reel", "följare"],
    "replacement": ["konkurs", "ersätta", "byta ut", "slippa", "byrå",
                    "anställa", "sparka", "istället för"],
    "unlimited": ["hur många", "obegränsat", "massor", "varenda", "oändligt",
                  "i all oändlighet", "hur mycket som helst"],
    "experiment": ["testkanin", "testa", "test", "experiment", "prova",
                   "försöka", "labbar"],
    "insane": ["sjukt", "galet", "insane", "otroligt", "magi", "grymt"],
    "claude-code": ["claude", "claude code", "cloud code", "anthropic"],
    "agents": ["agent", "agenter", "subagent"],
    "tooling": ["remotion", "whisper", "ffmpeg", "obsidian", "shopify",
                "nexus", "manus", "skills", "verktyg", "mcp"],
    "clawdbot": ["clawdbot", "clawbot", "openclaw"],
    "instagram": ["instagram", "reels", "ig "],
    "algorithm": ["algoritm", "räckvidd", "views", "visningar", "spridning"],
    "sales": ["sälj", "säljer", "kund", "kunder", "pris", "offert"],
    "objection": ["invändning", "för dyrt", "nej tack", "tveka"],
    "business": ["företag", "business", "byrå", "verksamhet", "bolag"],
    "money": ["pengar", "tjäna", "vinst", "kostar", "dollar", "kronor"],
    "startup": ["startup", "starta eget", "grunda"],
    "mistake": ["misstag", "fel", "sabbade", "sket sig", "gick åt skogen"],
    "warning": ["varning", "akta", "se upp", "banna", "stänger av", "risk"],
}

# What each slot kind is filled from in topic.txt.
SLOT_KEYS = {
    "tool": "tools",
    "subject": "subject",
    "output": "makes",
    "replaced": "replaces",
}

MAX_WORDS_CHANGED = 3

# Below this, the bank does not hold a hook for this video.
#
# Every candidate is scored, so there is always a top five -- but a top five is
# not a match. On a video the bank fits, the winner scores in the twenties; on
# one it does not, five hooks tie at 2.0 on a single incidental keyword and are
# presented with the same confidence. Saying so is more useful than ranking
# noise, because the honest answer is sometimes "write one, or grow the bank".
WEAK_BANK = 6.0


@dataclass
class Topic:
    """What the video is about, from <project>/topic.txt."""

    tools: list[str] = field(default_factory=list)
    # Each is a (swedish, english) pair -- Swedish is what gets rendered,
    # English is only there so the word-change count is honest.
    subject: tuple[str, str] | None = None
    makes: tuple[str, str] | None = None
    replaces: tuple[str, str] | None = None
    about: str = ""

    def fill(self, kind: str) -> list[tuple[str, str]]:
        key = SLOT_KEYS.get(kind)
        if key == "tools":
            return [(t, t) for t in self.tools]
        pair = getattr(self, key, None) if key else None
        return [pair] if pair else []


@dataclass
class Candidate:
    sv: str            # what renders on screen
    en: str            # the same hook in English, after any swap
    source_n: int      # which bank hook it came from
    source_en: str     # that hook, untouched
    changed: int       # English words changed. 0 is the goal.
    score: float
    why: list[str] = field(default_factory=list)


def load_bank(path: Path = BANK) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))["hooks"]


def parse_topic(text: str) -> Topic:
    """Read topic.txt. Unknown keys are ignored, so it can carry notes."""
    topic = Topic()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().casefold(), value.strip()
        if not value:
            continue
        if key == "tools":
            topic.tools = [t.strip() for t in value.split(",") if t.strip()]
        elif key == "about":
            topic.about = (topic.about + " " + value).strip()
        elif key in ("subject", "makes", "replaces"):
            # "svenska | English" -- the English half only exists so the
            # word-change count means what the rule says it means.
            swedish, _, english = value.partition("|")
            swedish = swedish.strip()
            english = english.strip() or swedish
            setattr(topic, key, (swedish, english))
    return topic


def load_topic(project: Path) -> Topic:
    path = Path(project) / "topic.txt"
    if not path.is_file():
        return Topic()
    return parse_topic(path.read_text(encoding="utf-8-sig"))


SEED_TOPIC = """\
# What this video is ABOUT. Hook matching reads this.
#
# The recording often never names the tools it is built from, so the transcript
# alone cannot rank hooks. Two minutes here is what makes the shortlist good.
#
# tools    : comma separated. A hook naming a different tool can have that one
#            word swapped for one of these.
# subject  : svenska | English -- the thing the video demonstrates.
# makes    : svenska | English -- what the system produces.
# replaces : svenska | English -- who or what it puts out of a job.
# about    : free text, Swedish or English. Repeatable.
#
# Every field is optional. With none of them, hooks are still ranked from the
# transcript and offered verbatim -- which is the preferred outcome anyway.

tools    :
subject  :
makes    :
replaces :
about    :
"""


def tag_hits(corpus: str, tag: str) -> int:
    """How many distinct lexicon terms for `tag` the corpus contains."""
    folded = corpus.casefold()
    return sum(1 for term in LEXICON.get(tag, []) if term in folded)


def real_change(slot_en: str, fill_en: str) -> bool:
    """Would this swap actually change what the hook is about?

    Filling "Viral Videos" with "Videos" spends two of the three words allowed
    and buys nothing but a weaker hook. One term containing the other means the
    hook already names the right subject.
    """
    a, b = slot_en.casefold(), fill_en.casefold()
    return a != b and a not in b and b not in a


def substitutions(hook: dict, topic: Topic) -> list[list[tuple[dict, tuple[str, str]]]]:
    """Every combination of slot fills for one hook, including filling none."""
    combos: list[list[tuple[dict, tuple[str, str]]]] = [[]]
    for slot in hook.get("slots", []):
        fills = [f for f in topic.fill(slot["kind"]) if real_change(slot["en"], f[1])]
        combos = [c + [(slot, f)] for c in combos for f in fills] + combos
    return combos


def apply_slots(hook: dict, fills: list[tuple[dict, tuple[str, str]]]) -> tuple[str, str, int]:
    sv, en, changed = hook["sv"], hook["en"], 0
    for slot, (swedish, english) in fills:
        sv = sv.replace(slot["sv"], swedish, 1)
        en = en.replace(slot["en"], english, 1)
        changed += slot["words"]
    return sv, en, changed


def score_candidate(
    hook: dict,
    en: str,
    changed: int,
    fills: list[tuple[dict, tuple[str, str]]],
    topic: Topic,
    corpus: str,
) -> tuple[float, list[str]]:
    score, why = 0.0, []
    folded_corpus = corpus.casefold()

    for tag in hook.get("tags", []):
        hits = min(tag_hits(corpus, tag), 3)
        if hits:
            score += 2.0 * hits
            why.append(f"{tag} x{hits}")

    folded_en = en.casefold()
    for tool in topic.tools:
        if tool.casefold() in folded_en:
            score += 4.0
            why.append(f"names {tool}")

    filled = {id(slot) for slot, _ in fills}
    for slot in hook.get("slots", []):
        if id(slot) in filled:
            # A slot the operator redirected onto this video's own subject.
            # Worth a little more than it costs: a hook naming what this system
            # replaces beats one naming a marketing agency nobody here has a
            # stake in. Generic nouns only -- a tool swap is already paid for
            # by the +4 above.
            if slot["kind"] in ("output", "replaced"):
                score += 1.5 * slot["words"] + 0.5
                why.append(f"{slot['kind']} is this video's own")
        elif slot["kind"] in ("tool", "subject") and slot["en"].casefold() not in folded_corpus:
            # A product the video is not about, still sitting in the hook.
            # Priced at roughly what swapping it out costs, so leaving it and
            # swapping it are compared on even terms.
            score -= 2.0 * slot["words"]
            why.append(f"still about {slot['en']}")

    for entity in hook.get("entities", []):
        if entity.casefold() not in folded_corpus:
            # Unlike a slot this cannot be swapped out -- the hook is simply
            # about something else.
            score -= 4.0
            why.append(f"about {entity}")

    # Every changed word is a step away from a hook that already worked.
    score -= 1.5 * changed

    return score, why


def generate(
    transcript: str, topic: Topic, count: int = 5, bank: list[dict] | None = None
) -> list[Candidate]:
    """The best `count` hooks for this video, best first."""
    corpus = f"{transcript}\n{topic.about}\n{' '.join(topic.tools)}"
    if topic.subject:
        corpus += " " + " ".join(topic.subject)

    best: list[Candidate] = []
    for hook in bank if bank is not None else load_bank():
        variants: list[Candidate] = []
        for fills in substitutions(hook, topic):
            sv, en, changed = apply_slots(hook, fills)
            if changed > MAX_WORDS_CHANGED:
                continue
            score, why = score_candidate(
                hook, en, changed, fills, topic, corpus
            )
            variants.append(
                Candidate(sv, en, hook["n"], hook["en"], changed, score, why)
            )
        if variants:
            # Ties go to the version that changed fewer words.
            best.append(max(variants, key=lambda c: (c.score, -c.changed)))

    best.sort(key=lambda c: (-c.score, c.changed, c.source_n))
    return best[:count]


def render_file(candidates: list[Candidate]) -> str:
    """The shortlist as hook.txt: first non-comment line is what renders."""
    out = [
        "# Matched from the winning-hooks bank -- none of these were written.",
        "# The FIRST non-comment line renders. Reorder to change it.",
        "#",
    ]
    for i, c in enumerate(candidates):
        prefix = "" if i == 0 else "# "
        out.append(f"{prefix}{c.sv}")
        out.append(f"#   ^ [{c.source_n}] {c.source_en!r}"
                   f" -- {c.changed} word{'' if c.changed == 1 else 's'} changed")
        if c.en != c.source_en:
            out.append(f"#     as: {c.en}")
        out.append("#")
    return "\n".join(out) + "\n"


def bank_has_nothing(candidates: list[Candidate]) -> bool:
    """True when the best candidate is indistinguishable from noise."""
    return not candidates or candidates[0].score < WEAK_BANK


def as_dicts(candidates: list[Candidate]) -> list[dict]:
    return [
        {"sv": c.sv, "en": c.en, "source_n": c.source_n,
         "source_en": c.source_en, "changed": c.changed,
         "score": round(c.score, 2), "why": c.why}
        for c in candidates
    ]
