#!/usr/bin/env python3
"""ffmpeg operations: cutting to a segment list, and colour grading."""

from __future__ import annotations

import json
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


def join(parts: list[Path], output: Path, crf: int = 18) -> None:
    """Concatenate finished videos end to end.

    `cut` concatenates segments of ONE recording, which is all the pipeline
    needed while a video was one take. Testing three spoken hooks against one
    body is two recordings, and no amount of trimming inside either reaches
    across the gap.

    The concat filter rather than the demuxer: the demuxer needs every input to
    share a codec and a timebase exactly, and produces a broken file when they
    do not. These come off a camera and a renderer, so they do not.

    The filter has its own requirement -- identical width, height, SAR and
    frame rate -- and fails outright when they differ, which a 1080x1920/30
    hook in front of a 720x1280/25 body proved on the first real test of this
    function. So every input is scaled into the FIRST one's frame, padded
    rather than stretched, and resampled to its rate. The first part is the
    hook, and the hook is what the finished video should look like.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height, fps = probe_video(parts[0])
    chains, streams = [], ""
    for i in range(len(parts)):
        chains.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
        )
        chains.append(f"[{i}:a]aresample=async=1[a{i}]")
        streams += f"[v{i}][a{i}]"
    args = ["ffmpeg", "-v", "error", "-y"]
    for part in parts:
        args += ["-i", str(part)]
    run(args + [
        "-filter_complex",
        ";".join(chains) + f";{streams}concat=n={len(parts)}:v=1:a=1[outv][outa]",
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ])


def mean_volume(path: Path) -> float:
    """The mean level of a file's audio, in dBFS, via volumedetect."""
    result = subprocess.run(
        [binary("ffmpeg"), "-v", "info", "-i", str(path),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    for line in result.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    raise FFmpegError(f"no audio level found in {path}")


def score(video: Path, track: Path, output: Path, start: float,
          gain_db: float, fade: float = 1.2) -> None:
    """Lay music under a video's own audio, from `start` in the track.

    The video is copied, not re-encoded: only the audio changes, and a fourth
    generation of h264 for the sake of a background bed is a bad trade.

    `normalize=0` on the mix matters. amix scales its inputs by default, so
    adding a quiet music bed would pull the speech DOWN by 6dB -- the voice
    getting quieter is the opposite of what adding background music is for.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    length = probe_duration(video)
    run([
        "ffmpeg", "-v", "error", "-y",
        "-i", str(video), "-i", str(track),
        "-filter_complex",
        f"[1:a]atrim=start={start}:duration={length},asetpts=PTS-STARTPTS,"
        f"volume={gain_db:.2f}dB,"
        f"afade=t=in:st=0:d={fade},"
        f"afade=t=out:st={max(0.0, length - fade):.3f}:d={fade}[bed];"
        f"[0:a][bed]amix=inputs=2:duration=first:normalize=0[out]",
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
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


def probe_video(path: Path) -> tuple[int, int, str]:
    """Width, height and frame rate, as ffmpeg's own fraction ('30000/1001').

    JSON, not CSV. The first version asked for three fields separated by 'x'
    and unpacked exactly three, which held until a file came back with four --
    an mp4 can carry more than one stream ffprobe is willing to call video, and
    a separator is only unambiguous until it is not. Parsing a structure cannot
    be surprised by an extra field; splitting a string can.
    """
    result = subprocess.run(
        [binary("ffprobe"), "-v", "error", "-select_streams", "v",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}")
    streams = json.loads(result.stdout).get("streams") or []
    # The first stream carrying real dimensions. A cover image is a video
    # stream to ffprobe and would otherwise decide the geometry of the join.
    for stream in streams:
        if stream.get("width") and stream.get("height"):
            return (int(stream["width"]), int(stream["height"]),
                    stream.get("r_frame_rate") or "30/1")
    raise FFmpegError(f"no video stream with dimensions in {path}")


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [binary("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}")
    return float(result.stdout.strip())
