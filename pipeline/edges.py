#!/usr/bin/env python3
"""Find where speech really starts and stops, from the audio.

    python edges.py raw.mp4 42.28-49.24
    python edges.py raw.mp4 --script pipeline/edit-scripts/clip.json
    python edges.py raw.mp4 42.28-49.24 --noise -40
    python edges.py raw.mp4 66.43-77.46 --gaps --noise -36

The source is the RAW recording -- the same file the edit script's times refer
to, not a cut of it. Nothing is modified; this only reports.

Word timestamps are not a clock. Whisper reports them by aligning the decoded
text against the audio, and with `vad_filter` on -- which is how this pipeline
transcribes -- the silence is stripped before decoding and the timestamps are
mapped back afterwards. That mapping accumulates error in proportion to how
much silence was removed, so on a take-heavy recording the whole alignment
slides progressively EARLY as it goes on.

Measured on the recording this was built for: no detectable error at 14s,
about 0.45s by 49s, about 0.55s by 81s. Cutting at `word_end + 0.15` therefore
landed inside the final word -- "video" came out as "vi" -- while the same
0.15s tail was clean on a word thirty seconds earlier. No tail value fixes
that. A larger one only hides it until the drift catches up again.

The audio has no such problem. `silencedetect` finds the boundary between
speech and room tone directly, which is the thing a cut point actually wants.
This measures that boundary near a stated cut and reports how far off the
transcript was.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ffmpeg_ops import FFmpegMissing  # noqa: E402
from takes import Run, detect_silences, speech_runs  # noqa: E402

# How far past a stated cut to look for the real edge. Wide enough to cover the
# drift measured above with room to spare; narrow enough that the next take,
# which is a pause away, cannot be swept in.
DEFAULT_SEARCH = 1.2

# A measurement further out than this is not drift, it is the wrong sound --
# a neighbouring take, or a threshold that is reading room tone as speech.
# Report it rather than trusting it.
DEFAULT_MAX_DRIFT = 0.8

# Quieter than take separation uses, and quieter than the first attempt at this.
#
# -35dB was set by analogy with take separation and it is too deaf for an edge.
# A speaker's voice declines through a sentence: the final syllable can sit
# 10-20dB below the middle of the phrase, and at -35dB the tail of "content"
# read as silence -- the measurement reproduced the clipped word instead of
# correcting it. -45dB still sits well above room tone on a decent mic while
# keeping a sentence-final syllable.
#
# Recordings differ. `--sweep` shows where the answer stops moving, and
# `--noise` sets it, on this tool and on the pipeline.
DEFAULT_NOISE_DB = -45.0

# Long enough not to trip on the closure of a plosive -- the silent beat inside
# the /t/ of "content" is 50-80ms and must not read as the end of the word.
DEFAULT_MIN_SILENCE = 0.14

# Short enough to keep a one-syllable word at the edge of the range.
DEFAULT_MIN_RUN = 0.12


@dataclass
class Edges:
    """Where speech actually runs, against where the transcript said it did."""

    start: float           # measured speech onset
    end: float             # measured speech offset
    stated_start: float
    stated_end: float
    measured: bool         # False when the audio could not answer

    # Tracked per side. A start that reaches back into the previous take says
    # nothing about whether the end is sound, and reporting one clamp for both
    # made a usable threshold look unusable.
    start_clamped: bool = False
    end_clamped: bool = False

    @property
    def clamped(self) -> bool:
        return self.start_clamped or self.end_clamped

    @property
    def start_drift(self) -> float:
        return round(self.start - self.stated_start, 3)

    @property
    def end_drift(self) -> float:
        return round(self.end - self.stated_end, 3)


def edges_from_runs(
    runs: list[Run],
    start: float,
    end: float,
    max_drift: float = DEFAULT_MAX_DRIFT,
) -> Edges:
    """Outer bounds of the speech overlapping a stated range.

    Split out from the ffmpeg call so the decision is testable without audio.
    """
    inside = [r for r in runs if r.end > start and r.start < end]
    if not inside:
        # Silence where speech was expected. The threshold is probably wrong,
        # and guessing would be worse than leaving the stated range alone.
        return Edges(start, end, start, end, measured=False)

    measured_start, measured_end = inside[0].start, inside[-1].end
    return Edges(
        start=round(max(measured_start, start - max_drift), 3),
        end=round(min(measured_end, end + max_drift), 3),
        stated_start=start,
        stated_end=end,
        measured=True,
        start_clamped=measured_start < start - max_drift,
        end_clamped=measured_end > end + max_drift,
    )


# A sound at the edge of a range, followed by a pause more than twice its own
# length, is not part of what follows -- it is a breath, a click, a chair. Both
# tests have to fail before it is dropped: a genuine short first word ("Men",
# a quarter second, then a beat before the sentence) has a pause of about its
# own length after it, not several times it.
BLIP_MAX = 0.35
BLIP_GAP_RATIO = 2.0


def drop_blips(runs: list[Run]) -> list[Run]:
    """Runs at either edge that are too short, and too alone, to be speech."""
    kept = list(runs)
    while len(kept) > 1:
        first, next_one = kept[0], kept[1]
        gap = next_one.start - first.end
        if first.duration <= BLIP_MAX and gap >= first.duration * BLIP_GAP_RATIO:
            kept.pop(0)
            continue
        break
    while len(kept) > 1:
        last, previous = kept[-1], kept[-2]
        gap = last.start - previous.end
        if last.duration <= BLIP_MAX and gap >= last.duration * BLIP_GAP_RATIO:
            kept.pop()
            continue
        break
    return kept


# A silence at the head or tail of a kept range worth taking out. Below this
# it is the head and tail the cut is supposed to have.
DEFAULT_SLACK = 0.12

# Edge silence small enough that the threshold has told us something real.
# Below this the range looks unbroken, which at a low threshold means the
# measurement is hearing the room rather than that the range is tight.
SILENT_EDGE = 0.05


def trim_to_speech(
    source: Path,
    start: float,
    end: float,
    noise_db: float = DEFAULT_NOISE_DB,
    min_silence: float = DEFAULT_MIN_SILENCE,
    min_run: float = DEFAULT_MIN_RUN,
) -> tuple[float, float] | None:
    """Where speech actually begins and ends INSIDE a range already chosen.

    Everything else here measures around a stated range and has to be stopped
    from wandering into a neighbouring take -- hence the search window and the
    drift clamp. This looks only within the range, where there is nothing to
    wander into: moving the start later or the end earlier can only ever remove
    something the cut already contains.

    That asymmetry is the whole point. `measure` takes the earliest speech run
    overlapping the range, so a breath or a chair creak before the sentence
    counts as its onset, and if the breath is within the drift budget nothing
    flags it -- the cut opens on the breath and the words arrive a second
    later. Trimming inwards afterwards cannot make that mistake, because it
    cannot reach anything the operator did not already choose.

    Returns None when the range holds no detectable speech at all, which is a
    threshold problem and not something to guess at.
    """
    # Climbed for the same reason measuring is: at a threshold below the room
    # there is no silence to find ANYWHERE, so the range comes back as one
    # unbroken run and nothing is trimmed. That is not "no silence here" -- it
    # is "this threshold cannot tell". Stop at the most sensitive threshold
    # that can, and if none can, leave the range alone.
    # Each edge gets the most sensitive threshold that can see it, separately.
    # Taking the first threshold that showed anything trimmed the head at -33dB
    # and left the tail untouched, because the tail's silence was not yet
    # detectable there.
    fallback: tuple[float, float] | None = None
    speaks_at: float | None = None
    stops_at: float | None = None
    for db in [d for d in LADDER if d >= noise_db] or [noise_db]:
        silences = detect_silences(Path(source), start, end, db, min_silence)
        runs = drop_blips(speech_runs(start, end, silences, min_run))
        if not runs:
            # Deaf enough that the whole range reads as silence. Climbing
            # further can only be worse.
            break
        first, last = runs[0].start, runs[-1].end
        if fallback is None:
            fallback = (first, last)
        if speaks_at is None and first - start > SILENT_EDGE:
            speaks_at = first
        if stops_at is None and end - last > SILENT_EDGE:
            stops_at = last
        if speaks_at is not None and stops_at is not None:
            break
    if fallback is None:
        return None
    return (speaks_at if speaks_at is not None else fallback[0],
            stops_at if stops_at is not None else fallback[1])


def measure(
    source: Path,
    start: float,
    end: float,
    search: float = DEFAULT_SEARCH,
    noise_db: float = DEFAULT_NOISE_DB,
    min_silence: float = DEFAULT_MIN_SILENCE,
    min_run: float = DEFAULT_MIN_RUN,
    max_drift: float = DEFAULT_MAX_DRIFT,
) -> Edges:
    """Measure the speech edges around a stated range, from the audio."""
    window_start = max(0.0, start - search)
    window_end = end + search
    silences = detect_silences(
        Path(source), window_start, window_end, noise_db, min_silence
    )
    runs = speech_runs(window_start, window_end, silences, min_run)
    return edges_from_runs(runs, start, end, max_drift)


# Climbed, most sensitive first, when a measurement reads room tone as speech.
# Stopping at the first threshold that answers confidently is the sweep's own
# advice -- "the most sensitive one before the numbers start climbing" -- done
# per beat instead of by hand.
LADDER = [-45.0, -42.0, -39.0, -36.0, -33.0, -30.0, -27.0]


def measure_best(
    source: Path,
    start: float,
    end: float,
    floor: float = DEFAULT_NOISE_DB,
    **kwargs,
) -> tuple[Edges, float]:
    """Measure at the most sensitive threshold that is not hearing the room.

    One number cannot be right for every recording, and the operator should not
    have to find it. A measurement that clamps has run past what drift
    explains: either a discarded take is inside the search window, or -- far
    more often -- the threshold is low enough that room tone counts as speech,
    so the "speech run" never ends and the edge lands wherever the clamp puts
    it. Every beat that came back with a silence in front of it in
    aieditoradvancing reported exactly that.

    So: start at the recording's stated floor and climb until the answer stops
    clamping. The first threshold that answers confidently is the one just
    above this room's noise. Returns the measurement and the threshold it took,
    so the checkpoint can say when it had to climb.
    """
    # Climbing means a LESS sensitive threshold, which is a higher number:
    # -45dB counts quieter sound as speech than -30dB does.
    ladder = [db for db in LADDER if db >= floor] or [floor]
    fallback: tuple[Edges, float] | None = None
    for noise_db in ladder:
        found = measure(source, start, end, noise_db=noise_db, **kwargs)
        if not found.measured:
            continue
        if fallback is None:
            fallback = (found, noise_db)
        if not found.clamped:
            return found, noise_db
    if fallback is not None:
        return fallback
    return measure(source, start, end, noise_db=ladder[0], **kwargs), ladder[0]


SWEEP_DB = [-30.0, -35.0, -40.0, -45.0, -50.0, -55.0, -60.0]


def report_sweep(script: Path, source: Path, args) -> int:
    """Where does the measured edge stop moving as the threshold drops?

    Every recording has its own noise floor, and one number cannot be right for
    all of them. Too deaf and a quiet sentence-final syllable reads as silence,
    which clips the word. Too sensitive and room tone reads as speech, which
    runs the cut into the next take -- shown here as `clamp`.

    The value to use is the most sensitive one before the numbers start
    climbing without end: that is the floor of the room, and the edge below it
    is the real one.
    """
    import json

    beats = [b for b in json.loads(script.read_text(encoding="utf-8"))
             if "start" in b and "end" in b]
    if not beats:
        print(f"{script} states no explicit ranges -- nothing to measure.")
        return 1

    print("Measured speech END at each threshold. 'clamp' means the measurement")
    print("ran past what drift explains -- room tone being read as speech.")
    print()
    print(f"{'beat':<12}{'stated':>9}" + "".join(f"{db:>10.0f}" for db in SWEEP_DB))
    for beat in beats:
        start, end = float(beat["start"]), float(beat["end"])
        cells = []
        for db in SWEEP_DB:
            found = measure(source, start, end, search=args.search,
                            noise_db=db, min_silence=args.min_silence)
            if not found.measured:
                cells.append(f"{'--':>9}")
            elif found.end_clamped:
                cells.append(f"{'clamp':>9}")
            else:
                # A start clamp is marked but does not hide the end: the two
                # sides fail independently, and usually the start is the one
                # that reaches into the take before it.
                cells.append(f"{found.end:>9.2f}" + ("<" if found.start_clamped else " "))
        print(f"{beat['beat']:<12}{end:>9.2f}" + "".join(cells))
    print()
    print("'clamp' = the END ran past what drift explains: room tone read as")
    print("speech. '<' = the START did, which says nothing about the end.")
    print()
    print("Take the most sensitive column that has not started to climb, then")
    print("  python pipeline\\pipeline.py redo --project <project> --retime "
          "--noise <db>")
    return 0


def report_script(script: Path, source: Path, head: float, tail: float, args) -> int:
    """Measure every stated range in an edit script, without rebuilding.

    The question this answers before a rebuild: does measuring move the cuts
    that already sounded right? A beat whose drift is near zero was fine on the
    transcript's clock and will stay where it is.
    """
    import json

    if not script.is_file():
        print(f"error: no such file: {script}", file=sys.stderr)
        return 2
    beats = [b for b in json.loads(script.read_text(encoding="utf-8"))
             if "start" in b and "end" in b]
    if not beats:
        print(f"{script} states no explicit ranges -- nothing to measure.")
        return 1

    from sentences import DEFAULT_END_TAIL
    print(f"{'beat':<12}{'stated':>17}{'speech':>17}{'drift':>15}{'cut':>17}")
    old_total = new_total = 0.0
    for index, beat in enumerate(beats):
        start, end = float(beat["start"]), float(beat["end"])
        this_tail = DEFAULT_END_TAIL if index == len(beats) - 1 else tail
        found = measure(source, start, end, search=args.search,
                        noise_db=args.noise, min_silence=args.min_silence)
        old_total += end - start
        if not found.measured:
            print(f"{beat['beat']:<12}{start:>8.2f} ->{end:>7.2f}"
                  f"{'no speech found':>17}")
            new_total += end - start
            continue
        cut_start, cut_end = found.start - head, found.end + this_tail
        new_total += cut_end - cut_start
        flag = ("  start!" if found.start_clamped else "") + \
               ("  end!" if found.end_clamped else "")
        print(f"{beat['beat']:<12}{start:>8.2f} ->{end:>7.2f}"
              f"{found.start:>9.2f} ->{found.end:>7.2f}"
              f"{found.start_drift:>+8.2f}{found.end_drift:>+7.2f}"
              f"{cut_start:>9.2f} ->{cut_end:>7.2f}{flag}")
    print()
    print(f"total {old_total:.1f}s stated, {new_total:.1f}s measured")
    print()
    print("A drift near zero means that beat was already right and will barely")
    print("move. 'start!' or 'end!' marks that side running further out than")
    print("drift explains -- another take in the window, or room tone read as")
    print("speech. The two sides fail independently.")
    return 0


def report_gaps(source: Path, start: float, end: float,
                noise_db: float, min_silence: float) -> int:
    """The silences inside a range, and the cut each one would make.

    Everything else here measures the EDGES of a take. This looks in the
    middle, for the case where one continuous range holds two sentences with a
    pause between them and the pause is the thing to remove. The pause is often
    quieter than the room but not silent, so the threshold usually has to come
    up from the default before it shows.
    """
    found = detect_silences(Path(source), start, end, noise_db, min_silence)
    if not found:
        print(f"No silence of {min_silence}s or more inside "
              f"{start:.2f}-{end:.2f} at {noise_db:.0f}dB.")
        print("A pause quieter than the room is still louder than this "
              "threshold: try --noise -36, then -30.")
        return 1

    print(f"{len(found)} gap(s) inside {start:.2f}-{end:.2f} "
          f"at {noise_db:.0f}dB:\n")
    for began, ended in found:
        print(f"  silence  {began:>8.2f} -> {ended:>8.2f}   ({ended - began:.2f}s)")
    print("\nSplitting on the first of these gives two ranges:")
    first, second = found[0]
    print(f"  {start:.2f} -> {first:.2f}")
    print(f"  {second:.2f} -> {end:.2f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", type=Path,
                        help="the RAW recording the edit script's times refer to")
    parser.add_argument("range", nargs="?", default=None,
                        help="START-END in seconds, as an edit script states it")
    parser.add_argument("--script", type=Path, default=None,
                        help="measure every explicit range in an edit script "
                             "instead of one range")
    parser.add_argument("--sweep", action="store_true",
                        help="with --script: measure at a range of thresholds, "
                             "to find where the answer stops moving")
    parser.add_argument("--head", type=float, default=None,
                        help="room before the speech (default: the pipeline's)")
    parser.add_argument("--tail", type=float, default=None,
                        help="room after the speech (default: the pipeline's)")
    parser.add_argument("--search", type=float, default=DEFAULT_SEARCH)
    parser.add_argument("--noise", type=float, default=DEFAULT_NOISE_DB,
                        help=f"silence threshold in dB (default {DEFAULT_NOISE_DB:.0f})")
    parser.add_argument("--min-silence", type=float, default=DEFAULT_MIN_SILENCE)
    parser.add_argument("--gaps", action="store_true",
                        help="list the silences INSIDE the range, for splitting "
                             "one long take into two beats")
    args = parser.parse_args()

    from sentences import DEFAULT_HEAD, DEFAULT_TAIL
    head = DEFAULT_HEAD if args.head is None else args.head
    tail = DEFAULT_TAIL if args.tail is None else args.tail

    if not args.source.is_file():
        print(f"error: no such file: {args.source}", file=sys.stderr)
        return 2

    if args.script is not None:
        if not args.script.is_file():
            print(f"error: no such file: {args.script}", file=sys.stderr)
            return 2
        if args.sweep:
            return report_sweep(args.script, args.source, args)
        return report_script(args.script, args.source, head, tail, args)
    if args.range is None:
        print("error: give a START-END range, or --script", file=sys.stderr)
        return 2
    first, _, second = args.range.partition("-")
    try:
        start, end = float(first), float(second)
    except ValueError:
        print(f"error: expected START-END, got {args.range!r}", file=sys.stderr)
        return 2

    if args.gaps:
        return report_gaps(args.source, start, end, args.noise, args.min_silence)

    try:
        edges = measure(args.source, start, end, search=args.search,
                        noise_db=args.noise, min_silence=args.min_silence)
    except FFmpegMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not edges.measured:
        print(f"No speech found in {start:.2f}-{end:.2f} at {args.noise}dB.")
        print("Try --noise -40, or check the range is right.")
        return 1

    print(f"stated   {start:>8.2f} -> {end:>8.2f}")
    print(f"speech   {edges.start:>8.2f} -> {edges.end:>8.2f}"
          f"   ({edges.start_drift:+.2f} / {edges.end_drift:+.2f})")
    print(f"cut      {edges.start - head:>8.2f} -> {edges.end + tail:>8.2f}"
          f"   (head {head}s, tail {tail}s)")
    if edges.clamped:
        print()
        print("The audio disagrees by more than the drift this corrects, so the")
        print("measurement was pulled back. Either the threshold is reading room")
        print("tone as speech, or another take is inside the search window.")
    print()
    print("Confirm by ear:")
    print(f"  python pipeline\\preview.py \"{args.source}\" "
          f"{edges.start - head:.2f}-{edges.end + tail:.2f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
