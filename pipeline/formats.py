#!/usr/bin/env python3
"""The formats bank: what a sequence may pick, and whether it still lines up.

    python pipeline/formats.py            list the bank
    python pipeline/formats.py --check    fail if it has drifted

The bank is the same rule as the hooks bank. A sequence picks a format by
name; nothing invents a layout. Drift is the failure mode worth catching --
a format built in tokens.ts and never banked cannot be picked, and a banked
name that no longer exists fails at render instead of here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = Path(__file__).resolve().parent / "formats" / "bank.json"
TOKENS = ROOT / "broll" / "src" / "tokens.ts"
SAMPLES = ROOT / "stories"


def load() -> list[dict]:
    return json.loads(BANK.read_text(encoding="utf-8"))["formats"]


def names() -> set[str]:
    return {entry["name"] for entry in load()}


def built() -> set[str]:
    """The format names tokens.ts actually defines, read off `slideFormat`."""
    source = TOKENS.read_text(encoding="utf-8")
    start = source.index("export const slideFormat = {")
    end = source.index("\n} as const;", start)
    # Two-space indentation is one key of slideFormat; deeper is inside one.
    return set(re.findall(r"^  ([a-z][A-Za-z]*): \{$", source[start:end], re.M))


def check() -> int:
    banked, real = names(), built()
    problems = []
    for name in sorted(real - banked):
        problems.append(f"{name} is built in tokens.ts but not in the bank,"
                        " so no sequence can pick it")
    for name in sorted(banked - real):
        problems.append(f"{name} is banked but tokens.ts does not define it")
    for entry in load():
        for sample in [s.strip() for s in entry["sample"].split(",")]:
            if not (SAMPLES / sample / "slides.json").is_file():
                problems.append(f"{entry['name']} names sample {sample},"
                                " which has no slides.json")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"formats: clean — {len(banked)} banked, built, and rendered.")
    return 0


def show() -> int:
    for entry in load():
        print(f"\n{entry['name']}  ({entry['ground']})")
        print(f"  {entry['what']}")
        print(f"  for: {'; '.join(entry['good_for'])}")
        print(f"  from: {entry['from']}   sample: {entry['sample']}")
        if entry.get("note"):
            print(f"  note: {entry['note']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail if the bank has drifted from the code")
    args = parser.parse_args()
    return check() if args.check else show()


if __name__ == "__main__":
    raise SystemExit(main())
