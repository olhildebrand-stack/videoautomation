import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pushBlur, pushScale } from './push.ts';
import { zoom } from '../tokens.ts';

const FPS = 30;
const ENTER = 0;
const LEAVE = 114;          // 3.8s, the length of the hook it was built for

test('the picture is untouched before the beat and at its first frame', () => {
  assert.equal(pushScale(-30, FPS, ENTER, LEAVE), 1);
  assert.equal(pushScale(ENTER, FPS, ENTER, LEAVE), 1);
});



const frames = (ms: number) => Math.round((ms / 1000) * FPS);

test('it is all the way in within a fifth of a second', () => {
  // The whole point of the rewrite. Creeping in across the sentence was
  // watched and rejected: the arrival landed after the line it was meant to
  // emphasise, and on the way there it read as a camera drifting.
  assert.equal(pushScale(ENTER + frames(zoom.inMs), FPS, ENTER, LEAVE), zoom.scale);
});

test('it holds all the way through the sentence', () => {
  const held = frames(zoom.inMs) + 5;
  for (let frame = ENTER + held; frame <= LEAVE - frames(zoom.outMs) - 5; frame += 3) {
    assert.equal(pushScale(frame, FPS, ENTER, LEAVE), zoom.scale,
      `frame ${frame} was not holding`);
  }
});

test('it is back to normal ON the leave, not after it', () => {
  // So the next beat cuts in at normal scale rather than mid-pullback.
  assert.equal(pushScale(LEAVE, FPS, ENTER, LEAVE), 1);
  assert.ok(pushScale(LEAVE - frames(zoom.outMs) / 2, FPS, ENTER, LEAVE) < zoom.scale);
  assert.equal(pushScale(LEAVE + 60, FPS, ENTER, LEAVE), 1);
});

test('a beat too short to hold still pushes rather than reversing early', () => {
  // The ramps would cross on a one-second beat. Meeting them in the middle
  // keeps it a push in and back out.
  const short = 20;
  const peak = pushScale(short / 2, FPS, 0, short);
  assert.ok(peak > 1, 'it never went in');
  assert.equal(pushScale(0, FPS, 0, short), 1);
  assert.equal(pushScale(short, FPS, 0, short), 1);
});

test('an unbounded push draws nothing rather than taking the render down', () => {
  // interpolate refuses a range that is not finite. Passing Infinity here
  // failed the whole render on the first frame -- the same shape of crash a
  // null `leave` caused in the overlay layer. The caller resolves "until the
  // end of the clip" to the last frame; anything still unbounded draws
  // nothing, which is visible in the result and cannot crash.
  assert.equal(pushScale(9999, FPS, ENTER, null), 1);
  assert.equal(pushScale(9999, FPS, ENTER, undefined), 1);
  assert.equal(pushScale(9999, FPS, ENTER, Infinity), 1);
});

test('the zoom is big enough to be felt and small enough to stay a zoom', () => {
  // 1.08 was chosen from theory and watched: invisible as a snap. 1.2 was
  // chosen by watching. Past about 1.3 the frame starts losing the speaker's
  // head to the crop, which is a different effect.
  assert.ok(zoom.scale >= 1.15 && zoom.scale <= 1.3);
});

test('the blur is zero while the push is held', () => {
  const held = ENTER + frames(zoom.inMs) + 10;
  assert.equal(pushBlur(held, FPS, ENTER, LEAVE), 0);
});

test('the blur peaks during the ramp and never exceeds its token', () => {
  let peak = 0;
  for (let frame = ENTER; frame <= LEAVE; frame += 1) {
    peak = Math.max(peak, pushBlur(frame, FPS, ENTER, LEAVE));
  }
  assert.ok(peak > 0, 'it never blurred at all');
  assert.ok(peak <= zoom.blurPx + 0.001, `peaked at ${peak}`);
});

test('the blur is slight', () => {
  // It is there to take the hard edge off a fast scale, not to be seen.
  assert.ok(zoom.blurPx <= 4);
});

test('a still picture is never blurred', () => {
  assert.equal(pushBlur(ENTER - 5, FPS, ENTER, LEAVE), 0);
  assert.equal(pushBlur(LEAVE + 30, FPS, ENTER, LEAVE), 0);
});
