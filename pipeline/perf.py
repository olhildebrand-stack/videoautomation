#!/usr/bin/env python3
"""What posted videos actually did, next to what they were made of.

    python pipeline/perf.py            the table, worst retention last
    python pipeline/perf.py --check    fail when a posted video is unrecorded

The idea stage has no other memory. Hooks are matched from banks of other
people's wins, and the only evidence about *this* account is `performance.json`
-- so a video whose numbers were never written down taught nobody anything,
and `IDEAS.md`'s learned rules stay at n=2 forever.

Retention, not views, is what this prints first. Views are downstream: the
platform distributes what holds people, so a video that lost its audience in
the first seconds was never given the chance to be judged on its content. The
reel that worked here held 54%; the one that died held 21% and took a ninefold
deficit in reach with it.

The join to `edit-scripts/` is the point. A number on its own says a video did
badly; a number beside the beats it was made of says which shape did badly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jsonfile import BadJSON, read as read_json  # noqa: E402

HERE = Path(__file__).resolve().parent
RECORD = HERE / "performance.json"
SCRIPTS = HERE / "edit-scripts"

# Below this the video lost its audience before the content was reached, which
# makes it a hook failure rather than a body failure. Sits between the two
# measured reels (21% and 54%) and is a working line, not a law -- move it when
# there are enough rows to put it somewhere better.
HOOK_FAILED = 0.35


def posts() -> list[dict]:
    # Read RECORD here rather than binding it as a default: a default is
    # evaluated once at import, which silently pins the path.
    return read_json(RECORD, "performance record")["posts"]


def beats(name: str) -> list[str]:
    path = SCRIPTS / f"{name}.json"
    if not path.is_file():
        return []
    return [b.get("beat", "?") for b in read_json(path, "edit script")]


def retention(post: dict) -> float | None:
    if not post.get("length") or post.get("watch") is None:
        return None
    return post["watch"] / post["length"]


def show() -> int:
    rows = sorted(posts(), key=lambda p: retention(p) or 0, reverse=True)
    print(f"{'video':24}{'kept':>7}{'watch':>10}{'views':>8}"
          f"{'saves':>7}{'shr':>5}{'cmt':>5}{'prof':>6}{'flw':>5}{'dm':>5}")
    for post in rows:
        kept = retention(post)
        dms = "?" if post.get("dms") is None else post["dms"]
        pct = "--" if kept is None else f"{kept:.0%}"
        span = f"{post['watch']:.0f}/{post['length']}s"
        print(f"{post['name'][:23]:24}{pct:>7}{span:>10}"
              f"{post.get('views', 0):>8}{post.get('saves', 0):>7}"
              f"{post.get('shares', 0):>5}{post.get('comments', 0):>5}"
              f"{post.get('profile_visits', 0):>6}"
              f"{post.get('follows', 0):>5}{str(dms):>5}")
        made_of = beats(post["name"])
        if made_of:
            print(f"    {' -> '.join(made_of)}")
        if kept is not None and kept < HOOK_FAILED:
            print(f"    lost them before the content -- read the hook, not"
                  f" the body")
        if post.get("note"):
            print(f"    {post['note']}")
        print()
    return 0


def unrecorded() -> list[str]:
    """Videos that went through the pipeline and never had their numbers kept."""
    recorded = {p["name"] for p in posts()}
    return sorted(p.stem for p in SCRIPTS.glob("*.json")
                  if p.stem not in recorded)


def check() -> int:
    missing = unrecorded()
    for name in missing:
        print(f"error: {name} was edited by the pipeline but has no row in"
              f" {RECORD.name}, so what it did is already lost",
              file=sys.stderr)
    if missing:
        return 1
    print(f"performance: {len(posts())} posts recorded, none unaccounted for.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail when a posted video has no numbers")
    args = parser.parse_args()
    try:
        return check() if args.check else show()
    except BadJSON as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
