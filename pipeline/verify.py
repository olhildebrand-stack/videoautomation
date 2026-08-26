#!/usr/bin/env python3
"""Look at the rendered frame, not at the code that produced it.

    python verify.py --project projects/ep01
    python verify.py --project projects/ep01 --at 3.2 --at 11.7

Two placement bugs got through code review, typechecking and a full test suite
this project already had: a chat window that grew as messages arrived until it
sat in the caption band, and a row pinned to the top of frame that centred
itself instead, because a flex row takes its vertical alignment from alignItems
and the pin was on justifyContent. Both were invisible in the source and
obvious in the pixels.

So this renders the overlay layer over a flat ground -- everything that is not
that colour is something the composition drew -- and measures where it landed.
No opinion about whether it looks good; only whether it is inside the frame it
is allowed to use.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cues import CHILD_KEYS  # noqa: E402
from ffmpeg_ops import FFmpegMissing, binary  # noqa: E402
from remotion_ops import RemotionMissing  # noqa: E402
from remotion_ops import command as remotion_command  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BROLL = ROOT / "broll"

# A ground no composition uses, so any pixel differing from it was drawn.
# Magenta rather than black: black is a legitimate fill (the hook card), and a
# ground the design might genuinely paint cannot be told from one it did not.
GROUND = "0xFF00FF"
GROUND_RGB = (255, 0, 255)

# How far a pixel must be from the ground to count as drawn. Anti-aliased edges
# blend toward it, and counting those as content would put every element a few
# pixels outside its real box.
TOLERANCE = 60


@dataclass
class Placement:
    """Where the composition actually drew, at one moment."""

    at: float
    frame: int
    top: int | None
    bottom: int | None
    left: int | None
    right: int | None
    width: int
    height: int
    problems: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.top is None


def safe_zone() -> dict[str, int]:
    """Read the insets from tokens.ts, so there is one definition of them."""
    import re

    text = (BROLL / "src" / "tokens.ts").read_text(encoding="utf-8")
    block = re.search(r"export const safeZone = \{(.*?)\}", text, re.S)
    if not block:
        raise RuntimeError("safeZone not found in tokens.ts")
    return {
        key: int(value)
        for key, value in re.findall(r"(\w+):\s*(\d+)", block.group(1))
    }


def dimensions() -> tuple[int, int]:
    import re

    text = (BROLL / "src" / "tokens.ts").read_text(encoding="utf-8")
    block = re.search(r"export const dimensions = \{(.*?)\}", text, re.S)
    if not block:
        return 1080, 1920
    found = dict(re.findall(r"(\w+):\s*(\d+)", block.group(1)))
    return int(found.get("width", 1080)), int(found.get("height", 1920))


def flat_ground(path: Path, seconds: float, width: int, height: int) -> None:
    subprocess.run(
        [binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=c={GROUND}:s={width}x{height}:d={max(1, int(seconds) + 1)}:r=30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


def content_box(png: Path, width: int, height: int) -> tuple[int | None, ...]:
    """The bounding box of everything drawn over the ground."""
    raw = subprocess.run(
        [binary("ffmpeg"), "-v", "error", "-i", str(png),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    ).stdout
    if len(raw) < width * height * 3:
        return (None, None, None, None)

    top = bottom = left = right = None
    for y in range(height):
        row = y * width * 3
        for x in range(0, width, 2):
            index = row + x * 3
            if (abs(raw[index] - GROUND_RGB[0]) > TOLERANCE
                    or abs(raw[index + 1] - GROUND_RGB[1]) > TOLERANCE
                    or abs(raw[index + 2] - GROUND_RGB[2]) > TOLERANCE):
                if top is None:
                    top = y
                bottom = y
                left = x if left is None else min(left, x)
                right = x if right is None else max(right, x)
    return (top, bottom, left, right)


def check(placement: Placement, zone: dict[str, int]) -> None:
    """Everything drawn has to sit inside the band the platform leaves alone."""
    if placement.empty:
        return
    if placement.top < zone["top"]:
        placement.problems.append(
            f"reaches {zone['top'] - placement.top}px into the top band "
            f"(y={placement.top}, band ends {zone['top']})")
    floor = placement.height - zone["bottom"]
    if placement.bottom > floor:
        placement.problems.append(
            f"reaches {placement.bottom - floor}px into the bottom band "
            f"(y={placement.bottom}, band starts {floor})")
    if placement.left < zone["side"]:
        placement.problems.append(
            f"{zone['side'] - placement.left}px past the left margin")
    edge = placement.width - zone["side"]
    if placement.right > edge:
        placement.problems.append(
            f"{placement.right - edge}px past the right margin")


def moments(cues: list[dict], fps: int, duration: float) -> list[float]:
    """When to look.

    The midpoint of every cue, because that is when an effect is fully arrived
    and at its largest. Plus a couple of fixed points, so a video with no cues
    is still checked for its captions.
    """
    seen = {round(duration * share, 2) for share in (0.15, 0.5, 0.85)}
    for cue in cues:
        enter = cue.get("enter", 0) / fps
        leave = cue["leave"] / fps if cue.get("leave") is not None else duration
        seen.add(round(min(duration - 0.05, (enter + leave) / 2), 2))
        # Every kind of child, from the one list of them. Spelling the kinds
        # out here is how chip rows came to be sampled at the parent's
        # midpoint only, and never at the moment a chip actually arrived.
        for key in CHILD_KEYS:
            for child in cue.get(key) or []:
                if child.get("enter") is None:
                    continue
                seen.add(round(min(duration - 0.05, child["enter"] / fps + 0.4), 2))
    return sorted(t for t in seen if t >= 0)


def reason(stderr: str, code: int) -> str:
    """The line of a Node stack trace worth showing.

    The last line is a call site inside Remotion; the first line naming an
    error is the one that says what the operator did -- asking for a frame
    past the end of the composition, most often, which means the props and the
    footage disagree about how long the video is.
    """
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in lines:
        if "Error" in line.split(":")[0] or line.startswith("Error"):
            return line
    body = [line for line in lines if not line.startswith("at ")]
    return body[-1] if body else f"remotion still exited {code}"


def remotion_still(props: Path, frame: int, out: Path) -> str | None:
    """One frame, rendered by the project's own Remotion.

    Returns None when the frame was written, or why it was not.

    Not `npx remotion`: npx is npx.cmd on Windows, which subprocess cannot run
    without a shell, so that spelling failed with a bare WinError 2 on the only
    machine this is used from.
    """
    args = remotion_command(
        "still", "CaptionedVideo", str(out.resolve()),
        f"--props={props}", f"--frame={frame}")
    done = subprocess.run(args, cwd=BROLL, capture_output=True, text=True)
    if done.returncode == 0 and out.is_file():
        return None
    # Reported, never swallowed. A skipped frame used to leave the run saying
    # "all sampled frames stay inside the safe zone" about the frames that did
    # render -- an unchecked layout that reads exactly like a checked one.
    return reason(done.stderr, done.returncode)


def verify(project: Path, at: list[float] | None = None,
           keep_frames: bool = False,
           ) -> tuple[list[Placement], str, list[tuple[float, str]]]:
    """Render the composition over a flat ground and measure what it drew."""
    state = json.loads((project / "pipeline.json").read_text(encoding="utf-8"))
    width, height = dimensions()
    zone = safe_zone()
    fps = 30

    final = state.get("final_video") or state.get("captioned_video")
    duration = 20.0
    if final and Path(final).is_file():
        probe = subprocess.run(
            [binary("ffprobe"), "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", final],
            capture_output=True, text=True).stdout.strip()
        if probe:
            duration = float(probe)

    public = BROLL / "public" / "video"
    public.mkdir(parents=True, exist_ok=True)
    ground = public / "verify-ground.mp4"
    flat_ground(ground, duration, width, height)

    cues = state.get("cue_snapshot") or []
    props = BROLL / "props.verify.json"
    props.write_text(json.dumps({
        "videoFile": "video/verify-ground.mp4",
        "transcriptFile": f"transcripts/{Path(state['cut_transcript']).name}"
        if state.get("cut_transcript") else "transcripts/cut.words.json",
        "videoDurationSeconds": duration,
        "hookText": state.get("hook", ""),
        "cues": cues,
    }), encoding="utf-8")

    frames_dir = project / "verify"
    frames_dir.mkdir(exist_ok=True)

    results: list[Placement] = []
    failures: list[tuple[float, str]] = []
    for moment in (at or moments(cues, fps, duration)):
        frame = int(round(moment * fps))
        png = frames_dir / f"t{moment:07.2f}.png"
        why = remotion_still(props, frame, png)
        if why:
            failures.append((moment, why))
            continue
        top, bottom, left, right = content_box(png, width, height)
        placement = Placement(moment, frame, top, bottom, left, right,
                              width, height)
        check(placement, zone)
        results.append(placement)
        # A frame that measured clean has nothing to look at. One that breached
        # is the only evidence of what went wrong, so it stays.
        if not keep_frames and not placement.problems:
            png.unlink(missing_ok=True)

    ground.unlink(missing_ok=True)
    props.unlink(missing_ok=True)
    if not any(frames_dir.iterdir()):
        frames_dir.rmdir()
    return results, str(frames_dir), failures


def report(results: list[Placement], zone: dict[str, int], where: str,
           failures: list[tuple[float, str]] | None = None) -> int:
    failures = failures or []
    if not results:
        print("Nothing rendered. Is the project finished?")
        for at, why in failures:
            print(f"  {at:.2f}s: {why}")
        return 2

    print(f"Safe zone: top {zone['top']}, bottom {zone['bottom']}, "
          f"sides {zone['side']}\n")
    print(f"{'at':>8}  {'drawn rows':>13}  {'drawn cols':>13}  verdict")
    bad = 0
    for placement in results:
        if placement.empty:
            print(f"{placement.at:>7.2f}s  {'nothing drawn':>13}"
                  f"  {'':>13}  --")
            continue
        rows = f"{placement.top}-{placement.bottom}"
        cols = f"{placement.left}-{placement.right}"
        if placement.problems:
            bad += 1
            print(f"{placement.at:>7.2f}s  {rows:>13}  {cols:>13}  BREACH")
            for problem in placement.problems:
                print(f"{'':>10}{problem}")
        else:
            print(f"{placement.at:>7.2f}s  {rows:>13}  {cols:>13}  ok")

    print()
    for at, why in failures:
        print(f"{at:>7.2f}s  did not render: {why}")
    if failures:
        print()

    if bad:
        print(f"{bad} of {len(results)} sampled frames draw outside the safe zone.")
        print(f"Frames kept in {where} -- look at them.")
        return 1
    if failures:
        print(f"{len(results)} sampled frames stay inside the safe zone, "
              f"but {len(failures)} never rendered, so they were not checked.")
        return 2
    print(f"All {len(results)} sampled frames stay inside the safe zone.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--at", type=float, action="append", default=None,
                        help="check this second instead of the chosen moments")
    parser.add_argument("--keep-frames", action="store_true",
                        help="leave the rendered stills behind to look at")
    args = parser.parse_args()

    if not (args.project / "pipeline.json").is_file():
        print(f"error: no pipeline at {args.project}", file=sys.stderr)
        return 2
    try:
        results, where, failures = verify(
            args.project, args.at, args.keep_frames)
    except (FFmpegMissing, RemotionMissing) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return report(results, safe_zone(), where, failures)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
