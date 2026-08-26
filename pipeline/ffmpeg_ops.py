#!/usr/bin/env python3
"""ffmpeg operations: cutting to a segment list, and colour grading."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cutlist import Segment


class FFmpegError(RuntimeError):
    pass


class FFmpegMissing(FFmpegError):
    pass


INSTALL_HINT = (
    "ffmpeg is not on PATH.\n"
    "  Windows : winget install Gyan.FFmpeg   (then reopen the terminal)\n"
    "  macOS   : brew install ffmpeg\n"
    "  Linux   : sudo apt install ffmpeg\n"
    "\n"
    "Remotion ships its own ffmpeg, but that build omits the eq and\n"
    "colortemperature filters, so it cannot do the colour grade. A real\n"
    "install is required."
)


def binary(name: str) -> str:
    """Locate ffmpeg/ffprobe, or fail with something actionable.

    Resolved per call rather than at import so a fresh install is picked up
    without restarting, and so importing this module never fails.
    """
    override = os.environ.get(f"{name.upper()}_BINARY")
    if override:
        return override
    found = shutil.which(name)
    if not found:
        raise FFmpegMissing(f"{name} not found.\n\n{INSTALL_HINT}")
    return found


def run(args: list[str]) -> None:
    """Run ffmpeg, surfacing its own error text rather than a bare exit code."""
    args = [binary(args[0])] + args[1:]
    try:
        result = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError as exc:                      # pragma: no cover
        raise FFmpegMissing(f"{args[0]} could not be run.\n\n{INSTALL_HINT}") from exc
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"ffmpeg failed ({result.returncode}):\n{tail}")


def build_trim_filter(segments: list[Segment]) -> str:
    """A filter_complex that trims and concatenates in one pass.

    Trim/concat rather than -ss per segment plus a concat demuxer: this is
    frame-accurate at arbitrary cut points, where stream copy would snap each
    cut to the nearest keyframe and drift by up to a GOP.
    """
    if not segments:
        raise ValueError("no segments to cut")

    parts = []
    for index, segment in enumerate(segments):
        parts.append(
            f"[0:v]trim=start={segment.start}:end={segment.end},"
            f"setpts=PTS-STARTPTS[v{index}];"
            f"[0:a]atrim=start={segment.start}:end={segment.end},"
            f"asetpts=PTS-STARTPTS[a{index}]"
        )
    streams = "".join(f"[v{i}][a{i}]" for i in range(len(segments)))
    parts.append(f"{streams}concat=n={len(segments)}:v=1:a=1[outv][outa]")
    return ";".join(parts)


def cut(source: Path, segments: list[Segment], output: Path, crf: int = 18) -> None:
    """Cut `source` down to `segments`, in the order given."""
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-v", "error", "-y",
        "-i", str(source),
        "-filter_complex", build_trim_filter(segments),
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ])


@dataclass
class Grade:
    """A colour grade, expressed as ffmpeg filters.

    Defaults are a restrained lift for talking-head footage: a touch of
    contrast, mild saturation, and a slight cool bias that sits with the Cyan
    Void palette rather than fighting it. No LUT, so nothing to ship or
    version; drop a .cube in and use `lut` when you want a real look.
    """

    contrast: float = 1.06
    brightness: float = 0.0
    saturation: float = 1.08
    gamma: float = 1.0
    temperature: int = 6200
    lut: Path | None = None

    def to_filter(self) -> str:
        chain = [
            f"eq=contrast={self.contrast}:brightness={self.brightness}"
            f":saturation={self.saturation}:gamma={self.gamma}",
            f"colortemperature={self.temperature}",
        ]
        if self.lut is not None:
            # The LUT goes last so it grades the corrected image, not the raw one.
            chain.append(f"lut3d='{self.lut.as_posix()}'")
        return ",".join(chain)


def grade(source: Path, output: Path, settings: Grade, crf: int = 18) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-v", "error", "-y",
        "-i", str(source),
        "-vf", settings.to_filter(),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output),
    ])


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [binary("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}")
    return float(result.stdout.strip())
