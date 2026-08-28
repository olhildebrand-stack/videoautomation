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
from formats import names as banked_formats  # noqa: E402
from verify import reason  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BROLL = ROOT / "broll"
# Remotion serves assets from public/ and staticFile cannot reach outside it.
STAGED = "slides"

# Every optional word on a slide, so none of them can fall back to a default.
OPTIONAL = {"kicker": "", "body": "", "emphasis": "", "focus": "",
            "headline": ""}

# The textured format holds its picture at a fixed place, so its words have a
# fixed slot above it: roughly three lines of about this many characters. Copy
# past that used to slide under the card and get cut in half.
TEXTURED_BUDGET = 3 * 38


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


def composite(video: Path, overlay: Path, out: Path,
              crop: str | None = None) -> None:
    """Lay the clip into the overlay's hole, cropped to fill it.

    Filling the hole rather than the frame is the whole point: a document
    scrolling past should be the size of the card, not a strip cut out of a
    full-frame scale. Silent by design -- these play muted in the feed.

    `crop` is ffmpeg's `W:H:X:Y`, taken out of the clip before anything else.
    A phone held up to a monitor spends most of its frame on the room, and
    scaling that to fill the card would leave the screen a sliver in the
    middle. `ffmpeg -i clip -vf cropdetect=limit=60 -f null -` names the lit
    part.
    """
    w, h, x, y = hole_in(overlay)
    canvas_w, canvas_h = frame_size(overlay)
    taken = f"crop={crop}," if crop else ""
    graph = (
        f"[0:v]{taken}scale={w}:{h}:force_original_aspect_ratio=increase,"
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

    # One shape, one format and one ground for the whole set. Mixing any of
    # them inside a sequence is what makes a set read as separate posts.
    shape = data.get("shape", "carousel")
    fmt = data.get("format", "textured")
    ground = data.get("background")
    if ground:
        source = story / ground
        if not source.is_file():
            print(f"error: background {source} is not there", file=sys.stderr)
            return 2
        shutil.copy2(source, public / source.name)
        ground = f"{STAGED}/{source.name}"

    # A sequence picks a format from the bank; it never invents a layout. The
    # same rule the hooks bank enforces, for the same reason.
    if fmt not in banked_formats():
        print(f"error: format {fmt!r} is not in the bank. Pick one of:"
              f" {', '.join(sorted(banked_formats()))}."
              "\n       `python pipeline/formats.py` says what each one is.",
              file=sys.stderr)
        return 2

    if fmt == "textured":
        for index, entry in enumerate(slides, start=1):
            words = len(entry.get("body", "")) + len(entry.get("emphasis", ""))
            if words > TEXTURED_BUDGET:
                print(f"error: slide {index} has {words} characters of body, and"
                      f" the textured format holds about {TEXTURED_BUDGET} above"
                      " the picture. Cut it, or use a format whose words are not"
                      " bounded by a card.", file=sys.stderr)
                return 2

    for index, entry in enumerate(slides, start=1):
        # Stated, not omitted. Remotion merges the composition's defaultProps
        # over anything the props file leaves out, so a key a slide does not
        # set does not come out empty -- it comes out holding the studio's
        # placeholder text.
        props = {**OPTIONAL, **entry, "shape": shape, "format": fmt,
                 "step": entry.get("step", index),
                 "of": entry.get("of", len(slides)),
                 "handle": entry.get("handle", data.get("handle", ""))}
        if ground:
            props["background"] = ground
        # The punch is for a video, and only for a video. Keying it on a missing
        # image instead meant a slide could not simply have no card -- and the
        # first slide of a set usually should not, since there is nothing to
        # show yet.
        overlay = bool(entry.get("video"))
        props["punch"] = overlay
        if not entry.get("image"):
            props["image"] = ""
        else:
            source = story / entry["image"]
            if not source.is_file():
                print(f"error: slide {index} names {source}, which is not there",
                      file=sys.stderr)
                return 2
            shutil.copy2(source, public / source.name)
            props["image"] = f"{STAGED}/{source.name}"

        # The formats that scatter or stack screenshots name more than one.
        staged = []
        for name in entry.get("images", []):
            source = story / name
            if not source.is_file():
                print(f"error: slide {index} names {source}, which is not there",
                      file=sys.stderr)
                return 2
            shutil.copy2(source, public / source.name)
            staged.append(f"{STAGED}/{source.name}")
        if staged:
            props["images"] = staged

        props_file.write_text(json.dumps(props, ensure_ascii=False),
                              encoding="utf-8")
        target = out / (f"{index:02d}-overlay.png" if overlay else f"{index:02d}.png")
        # One composition per shape: Remotion fixes width and height per id, and
        # a story is a different canvas rather than the same one cropped.
        composition = "SlideStory" if shape == "story" else "Slide"
        # A photograph behind the type is a ground, not a punched-out card, so
        # these formats never render the overlay variant.
        if fmt in ("labels", "blurred"):
            overlay = False
        print(f"Rendering {target.name} ...", flush=True)
        done = subprocess.run(
            remotion_command("still", composition, str(target),
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
            composite(clip, target, moving, entry.get("crop"))
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
