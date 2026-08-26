import { Easing, interpolate } from 'remotion';
import { easingBezier, tempoFrames } from './tokens';

/**
 * The one curve. Fast out of the gate, long settle, no overshoot. Every
 * animated value in this project goes through this easing — there is no second
 * curve, and no spring anywhere.
 */
export const easing = Easing.bezier(...easingBezier);

/**
 * Fade in over the b-roll enter tempo, starting at `startFrame`.
 *
 * Fade, do not travel: this returns opacity and nothing else. One idea per
 * beat — never pair it with a transform.
 */
export const fadeIn = (frame: number, startFrame: number = 0): number =>
  interpolate(frame, [startFrame, startFrame + tempoFrames.in], [0, 1], {
    easing,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

/** Fade out over the b-roll exit tempo, ending on `endFrame`. */
export const fadeOut = (frame: number, endFrame: number): number =>
  interpolate(frame, [endFrame - tempoFrames.out, endFrame], [1, 0], {
    easing,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

/** Fade in, hold, fade out — the shape of every element in a b-roll clip. */
export const fadeInOut = (
  frame: number,
  startFrame: number,
  endFrame: number,
): number => Math.min(fadeIn(frame, startFrame), fadeOut(frame, endFrame));

/**
 * A state change on the b-roll state tempo, returning 0 → 1 across the switch.
 *
 * Used to cross-fade between the resting and inverted treatments. The
 * inversion is the beat — nothing scales, nothing moves.
 */
export const stateChange = (frame: number, atFrame: number): number =>
  interpolate(frame, [atFrame, atFrame + tempoFrames.state], [0, 1], {
    easing,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
