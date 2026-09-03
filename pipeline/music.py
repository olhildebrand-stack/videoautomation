#!/usr/bin/env python3
"""Find the part of a song worth putting under a video, and say how loud.

    python music.py track.mp3 --seconds 31

The operator's instruction was "not the absolute beginning because there will
be a lot of silences and buildup, and not during a climax, find somewhere
inbetween". That is a description of a loudness profile, so it is measured
rather than recalled: knowing a popular song is not the same as knowing which
second of it is steady, and a remembered timestamp is a guess wearing a number.

What "somewhere inbetween" means, made checkable:

  steady   the window's loudness barely moves. A buildup rises across itself
           and a drop arrives as a step; both show up as spread. The quietest
           spread wins.
  mid      its level sits near the track's own median, so it is neither the
           intro nor the loudest bar.

Both are needed. A silent intro is perfectly steady.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from array import array
from pathlib import Path

# One second is the window the ear judges "is this loud" over, and it is short
# enough that a four-bar buildup spans several of them.
WINDOW = 1.0
RATE = 8000

# The first fifth of a track is intro and the last tenth is an outro or a fade,
# and neither is what "somewhere inbetween" means.
SKIP_HEAD = 0.20
SKIP_TAIL = 0.10


class NoTrack(RuntimeError):
    pass


def levels(track: Path, rate: int = RATE) -> list[float]:
    """Loudness of each one-second window, in dBFS. Silence reads -90."""
    if not Path(track).is_file():
        raise NoTrack(f"no such track: {track}")
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(track), "-ac", "1",
         "-ar", str(rate), "-f", "s16le", "-"],
        capture_output=True)
    if done.returncode != 0:
        raise NoTrack(f"ffmpeg could not read {track}: "
                      f"{done.stderr.decode(errors='replace').strip()[-200:]}")
    raw = done.stdout
    if not raw:
        raise NoTrack(f"{track} has no audio in it")
    samples = array("h")
    samples.frombytes(raw[:len(raw) - len(raw) % 2])
    step = int(rate * WINDOW)
    out = []
    for start in range(0, len(samples) - step + 1, step):
        window = samples[start:start + step]
        mean_square = sum(s * s for s in window) / step
        out.append(10 * math.log10(mean_square / (32768.0 ** 2))
                   if mean_square > 0 else -90.0)
    return out


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def spread(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def best_start(track: Path, seconds: float) -> tuple[float, float, float]:
    """Where to start, the window's level, and how much it moves.

    Ranked on spread first and distance from the median second, because a
    steady stretch slightly off the median is still background; a stretch that
    swings through the median is a buildup passing through.
    """
    profile = levels(track)
    need = max(1, int(round(seconds / WINDOW)))
    if len(profile) <= need:
        return 0.0, median(profile), spread(profile)

    first = int(len(profile) * SKIP_HEAD)
    last = len(profile) - int(len(profile) * SKIP_TAIL) - need
    if last <= first:                       # a track barely longer than the clip
        first, last = 0, len(profile) - need

    centre = median(profile)
    best, chosen = None, first
    for start in range(first, last + 1):
        window = profile[start:start + need]
        move = spread(window)
        level = sum(window) / need
        score = move + abs(level - centre) * 0.5
        if best is None or score < best:
            best, chosen = score, start
    window = profile[chosen:chosen + need]
    return chosen * WINDOW, sum(window) / need, spread(window)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track", type=Path)
    parser.add_argument("--seconds", type=float, required=True,
                        help="how much of it you need")
    args = parser.parse_args()
    try:
        start, level, move = best_start(args.track, args.seconds)
    except NoTrack as exc:
        print(f"error: {exc}")
        return 2
    print(f"{args.track.name}")
    print(f"  start   {start:.1f}s")
    print(f"  level   {level:.1f} dBFS   (moves {move:.1f} dB across the window)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
