#!/usr/bin/env python3
"""Measure how a reference video was edited.

    python analyse.py reference/*.mp4
    python analyse.py reference/one.mp4 --frames out/frames

What it reports is the boring, measurable half of an editing style: how often
they cut, how long a shot lasts, how graded the picture is, how much of the
audio is silence. Those numbers transfer. Taste does not, and this does not try
to measure it.

It also writes a frame from just after every cut. That is the part worth
looking at by eye -- caption treatment, where overlays sit, what the grade
actually looks like -- and a still is something a person can read where a video
is not.

Nothing here downloads anything. Put the files in a directory and point at them.
"""

from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ffmpeg_ops import FFmpegMissing, binary  # noqa: E402
from takes import detect_silences  # noqa: E402

PTS = re.compile(r"pts_time:([0-9.]+)")
META = re.compile(r"lavfi\.signalstats\.(\w+)=([-0-9.]+)")

# How different two frames must be to count as a cut. 0.3 catches a hard cut
# and ignores a fast pan; a whip transition will read as one cut, which is what
# it is for pacing purposes.
DEFAULT_SCENE = 0.3

# Frames per second sampled for colour. Every frame is unnecessary -- a grade
# does not change within a shot -- and 900 samples of a 30s clip is slow.
GRADE_FPS = 2


@dataclass
class Shape:
    duration: float
    fps: float
    width: int
    height: int

    @property
    def vertical(self) -> bool:
        return self.height > self.width


@dataclass
class Report:
    path: Path
    shape: Shape
    cuts: list[float]
    brightness: float
    saturation: float
    contrast: float
    silence: float
    frames: list[Path] = field(default_factory=list)

    @property
    def shots(self) -> list[float]:
        """How long each shot lasts, in seconds."""
        edges = [0.0, *self.cuts, self.shape.duration]
        return [round(b - a, 3) for a, b in zip(edges, edges[1:]) if b > a]

    @property
    def cuts_per_minute(self) -> float:
        if self.shape.duration <= 0:
            return 0.0
        return len(self.cuts) / (self.shape.duration / 60)


def probe(path: Path) -> Shape:
    out = subprocess.run(
        [binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=0", str(path)],
        capture_output=True, text=True,
    ).stdout
    values = dict(
        line.split("=", 1) for line in out.splitlines() if "=" in line
    )
    rate = values.get("r_frame_rate", "30/1")
    numerator, _, denominator = rate.partition("/")
    fps = float(numerator) / float(denominator or 1)
    return Shape(
        duration=float(values.get("duration", 0) or 0),
        fps=round(fps, 3),
        width=int(values.get("width", 0)),
        height=int(values.get("height", 0)),
    )


def scene_cuts(path: Path, threshold: float = DEFAULT_SCENE) -> list[float]:
    """Every hard cut, in seconds.

    Note the log level: showinfo writes at info, so running this quietly --
    which is the obvious thing to do -- returns an empty list and looks like a
    video with no cuts in it.
    """
    result = subprocess.run(
        [binary("ffmpeg"), "-v", "info", "-nostats", "-i", str(path),
         "-vf", f"select='gt(scene,{threshold})',showinfo", "-an",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return [round(float(m), 3) for m in PTS.findall(result.stderr)]


def grade(path: Path) -> tuple[float, float, float]:
    """(brightness, saturation, contrast) averaged over the clip.

    Brightness and saturation are what a grade obviously changes. Contrast is
    the spread of luma across the clip rather than within a frame, which is a
    rough measure but tracks how punchy an edit looks.
    """
    result = subprocess.run(
        [binary("ffmpeg"), "-v", "info", "-nostats", "-i", str(path),
         "-vf", f"fps={GRADE_FPS},signalstats,metadata=print:file=-", "-an",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    found: dict[str, list[float]] = {}
    for key, value in META.findall(result.stdout + result.stderr):
        found.setdefault(key, []).append(float(value))

    luma = found.get("YAVG", [0.0])
    sat = found.get("SATAVG", [0.0])
    return (
        round(statistics.fmean(luma), 1),
        round(statistics.fmean(sat), 1),
        round(statistics.pstdev(luma) if len(luma) > 1 else 0.0, 1),
    )


def silence_ratio(path: Path, duration: float) -> float:
    """Share of the clip with nobody speaking."""
    if duration <= 0:
        return 0.0
    try:
        silences = detect_silences(path, 0.0, duration, -45.0, 0.15)
    except FFmpegMissing:
        raise
    except Exception:
        return 0.0
    quiet = sum(end - start for start, end in silences)
    return round(min(1.0, quiet / duration), 3)


def grab_frames(path: Path, cuts: list[float], out_dir: Path,
                shape: Shape, limit: int = 12) -> list[Path]:
    """A frame from just inside each shot, for reading by eye.

    Taken a beat after the cut rather than on it, so a transition mid-wipe does
    not stand in for the shot it becomes.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    moments = [0.4] + [c + 0.4 for c in cuts]
    moments = [m for m in moments if m < shape.duration][:limit]

    written: list[Path] = []
    for index, at in enumerate(moments):
        target = out_dir / f"{path.stem}-{index:02d}-{at:06.2f}s.png"
        subprocess.run(
            [binary("ffmpeg"), "-v", "error", "-y", "-ss", f"{at}",
             "-i", str(path), "-frames:v", "1", str(target)],
            capture_output=True,
        )
        if target.is_file():
            written.append(target)
    return written


def analyse(path: Path, frames_dir: Path | None, threshold: float) -> Report:
    shape = probe(path)
    cuts = scene_cuts(path, threshold)
    brightness, saturation, contrast = grade(path)
    report = Report(
        path=path,
        shape=shape,
        cuts=cuts,
        brightness=brightness,
        saturation=saturation,
        contrast=contrast,
        silence=silence_ratio(path, shape.duration),
    )
    if frames_dir is not None:
        report.frames = grab_frames(path, cuts, frames_dir, shape)
    return report


def show(report: Report) -> None:
    shape = report.shape
    shots = report.shots
    print(f"\n{report.path.name}")
    print(f"  {shape.duration:.1f}s  {shape.width}x{shape.height}"
          f"  {shape.fps:g}fps"
          f"  {'vertical' if shape.vertical else 'landscape'}")
    print(f"  cuts        {len(report.cuts)}"
          f"  ({report.cuts_per_minute:.0f}/min)")
    if shots:
        print(f"  shot length median {statistics.median(shots):.2f}s"
              f"   shortest {min(shots):.2f}s   longest {max(shots):.2f}s")
    print(f"  picture     brightness {report.brightness}"
          f"   saturation {report.saturation}"
          f"   contrast {report.contrast}")
    print(f"  silence     {report.silence * 100:.0f}% of the clip")
    if report.frames:
        print(f"  frames      {len(report.frames)} written to "
              f"{report.frames[0].parent}")


def compare(reports: list[Report]) -> None:
    """What repeats across the set is the style; what does not is one habit."""
    if len(reports) < 2:
        return
    print("\n--- across all " + str(len(reports)) + " ---")
    rows = [
        ("cuts/min", [r.cuts_per_minute for r in reports], "{:.0f}"),
        ("median shot", [statistics.median(r.shots) if r.shots else 0
                         for r in reports], "{:.2f}s"),
        ("brightness", [r.brightness for r in reports], "{:.0f}"),
        ("saturation", [r.saturation for r in reports], "{:.0f}"),
        ("silence", [r.silence * 100 for r in reports], "{:.0f}%"),
    ]
    for name, values, fmt in rows:
        low, high = min(values), max(values)
        mid = statistics.median(values)
        spread = "" if high - low < 1e-9 else f"  (range {fmt.format(low)}-{fmt.format(high)})"
        print(f"  {name:<12} median {fmt.format(mid)}{spread}")
    print("\n  A number that holds across the set is the style. One that swings")
    print("  is that video, not that editor.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--frames", type=Path, default=None,
                        help="write a frame from each shot into this directory")
    parser.add_argument("--scene", type=float, default=DEFAULT_SCENE,
                        help=f"cut sensitivity, 0-1 (default {DEFAULT_SCENE})")
    args = parser.parse_args()

    missing = [v for v in args.videos if not v.is_file()]
    if missing:
        for path in missing:
            print(f"error: no such file: {path}", file=sys.stderr)
        return 2

    try:
        reports = [analyse(v, args.frames, args.scene) for v in args.videos]
    except FFmpegMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for report in reports:
        show(report)
    compare(reports)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
