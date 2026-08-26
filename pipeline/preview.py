#!/usr/bin/env python3
"""Export ranges from a source so they can be auditioned.

    python preview.py video.mp4 0.18-14.42 22.8-30.92
    python preview.py --project projects/ep01 --smeared

Where the transcript's alignment is weak, the split is a guess and the only
way to settle it is to listen. This writes each range to its own file so the
question becomes "which of these sounds right" rather than scrubbing a
timeline for a boundary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ffmpeg_ops import FFmpegMissing, binary, run  # noqa: E402


def parse_range(text: str) -> tuple[float, float]:
    if "-" not in text:
        raise ValueError(f"expected START-END, got {text!r}")
    start, _, end = text.partition("-")
    return float(start), float(end)


def export(source: Path, start: float, end: float, out: Path, audio_only: bool) -> None:
    args = [
        "ffmpeg", "-v", "error", "-y",
        # -ss before -i seeks fast; re-encoding keeps it frame-accurate.
        "-ss", f"{start}", "-to", f"{end}", "-i", str(source),
    ]
    if audio_only:
        args += ["-vn", "-c:a", "libmp3lame", "-q:a", "4"]
    else:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                 "-pix_fmt", "yuv420p", "-c:a", "aac"]
    args.append(str(out))
    run(args)


def smeared(project: Path) -> tuple[Path, list[tuple[float, float, str]]]:
    """Every continuous run of speech where the transcript cannot be trusted.

    The brief already says which stretches those are and what the audio says
    is in them. Turning that into "which file do I play" was the operator
    reading two tables and typing timestamps by hand, which is the step this
    removes: one command, one file per run, named by when it happens.
    """
    import json

    import brief as brief_module
    from brief import RUN_MIN, RUN_MIN_SILENCE, RUN_NOISE_DB
    from takes import detect_silences, speech_runs

    state = json.loads((project / "pipeline.json").read_text(encoding="utf-8"))
    source = Path(state["source"])
    words = brief_module.read_words(Path(state["raw_transcript"]))
    found = brief_module.take_list(words)
    ends = words[-1].end if words else 0.0

    runs: list[tuple[float, float, str]] = []
    for start, end in brief_module.smeared_windows(found, ends):
        silences = detect_silences(
            source, start, end, RUN_NOISE_DB, RUN_MIN_SILENCE)
        for run_found in speech_runs(start, end, silences, RUN_MIN):
            # What the transcript CLAIMS is in this run, so the two can be
            # compared by ear rather than by squinting at two tables.
            said = " ".join(
                take.text for take in found
                if take.start < run_found.end and take.end > run_found.start)
            runs.append((run_found.start, run_found.end, said))
    return source, runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("ranges", nargs="*", help="START-END in seconds")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument(
        "--smeared", action="store_true",
        help="every run of speech the transcript could not place, from the "
             "project's own source; needs --project")
    parser.add_argument("--out", type=Path, default=Path("previews"))
    parser.add_argument("--video", action="store_true",
                        help="export video too (audio only by default)")
    args = parser.parse_args()

    claimed: dict[tuple[float, float], str] = {}
    if args.smeared:
        if not args.project or not (args.project / "pipeline.json").is_file():
            print("error: --smeared needs --project <project>", file=sys.stderr)
            return 2
        args.source, runs = smeared(args.project)
        if not runs:
            print("Nothing smeared in this recording -- the transcript places "
                  "every word it wrote.")
            return 0
        args.ranges = [f"{start}-{end}" for start, end, _ in runs]
        claimed = {(start, end): said for start, end, said in runs}

    if not args.source or not args.source.is_file():
        print(f"error: no such file: {args.source}", file=sys.stderr)
        return 2
    if not args.ranges:
        print("error: give at least one START-END range", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "mp4" if args.video else "mp3"

    try:
        binary("ffmpeg")
    except FFmpegMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for text in args.ranges:
        try:
            start, end = parse_range(text)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        out = args.out / f"{start:07.2f}-{end:07.2f}.{suffix}"
        export(args.source, start, end, out, not args.video)
        print(f"{out}  ({end - start:.2f}s)")
        if (start, end) in claimed:
            said = claimed[(start, end)] or "(nothing)"
            print(f"    transcript has: {said}")

    print()
    print("Play them in order. The take you want is the one that runs clean")
    print("from start to finish; note where it begins and ends.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
