import assert from 'node:assert/strict';
import { test } from 'node:test';
import { move, staggerFrames } from './motion.ts';
import { overlayMotion } from '../tokens.ts';

const FPS = 30;

test('an element is invisible and below its resting place before it enters', () => {
  const { opacity, translateY } = move(0, FPS, 30);
  assert.equal(opacity, 0);
  assert.equal(translateY, overlayMotion.travel);
});

test('it has risen into place once the fade completes', () => {
  const { opacity, translateY } = move(60, FPS, 30);
  assert.equal(opacity, 1);
  assert.equal(translateY, 0);
});

test('travel and fade cannot drift apart', () => {
  // The bug this prevents: an element fully opaque but still sliding, or
  // settled but still transparent. Both read as a glitch.
  for (let frame = 30; frame <= 60; frame += 1) {
    const { opacity, translateY } = move(frame, FPS, 30);
    if (opacity === 1) assert.equal(translateY, 0);
    if (opacity === 0) assert.equal(translateY, overlayMotion.travel);
  }
});

test('it leaves downward, not back the way it came', () => {
  const during = move(90, FPS, 30, 90);
  const after = move(120, FPS, 30, 90);
  assert.equal(during.translateY, 0);
  assert.ok(after.translateY > 0, 'it should exit downward');
  assert.equal(after.opacity, 0);
});

test('an element with no exit stays up', () => {
  assert.equal(move(600, FPS, 30).opacity, 1);
});

test('a sequence steps by the stagger, and the first waits for nobody', () => {
  assert.equal(staggerFrames(0, FPS), 0);
  const step = staggerFrames(1, FPS);
  assert.equal(staggerFrames(3, FPS), step * 3);
  assert.ok(step > 0);
});

test('the whole stagger of four stays under half a second', () => {
  // Four emoji landing one after another is the longest sequence planned.
  // Past ~500ms a stagger stops reading as rhythm and starts reading as lag.
  assert.ok(staggerFrames(3, FPS) / FPS < 0.5);
});

test('a null exit means "stays up", the same as no exit at all', () => {
  // The pipeline sends null for `until: "end"`. Treated as a number it reached
  // interpolate as [null, null + n] and failed the render on frame 3.
  assert.equal(move(600, FPS, 30, null).opacity, 1);
  assert.equal(move(600, FPS, 30, null).translateY, 0);
  assert.deepEqual(move(600, FPS, 30, null), move(600, FPS, 30, undefined));
});
