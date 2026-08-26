#!/usr/bin/env python3
"""Move one word's timestamps, for when the transcript places it wrong.

    python retime.py clip.words.json --at 0.0 --start 0.65 --end 0.72
    python retime.py clip.mp4 --at 0.0 --start 0.65 --dry-run

Where Whisper could not place words -- a stretch it heard but did not time --
a word can carry a timestamp seconds from when it was said. The cut is chosen
by ear and by audio, so the sound is right; the word simply falls outside the
range and its caption goes missing. This says where it really was.

The word is named by the time the transcript currently gives it, which is
unambiguous where a word like "AI" appears five times.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from show import resolve_json_path  # noqa: E402
from transcribe import rebuild_segments  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="a .words.json, or the media file")
    parser.add_argument("--at", type=float, required=True,
                        help="the word's current start, as show.py reports it")
    parser.add_argument("--start", type=float, required=True, help="where it really begins")
    parser.add_argument("--end", type=float, default=None,
                        help="where it really ends (default: leave as it is)")
    parser.add_argument("--dry-run", action="store_true", help="report, do not write")
    args = parser.parse_args()

    path = resolve_json_path(args.target)
    if path is None:
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))

    hits = [w for w in data["words"] if abs(w["start"] - args.at) < 0.001]
    if len(hits) != 1:
        print(f"error: {len(hits)} words start at {args.at}s -- "
              "run show.py --timings and name an exact one", file=sys.stderr)
        return 2
    word = hits[0]

    end = args.end if args.end is not None else word["end"]
    if not args.start < end:
        print(f"error: {args.start} is not before {end}", file=sys.stderr)
        return 2

    print(f"{word['word']!r}  {word['start']}-{word['end']}s "
          f"->  {args.start}-{end}s")
    word["start"], word["end"] = args.start, end
    data["words"].sort(key=lambda w: w["start"])
    data["segments"] = rebuild_segments(data["words"])

    if args.dry_run:
        print("\n(dry run, nothing written)")
        return 0

    backup = path.with_suffix(".json.bak")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {path}  (previous kept at {backup.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
