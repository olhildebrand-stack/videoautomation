#!/usr/bin/env python3
"""The shape of a director's answer, and every check that can be made of it.

Nothing here calls a model. The value of a brain in the loop depends entirely
on being able to tell, mechanically, when it has said something that will not
work -- an index that does not exist, a take left undecided, a cue phrase
that is never said in the words that survive. Those are all checkable, and a
checkable complaint can be handed straight back for another pass.

So this module is the contract:

    SCHEMA      what the answer must look like    (enforced by the CLI)
    validate    what the answer must be true of   (enforced here)
    edit_script / overlay_sheet   the files it becomes

The split matters. A schema stops malformed JSON; it cannot stop a director
from dropping the take the whole video is about.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brief import Take  # noqa: E402
from cues import resolve as resolve_cues  # noqa: E402

COLOURS = ["green", "red", "lightBlue", "ink"]
# `wordStack` is deliberately absent: the operator watched it and ruled it out
# for good ("that was a horrible idea from my end"). The component is still in
# the renderer -- it is not dead until something else needs deleting -- but a
# kind the director cannot name is a kind that cannot come back by accident.
KINDS = ["emojiRow", "image", "chat", "dualGraph", "chipRow",
         "html", "iconRow", "terminal", "clip", "push", "flash"]

# Keys the director may set on a cue. Deliberately not `enter`/`leave`/`types`
# /`replies`: those are frame numbers, and a director who writes a frame number
# has written a timestamp, which is the thing this whole design removes.
_CHILD = {
    "emoji": ["emoji", "cue"],
    "chips": ["text", "cue"],
    "series": ["label", "direction", "colour", "cue"],
    "slots": ["tone", "name", "cue"],
}


def _child_schema(key: str) -> dict:
    fields: dict[str, dict] = {"cue": {"type": "string"}}
    if key == "emoji":
        fields["emoji"] = {"type": "string"}
    if key == "chips":
        fields["text"] = {"type": "string"}
    if key == "series":
        fields["label"] = {"type": "string"}
        fields["direction"] = {"enum": ["rising", "falling"]}
        fields["colour"] = {"enum": COLOURS}
    if key == "slots":
        fields["tone"] = {"enum": ["bad", "good", "great"]}
        fields["name"] = {"type": "string"}
        fields["emoji"] = {"type": "string"}
        fields["src"] = {"type": "string"}
    return {
        "type": "array",
        "items": {"type": "object", "additionalProperties": False,
                  "required": _CHILD[key], "properties": fields},
    }


OVERLAY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "why"],
    "properties": {
        "kind": {"enum": KINDS},
        "cue": {"type": "string",
                "description": "the phrase this hangs on, said in a kept take"},
        "until": {"type": "string",
                  "description": '"end", or another phrase it stays until -- '
                                 'it leaves as that phrase BEGINS'},
        "untilEndOf": {"type": "string",
                       "description": "a phrase it stays through, leaving as "
                                      "that phrase ends. What the push wants: "
                                      "naming the next sentence's first word "
                                      "instead ends it inside that sentence"},
        "from": {"enum": ["start"],
                 "description": "anchor to the clip's first frame instead of "
                                "a phrase -- for an effect that fires the "
                                "instant the video begins"},
        "hold": {"type": "number",
                 "description": "seconds to stay after the phrase ends"},
        "why": {"type": "string",
                "description": "what this shows that the words alone do not"},
        "words": {"type": "array", "items": {"type": "string"}},
        "colour": {"enum": COLOURS},
        "line": {"enum": ["rising", "falling"]},
        "lineColour": {"enum": COLOURS},
        "emoji": _child_schema("emoji"),
        "chips": _child_schema("chips"),
        "reveal": {"enum": ["blur", "enter"]},
        "row": {"type": "integer",
                "description": "chipRow: 0 under the hook, 1 under a row "
                               "already on screen"},
        "series": _child_schema("series"),
        "slots": _child_schema("slots"),
        "question": {"type": "string"},
        "src": {"type": "string"},
        "htmlFile": {"type": "string"},
        "full": {"type": "boolean"},
        "scale": {"type": "number",
                  "description": "push: how far in, e.g. 1.08"},
        "lines": {"type": "array", "items": {"type": "string"}},
        "finishBy": {"type": "string",
                     "description": "terminal: the phrase its output should "
                                    "have finished by, if not when it leaves"},
        "title": {"type": "string"},
        "prompt": {"type": "string"},
        "replyVideo": {"type": "string"},
        "replyText": {"type": "string"},
    },
}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["throughline", "keep", "drop", "overlays", "hook"],
    "properties": {
        "throughline": {
            "type": "string",
            "description": "one sentence: what this video promises and pays off",
        },
        "keep": {
            "type": "array",
            "description": "the beats, in the order they will play",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["beat", "takes", "why"],
                "properties": {
                    "beat": {"type": "string",
                             "description": "SHORT CAPS name, e.g. HOOK, PROBLEM, STEP 1"},
                    "takes": {"type": "array", "items": {"type": "integer"},
                              "description": "take numbers, in the order they play"},
                    "why": {"type": "string"},
                },
            },
        },
        "drop": {
            "type": "array",
            "description": "every take that does not make it, and why",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["takes", "why"],
                "properties": {
                    "takes": {"type": "array", "items": {"type": "integer"}},
                    "why": {"type": "string"},
                },
            },
        },
        "overlays": {"type": "array", "items": OVERLAY_SCHEMA},
        "hook": {
            "type": "object", "additionalProperties": False,
            "required": ["pick", "why"],
            "properties": {
                "pick": {"type": "integer",
                         "description": "1-based into the shortlist; 0 if none fit"},
                "why": {"type": "string"},
            },
        },
        "risks": {
            "type": "array", "items": {"type": "string"},
            "description": "what you are unsure of, in the operator's words",
        },
    },
}


def _indices(groups: list[dict]) -> list[int]:
    return [i for group in groups for i in group.get("takes", [])]


def validate(decision: dict, takes: list[Take], fps: int = 30) -> list[str]:
    """Everything wrong with this decision, in the order worth fixing it.

    Returned as plain sentences because they are handed back to the director
    verbatim. A complaint that does not say what to do instead produces another
    round of the same mistake.
    """
    problems: list[str] = []
    known = {take.index: take for take in takes}

    keep = decision.get("keep") or []
    drop = decision.get("drop") or []
    kept = _indices(keep)
    dropped = _indices(drop)

    if not keep:
        problems.append("`keep` is empty: there is no video.")

    for where, used in (("keep", kept), ("drop", dropped)):
        for index in used:
            if index not in known:
                problems.append(
                    f"`{where}` names take {index}, which does not exist. "
                    f"The transcript runs {min(known)}-{max(known)}."
                    if known else f"`{where}` names take {index}.")

    seen: set[int] = set()
    for index in kept + dropped:
        if index in seen:
            problems.append(
                f"Take {index} is listed twice. Each take belongs to exactly "
                "one beat, or to `drop`.")
        seen.add(index)

    # The check that exists because a take full of retakes shipped with every
    # one of them intact: silence is not a decision.
    missing = sorted(set(known) - seen)
    if missing:
        shown = ", ".join(str(i) for i in missing[:12])
        more = f" (and {len(missing) - 12} more)" if len(missing) > 12 else ""
        problems.append(
            f"{len(missing)} take(s) are in neither `keep` nor `drop`: "
            f"{shown}{more}. Every take needs a decision, even if the reason "
            "is \"nothing wrong with it, the video is better without\".")

    for group in keep:
        if not group.get("takes"):
            problems.append(
                f"Beat {group.get('beat', '?')!r} keeps no takes.")

    # Cue phrases are checked against the words that will actually survive,
    # which is the only text they can hang on. Doing this at render time meant
    # finding out after the edit was already committed.
    surviving = [w for index in kept if index in known for w in known[index].words]
    sheet = [{k: v for k, v in cue.items() if k != "why"}
             for cue in (decision.get("overlays") or [])]
    if sheet and surviving:
        _, cue_problems = resolve_cues(sheet, surviving, fps,
                                       int(len(surviving) * fps))
        for problem in cue_problems:
            problems.append(
                f"Overlay {problem.kind}: the phrase \"{problem.cue}\" -- "
                f"{problem.reason}. A cue has to quote words you kept, "
                "exactly as they were said.")

    # A push scales the footage. One that never releases leaves the whole
    # video cropped at 1.2 with no way to tell from the sheet that it was
    # meant to be a moment. Every other kind can reasonably stay to the end.
    for cue in decision.get("overlays") or []:
        if cue.get("kind") != "push":
            continue
        if (not cue.get("until") and not cue.get("untilEndOf")
                and cue.get("hold") is None):
            problems.append(
                "The `push` says where it starts and never where it ends, so "
                "it would hold the picture zoomed for the rest of the video. "
                "Give it `untilEndOf` — the hook's last word, so it is over "
                "as the sentence is — or a `hold` in seconds.")
        elif cue.get("until") == "end":
            problems.append(
                "The `push` runs `until: \"end\"`, which crops the whole "
                "video rather than emphasising one line. It belongs on the "
                "hook and should release when the hook does.")

    hook = decision.get("hook") or {}
    pick = hook.get("pick", 0)
    if not isinstance(pick, int) or pick < 0:
        problems.append("`hook.pick` must be a whole number, 0 for none.")

    return problems


def edit_script(decision: dict, takes: list[Take]) -> list[dict]:
    """The decision as beats the pipeline already knows how to cut.

    One entry per take, carrying the range that take was measured at. A beat
    spanning several takes would span the silence between them; separate
    entries drop it without silence removal having to find it.

    The beat name carries the take number (`HOOK.T4`) so a script edited by
    hand afterwards can still be read back against the decision that made it --
    which is what `--learn` does.
    """
    known = {take.index: take for take in takes}
    beats: list[dict] = []
    for group in decision.get("keep", []):
        for index in group.get("takes", []):
            take = known.get(index)
            if take is None:
                continue
            beats.append({"beat": f"{group['beat']}.T{index}",
                          "start": round(take.start, 3),
                          "end": round(take.end, 3),
                          "line": take.text})
    return beats


def overlay_sheet(decision: dict) -> list[dict]:
    """The cues, with the reasoning stripped back out.

    `why` earns its place in the decision -- it is how the checkpoint explains
    an overlay to the operator -- and has no business in a file the renderer
    reads.
    """
    return [{k: v for k, v in cue.items() if k != "why"}
            for cue in (decision.get("overlays") or [])]
