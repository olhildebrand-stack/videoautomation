import { Easing, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { framesFor } from './motion.ts';
import { zoom } from '../tokens.ts';

/**
 * A push into the picture: in fast, held, out fast.
 *
 * The only effect here that touches the footage rather than sitting on it, so
 * it is not drawn by `Overlays` -- `CaptionedVideo` reads it and scales the
 * video layer. A zoom drawn on top of the frame would scale the captions and
 * the hook card with it, which is the opposite of what a push is for.
 *
 * It used to creep in across the whole beat. Watched, that reads as a camera
 * drifting, and the arrival lands after the line it was meant to emphasise.
 * The emphasis is in the jump and in being already there while the words land,
 * so: 220ms in, hold for the sentence, 220ms out finishing ON the leave rather
 * than starting there -- the picture is normal again before the next cut.
 */
export const pushScale = (
  frame: number,
  fps: number,
  enter: number,
  leave: number | null | undefined,
  scale: number = zoom.scale,
): number => {
  const [a, b, c, d] = zoom.easing;
  const ease = Easing.bezier(a, b, c, d);

  // A push has to know where it ends: `interpolate` refuses a range that is
  // not finite, so passing Infinity here took the whole render down rather
  // than producing a zoom that never stopped. The caller resolves "until the
  // end of the clip" to the last frame; anything still unbounded here draws
  // nothing, which is visible in the result and cannot crash.
  if (leave === undefined || leave === null || !Number.isFinite(leave)) return 1;

  const inFrames = framesFor(zoom.inMs, fps);
  const outFrames = framesFor(zoom.outMs, fps);

  // On a beat too short to hold, the two ramps would cross and the zoom would
  // reverse before arriving. Meeting them in the middle keeps it a push.
  const middle = (enter + leave) / 2;
  const arrived = Math.min(enter + inFrames, middle);
  const leaving = Math.max(leave - outFrames, middle);

  return interpolate(
    frame,
    [enter, arrived, leaving, leave],
    [1, scale, scale, 1],
    { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
};

/**
 * Blur to pair with the scale, in px, tracking how fast the push is moving.
 *
 * Not real motion blur: a directionless blur that rises with the rate of
 * change and is zero while the push is held. At 300ms for a fifth of the frame
 * that reads as motion blur and costs one CSS filter.
 */
export const pushBlur = (
  frame: number,
  fps: number,
  enter: number,
  leave: number | null | undefined,
  scale: number = zoom.scale,
): number => {
  const now = pushScale(frame, fps, enter, leave, scale);
  const next = pushScale(frame + 1, fps, enter, leave, scale);
  const moving = Math.abs(next - now);
  // The fastest the ramp can move: the whole distance over its own length.
  const fastest = (scale - 1) / framesFor(zoom.inMs, fps);
  if (fastest <= 0) return 0;
  return Math.min(1, moving / fastest) * zoom.blurPx;
};


/** The scale to apply at this frame, from every push cue on the sheet. */
export const usePush = (
  cues: { kind: string; enter: number; leave?: number | null; scale?: number }[],
): number => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const pushes = cues.filter((cue) => cue.kind === 'push');
  if (pushes.length === 0) return 1;
  // `until: "end"` arrives as null. For a push that means the last frame of
  // the clip, which is a number the curve can use.
  const ends = (cue: { leave?: number | null }) => cue.leave ?? durationInFrames;
  // Whichever is furthest in right now. Two pushes overlapping is a mistake in
  // the sheet, not a case to blend: taking the larger keeps it obvious.
  return Math.max(
    ...pushes.map((cue) => pushScale(frame, fps, cue.enter, ends(cue), cue.scale)),
  );
};

/** The blur to apply at this frame, from every push cue on the sheet. */
export const usePushBlur = (
  cues: { kind: string; enter: number; leave?: number | null; scale?: number }[],
): number => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const pushes = cues.filter((cue) => cue.kind === 'push');
  if (pushes.length === 0) return 0;
  return Math.max(
    ...pushes.map((cue) =>
      pushBlur(frame, fps, cue.enter, cue.leave ?? durationInFrames, cue.scale)),
  );
};
