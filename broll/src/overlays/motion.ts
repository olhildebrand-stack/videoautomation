import type React from 'react';
import { Easing, interpolate } from 'remotion';
import { overlayMotion } from '../tokens.ts';

/**
 * Enter rising, leave falling.
 *
 * The whole overlay layer moves one way: a short fade paired with a short
 * vertical travel, upward on the way in and continuing downward on the way
 * out. Nothing scales, nothing bounces, nothing arrives from the side. One
 * gesture used everywhere is what makes ten unrelated effects read as one
 * video.
 *
 * (CYANVOID.md forbids pairing a fade with a transform at all. That rule does
 * not govern this layer -- see `overlay` in tokens.ts.)
 */

/** Out fast, settle long. No overshoot. */
export const ease = Easing.bezier(0.22, 1, 0.36, 1);

export const framesFor = (ms: number, fps: number): number =>
  Math.max(1, Math.round((ms / 1000) * fps));

export type Move = { opacity: number; translateY: number };

/**
 * Where an element is at `frame`, given when it enters and when it leaves.
 *
 * Both are absolute frames within the composition. An element with no `leave`
 * stays up until the clip ends.
 */
export const move = (
  frame: number,
  fps: number,
  enter: number,
  // Nullable, not just optional. "stays until the clip ends" arrives from the
  // pipeline as JSON null, and a `=== undefined` check let it through into
  // interpolate, which failed the whole render on frame 3.
  leave?: number | null,
): Move => {
  const inFrames = framesFor(overlayMotion.inMs, fps);
  const outFrames = framesFor(overlayMotion.outMs, fps);

  const rising = interpolate(frame, [enter, enter + inFrames], [0, 1], {
    easing: ease,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const falling =
    leave === undefined || leave === null
      ? 1
      : interpolate(frame, [leave, leave + outFrames], [1, 0], {
          easing: ease,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });

  // Travel tracks the fade rather than running on its own clock, so the two
  // cannot drift apart: fully faded in is fully settled, always.
  return {
    opacity: Math.min(rising, falling),
    translateY:
      (1 - rising) * overlayMotion.travel + (1 - falling) * overlayMotion.travel,
  };
};

/** `move` as a style object, for spreading onto a div. */
export const moveStyle = (
  frame: number,
  fps: number,
  enter: number,
  leave?: number | null,
): React.CSSProperties => {
  const { opacity, translateY } = move(frame, fps, enter, leave);
  return { opacity, transform: `translateY(${translateY}px)` };
};

/** The nth element of a staggered sequence enters this many frames late. */
export const staggerFrames = (index: number, fps: number): number =>
  index * framesFor(overlayMotion.stagger, fps);
