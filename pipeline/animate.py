#!/usr/bin/env python3
"""Render a preview of every saved animation, from the JSON you would paste.

    python animate.py            # all of them
    python animate.py --only named-files

An animation is worth saving only if you can tell what you are getting without
running it, and a preview drawn by hand goes stale the first time a component
changes. So the same file that holds the paste-ready cue holds the frames to
render it at, and the GIF beside it is built from that -- one source, no drift.

`preview` carries only timings, because the cue itself carries phrases: the
pipeline turns phrases into frames when it resolves a real sheet, and here
there is no speech to resolve against.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cues import CHILD_KEYS  # noqa: E402
from ffmpeg_ops import FFmpegMissing, binary  # noqa: E402
from remotion_ops import RemotionMissing  # noqa: E402
from remotion_ops import command as remotion_command  # noqa: E402
from verify import reason  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BROLL = ROOT / "broll"
CATALOGUE = HERE / "animations"

FPS = 30
# Wide enough to read the words, small enough to sit in a README. The frame is
# 1080x1920, so this is an exact eighth.
PREVIEW_WIDTH = 270


def ground_colour() -> str:
    """The brand ground, so a preview looks like the video and not like a test."""
    import re

    text = (BROLL / "src" / "tokens.ts").read_text(encoding="utf-8")
    found = re.search(r"void:\s*'(#[0-9A-Fa-f]{6})'", text)
    return "0x" + (found.group(1)[1:] if found else "060607")


def ground_source(kind: str, seconds: float) -> str:
    """The lavfi source to render the animation over.

    Flat by default. An effect that moves the PICTURE rather than drawing on it
    is invisible over a flat ground -- a 20% zoom on an empty frame looks like
    an empty frame -- so `"ground": "bars"` gives it something with edges to
    move. That is why the push had no preview when it was built.
    """
    if kind == "bars":
        return f"smptehdbars=s=1080x1920:d={seconds:.2f}:r={FPS}"
    return (f"color=c={ground_colour()}:s=1080x1920:"
            f"d={seconds:.2f}:r={FPS}")


def timed(animation: dict) -> dict:
    """The cue with frame numbers in place of phrases.

    The phrases are what a person writes and what the pipeline resolves. The
    renderer only ever sees frames, so a preview has to do by hand what a real
    run does from the transcript.
    """
    preview = animation["preview"]
    cue = deepcopy(animation["cue"])
    for key in ("until", "hold", "from", "finishBy"):
        cue.pop(key, None)
    cue["enter"] = preview["enter"]
    cue["leave"] = preview.get("leave")
    if "finishes" in preview:
        cue["finishes"] = preview["finishes"]

    entering = list(preview.get("children", []))
    for key in CHILD_KEYS:
        for child in cue.get(key) or []:
            child["enter"] = entering.pop(0) if entering else preview["enter"]
    return cue


def render(animation: dict, out: Path) -> None:
    public = BROLL / "public" / "video"
    public.mkdir(parents=True, exist_ok=True)
    ground = public / "animate-ground.mp4"
    seconds = animation["preview"]["frames"] / FPS

    subprocess.run(
        [binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi",
         "-i", ground_source(animation["preview"].get("ground", "flat"), seconds),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(ground)],
        check=True,
    )

    props = BROLL / "props.animate.json"
    props.write_text(json.dumps({
        "videoFile": "video/animate-ground.mp4",
        # No captions over a preview: the animation is the subject.
        "transcriptFile": "transcripts/cut.words.json",
        "videoDurationSeconds": seconds,
        "hookText": "",
        "cues": [timed(animation)],
    }), encoding="utf-8")

    # Straight to mp4 and then to GIF, rather than a PNG sequence: one output
    # Remotion needs no flags to produce, and ffmpeg reads it the same way.
    clip = BROLL / "out" / "animate.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        remotion_command("render", "CaptionedVideo", str(clip),
                         f"--props={props}"),
        cwd=BROLL, capture_output=True, text=True)
    props.unlink(missing_ok=True)
    ground.unlink(missing_ok=True)
    if done.returncode != 0:
        raise RuntimeError(
            f"render failed: {reason(done.stderr, done.returncode)}")

    # Two passes for the palette: a GIF quantised without one turns white
    # boxes on a near-black ground into banding, which is most of what these
    # previews are showing.
    palette = clip.with_name("palette.png")
    scale = f"scale={PREVIEW_WIDTH}:-1:flags=lanczos"
    subprocess.run(
        [binary("ffmpeg"), "-v", "error", "-y", "-i", str(clip),
         "-vf", f"{scale},palettegen", str(palette)], check=True)
    subprocess.run(
        [binary("ffmpeg"), "-v", "error", "-y", "-i", str(clip),
         "-i", str(palette),
         "-lavfi", f"{scale}[x];[x][1:v]paletteuse", "-loop", "0", str(out)],
        check=True)
    palette.unlink(missing_ok=True)
    clip.unlink(missing_ok=True)


def unrendered(animation: dict) -> list[str]:
    """Files the cue names that the renderer has no copy of.

    An animation may point at a project's own logos, which live with that
    project rather than here. There is nothing to draw it over, so it joins the
    catalogue without a preview instead of failing the whole run.
    """
    cue = animation["cue"]
    holders = [cue] + [child for key in CHILD_KEYS
                       for child in (cue.get(key) or [])
                       if isinstance(child, dict)]
    return [holder["src"] for holder in holders
            if holder.get("src")
            and not (BROLL / "public" / holder["src"]).is_file()]


def snippet(animation: dict) -> str:
    return json.dumps(animation["cue"], ensure_ascii=False, indent=2)


def picture(name: str, animation: dict) -> str:
    """The preview, or what to do instead when there is none."""
    if (CATALOGUE / f"{name}.gif").is_file():
        return f"\n![{animation['title']}]({name}.gif)\n"
    needed = ", ".join(unrendered(animation)) or "assets it cannot see"
    return ("\nNo preview here: it draws " + needed + ", which belongs to the "
            "project that uses it. Render one against your own copies.\n")


def index(animations: list[tuple[str, dict]]) -> str:
    """The catalogue, written from the files rather than kept beside them."""
    parts = ["""# Saved animations

Paste the snippet into a project's `overlays.json` and replace the phrases with
words you actually say. Every `cue` is a phrase, never a time.

Written by `python pipeline/animate.py`, which also renders the previews. Add a
`.json` here and run it again rather than editing this file.
"""]
    for name, animation in animations:
        parts.append(f"""
## {animation['title']}
{picture(name, animation)}
**What it does.** {animation['what']}

**When to reach for it.** {animation['when']}

**Seen in.** {animation['seen_in']}

```json
{snippet(animation)}
```
""")
    return "\n".join(parts)


def load() -> list[tuple[str, dict]]:
    return [(path.stem, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(CATALOGUE.glob("*.json"))]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default=None, help="one animation by name")
    parser.add_argument("--index-only", action="store_true",
                        help="rewrite README.md without rendering")
    args = parser.parse_args()

    animations = load()
    if not animations:
        print(f"No animations in {CATALOGUE}.", file=sys.stderr)
        return 2

    if not args.index_only:
        for name, animation in animations:
            if args.only and name != args.only:
                continue
            out = CATALOGUE / f"{name}.gif"
            missing = unrendered(animation)
            if missing:
                print(f"Skipping {name}: no copy of {', '.join(missing)}")
                continue
            print(f"Rendering {name} ...", flush=True)
            render(animation, out)
            print(f"  {out} ({out.stat().st_size // 1024}kb)")

    (CATALOGUE / "README.md").write_text(index(animations), encoding="utf-8")
    print(f"Wrote {CATALOGUE / 'README.md'} ({len(animations)} animations).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FFmpegMissing, RemotionMissing, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
