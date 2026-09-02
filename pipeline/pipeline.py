#!/usr/bin/env python3
"""Raw video to graded, captioned cut -- stopping at two human checkpoints.

    python pipeline/pipeline.py init   <video> --project projects/ep01
    python pipeline/pipeline.py run    --project projects/ep01
    python pipeline/pipeline.py status --project projects/ep01

`run` advances as far as it can and stops at the next gate, printing exactly
what is needed. Run it again after supplying that, and it continues.

The three gates are deliberate. Stage 3 of the editing prompt asks whether the
throughline matches your intent; a cut list is worth eyeballing before a render;
and the hook is the one line that decides whether any of the rest is watched.
All three are cheap to check and expensive to get wrong.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from cutlist import (
    build_cutlist, clamp_slack, drop_fillers, drop_hallucinations,
    merge_adjacent, read_words, tighten, words_between,
)
from ffmpeg_ops import FFmpegMissing, Grade, cut, grade, probe_duration
from remotion_ops import command as remotion_command
from hookgen import (
    BANK as HOOK_BANK, BankUnavailable, SEED_TOPIC, as_dicts, generate,
    load_topic, render_file,
)
from director import DirectorUnavailable
from brief import TARGET_SECONDS
from jsonfile import BadJSON, read as read_json
from cues import CHILD_KEYS, load_sheet, resolve as resolve_cues
from edges import DEFAULT_SLACK, measure_best, trim_to_speech
from sentences import (
    DEFAULT_END_TAIL, DEFAULT_HEAD, DEFAULT_TAIL, analyse, keepers,
    retime_range, sentence_ranges,
)
from state import ORDER, PipelineState, Stage, load, save

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIBE = ROOT / "transcribe" / "transcribe.py"
BROLL = ROOT / "broll"
CAPTION_COMPOSITION = "CaptionedVideo"


def normalise_loose(text: str) -> str:
    """Compare wording while ignoring case, punctuation and spacing."""
    return " ".join(
        token for token in (
            "".join(ch for ch in text.casefold() if ch.isalnum() or ch.isspace())
        ).split()
    )


def say(message: str = "") -> None:
    print(message, flush=True)


def rule(title: str) -> None:
    say(f"\n{'=' * 4} {title}")


def python_for_transcribe() -> str:
    """The transcribe venv if present, else whatever is running this."""
    for candidate in (
        ROOT / "transcribe" / ".venv" / "Scripts" / "python.exe",
        ROOT / "transcribe" / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def transcribe(video: Path, project: Path) -> Path:
    """Transcribe verbatim, because this pipeline exists to cut video.

    Whisper's decoder is conditioned to produce fluent text: by default it
    silently smooths false starts and repetitions out of the transcript while
    the audio still contains them. transcribe.py has had a --verbatim mode
    since it was written -- vad_filter and condition_on_previous_text both off
    -- and the pipeline never passed it.

    That is the root of every smeared stretch this project has fought:

      vas3            a hook written as one sentence over fourteen seconds,
                      six of which were false starts nobody could see
      aieditor        a problem sentence whose real delivery ran 49.5-57.5 and
                      whose transcript began at 52.7 with the first half gone
      aivoice         "en businessgrej som alla hoppar på hemsidodesigning nu",
                      which does not parse because the words between were
                      dropped

    VAD off also removes the drift `edges.py` exists to correct: the timestamps
    are no longer mapped back through stripped silence, so they stop sliding in
    proportion to how much was removed. Measuring the audio still earns its
    place -- it is right about the last consonant where the transcript is
    approximate -- but it is correcting a smaller error.

    The cost is a messier transcript. That is the point: an edit script has to
    be written against what was said, not against what Whisper wishes had been.
    """
    output = video.with_suffix(".words.json")
    args = [python_for_transcribe(), str(TRANSCRIBE), str(video),
            "-o", str(output), "--verbatim"]

    # A project may carry its own terms and rules. The two are treated
    # differently on purpose:
    #
    #   vocabulary.txt   REPLACES the shared list. Hotwords bias the decoder,
    #                    and a term this recording never says is pure risk --
    #                    fed in as a prompt, it gets emitted as text over audio
    #                    the model cannot read. A Swedish video about voice
    #                    agents came back with "TypeScript React GIS" in it,
    #                    because TypeScript and React are in the shared list
    #                    for an entirely different video.
    #   corrections.txt  ADDS to the shared rules, which cannot misfire the
    #                    same way: a find/replace only acts on text that is
    #                    already there.
    vocabulary = project / "vocabulary.txt"
    if vocabulary.is_file():
        args += ["--vocabulary", str(vocabulary)]
        say(f"Vocabulary: {vocabulary} instead of the shared list.")
    corrections = project / "corrections.txt"
    if corrections.is_file():
        args += ["--extra-corrections", str(corrections)]
        say(f"Corrections: the shared rules plus {corrections}.")

    say(f"Transcribing {video.name} (verbatim) ...")
    result = subprocess.run(args)
    if result.returncode != 0:
        raise RuntimeError(f"transcription failed ({result.returncode})")
    return output


# The renderer's frame rate. Cues resolve to frame numbers here and are read
# as frame numbers there, so the two have to agree; `test_fps_matches_the
# _renderer` fails if broll/src/tokens.ts ever says otherwise.
FPS = 30


def render_captions(
    video: Path,
    transcript: Path,
    output: Path,
    hook_text: str = "",
    cues: list[dict] | None = None,
) -> None:
    """Burn captions over `video` using Remotion.

    Both inputs are copied into broll/public because Remotion serves assets
    from there; staticFile cannot reach outside it.
    """
    public = BROLL / "public"
    (public / "video").mkdir(parents=True, exist_ok=True)
    (public / "transcripts").mkdir(parents=True, exist_ok=True)

    video_name = f"video/{video.name}"
    transcript_name = f"transcripts/{transcript.name}"
    shutil.copy2(video, public / video_name)
    shutil.copy2(transcript, public / transcript_name)

    # Props go via a file, not an inline argument: a JSON string on the command
    # line is mangled by Windows PowerShell's native-argument quoting.
    props = public.parent / "props.generated.json"
    props.write_text(
        json.dumps({
            "videoFile": video_name,
            "transcriptFile": transcript_name,
            # The composition caps its length at this, so a transcript longer
            # than its footage cannot leave the clip ending in black.
            "videoDurationSeconds": probe_duration(video),
            "hookText": hook_text,
            # Already resolved to frames. The renderer never sees a phrase.
            "cues": cues or [],
        }),
        encoding="utf-8",
    )

    args = remotion_command(
        "render", CAPTION_COMPOSITION, str(output.resolve()), f"--props={props}")

    say(f"Rendering captions over {video.name} ...")
    result = subprocess.run(args, cwd=BROLL)
    if result.returncode != 0:
        raise RuntimeError(f"Remotion render failed ({result.returncode})")


DEFAULT_HOOK_COUNT = 5


def build_hook_shortlist(state: PipelineState, project: Path, count: int) -> None:
    """Match hooks/onscreen-hooks.md against this video and store the result.

    A bank of prose cannot be scored, so this is a judgement stage like the
    director: the bank goes to Claude and a shortlist comes back, each option
    carrying the source it was matched from. When that call cannot be made the
    gate still opens -- matching by hand and picking with `hook 0` is the same
    work without the shortcut, and is better than a stage that refuses.
    """
    topic_path = project / "topic.txt"
    if not topic_path.is_file():
        topic_path.write_text(SEED_TOPIC, encoding="utf-8")
        say(f"Wrote a blank {topic_path} -- filling it in sharpens the match.")

    transcript = ""
    if state.cut_transcript and Path(state.cut_transcript).is_file():
        # The cut, not the raw recording: the hook has to fit what survived.
        transcript = transcript_text(Path(state.cut_transcript))

    try:
        candidates = generate(transcript, load_topic(project), count=count)
    except (BankUnavailable, DirectorUnavailable) as exc:
        state.hook_candidates = []
        state.hook_weak = False
        say(f"Could not match a shortlist: {exc}")
        return
    state.hook_weak = not candidates
    state.hook_candidates = as_dicts(candidates)
    # A record of the whole shortlist, so a rejected option can be recovered
    # later without regenerating and hoping the match comes out the same.
    (project / "hooks.txt").write_text(render_file(candidates), encoding="utf-8")


def caption_only(videos: list[Path], out_dir: Path | None) -> int:
    """Burn captions over videos that are already cut.

    Everything else in this file exists to decide where to cut. A video that
    arrives already edited needs none of it -- no gates, no edit script, no
    hook card, no overlays -- so this skips the state machine entirely rather
    than driving one through stages it has nothing to do.

    Several videos at once because the case this was written for is four cuts
    of one recording differing only in the spoken hook, being tested against
    each other.
    """
    for video in videos:
        if not video.is_file():
            say(f"No such video: {video}")
            return 2
    for video in videos:
        # The video's own folder as the project: a vocabulary.txt or
        # corrections.txt dropped beside the footage then applies to all of it.
        transcript = transcribe(video, video.parent)
        output = (out_dir or video.parent) / f"{video.stem}-captioned.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        render_captions(video, transcript, output)
        say(f"  {output}  ({probe_duration(output):.1f}s)")
    return 0


def me() -> str:
    """How this script was invoked, for printing runnable next steps.

    Hardcoding "pipeline.py" produced instructions that failed from the repo
    root, which is where it is actually run from. sys.argv[0] is what the
    operator typed, so it works wherever they typed it.
    """
    return sys.argv[0] or "pipeline/pipeline.py"


def load_hook(project: Path) -> str:
    """The on-screen hook, from <project>/hook.txt. Blank if absent."""
    path = project / "hook.txt"
    if not path.is_file():
        return ""
    lines = [
        line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return lines[0] if lines else ""


def load_fillers(project: Path) -> set[str]:
    """Read fillers.txt from the project, if present.

    Per project rather than global: "typ" and "liksom" are filler in one
    recording and load-bearing in the next, so the list is the operator's.
    """
    path = project / "fillers.txt"
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.startswith("#")
    }


def transcript_text(path: Path) -> str:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return "".join(w["word"] for w in data["words"]).strip()


# --- gates ------------------------------------------------------------------

def show_throughline_gate(state: PipelineState, project: Path) -> None:
    rule("CHECKPOINT 1 of 3 -- throughline")
    say()

    words = read_words(Path(state.raw_transcript))
    sentences = analyse(words)
    good = keepers(sentences)
    bloopers = [s for s in sentences if s.is_blooper]

    say("Transcript, sentence by sentence:")
    say()
    for sentence in sentences:
        if sentence.truncated:
            mark, why = "CUT ", "truncated"
        elif sentence.superseded_by is not None:
            mark, why = "CUT ", f"said again as #{sentence.superseded_by}"
        else:
            mark, why = "keep", ""
        text = sentence.text.strip()
        if len(text) > 78:
            text = text[:75] + "..."
        say(f"  {sentence.index:>2} {mark} {sentence.start:>6.2f}-{sentence.end:<6.2f} {text}")
        if why:
            say(f"          ^ {why}")

    say()
    if bloopers:
        dropped = sum(s.end - s.start for s in bloopers)
        say(f"{len(bloopers)} of {len(sentences)} sentences look like bloopers "
            f"({dropped:.1f}s). A retake keeps the LAST attempt.")
    else:
        say(f"No bloopers found in {len(sentences)} sentences -- "
            "one clean take, or they are subtler than punctuation shows.")

    say()
    say("Next: choosing which beats to keep, and in what order. That is the")
    say("one part of this pipeline that needs judgement rather than a rule:")
    say()
    say(f"  python {me()} direct --project {project}")
    say()
    say("That hands the transcript above to Claude with the rules in")
    say("pipeline/DIRECTOR.md, and writes the edit script and overlay sheet")
    say("from what comes back -- every sentence either kept with a reason or")
    say("dropped with one. Read the reasons; they are the point.")
    say()
    say("Or decide it yourself. Either take the sentences as they stand:")
    say(f"  python {me()} draft --project {project}")
    say("or write the beats by hand to")
    say(f"  {project / 'edit-script.json'}")
    say()
    say('  [{"beat": "HOOK", "line": "exact words from the transcript"}, ...]')
    say()
    if bloopers:
        # The verdicts above are useless if the edit script is written without
        # them -- which is exactly how a take full of bloopers shipped with
        # every one intact.
        say("NOTE: an edit script decides what is kept. Nothing above is dropped")
        say("NOTE: unless the script leaves it out. `direct` decides each one")
        say("NOTE: explicitly; `draft` keeps everything not flagged above.")
        say()
    say(f"Then run:  python {me()} run --project {project}")


def draft_edit_script(state: PipelineState, project: Path) -> int:
    """Write an edit script of everything that is not a blooper.

    The classification was already being done and then thrown away: the gate
    printed a raw transcript, and whatever the operator wrote by hand decided
    what survived. A take full of retakes could -- and did -- ship with every
    one of them intact.
    """
    words = read_words(Path(state.raw_transcript))
    sentences = analyse(words)
    good = keepers(sentences)
    if not good:
        say("Nothing survived classification. Not writing a script over that.")
        return 1

    beats = []
    for sentence in good:
        # A sentence can hold a discarded take as silence in its middle, so it
        # is emitted as the pieces that actually carry speech.
        pieces = sentence_ranges(
            sentence, words, is_final=sentence is good[-1]
        )
        for index, (start, end) in enumerate(pieces, 1):
            name = f"S{sentence.index}" + (f".{index}" if len(pieces) > 1 else "")
            beats.append({"beat": name, "start": round(start, 3),
                          "end": round(end, 3), "line": sentence.text.strip()})

    target = project / "edit-script.json"
    target.write_text(json.dumps(beats, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    kept = sum(b["end"] - b["start"] for b in beats)
    say(f"Wrote {len(beats)} beats to {target} ({kept:.1f}s "
        f"of {len(sentences)} sentences, {len(sentences) - len(good)} dropped).")
    say("NOTE: this keeps everything that is not a blooper, in the order said.")
    say("NOTE: reorder or delete beats to shape the edit, then run.")
    return 0


# A ".N" suffix marks a piece that silence removal split off. Only a trailing
# NUMBER means that -- splitting on the first dot instead treated "P.INTRO" and
# "P.LAND" as two pieces of one beat called "P", reassembled their text
# together, and then reported every one of them as differing from its own
# script line.
PIECE_SUFFIX = re.compile(r"\.\d+$")


def base_beat(name: str) -> str:
    """The beat a piece belongs to, with any split suffix removed."""
    return PIECE_SUFFIX.sub("", name.split("+")[0])


def range_settings(entry: dict, is_last: bool,
                   retiming: bool) -> tuple[bool, bool, float]:
    """Which edges of this beat to measure against the audio, and its tail.

    Per-beat overrides, each from a cut no global setting could fix:

      "retime": false   take THIS range as written, both ends. Where a
                        discarded attempt sits just before a beat, the audio
                        search reaches back into it and pulls the cut open over
                        words that were meant to be gone.
      "retime": "end"   take the START as written and measure the END. This is
                        the common case, and false was too blunt for it: a
                        start pinned off a smeared transcript also keeps
                        whatever silence the transcript put after the last
                        word, which plays as a long pause before the next beat.
      "retime": "start" the mirror, for a beat whose end is the unreliable one.
      "tail": 0.0       how long to hold after the last word. Where the speaker
                        stops to think, the default 0.15s is long enough to
                        show them doing it.

    The very last cut is the only thing between the final consonant and black,
    so it keeps the longer tail unless it asks for its own.
    """
    default = DEFAULT_END_TAIL if is_last else DEFAULT_TAIL
    tail = float(entry.get("tail", default))
    if not retiming:
        return False, False, tail

    setting = entry.get("retime", True)
    if setting is True:
        return True, True, tail
    if setting == "end":
        return False, True, tail
    if setting == "start":
        return True, False, tail
    return False, False, tail


def show_cutlist_gate(state: PipelineState, project: Path) -> None:
    rule("CHECKPOINT 2 of 3 -- cut list")
    say()
    total = 0.0
    previous = None

    # Silence removal splits one line into ".1/.2" pieces, each holding part of
    # the wording. Compare the reassembled whole, or every split would be
    # reported as a mismatch and the warning would become noise.
    reassembled: dict[str, str] = {}
    for entry in state.cutlist:
        base = base_beat(entry["beat"])
        reassembled[base] = (
            reassembled.get(base, "") + " " + entry.get("actual_text", "")
        ).strip()

    for entry in state.cutlist:
        # A ".N" suffix means silence removal split one line at a pause.
        base = base_beat(entry["beat"])
        if previous and base_beat(previous["beat"]) == base:
            removed = entry["start"] - previous["end"]
            say(f"    -- split: {removed:.2f}s removed here")
            if removed >= 2.0:
                # Long removals at this point are almost always untranscribed
                # speech exposed by clamping, not a pause somebody chose.
                say("       likely untranscribed audio (a discarded take)")
            elif removed >= 0.8:
                say("       a pause this long may be deliberate -- see --max-gap")
        previous = entry
        flag = "  " if entry["score"] >= 0.999 else "~ "
        say(f"{flag}{entry['beat']:<12} {entry['start']:>7.2f} -> {entry['end']:>7.2f}"
            f"  ({entry['duration']:>5.2f}s)  match {entry['score']:.2f}")
        was = entry.get("was")
        if was and (abs(was[0] - entry["start"]) > 0.05
                    or abs(was[1] - entry["end"]) > 0.05):
            # Signed as a change in length, so -0.85s reads as shorter.
            change = entry["duration"] - (was[1] - was[0])
            say(f"    retimed from {was[0]:.2f} -> {was[1]:.2f}  ({change:+.2f}s)")
            drift = was[2] if len(was) > 2 else None
            if drift:
                start_drift, end_drift, clamped = drift
                say(f"      speech runs {start_drift:+.2f}s / {end_drift:+.2f}s "
                    "from where the transcript put it")
                if clamped:
                    say("      further out than drift explains -- another take "
                        "may be inside the search window, or the threshold is "
                        "reading room tone as speech")
                elif end_drift > 0.25:
                    # The case that clipped "video" to "vi": the transcript
                    # ended the word before the speaker did.
                    say("      the transcript ended this cut inside the last "
                        "word; the audio says where it really finishes")
            elif was[1] - entry["end"] > 0.25:
                say("      the script held this longer than the tail rule does "
                    "-- if it was set by ear, listen to the end of it")
        say(f"    script: {entry['text']}")
        actual = entry.get("actual_text") or entry["matched_text"]
        say(f"    CUT   : {actual}")

        whole = reassembled.get(base_beat(entry["beat"]), actual)
        wording_matches = normalise_loose(whole) == normalise_loose(entry["text"])
        if entry.get("explicit"):
            # The CUT line lists what the transcript places in this range. Where
            # the alignment smears across retakes it will under-report, which is
            # the very reason the range was stated by hand. Nothing to warn about.
            if not wording_matches:
                say("    (transcript places only part of the line here; the range "
                    "was set by ear)")
        elif entry.get("actual_text") and not wording_matches:
            say("    ^^ differs from the script line -- read it before approving")
        elif entry["score"] < 0.999 and wording_matches:
            say("    ^^ wording is exact; the score is a match-window artifact")
        total += entry["duration"]
    say()
    say(f"Total: {total:.1f}s across {len(state.cutlist)} segments.")
    # The band, from the one place it is measured. This used to test one pair
    # of numbers and print a different pair, neither of them matching the
    # reels the band was measured from -- so a 35s cut and a 69s cut were both
    # reported as wrong lengths.
    low, high = TARGET_SECONDS
    if not low <= total <= high:
        say(f"NOTE: {total:.0f}s is outside the {low:.0f}-{high:.0f}s range "
            "the ten reference reels run.")
    for entry in state.cutlist:
        if entry["score"] < 0.999:
            whole = reassembled.get(base_beat(entry["beat"]),
                                    entry.get("actual_text", ""))
            if normalise_loose(whole) != normalise_loose(entry["text"]):
                say(f"NOTE: '{entry['beat']}' wording differs -- check it above.")
    say()
    if any(e["score"] < 0.999 for e in state.cutlist):
        say("Lines marked ~ were not an exact match.")
    say("Edit edit-script.json and re-run to redo,")
    say(f"or approve:  python {me()} approve --project {project}")


def show_hook_gate(state: PipelineState, project: Path) -> None:
    rule("CHECKPOINT 3 of 3 -- hook")
    say()
    if not state.hook_candidates:
        # Either nothing fit, or the matcher could not be reached. Both end in
        # the same place: the bank is right there, and matching by hand is the
        # same judgement the stage would have made.
        if state.hook_weak:
            say("Nothing in the on-screen bank fits this video without being")
            say("rewritten into a different hook, so nothing is offered.")
        say(f"Match one yourself from {HOOK_BANK}, put it in")
        say(f"{project / 'hook.txt'}, then:")
        say(f"  python {me()} hook 0 --project {project}")
        say()
        say(f"Or try again:  python {me()} hooks --project {project}")
        say(f"Or no card at all:  python {me()} hook --none --project {project}")
        return
    for i, c in enumerate(state.hook_candidates, 1):
        say(f"  {i}. {c['sv']}")
        say(f"       from: {c['source']}")
        say(f"       changed: {c['changed']}")
        say()
    say(f"All of these are MATCHED from {HOOK_BANK.name} -- none were written.")
    say("Word-for-word is a fine outcome; one noun swapped is the usual one.")
    say()
    say(f"Pick one:      python {me()} hook 1 --project {project}")
    say(f"See more:      python {me()} hooks --count 10 --project {project}")
    say(f"Write your own: put it in {project / 'hook.txt'}, then")
    say(f"               python {me()} hook 0 --project {project}")
    say(f"No card at all: python {me()} hook --none --project {project}")


# --- stages -----------------------------------------------------------------

def step(state: PipelineState, project: Path) -> bool:
    """Advance one stage. Returns False when blocked at a gate or finished."""
    stage = state.stage_enum
    source = Path(state.source)

    if stage is Stage.NEW:
        state.raw_transcript = str(transcribe(source, project))
        state.advance_to(Stage.TRANSCRIBED_RAW)
        return True

    if stage is Stage.TRANSCRIBED_RAW:
        state.advance_to(Stage.GATE_THROUGHLINE)
        return True

    if stage is Stage.GATE_THROUGHLINE:
        script_path = project / "edit-script.json"
        if not script_path.is_file():
            show_throughline_gate(state, project)
            return False
        state.edit_script = read_json(script_path, "edit script")
        state.advance_to(Stage.THROUGHLINE_APPROVED)
        return True

    if stage is Stage.THROUGHLINE_APPROVED:
        # Always re-read the script from disk. Caching it in the state file
        # meant a rewind to this stage -- which is after the gate that loads it
        # -- kept using the previous version, so editing the script or
        # installing a new one silently changed nothing.
        script_path = project / "edit-script.json"
        if script_path.is_file():
            state.edit_script = read_json(script_path, "edit script")

        words = read_words(Path(state.raw_transcript))

        # Two cleanups before anything is matched, because both distort the
        # timeline rather than the text.
        words, hallucinated = drop_hallucinations(words)
        if hallucinated:
            say(f"Dropped {len(hallucinated)} near-zero-confidence words: "
                + " ".join(w.word.strip() for w in hallucinated[:8]))
            say("  (hotword biasing can emit its own prompt over unreadable audio)")

        words, clamped = clamp_slack(words)
        for word in clamped:
            say(f"Clamped {word.word.strip()!r}: "
                f"{word.end - word.start:.1f}s is implausible for one word -- "
                f"untranscribed speech was inside it")

        # An entry may name an explicit time range instead of a line. Matching
        # infers cut points from a transcript whose timings do not always
        # separate a good take from a discarded one; when it fights the data,
        # stating the range directly is faster and exact. Explicit ranges skip
        # matching, silence removal and merging entirely -- they are the
        # operator's call, not a suggestion.
        explicit = [e for e in state.edit_script if "start" in e and "end" in e]
        explicit_beats: set[str] = {e["beat"] for e in explicit}
        matched_beats = [
            (e["beat"], e["line"]) for e in state.edit_script if "line" in e
            and not ("start" in e and "end" in e)
        ]
        cuts = build_cutlist(words, matched_beats)
        if cuts.misses:
            rule("Lines not found in the transcript")
            for beat, line in cuts.misses:
                say(f"  {beat}: {line}")
            say()
            say("The edit prompt requires exact words from the transcript.")
            say("NOTE: correct these in edit-script.json and re-run.")
            return False
        segments = merge_adjacent(cuts.segments, words)

        # Order matters. Fillers are dropped first so the holes they leave are
        # then treated as pauses; tightening runs next so it sees those holes;
        # merging runs last to rejoin anything the two split needlessly.
        fillers = load_fillers(project)
        if fillers:
            before = sum(s.duration for s in segments)
            segments = drop_fillers(words, segments, fillers)
            say(f"Fillers: removed {before - sum(s.duration for s in segments):.1f}s")

        if state.max_gap > 0:
            before = sum(s.duration for s in segments)
            segments = tighten(segments, words, max_gap=state.max_gap)
            removed = before - sum(s.duration for s in segments)
            if removed > 0.05:
                say(f"Silence: removed {removed:.1f}s of pauses over {state.max_gap}s")
        else:
            say("Silence: removal disabled (--max-gap 0)")
        segments = merge_adjacent(segments, words)

        if explicit:
            from cutlist import Segment
            # Measure against the audio where the source is reachable. The
            # word timestamps slide early in proportion to the silence VAD
            # removed before decoding, so any cut derived from them slides too.
            from_audio = state.retime and source.is_file()
            if state.retime and not from_audio:
                say(f"warning: cannot read {source}, so retiming falls back to "
                    "the word timestamps -- the clock that drifts. Expect the "
                    "last word of a late cut to be clipped.")
            if state.retime:
                where = (f"the audio at {state.noise_db:.0f}dB" if from_audio
                         else "the transcript")
                say(f"{len(explicit)} explicit range(s) re-measured against "
                    f"{where} ({DEFAULT_HEAD}s before, {DEFAULT_TAIL}s after, "
                    f"{DEFAULT_END_TAIL}s at the end)")
            else:
                say(f"{len(explicit)} explicit range(s) taken as given")
            held = [f'{e["beat"]} ({e.get("retime")})'
                    for e in explicit if e.get("retime", True) is not True]
            if held and state.retime:
                say("  edges taken as written: " + ", ".join(held))
            tuned = [f'{e["beat"]} {float(e["tail"]):.2f}s'
                     for e in explicit if "tail" in e]
            if tuned and state.retime:
                say("  own tail: " + ", ".join(tuned))
            by_beat = {base_beat(s.beat): s for s in segments}
            rebuilt: list[Segment] = []
            moved: dict[str, tuple[float, float, tuple | None]] = {}
            # Beats whose measurement had to climb off the recording's stated
            # floor, so the checkpoint can say the room was louder than -45dB.
            climbed: dict[str, float] = {}
            tails: dict[str, float] = {}
            # Edges the script pinned, by beat: (move start, move end).
            pinned: dict[str, tuple[bool, bool]] = {}
            trimmed_lead: dict[str, float] = {}
            trimmed_trail: dict[str, float] = {}
            for entry in state.edit_script:
                if "start" in entry and "end" in entry:
                    begin, finish = float(entry["start"]), float(entry["end"])
                    drift = None
                    is_last = entry is state.edit_script[-1]
                    do_start, do_end, tail = range_settings(
                        entry, is_last, state.retime)
                    # Kept for the trim below: the room a beat is supposed to
                    # have after its last word is not silence to remove, and an
                    # edge taken as written is not the trim's to move either.
                    tails[entry["beat"]] = tail
                    pinned[entry["beat"]] = (do_start, do_end)
                    if do_start or do_end:
                        if not from_audio:
                            moved_begin, moved_finish = retime_range(
                                words, begin, finish, tail=tail)
                            begin = moved_begin if do_start else begin
                            finish = moved_finish if do_end else finish
                        else:
                            found, used_db = measure_best(
                                source, begin, finish,
                                floor=state.noise_db,
                            )
                            if used_db != state.noise_db:
                                climbed[entry["beat"]] = used_db
                            if found.measured:
                                drift = (found.start_drift, found.end_drift,
                                         found.clamped)
                                if do_start:
                                    begin = round(found.start - DEFAULT_HEAD, 3)
                                if do_end:
                                    finish = round(found.end + tail, 3)
                            else:
                                say(f"  {entry['beat']}: no speech found in the "
                                    "audio here, so the range stands as written")
                    covered = words_between(words, begin, finish)
                    segment = Segment(
                        beat=entry["beat"],
                        text=entry.get("line", "(explicit range)"),
                        start=begin,
                        end=finish,
                        score=1.0,
                        matched_text="".join(w.word for w in covered).strip(),
                    )
                    if state.retime:
                        # Keep what was written down. A range set by ear can
                        # sit well past the tails, and retiming takes that back
                        # -- which the gate has to show rather than leave to be
                        # noticed on playback.
                        moved[entry["beat"]] = (
                            float(entry["start"]), float(entry["end"]), drift
                        )
                    rebuilt.append(segment)
                else:
                    found = [s for s in segments
                             if base_beat(s.beat) == entry["beat"]]
                    rebuilt.extend(found)
            # Explicit ranges are taken as given, but two that overlap would
            # cut the same speech twice and stutter at the seam. Trim the later
            # one back rather than silently duplicating.
            for earlier, later in zip(rebuilt, rebuilt[1:]):
                if later.start < earlier.end:
                    overlap = earlier.end - later.start
                    say(f"trimmed {overlap:.2f}s overlap between "
                        f"{earlier.beat} and {later.beat}")
                    later.start = earlier.end

            # Everything above chose the ranges. This looks inside the ones
            # chosen and takes out silence they still contain -- the last
            # thing before cutting, and the only measurement that cannot
            # reach a neighbouring take, because it never leaves the range.
            if from_audio:
                for segment in rebuilt:
                    at = climbed.get(segment.beat, state.noise_db)
                    speech = trim_to_speech(
                        source, segment.start, segment.end, noise_db=at)
                    if speech is None:
                        continue
                    speaks_at, stops_at = speech
                    tail = tails.get(segment.beat, DEFAULT_TAIL)
                    # Measured against the room the beat is meant to have, not
                    # against zero: a beat is supposed to open a head before
                    # the first word and hold a tail after the last one. Only
                    # what is left over is silence nobody asked for.
                    lead = (speaks_at - segment.start) - DEFAULT_HEAD
                    trail = (segment.end - stops_at) - tail
                    # "retime": false was asked for because the measurement got
                    # this edge wrong. Trimming it here would be the same
                    # measurement arriving by a different door.
                    move_start, move_end = pinned.get(segment.beat, (True, True))
                    if move_start and lead > DEFAULT_SLACK:
                        segment.start = round(speaks_at - DEFAULT_HEAD, 3)
                        trimmed_lead[segment.beat] = round(lead, 2)
                    if move_end and trail > DEFAULT_SLACK:
                        segment.end = round(stops_at + tail, 3)
                        trimmed_trail[segment.beat] = round(trail, 2)

            if trimmed_lead or trimmed_trail:
                say("  silence found inside the kept ranges and removed:")
                for beat in dict.fromkeys(
                        list(trimmed_lead) + list(trimmed_trail)):
                    parts = []
                    if beat in trimmed_lead:
                        parts.append(f"{trimmed_lead[beat]:.2f}s before")
                    if beat in trimmed_trail:
                        parts.append(f"{trimmed_trail[beat]:.2f}s after")
                    say(f"    {beat}: " + " and ".join(parts))

            if climbed:
                # Said out loud because it changes what was measured, and
                # because a room noisier than the default is a property of the
                # recording setup, not of this one video.
                say(f"  the room is louder than {state.noise_db:.0f}dB -- "
                    "measured these at a higher threshold instead:")
                for beat, used in climbed.items():
                    say(f"    {beat}: {used:.0f}dB")

            segments = rebuilt

        state.cutlist = [
            {
                "beat": s.beat,
                "text": s.text,
                "matched_text": s.matched_text,
                # What the cut will ACTUALLY contain, rebuilt from the words the
                # span covers. matched_text is the per-line match concatenated,
                # which after a merge hides anything swept up in between -- the
                # one thing this checkpoint exists to catch.
                "actual_text": "".join(
                    w.word for w in words_between(words, s.start, s.end)
                ).strip(),
                "start": s.start, "end": s.end, "duration": s.duration, "score": s.score,
                # An explicit range was chosen precisely because the timings
                # here are unreliable, so comparing against them proves nothing.
                "explicit": s.beat in explicit_beats,
                # What the edit script said, when retiming replaced it.
                "was": moved.get(s.beat) if explicit else None,
            }
            for s in segments
        ]
        state.advance_to(Stage.GATE_CUTLIST)
        return True

    if stage is Stage.GATE_CUTLIST:
        show_cutlist_gate(state, project)
        return False

    if stage is Stage.CUTLIST_APPROVED:
        from cutlist import Segment
        segments = [
            Segment(e["beat"], e["text"], e["start"], e["end"], e["score"])
            for e in state.cutlist
        ]
        output = project / "cut.mp4"
        say(f"Cutting {len(segments)} segments -> {output.name} ...")
        cut(source, segments, output)
        state.cut_video = str(output)
        say(f"  {probe_duration(output):.1f}s")
        state.advance_to(Stage.CUT)
        return True

    if stage is Stage.CUT:
        state.cut_transcript = str(transcribe(Path(state.cut_video), project))
        state.advance_to(Stage.TRANSCRIBED_CUT)
        return True

    if stage is Stage.TRANSCRIBED_CUT:
        output = project / "graded.mp4"
        say(f"Grading -> {output.name} ...")
        grade(Path(state.cut_video), output, Grade())
        state.graded_video = str(output)
        state.advance_to(Stage.GRADED)
        return True

    if stage is Stage.GRADED:
        build_hook_shortlist(state, project, DEFAULT_HOOK_COUNT)
        state.advance_to(Stage.GATE_HOOK)
        return True

    if stage is Stage.GATE_HOOK:
        show_hook_gate(state, project)
        return False

    if stage is Stage.HOOK_CHOSEN:
        output = project / "final.mp4"
        # state.hook is what was picked at the gate; hook.txt is the escape
        # hatch for a hook written by hand, and takes over when nothing was.
        hook_text = "" if state.no_hook else (state.hook or load_hook(project))
        if hook_text:
            say(f'Hook: "{hook_text}"')
        else:
            say("No hook.txt in the project; rendering without a hook card.")
        state.cue_snapshot = build_cues(state, project)
        render_captions(
            Path(state.graded_video), Path(state.cut_transcript), output,
            hook_text, state.cue_snapshot,
        )
        state.captioned_video = str(output)
        state.final_video = str(output)
        say(f"  {probe_duration(output):.1f}s")
        # Not run automatically: Remotion re-bundles for every still, so
        # checking six moments costs more than the render did. Worth it after a
        # layout change, wasted after a re-cut.
        say(f"  check the layout:  python {me().replace('pipeline.py', 'verify.py')}"
            f" --project {project}")
        state.advance_to(Stage.DONE)
        return True

    return False


# Where a cue's images and videos live, and where they get staged to. Assets
# belong with the project that uses them; broll/public is a build directory.
ASSET_DIR = "assets"
STAGED = "overlay-assets"

# Which cue fields name a file, and whether the cue can survive without it.
ASSET_FIELDS = (("src", True), ("replyVideo", False))

# Where b-roll clips live, and what a filename means. A clip named after the
# phrase it illustrates needs no configuration at all: hemsidor.mp4 plays when
# "hemsidor" is said. The name IS the cue.
BROLL_DIR = "broll"
CLIP_SUFFIXES = (".mp4", ".mov", ".webm", ".m4v")


def inline_html(cue: dict, project: Path) -> list[str]:
    """Read a beat's markup into the cue.

    Inlined rather than fetched at render time, so a missing file is caught
    here with every other asset instead of by Remotion 404ing mid-render and
    cancelling the whole thing.
    """
    name = cue.pop("htmlFile", None)
    if not name:
        return []
    source = project / ASSET_DIR / name
    if not source.is_file():
        return [f"htmlFile: {source}"]
    cue["html"] = source.read_text(encoding="utf-8-sig")
    return []


def discover_broll(project: Path) -> list[dict]:
    """B-roll clips named after the phrase they illustrate.

    Placement does not need judgement, only a convention. A file called
    hemsidor.mp4 in <project>/assets/broll/ plays when "hemsidor" is said, and
    the cue matcher does the rest -- so gathering the footage is the whole job,
    and nothing has to be written down twice.
    """
    directory = project / ASSET_DIR / BROLL_DIR
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in CLIP_SUFFIXES:
            continue
        # "motion-design.mp4" and "motion design.mp4" both mean the same
        # phrase; the transcript decides which spelling it matched.
        phrase = path.stem.replace("-", " ").replace("_", " ").strip()
        if not phrase:
            continue
        found.append({"kind": "clip", "cue": phrase,
                      "src": f"{BROLL_DIR}/{path.name}", "hold": 0.3})
    return found


def stage_assets(cue: dict, project: Path) -> list[str]:
    """Copy a cue's files into broll/public, reporting whatever is missing.

    Remotion does not degrade on a missing asset -- a 404 on an <Img> fails the
    entire render, several thousand lines of stack trace deep. So the check
    happens here, where it can say which file, for which cue, and where to put
    it.
    """
    missing: list[str] = []
    # An iconRow names a file per slot rather than one for the cue, so the
    # holders to check are the cue itself and each of its children.
    holders = [cue] + [child for key in CHILD_KEYS
                       for child in (cue.get(key) or [])
                       if isinstance(child, dict)]
    for holder in holders:
        for field, required in ASSET_FIELDS:
            name = holder.get(field)
            if not name:
                continue
            source = project / ASSET_DIR / name
            if not source.is_file():
                missing.append(f"{field}: {source}")
                if not required:
                    # The chat still works without the video it sends back.
                    holder.pop(field, None)
                continue
            target = BROLL / "public" / STAGED / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            holder[field] = f"{STAGED}/{name}"
    return missing


def build_cues(state: PipelineState, project: Path) -> list[dict]:
    """Resolve <project>/overlays.json against the cut transcript.

    Reported at the checkpoint rather than silently applied: a cue that lands
    on the wrong word is a mistake nobody sees until playback, which is exactly
    the failure this pipeline keeps being bitten by.
    """
    if not state.overlays:
        say("Overlays: off (--no-overlays). Cut, grade and captions only.")
        return []

    sheet_path = project / "overlays.json"
    if not sheet_path.is_file():
        return []

    sheet = load_sheet(sheet_path)
    # A clip whose filename is already the phrase needs no sheet entry. An
    # explicit entry for the same phrase wins, so the convention is a default
    # rather than a rule.
    spoken = {str(entry.get("cue", "")).casefold() for entry in sheet}
    discovered = [c for c in discover_broll(project)
                  if c["cue"].casefold() not in spoken]
    if discovered:
        say(f"B-roll: {len(discovered)} clip(s) found by filename in "
            f"{project / ASSET_DIR / BROLL_DIR}")
        sheet = sheet + discovered

    words = read_words(Path(state.cut_transcript))
    duration = int(round(probe_duration(Path(state.graded_video)) * FPS))
    resolved, problems = resolve_cues(sheet, words, FPS, duration)

    kept: list[dict] = []
    absent: list[str] = []
    for cue in resolved:
        missing = inline_html(cue, project) + stage_assets(cue, project)
        # A file named but not there is required for the cue that names it in
        # `src`; anything still missing after staging drops the cue.
        if any(entry.startswith(("src:", "htmlFile:")) for entry in missing):
            absent.extend(f"{cue['kind']} -- {entry}" for entry in missing)
            continue
        absent.extend(f"{cue['kind']} -- {entry} (rendered without it)"
                      for entry in missing)
        kept.append(cue)

    say(f"Overlays: {len(kept)} of {len(sheet)} cues placed")
    for cue in kept:
        at = cue["enter"] / FPS
        leave = "end of clip" if cue.get("leave") is None else f"{cue['leave'] / FPS:.2f}s"
        say(f"  {cue['kind']:<11} {at:>6.2f}s -> {leave:<12} \"{cue.get('cue', '')}\"")
        # Every kind of child, from the one list of them. Spelling the kinds
        # out here left a chip row reporting as a single line with no chips
        # under it, so a chip whose phrase had gone was invisible in the very
        # report that exists to say so.
        for key in CHILD_KEYS:
            for child in cue.get(key) or []:
                label = (child.get("emoji") or child.get("label")
                         or child.get("text") or child.get("name") or "")
                say(f"      {label:<12} {child['enter'] / FPS:>6.2f}s  "
                    f"\"{child['cue']}\"")
    for problem in problems:
        say(f"  ! {problem.kind}: \"{problem.cue}\" -- {problem.reason}")
    for entry in absent:
        say(f"  ! no such file -- {entry}")
    if problems:
        # Prefixed, because an unprefixed imperative sentence in a terminal
        # reads as something to run -- and has been pasted back as one.
        say("  NOTE: a cue that did not match was dropped, not guessed at.")
        say("  NOTE: correct the phrase in overlays.json to what was said.")
    if absent:
        say(f"  NOTE: cue files are read from {project / ASSET_DIR}.")
        say("  NOTE: a cue whose file is absent was dropped so the render "
            "could finish.")
    return kept


def find_footage(name: str, limit: int = 5) -> list[Path]:
    """Where a video of this name actually is.

    A bare filename is the natural thing to type and the wrong thing to pass,
    since footage lives in videos/ and the command runs from the repository
    root. Saying only that the path does not exist leaves the operator to guess
    which of the two it was.
    """
    seen: list[Path] = []
    for directory in (ROOT / "videos", ROOT, ROOT / "projects"):
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.rglob(name)):
            if candidate.is_file() and candidate not in seen:
                seen.append(candidate)
            if len(seen) >= limit:
                return seen
    return seen


def install_edit_script(project: Path, source: Path | None) -> bool:
    """Copy an edit script into the project. Saves a shell-specific copy step."""
    if source is None:
        return True
    if not source.is_file():
        say(f"error: no such edit script: {source}")
        return False
    project.mkdir(parents=True, exist_ok=True)
    target = project / "edit-script.json"
    shutil.copyfile(source, target)
    say(f"Using {source} ({len(json.loads(target.read_text(encoding='utf-8')))} beats)")
    return True


def install_topic(project: Path, source: Path | None) -> bool:
    """Copy a topic file into the project, as --edit-script does for beats."""
    if source is None:
        return True
    if not source.is_file():
        say(f"error: no such topic file: {source}")
        return False
    project.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, project / "topic.txt")
    say(f"Using {source}")
    return True


def run(project: Path, max_gap: float | None = None,
        retime: bool | None = None, noise_db: float | None = None,
        overlays: bool | None = None) -> int:
    state = load(project)
    if state is None:
        say(f"No pipeline at {project}. Run: python {me()} init <video> --project {project}")
        return 2

    started_done = state.stage_enum is Stage.DONE

    if max_gap is not None and max_gap != state.max_gap:
        state.max_gap = max_gap
        # Re-deriving the cut list is the only way a new value takes effect,
        # and that holds after the run has finished as much as at the gate.
        if ORDER.index(state.stage_enum) >= ORDER.index(Stage.GATE_CUTLIST):
            say(f"max-gap changed to {max_gap}; rebuilding the cut list")
            state.advance_to(Stage.THROUGHLINE_APPROVED)

    if overlays is not None and overlays != state.overlays:
        state.overlays = overlays
        # Only the caption render reads the cue sheet, so that is as far back
        # as this has to rewind -- no re-cut, no re-grade, no re-transcribe.
        if ORDER.index(state.stage_enum) > ORDER.index(Stage.HOOK_CHOSEN):
            say(f"Overlays {'on' if overlays else 'off'}; re-rendering captions")
            state.advance_to(Stage.HOOK_CHOSEN)

    if noise_db is not None and noise_db != state.noise_db:
        state.noise_db = noise_db
        if ORDER.index(state.stage_enum) >= ORDER.index(Stage.GATE_CUTLIST):
            say(f"noise threshold changed to {noise_db:.0f}dB; rebuilding the "
                "cut list")
            state.advance_to(Stage.THROUGHLINE_APPROVED)

    if retime is not None and retime != state.retime:
        state.retime = retime
        # Same as max-gap: the setting only reaches the cut through a rebuild.
        if ORDER.index(state.stage_enum) >= ORDER.index(Stage.GATE_CUTLIST):
            say("retime changed; rebuilding the cut list")
            state.advance_to(Stage.THROUGHLINE_APPROVED)

    try:
        while step(state, project):
            save(project, state)
    except FFmpegMissing as exc:
        # A missing dependency is a setup problem, not a crash. Say what to do
        # and keep the state where it is so nothing has to be redone.
        save(project, state)
        say("")
        say(f"Cannot continue: {exc}")
        say("")
        say(f"Install it, then re-run:  python {me()} run --project {project}")
        return 2
    save(project, state)

    if state.stage_enum is Stage.DONE:
        if started_done:
            rule("Already finished -- nothing was rebuilt")
            say(f"  {state.final_video}")
            say("")
            say("This pipeline had already completed, so run had nothing to do.")
            say("A new transcript, changed settings or updated code will NOT be")
            say("picked up by run alone. To rebuild:")
            say("")
            say(f"  python {me()} redo --project {project}       # from the cut list")
            say(f"  python {me()} redo --project {project} --from hook")
            say(f"  python {me()} redo --project {project} --from transcribe")
            return 0
        rule("Done")
        say(f"  {state.final_video}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="start a pipeline for a video")
    p_init.add_argument("video", type=Path)
    p_init.add_argument("--project", type=Path, required=True)

    p_redo = sub.add_parser("redo", help="rewind so a stage runs again")
    p_redo.add_argument("--project", type=Path, required=True)
    p_redo.add_argument(
        "--from", dest="from_stage", default="cutlist",
        choices=["cutlist", "transcribe", "grade", "hook", "captions"],
        help="where to restart (default: cutlist). 'hook' matches a fresh "
             "shortlist and asks again; 'captions' keeps the hook already "
             "picked and only re-renders",
    )
    p_redo.add_argument("--max-gap", type=float, default=None)
    p_redo.add_argument("--edit-script", type=Path, default=None)
    p_redo.add_argument("--topic", type=Path, default=None)
    p_redo.add_argument("--noise", type=float, default=None)
    p_redo.add_argument("--overlays", dest="overlays", action="store_true",
                        default=None)
    p_redo.add_argument("--no-overlays", dest="overlays", action="store_false")
    p_redo.add_argument("--retime", dest="retime", action="store_true",
                        default=None)
    p_redo.add_argument("--no-retime", dest="retime", action="store_false")

    p_hook = sub.add_parser("hook", help="pick a hook from the shortlist by number")
    p_hook.add_argument(
        "--none", dest="no_hook", action="store_true",
        help="render with no hook card at all -- the gate offered this and "
             "had no way to do it",
    )
    p_hook.add_argument(
        "number", type=int, nargs="?", default=None,
        help="1-based, as printed at checkpoint 3. 0 means 'use hook.txt as "
             "written' -- for a hook you supplied yourself",
    )
    p_hook.add_argument("--project", type=Path, required=True)

    p_draft = sub.add_parser(
        "draft", help="write an edit script keeping everything that is not a blooper")
    p_draft.add_argument("--project", type=Path, required=True)

    p_direct = sub.add_parser(
        "direct", help="have Claude decide the shape of the video")
    p_direct.add_argument("--project", type=Path, required=True)
    p_direct.add_argument("--model", default=None,
                          help="model for the director call")
    p_direct.add_argument("--attempts", type=int, default=None)
    p_direct.add_argument(
        "--brief-only", action="store_true",
        help="write <project>/brief.md and stop, to direct it by hand")
    p_direct.add_argument("--topic", type=Path, default=None,
                          help="read what the video is about from this file "
                               "instead of <project>/topic.txt, and copy it in")

    p_captions = sub.add_parser(
        "captions", help="burn captions over videos that are already cut")
    p_captions.add_argument("video", type=Path, nargs="+")
    p_captions.add_argument(
        "--out-dir", type=Path,
        help="where the captioned files go (default: beside each input)")

    p_hooks = sub.add_parser("hooks", help="match a fresh hook shortlist and show it")
    p_hooks.add_argument("--project", type=Path, required=True)
    p_hooks.add_argument(
        "--topic", type=Path, default=None,
        help="read what the video is about from this file instead of "
             "<project>/topic.txt, and copy it in",
    )
    p_hooks.add_argument(
        "--count", type=int, default=DEFAULT_HOOK_COUNT,
        help=f"how many to offer (default {DEFAULT_HOOK_COUNT})",
    )

    for name, helptext in [("run", "advance to the next gate"),
                           ("status", "show current stage"),
                           ("approve", "approve the current gate")]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--project", type=Path, required=True)
        p.add_argument(
            "--edit-script", type=Path, default=None,
            help="read the beats from this file instead of "
                 "<project>/edit-script.json, and copy it in",
        )
        p.add_argument("--topic", type=Path, default=None,
                       help="read what the video is about from this file "
                            "instead of <project>/topic.txt, and copy it in")
        p.add_argument("--overlays", dest="overlays", action="store_true",
                       default=None, help="run the overlay layer (the default)")
        p.add_argument("--no-overlays", dest="overlays", action="store_false",
                       help="ship the cut, grade and captions alone, keeping "
                            "the cue sheet for later")
        p.add_argument(
            "--noise", type=float, default=None,
            help="silence threshold for --retime, in dB. Find this "
                 "recording's with: edges.py <raw> --script <script> --sweep",
        )
        p.add_argument(
            "--retime", dest="retime", action="store_true", default=None,
            help="re-measure explicit ranges around the words they cover, "
                 "using the current head and tail, instead of taking the "
                 "numbers as written",
        )
        p.add_argument(
            "--no-retime", dest="retime", action="store_false",
            help="take explicit ranges exactly as written (the default)",
        )
        p.add_argument(
            "--max-gap", type=float, default=None,
            help="cut pauses longer than this many seconds; 0 disables silence "
                 "removal entirely (default 0.30). Raise it to protect a "
                 "deliberate pause",
        )

    args = parser.parse_args()

    if args.command == "init":
        args.max_gap = None
        args.topic = None
        args.retime = None
        args.noise = None
        args.overlays = None
        if not args.video.is_file():
            say(f"error: no such file: {args.video}")
            found = find_footage(args.video.name)
            if found:
                say("Did you mean:")
                for candidate in found:
                    say(f"  {candidate}")
            return 2
        save(args.project, PipelineState(source=str(args.video.resolve())))
        say(f"Initialised {args.project} for {args.video.name}")
        return run(args.project)

    if args.command == "status":
        state = load(args.project)
        if state is None:
            say(f"No pipeline at {args.project}")
            return 2
        say(f"stage   : {state.stage}")
        say(f"source  : {state.source}")
        # The settings a rebuild will use. They live in pipeline.json and are
        # easy to forget a week later, which is the whole reason to print them.
        say(f"silence : pauses over {state.max_gap}s removed"
            if state.max_gap > 0 else "silence : removal disabled")
        if state.retime:
            say(f"retime  : on, measured against the audio at "
                f"{state.noise_db:.0f}dB")
        else:
            say("retime  : off -- stated ranges are taken as written")
        say(f"room    : {DEFAULT_HEAD}s before a cut, {DEFAULT_TAIL}s after, "
            f"{DEFAULT_END_TAIL}s at the very end")
        say(f"overlays: {'on' if state.overlays else 'off'}")
        if state.hook:
            say(f"hook    : {state.hook}")
        if state.is_at_gate():
            say("")
            say("waiting at a checkpoint -- run 'run' to see what it needs")
        return 0

    if args.command == "approve":
        if not install_edit_script(args.project, args.edit_script):
            return 2
        if not install_topic(args.project, args.topic):
            return 2
        state = load(args.project)
        if state is None:
            say(f"No pipeline at {args.project}")
            return 2
        if not state.is_at_gate():
            say(f"Not at a checkpoint (stage: {state.stage}). Nothing to approve.")
            return 1
        if state.stage_enum is Stage.GATE_HOOK:
            # The hook gate is a choice, not a yes/no. Approving it without
            # naming a number takes the top match rather than guessing.
            say("The hook checkpoint expects a number.")
            say(f"  python {me()} hook <1-{len(state.hook_candidates)}> "
                f"--project {args.project}")
            return 1
        following = {
            Stage.GATE_THROUGHLINE: Stage.THROUGHLINE_APPROVED,
            Stage.GATE_CUTLIST: Stage.CUTLIST_APPROVED,
        }[state.stage_enum]
        state.advance_to(following)
        save(args.project, state)
        say(f"Approved. Now at {state.stage}.")
        return run(args.project, args.max_gap, args.retime, args.noise,
                   args.overlays)

    if args.command == "redo":
        state = load(args.project)
        if state is None:
            say(f"No pipeline at {args.project}")
            return 2
        if not install_edit_script(args.project, args.edit_script):
            return 2
        if not install_topic(args.project, args.topic):
            return 2
        target = {
            "transcribe": Stage.NEW,
            "cutlist": Stage.THROUGHLINE_APPROVED,
            "grade": Stage.TRANSCRIBED_CUT,
            "hook": Stage.GRADED,
            "captions": Stage.HOOK_CHOSEN,
        }[args.from_stage]
        state.advance_to(target)
        save(args.project, state)
        say(f"Rewound to {target.value}; rebuilding.")
        return run(args.project, args.max_gap, args.retime, args.noise,
                   args.overlays)

    if args.command == "draft":
        state = load(args.project)
        if state is None:
            say(f"No pipeline at {args.project}")
            return 2
        if not state.raw_transcript:
            say("Nothing transcribed yet.")
            return 2
        return draft_edit_script(state, args.project)

    if args.command == "direct":
        if not install_topic(args.project, args.topic):
            return 2
        # Delegated rather than reimplemented: director.py is runnable on its
        # own, and having two entry points that drift is how the cue-child
        # list came to be wrong in one place and right in the other.
        forwarded = [sys.executable, str(Path(__file__).parent / "director.py"),
                     "--project", str(args.project)]
        if args.model:
            forwarded += ["--model", args.model]
        if args.attempts:
            forwarded += ["--attempts", str(args.attempts)]
        if args.brief_only:
            forwarded += ["--brief-only"]
        return subprocess.run(forwarded).returncode

    if args.command == "captions":
        return caption_only(args.video, args.out_dir)

    if args.command == "hooks":
        if not install_topic(args.project, args.topic):
            return 2
        state = load(args.project)
        if state is None:
            say(f"No pipeline at {args.project}")
            return 2
        build_hook_shortlist(state, args.project, args.count)
        save(args.project, state)
        show_hook_gate(state, args.project)
        return 0

    if args.command == "hook":
        state = load(args.project)
        if state is None:
            say(f"No pipeline at {args.project}")
            return 2
        if args.no_hook:
            state.hook, state.no_hook = "", True
            say("No hook card. Rendering the cut, the grade and the captions.")
            state.advance_to(Stage.HOOK_CHOSEN)
            save(args.project, state)
            return run(args.project)
        if args.number is None:
            say(f"Pick 1-{len(state.hook_candidates)}, 0 for {args.project / 'hook.txt'}"
                ", or --none for no card.")
            return 2
        if args.number == 0:
            chosen = load_hook(args.project)
            if not chosen:
                say(f"hook 0 uses {args.project / 'hook.txt'}, but it is empty "
                    "or absent.")
                return 2
        else:
            if not 1 <= args.number <= len(state.hook_candidates):
                say(f"Pick 1-{len(state.hook_candidates)}, or 0 to use hook.txt "
                    "as written.")
                say(f"Nothing shortlisted yet?  python {me()} hooks "
                    f"--project {args.project}")
                return 2
            chosen = state.hook_candidates[args.number - 1]["sv"]
            # Written out as well as stored, so the choice survives a rebuild
            # from an earlier stage and can be edited by hand afterwards.
            (args.project / "hook.txt").write_text(
                chosen + "\n", encoding="utf-8"
            )
        state.hook = chosen
        # Also the right stage when the pipeline had already finished: a new
        # hook means the captions layer is laid down again, and nothing before
        # it needs to be.
        state.advance_to(Stage.HOOK_CHOSEN)
        save(args.project, state)
        say(f'Hook: "{chosen}"')
        return run(args.project)

    if args.command == "run":
        if not install_edit_script(args.project, args.edit_script):
            return 2
        if not install_topic(args.project, args.topic):
            return 2
        return run(args.project, args.max_gap, args.retime, args.noise,
                   args.overlays)

    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BadJSON as exc:
        # A hand-edited file with a missing comma is an ordinary mistake, not a
        # crash. It was reported as six frames of interpreter internals.
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except BrokenPipeError:
        sys.exit(0)
