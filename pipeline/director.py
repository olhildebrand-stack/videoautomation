#!/usr/bin/env python3
"""Ask a brain to shape the video, then check what it said.

    python director.py --project projects/ep01
    python director.py --project projects/ep01 --brief-only

The pipeline is deterministic everywhere except one decision, and that decision
was being made by hand in a chat window, per video, forever. This makes it a
stage: the brief goes to `claude -p` with a schema it has to answer in, the
answer is checked against the transcript it claims to describe, and anything
wrong is handed straight back for another pass.

Three passes, then it stops and shows the operator what it could not resolve. A
model that has failed the same check twice is not one round away from passing
it, and burning tokens on a fourth try is worse than saying so.

The decision is kept at `<project>/decision.json` whatever happens, because the
reasoning in it -- why a take was dropped, what an overlay is for -- is the part
worth reading when the cut looks wrong.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brief as brief_module  # noqa: E402
from decision import SCHEMA, edit_script, overlay_sheet, validate  # noqa: E402
from jsonfile import BadJSON, read as read_json  # noqa: E402
from state import Stage  # noqa: E402
from state import load as load_state, save as save_state  # noqa: E402

HERE = Path(__file__).resolve().parent
RULES = HERE / "DIRECTOR.md"

ATTEMPTS = 3

# Sonnet, not the biggest model available: this is a judgement over a page of
# text with a schema around it, which is what Sonnet is good at, and the stage
# runs on every video. Override with --model when a video is worth more.
MODEL = "sonnet"

SYSTEM = (
    "You are directing a short vertical video from a raw talking-head "
    "recording. You answer only in the JSON schema you were given. Every "
    "sentence in the transcript gets a decision, and every reason you give is "
    "read by the person whose video this is."
)


class DirectorUnavailable(RuntimeError):
    pass


def claude_cli() -> str:
    found = shutil.which("claude")
    if not found:
        raise DirectorUnavailable(
            "The `claude` CLI is not on PATH, so the director stage cannot "
            "run.\n"
            "  Install it: npm install -g @anthropic-ai/claude-code\n"
            "  Or run `--brief-only`, hand the brief to Claude yourself, and "
            "save the answer as <project>/decision.json."
        )
    return found


def ask(prompt: str, model: str, schema: dict | None = None,
        system: str = SYSTEM, timeout: float = 600.0) -> dict:
    """One call, returning the parsed answer.

    `schema` and `system` default to the director's own. The hook stage is the
    other judgement in this pipeline and passes its own pair; everything about
    how the call is made -- stdin, no tools, the envelope -- is the same
    problem twice and is solved here once.

    The prompt goes in on **stdin**, never as an argument. On Windows `claude`
    is a .cmd shim, so the call runs through cmd.exe, which refuses a command
    line over 8191 characters -- and a brief for a one-minute recording is
    already 12k. Passing it as an argument worked on Linux and failed on the
    only machine that matters, with "The command line is too long".

    `--json-schema` makes the shape the CLI's problem rather than ours; what
    comes back in `result` is a JSON string already conforming to it, so the
    only failure left to handle here is the call itself failing.
    """
    args = [
        claude_cli(), "-p",
        "--model", model,
        "--system-prompt", system,
        "--json-schema", json.dumps(schema if schema is not None else SCHEMA),
        "--output-format", "json",
        # No tools, no MCP servers, no skills. Everything needed is in the
        # prompt, and a director that goes reading the repository is a
        # director whose answer depends on what it happened to open.
        #
        # --strict-mcp-config is also the cheapest line here: the MCP tool
        # definitions were 10k tokens of a 38k call that uses no tools.
        "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebSearch",
        "--strict-mcp-config", "--disable-slash-commands",
    ]
    try:
        done = subprocess.run(args, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise DirectorUnavailable(
            f"`claude -p` did not answer within {timeout:.0f}s. A long "
            "recording can take a few minutes; a hang looks the same from "
            "here. Try again, or --brief-only to direct it by hand."
        ) from None
    if done.returncode != 0:
        raise DirectorUnavailable(explain(done.returncode, done.stderr, done.stdout))
    try:
        envelope = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise DirectorUnavailable(
            f"`claude -p` did not return JSON: {done.stdout[:300]}") from exc
    if envelope.get("is_error"):
        raise DirectorUnavailable(f"`claude -p` failed: {envelope.get('result')}")
    return json.loads(envelope["result"])


def explain(code: int, stderr: str, stdout: str) -> str:
    """Why the call failed, in a sentence the operator can act on.

    The CLI reports a failure by printing its whole result envelope, so the
    first version showed the last 400 characters of JSON. An expired login --
    which is the common failure and the only one with an obvious fix -- arrived
    as `:0,"spawned_by_subagents":0,...` with the actual reason buried in the
    middle of it. The reason is in there under `result`; take that.
    """
    reason = (stderr or "").strip()
    try:
        reason = json.loads(stdout).get("result") or reason
    except (json.JSONDecodeError, AttributeError):
        reason = reason or stdout.strip()[-400:]
    if "authenticate" in reason.lower() or "oauth" in reason.lower():
        return (f"{reason}\n"
                "  Log in again: run `claude` in a terminal, or `/login` "
                "inside it.\n"
                "  Nothing is lost -- the transcript and the checkpoint are "
                "still in the project.")
    return f"`claude -p` exited {code}: {reason}"


def complaint(problems: list[str]) -> str:
    """The failed checks, phrased as the next question rather than a verdict."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return (
        "\n\n---\n\n## Your previous answer did not pass these checks\n\n"
        f"{listed}\n\n"
        "Fix exactly these and return the whole decision again. Everything "
        "that was not listed was fine -- keep it as it was."
    )


def direct(project: Path, state: dict, model: str = MODEL,
           attempts: int = ATTEMPTS,
           asker=ask) -> tuple[dict, list[str], str]:
    """Get a decision that passes, or the best one and what is still wrong."""
    words = brief_module.read_words(Path(state["raw_transcript"]))
    takes = brief_module.take_list(words)
    prompt = brief_module.build(project, state, RULES.read_text(encoding="utf-8"))

    decision: dict = {}
    problems: list[str] = ["no answer yet"]
    for attempt in range(1, attempts + 1):
        # Said out loud because the call takes minutes and printed nothing:
        # a stage that looks identical to a hang gets killed by the operator.
        print(f"Reading {len(takes)} takes with Claude "
              f"(attempt {attempt} of {attempts}, a few minutes) ...",
              flush=True)
        decision = asker(prompt, model)
        problems = validate(decision, takes)
        if not problems:
            return decision, [], f"passed on attempt {attempt}"
        if attempt < attempts:
            prompt = prompt + complaint(problems)
    return decision, problems, f"still failing after {attempts} attempts"


def write(project: Path, decision: dict, state: dict) -> dict:
    """Turn a passing decision into the two files the pipeline reads."""
    words = brief_module.read_words(Path(state["raw_transcript"]))
    takes = brief_module.take_list(words)

    beats = edit_script(decision, takes)
    (project / "edit-script.json").write_text(
        json.dumps(beats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sheet = overlay_sheet(decision)
    if sheet:
        (project / "overlays.json").write_text(
            json.dumps(sheet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    try:
        stored = load_state(project)
    except TypeError:
        # A state file this build cannot parse is not a reason to throw away a
        # decision that took a minute and a half to get. Say so and move on.
        stored = None
        print("NOTE: could not read pipeline.json, so the pipeline was not "
              "rewound and --retime was not set. Pass --retime to `run`.")
    if stored is not None:
        # Ranges written from word timestamps need measuring against the
        # audio: the transcript clock drifts in proportion to the silence the
        # decoder removed, so a range taken as written clips the last word of
        # a late cut.
        stored.retime = True
        # A new edit script makes every stage after the cut list stale. Without
        # this, directing a project that had already been rendered left the
        # stage at `done`, so the next `run` said "already finished -- nothing
        # was rebuilt" and the old video stood.
        rewound = stored.stage_enum is not Stage.THROUGHLINE_APPROVED
        stored.advance_to(Stage.THROUGHLINE_APPROVED)
        save_state(project, stored)
        if rewound:
            print("Rewound to the cut list -- everything after it is stale now.")

    return {"beats": len(beats), "overlays": len(sheet),
            "seconds": sum(b["end"] - b["start"] for b in beats)}


def drift(decision: dict, beats: list[dict]) -> list[str]:
    """What the operator changed after the director decided it.

    This is the only honest signal about whether the rules are any good. A
    director that keeps being overruled the same way is a rule that has not
    been written yet, and without this the overruling happens in an editor and
    leaves no trace.

    Beat names carry the sentence they came from (`HOOK.S4`), so a hand-edited
    script can still be read back against the decision that produced it.
    """
    import re

    chose = [index
             for group in decision.get("keep", [])
             for index in group.get("takes", [])]
    shipped: list[int] = []
    for entry in beats:
        found = re.search(r"\.T(\d+)$", str(entry.get("beat", "")))
        if found:
            index = int(found.group(1))
            if index not in shipped:
                shipped.append(index)

    if not shipped:
        return ["The shipped script has no take numbers in its beat names, so "
                "it cannot be read back against the decision."]

    dropped_by_hand = [i for i in chose if i not in shipped]
    kept_by_hand = [i for i in shipped if i not in chose]
    notes = []
    if dropped_by_hand:
        notes.append(
            f"You cut {len(dropped_by_hand)} take(s) the director kept: "
            + ", ".join(str(i) for i in dropped_by_hand))
    if kept_by_hand:
        notes.append(
            f"You put back {len(kept_by_hand)} take(s) the director cut: "
            + ", ".join(str(i) for i in kept_by_hand))
    common = [i for i in chose if i in shipped]
    if common != [i for i in shipped if i in chose]:
        notes.append("You reordered the beats.")
    if not notes:
        notes.append("Nothing changed -- the decision shipped as it was.")
    return notes


def report(decision: dict, summary: dict, problems: list[str]) -> None:
    print()
    print(f"Throughline: {decision.get('throughline', '(none stated)')}")
    print()
    for group in decision.get("keep", []):
        listed = ", ".join(str(i) for i in group.get("takes", []))
        print(f"  {group.get('beat', '?'):<14} {listed}")
        print(f"  {'':<14} {group.get('why', '')}")
    dropped = sum(len(g.get("takes", [])) for g in decision.get("drop", []))
    print()
    print(f"Dropped {dropped} take(s):")
    for group in decision.get("drop", []):
        listed = ", ".join(str(i) for i in group.get("takes", []))
        print(f"  {listed}: {group.get('why', '')}")

    if decision.get("overlays"):
        print()
        print("Overlays:")
        for cue in decision["overlays"]:
            # An anchor is a phrase OR the clip's first frame, and printing
            # only the phrase showed a push as `on ""`, which reads as a cue
            # that failed rather than one that never had a phrase.
            anchor = (f'"{cue["cue"]}"' if cue.get("cue")
                      else "the first frame" if cue.get("from") == "start"
                      else "its children")
            leaves = (f' until "{cue["until"]}"' if cue.get("until") else "")
            print(f"  {cue.get('kind', '?'):<12} on {anchor}{leaves}")
            print(f"  {'':<12} {cue.get('why', '')}")

    hook = decision.get("hook") or {}
    print()
    print(f"Hook: {hook.get('pick', 0) or 'none of the shortlist'} "
          f"-- {hook.get('why', '')}")

    if decision.get("risks"):
        print()
        print("Worth looking at:")
        for risk in decision["risks"]:
            print(f"  - {risk}")

    print()
    low, high = brief_module.TARGET_SECONDS
    over = ""
    if summary["seconds"] > high:
        # It ran 22s past the band once and said nothing about it, because the
        # number was printed without the target beside it.
        over = (f"  -- {summary['seconds'] - high:.0f}s longer than the "
                f"longest of the ten reference reels")
    elif summary["seconds"] < low:
        over = "  -- shorter than any of the ten reference reels"
    print(f"{summary['beats']} beats, {summary['seconds']:.1f}s, "
          f"{summary['overlays']} overlay(s).{over}")
    if problems:
        print()
        print("Checks still failing -- the files were written anyway so you can")
        print("see what it meant, but they are not right yet:")
        for problem in problems:
            print(f"  - {problem}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--attempts", type=int, default=ATTEMPTS)
    parser.add_argument("--brief-only", action="store_true",
                        help="write the brief and stop, to direct it by hand")
    parser.add_argument("--learn", action="store_true",
                        help="say what you changed after the director decided, "
                             "so the difference can become a rule")
    parser.add_argument("--from-file", type=Path, default=None,
                        help="check and install a decision written by hand, "
                             "rather than calling the CLI")
    args = parser.parse_args()

    state_path = args.project / "pipeline.json"
    if not state_path.is_file():
        print(f"error: no pipeline at {args.project}", file=sys.stderr)
        return 2
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not state.get("raw_transcript"):
        print("error: nothing transcribed yet. Run `init` first.",
              file=sys.stderr)
        return 2

    if args.learn:
        decision_path = args.project / "decision.json"
        script_path = args.project / "edit-script.json"
        if not decision_path.is_file() or not script_path.is_file():
            print("error: need both decision.json and edit-script.json.",
                  file=sys.stderr)
            return 2
        for note in drift(
                read_json(decision_path, "decision"),
                read_json(script_path, "edit script")):
            print(note)
        print()
        print(f"NOTE: a difference that will recur belongs in {RULES} under")
        print("NOTE: \"Learned rules\", written as what to do instead.")
        return 0

    if args.brief_only:
        out = args.project / "brief.md"
        out.write_text(
            brief_module.build(args.project, state,
                               RULES.read_text(encoding="utf-8")),
            encoding="utf-8")
        print(f"Wrote {out}.")
        print("NOTE: hand it to Claude, save the answer as "
              f"{args.project / 'decision.json'}, then run:")
        print(f"NOTE:   {sys.argv[0]} --project {args.project} "
              f"--from-file {args.project / 'decision.json'}")
        return 0

    if args.from_file:
        # The hand-directed path. Same checks, same files: a decision written
        # in a chat window is not a lesser kind of decision, it just did not
        # come through the CLI.
        source = args.from_file
        if not source.is_file():
            print(f"error: no decision at {source}", file=sys.stderr)
            return 2
        decision = read_json(source, "decision")
        words = brief_module.read_words(Path(state["raw_transcript"]))
        problems = validate(
            decision, brief_module.take_list(words))
        how = "checked as written" if not problems else "written by hand, and"
    else:
        try:
            decision, problems, how = direct(
                args.project, state, args.model, args.attempts)
        except DirectorUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    (args.project / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    summary = write(args.project, decision, state)
    print(how)
    report(decision, summary, problems)
    return 1 if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BadJSON as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except BrokenPipeError:
        sys.exit(0)
