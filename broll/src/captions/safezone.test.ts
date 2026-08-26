import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dimensions, safeZone } from '../tokens.ts';

test('the safe zone matches the platform figures', () => {
  assert.equal(safeZone.top, 220);
  assert.equal(safeZone.bottom, 450);
  assert.equal(safeZone.side, 100);
});

test('the usable band is still large enough to work in', () => {
  const height = dimensions.height - safeZone.top - safeZone.bottom;
  const width = dimensions.width - safeZone.side * 2;
  assert.ok(height > 1000, `only ${height}px of usable height`);
  assert.ok(width >= 880, `only ${width}px of usable width`);
});

test('the insets take the cautious end of each range', () => {
  // 420-450 for the bottom, 60-100 at the sides: 30px of extra caution costs
  // nothing, 30px of optimism loses a word behind a Follow button.
  assert.ok(safeZone.bottom >= 450);
  assert.ok(safeZone.side >= 100);
});

test('the bottom inset is the largest, since it carries the most furniture', () => {
  assert.ok(safeZone.bottom > safeZone.top);
  assert.ok(safeZone.top > safeZone.side);
});
