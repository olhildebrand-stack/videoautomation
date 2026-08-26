import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hook, radius, radiusMsg } from '../tokens.ts';

test('the hook card is rounded', () => {
  assert.equal(hook.radius, 24);
});

test('rounding the hook card did not round anything else', () => {
  // CYANVOID.md: zero, every corner, every element. The hook card and the
  // b-roll message row are the only two named departures, and each carries its
  // own token so no third can be added by accident.
  assert.equal(radius, 0);
  assert.equal(radiusMsg, 6);
});

test('the hook corner registers at 1080 wide without becoming a pill', () => {
  assert.ok(hook.radius > radiusMsg, "too subtle to read at arm's length");
  assert.ok(hook.radius < 60, 'reads as a pill, not a plate');
});
