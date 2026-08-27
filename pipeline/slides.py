#!/usr/bin/env python3
"""Render a carousel from a folder of images and a slides.json beside them.

    python slides.py --story stories/system

Stills, not clips, so nothing here is timed. The folder holds the pictures and
the words; `out/` beside them holds what to post.

A slide that names no `image` is one whose picture is a video. It renders as
`NN-overlay.png` with the card punched clean out of the ground: put the clip
behind the PNG in the editor, filling the frame, and the hole IS the card.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ffmpeg_ops import FFmpegError, FFmpegMissing, binary  # noqa: E402
from jsonfile import BadJSON  # noqa: E402
from jsonfile import read as read_json  # noqa: E402
from remotion_ops import RemotionMissing  # noqa: E402
from remotion_ops import command as remotion_command  # noqa: E402
from verify import reason  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BROLL = ROOT / "broll"
# Remotion serves assets from public/ and staticFile cannot reach outside it.
STAGED = "slides"


def hole_in(overlay: Path) -> tuple[int, int, int, int]:
    """Where the ground is missing from an overlay: width, height, x, y.

    Asked of the file rather than restated here. The rectangle is decided in
    tokens.ts by the slide layout, and a second copy of those numbers in this
    script would be a copy to keep in step -- which is how every other pair of
    numbers in this project has drifted. cropdetect over the alpha channel
    reads back whatever the renderer actually drew.
    """
    done = subprocess.run(
        [binary("ffmpeg"), "-v", "info", "-i", str(overlay),
         "-vf", "alphaextract,negate,cropdetect=limit=0:round=2:skip=0",
         "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", done.stderr)
    if not found:
        raise FFmpegError(
            f"{overlay.name} has no transparent area, so there is nowhere to "
            "put the video. A slide meant to carry one names no `image`.")
    return tuple(int(n) for n in found[-1])  # type: ignore[return-value]


def frame_size(image: Path) -> tuple[int, int]:
    done = subprocess.run(
        [binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
         str(image)],
        capture_output=True, text=True, check=True)
    width, height = done.stdout.strip().split("x")
    return int(width), int(height)


def composite(video: Path, overlay: Path, out: Path) -> None:
    """Lay the clip into the overlay's hole, cropped to fill it.

    Filling the hole rather than the frame is the whole point: a document
    scrolling past should be the size of the card, not a strip cut out of a
    full-frame scale. Silent by design -- these play muted in the feed.
    """
    w, h, x, y = hole_in(overlay)
    canvas_w, canvas_h = frame_size(overlay)
    graph = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},pad={canvas_w}:{canvas_h}:{x}:{y}[bed];"
        # shortest=1 on the overlay filter itself, not the -shortest
        # flag: the still is a looped input, so without it the graph
        # never ends and the encode runs until the disk does.
        f"[bed][1:v]overlay=0:0:shortest=1,format=yuv420p[v]"
    )
    done = subprocess.run(
        [binary("ffmpeg"), "-v", "error", "-y",
         "-i", str(video), "-loop", "1", "-i", str(overlay),
         "-filter_complex", graph, "-map", "[v]", "-an", "-shortest",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(out)],
        capture_output=True, text=True)
    if done.returncode != 0:
        raise FFmpegError(done.stderr.strip().splitlines()[-1]
                          if done.stderr.strip() else "ffmpeg failed")


def render(story: Path) -> int:
    sheet = story / "slides.json"
    if not sheet.is_file():
        print(f"error: no such file: {sheet}", file=sys.stderr)
        return 2
    data = read_json(sheet)
    slides = data.get("slides") or []
    if not slides:
        print(f"error: {sheet} lists no slides", file=sys.stderr)
        return 2

    public = BROLL / "public" / STAGED
    public.mkdir(parents=True, exist_ok=True)
    # Absolute: the CLI runs with broll/ as its working directory, so a
    # relative path would write the stills inside the renderer.
    out = (story / "out").resolve()
    out.mkdir(exist_ok=True)
    props_file = BROLL / "props.slide.json"

    for index, entry in enumerate(slides, start=1):
        props = {**entry, "handle": entry.get("handle", data.get("handle", ""))}
        # A slide naming no image is one whose picture is a video: the still is
        # the overlay to lay over it, with the card punched out of the ground.
        overlay = not entry.get("image")
        if overlay:
            # Stated, not omitted: Remotion merges defaultProps over anything
            # a props file leaves out, so a missing key is not an empty one.
            props["image"] = ""
        else:
            source = story / entry["image"]
            if not source.is_file():
                print(f"error: slide {index} names {source}, which is not there",
                      file=sys.stderr)
                return 2
            shutil.copy2(source, public / source.name)
            props["image"] = f"{STAGED}/{source.name}"

        props_file.write_text(json.dumps(props, ensure_ascii=False),
                              encoding="utf-8")
        target = out / (f"{index:02d}-overlay.png" if overlay else f"{index:02d}.png")
        print(f"Rendering {target.name} ...", flush=True)
        done = subprocess.run(
            remotion_command("still", "Slide", str(target),
                             f"--props={props_file}"),
            cwd=BROLL, capture_output=True, text=True)
        if done.returncode != 0:
            props_file.unlink(missing_ok=True)
            print(f"error: {reason(done.stderr, done.returncode)}",
                  file=sys.stderr)
            return 1
        print(f"  {target}  ({target.stat().st_size // 1024}kb)")

        if entry.get("video"):
            clip = story / entry["video"]
            if not clip.is_file():
                print(f"error: slide {index} names {clip}, which is not there",
                      file=sys.stderr)
                return 2
            moving = out / f"{index:02d}.mp4"
            print(f"  laying {clip.name} into the hole ...", flush=True)
            composite(clip, target, moving)
            print(f"  {moving}  ({moving.stat().st_size // 1024}kb)")

    props_file.unlink(missing_ok=True)
    print(f"\n{len(slides)} slide(s) in {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, required=True,
                        help="the folder holding the images and slides.json")
    args = parser.parse_args()
    return render(args.story)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (BadJSON, FFmpegError, FFmpegMissing, RemotionMissing) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
