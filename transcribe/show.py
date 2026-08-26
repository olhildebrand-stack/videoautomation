#!/usr/bin/env python3
"""Inspect a .words.json: print the transcript and search it.

    python show.py clip.words.json
    python show.py clip.words.json --find Cloud Claude jätte

Exists because a correction that matches nothing and a correction that never
loaded look identical from the transcribe output alone. This shows the literal
text, so a rule can be written against what is actually there.
"""

import argparse
import json
import sys
from pathlib import Path


def resolve_json_path(given: Path) -> Path | None:
    """Accept either the transcript JSON or the media file it came from.

    Passing the video is the natural mistake -- it is the path already on the
    clipboard -- and reading an mp4 as UTF-8 fails with a decode error that
    says nothing useful. Resolve the sibling .words.json instead.
    """
    if given.suffix.lower() == ".json":
        if given.is_file():
            return given
        print(f"error: no such file: {given}", file=sys.stderr)
        return None

    sibling = given.with_suffix(".words.json")
    if sibling.is_file():
        print(f"(reading {sibling.name})\n")
        return sibling

    if given.is_file():
        print(f"error: {given.name} is not a transcript.", file=sys.stderr)
        print(f"       Expected {sibling.name}, which does not exist yet.", file=sys.stderr)
        print("       Run transcribe.ps1 on the video first.", file=sys.stderr)
    else:
        print(f"error: no such file: {given}", file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a transcription JSON.")
    parser.add_argument("json_file", type=Path)
    parser.add_argument(
        "--timings",
        action="store_true",
        help="print every word with its gap from the previous one",
    )
    parser.add_argument(
        "--find",
        nargs="*",
        default=[],
        help="case-insensitive substrings to locate, with timestamps",
    )
    args = parser.parse_args()

    path = resolve_json_path(args.json_file)
    if path is None:
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: {path} is not readable as JSON ({exc})", file=sys.stderr)
        return 2

    print(f"device          : {data.get('device')}/{data.get('compute_type')}")
    print(f"language        : {data.get('language')}")
    print(f"words           : {data.get('word_count')}")
    print(f"vocabulary_terms: {data.get('vocabulary_terms')}")
    print(f"corrections     : {data.get('corrections_applied')}")
    print()

    words = data.get("words", [])
    transcript = "".join(word["word"] for word in words)
    print("--- transcript ---")
    print(transcript.strip())
    print()

    if args.timings:
        print("--- word timings (gap = silence before this word) ---")
        print(f"{'#':>4} {'start':>8} {'end':>8} {'gap':>7} {'p':>6}  word")
        previous_end = 0.0
        for index, word in enumerate(words):
            gap = word["start"] - previous_end
            # A gap far longer than a breath means audio Whisper transcribed
            # nothing for -- a false start it dropped, or dead air.
            mark = "  <-- GAP" if gap >= 0.35 else ""
            print(
                f"{index:>4} {word['start']:>8.2f} {word['end']:>8.2f} "
                f"{gap:>7.2f} {word['probability']:>6.2f}  {word['word']!r}{mark}"
            )
            previous_end = word["end"]
        print()
        total_gap = sum(
            max(0.0, w["start"] - (words[i - 1]["end"] if i else 0.0))
            for i, w in enumerate(words)
        )
        spoken = sum(w["end"] - w["start"] for w in words)
        print(f"spoken: {spoken:.1f}s   gaps: {total_gap:.1f}s   "
              f"span: {words[-1]['end'] if words else 0:.1f}s")
        print()

    if args.find:
        print("--- matches ---")
        for needle in args.find:
            lowered = needle.lower()
            hits = [w for w in words if lowered in w["word"].lower()]
            if not hits:
                print(f"{needle!r}: no match")
                continue
            for hit in hits:
                print(f"{needle!r}: {hit['word']!r} at {hit['start']}s (p={hit['probability']})")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Piping into head closes stdout early; that is not an error.
        try:
            sys.stdout.close()
        finally:
            sys.exit(0)
