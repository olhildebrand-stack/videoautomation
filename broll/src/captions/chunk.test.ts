import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  activeWordIndex, chunkWords, defaultChunkOptions, lineAt,
} from './chunk.ts';
import type { TranscriptWord } from './types.ts';

const w = (word: string, start: number, end: number): TranscriptWord => ({
  word: ` ${word}`,
  start,
  end,
  probability: 0.9,
});

const opts = { maxWords: 3, maxChars: 18, gapSeconds: 0.6 };

test('breaks on the word ceiling', () => {
  const lines = chunkWords([w('a', 0, 1), w('b', 1, 2), w('c', 2, 3), w('d', 3, 4)], opts);
  assert.equal(lines.length, 2);
  assert.deepEqual(lines[0]?.words.map((x) => x.word.trim()), ['a', 'b', 'c']);
});

test('breaks on a silence longer than the gap', () => {
  const lines = chunkWords([w('a', 0, 0.5), w('b', 2.0, 2.5)], opts);
  assert.equal(lines.length, 2, 'a 1.5s silence must split the line');
});

test('breaks after sentence-ending punctuation', () => {
  const lines = chunkWords([w('slut.', 0, 0.5), w('Ny', 0.6, 1.0)], opts);
  assert.equal(lines.length, 2);
  assert.equal(lines[0]?.words.length, 1);
});

test('breaks on the character ceiling before the word ceiling', () => {
  const lines = chunkWords([w('sammanfattning', 0, 1), w('formulärdesign', 1, 2)], opts);
  assert.equal(lines.length, 2, 'two long words exceed maxChars despite being under maxWords');
});

test('line start and end span its words', () => {
  const [line] = chunkWords([w('a', 0.5, 1.0), w('b', 1.1, 1.9)], opts);
  assert.equal(line?.start, 0.5);
  assert.equal(line?.end, 1.9);
});

test('every word survives chunking', () => {
  const words = Array.from({ length: 40 }, (_, i) => w(`ord${i}`, i * 0.4, i * 0.4 + 0.3));
  const total = chunkWords(words, opts).reduce((n, l) => n + l.words.length, 0);
  assert.equal(total, 40);
});

test('lineAt finds the covering line and nothing outside', () => {
  const lines = chunkWords([w('a', 1.0, 2.0)], opts);
  assert.ok(lineAt(lines, 1.5));
  assert.equal(lineAt(lines, 0.2), null);
  assert.equal(lineAt(lines, 9.0), null);
});

test('activeWordIndex tracks the spoken word and reports gaps', () => {
  const [line] = chunkWords([w('a', 0, 0.4), w('b', 0.5, 0.9)], opts);
  assert.ok(line);
  assert.equal(activeWordIndex(line, 0.2), 0);
  assert.equal(activeWordIndex(line, 0.7), 1);
  assert.equal(activeWordIndex(line, 0.45), -1, 'between words nothing is highlighted');
});

test('an empty transcript yields no lines', () => {
  assert.deepEqual(chunkWords([], opts), []);
});

test('captions default to one word, as the reference reels set them', () => {
  const words = ['Jag', 'håller', 'på', 'att', 'bygga'].map((word, i) =>
    w(word, i * 0.4, i * 0.4 + 0.3),
  );
  assert.equal(defaultChunkOptions.maxWords, 1);
  const lines = chunkWords(words, defaultChunkOptions);
  assert.equal(lines.length, words.length, 'one line per word');
});
