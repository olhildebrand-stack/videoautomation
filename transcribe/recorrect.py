#!/usr/bin/env python3
"""Re-apply corrections.txt to an existing transcript, without re-transcribing.

    python recorrect.py clip.words.json
    python recorrect.py clip.mp4 --dry-run

Corrections are text-level, so needing a fresh GPU transcription to pick up a
new rule is pure waste -- and worse, it makes a stale transcript look like a
rule that did not work. This rewrites the words in place instead.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from transcribe import (  # noqa: E402
    CORRECTIONS_FILE, apply_corrections, apply_sequence_corrections,
    drop_deleted, load_corrections, rebuild_segments,
)


def recorrect(data: dict, rules: list[tuple[str, str]]) -> tuple[dict, dict[str, int]]:
    """Apply the rules to every word and rebuild the segment text."""
    applied: dict[str, int] = {}

    def tally(counts: dict[str, int]) -> None:
        for key, count in counts.items():
            applied[key] = applied.get(key, 0) + count

    # Work on the flat word list. Whisper breaks segments at sentence ends, so
    # a rule targeting an invented full stop spans a boundary by definition --
    # applied per segment it can never match, which is exactly how a correct
    # rule came to look broken.
    all_words = []
    for word in data.get("words", []):
        fixed, counts = apply_corrections(word["word"], rules)
        tally(counts)
        all_words.append({**word, "word": fixed})

    all_words, counts = apply_sequence_corrections(all_words, rules)
    tally(counts)
    all_words = drop_deleted(all_words)

    data["segments"] = rebuild_segments(all_words)
    data["words"] = all_words
    data["word_count"] = len(all_words)
    # Merge with whatever the original run recorded, so the file stays a true
    # account of every correction the text has been through.
    previous = data.get("corrections_applied") or {}
    for key, count in applied.items():
        previous[key] = previous.get(key, 0) + count
    data["corrections_applied"] = previous
    return data, applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="a .words.json, or the media file")
    parser.add_argument("--corrections", type=Path, default=CORRECTIONS_FILE)
    parser.add_argument("--dry-run", action="store_true", help="report, do not write")
    args = parser.parse_args()

    path = args.target
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".words.json")
    if not path.is_file():
        print(f"error: no such transcript: {path}", file=sys.stderr)
        return 2

    rules = load_corrections(args.corrections)
    if not rules:
        print(f"no rules in {args.corrections}")
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    before = "".join(w["word"] for w in data["words"]).strip()
    data, applied = recorrect(data, rules)
    after = "".join(w["word"] for w in data["words"]).strip()

    if not applied:
        print(f"{len(rules)} rules loaded, none matched. Nothing to change.")
        return 0

    for rule, count in applied.items():
        print(f"applied {count}x  {rule}")
    print(f"\nwords: {len(before.split())} -> {len(after.split())}")

    if args.dry_run:
        print("\n(dry run, nothing written)")
        return 0

    backup = path.with_suffix(".json.bak")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {path}  (previous kept at {backup.name})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
