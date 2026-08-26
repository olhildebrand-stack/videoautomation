#!/usr/bin/env python3
"""Find the separate takes inside a stretch of source, from the audio itself.

    python takes.py video.mp4 0.18-14.42
    python takes.py video.mp4 0.18-14.42 --expect 6

Where a line was recorded several times, Whisper's word alignment smears
across the attempts and cannot say where one ends and the next begins. The
audio can: retakes are separated by the pause the speaker leaves before
starting again. This reports the speech runs in a range, so the good take --
almost always the last one long enough to hold the line -- can be identified
without trusting the transcript at all.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ffmpeg_ops import FFmpegMissing, binary  # noqa: E402

SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


@dataclass
class Run:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


def detect_silences(
    source: Path, start: float, end: float, noise_db: float, min_silence: float
) -> list[tuple[float, float]]:
    """Silences within the range, as absolute times in the source."""
    result = subprocess.run(
        [
            binary("ffmpeg"), "-v", "info", "-nostats",
            "-ss", f"{start}", "-to", f"{end}", "-i", str(source),
            # Audio only. Decoding the picture to measure silence is the bulk
            # of the cost and none of the answer.
            "-vn",
            "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    stderr = result.stderr

    silences: list[tuple[float, float]] = []
    pending: float | None = None
    for line in stderr.splitlines():
        found_start = SILENCE_START.search(line)
        if found_start:
            pending = float(found_start.group(1))
        found_end = SILENCE_END.search(line)
        if found_end and pending is not None:
            silences.append((start + pending, start + float(found_end.group(1))))
            pending = None
    if pending is not None:
        silences.append((start + pending, end))
    return silences


def speech_runs(
    start: float, end: float, silences: list[tuple[float, float]], min_run: float
) -> list[Run]:
    """The complement of the silences: where someone is actually talking."""
    runs: list[Run] = []
    cursor = start
    for silence_start, silence_end in silences:
        if silence_start - cursor >= min_run:
            runs.append(Run(round(cursor, 3), round(silence_start, 3)))
        cursor = max(cursor, silence_end)
    if end - cursor >= min_run:
        runs.append(Run(round(cursor, 3), round(end, 3)))
    return runs


def pick_take(runs: list[Run], expect: float | None) -> Run | None:
    """The good take: the last run long enough to hold the line.

    Last, because a speaker who restarts does so because the previous attempt
    failed. Long enough, because a false start is by definition shorter than
    the line it abandons.
    """
    if not runs:
        return None
    if expect is None:
        return max(runs, key=lambda r: r.duration)
    threshold = expect * 0.7
    candidates = [r for r in runs if r.duration >= threshold]
    return candidates[-1] if candidates else max(runs, key=lambda r: r.duration)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("range", help="START-END in seconds")
    parser.add_argument("--expect", type=float, default=None,
                        help="roughly how long the line takes to say")
    parser.add_argument("--noise", type=float, default=-30.0,
                        help="silence threshold in dB (default -30)")
    parser.add_argument("--min-silence", type=float, default=0.35,
                        help="shortest pause that separates two takes")
    parser.add_argument("--min-run", type=float, default=0.4,
                        help="ignore speech runs shorter than this")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"error: no such file: {args.source}", file=sys.stderr)
        return 2
    start, _, end_text = args.range.partition("-")
    try:
        start, end = float(start), float(end_text)
    except ValueError:
        print(f"error: expected START-END, got {args.range!r}", file=sys.stderr)
        return 2

    try:
        silences = detect_silences(args.source, start, end, args.noise,
                                   args.min_silence)
    except FFmpegMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    runs = speech_runs(start, end, silences, args.min_run)
    if not runs:
        print("No speech runs found. Try --noise -40 or --min-silence 0.25.")
        return 1

    print(f"{len(runs)} speech run(s) in {start:.2f}-{end:.2f}:\n")
    chosen = pick_take(runs, args.expect)
    for index, run in enumerate(runs, 1):
        mark = " <-- likely the good take" if run is chosen else ""
        print(f"  {index}. {run.start:>7.2f} -> {run.end:>7.2f}  "
              f"({run.duration:>5.2f}s){mark}")

    if chosen:
        print()
        print("edit-script entry:")
        print(f'  {{"beat": "X", "start": {chosen.start}, "end": {chosen.end}}}')
        print()
        print("Confirm by ear first:")
        print(f"  python pipeline\\preview.py \"{args.source}\" "
              f"{chosen.start}-{chosen.end}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
