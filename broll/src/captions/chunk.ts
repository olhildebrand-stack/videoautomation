import type { CaptionLine, TranscriptWord } from './types';

export type ChunkOptions = {
  /** Hard ceiling on words per line. */
  maxWords: number;
  /** Hard ceiling on characters per line, so long words do not overflow. */
  maxChars: number;
  /** A silence at least this long forces a break, in seconds. */
  gapSeconds: number;
};

/**
 * Tuned for 1080-wide vertical at the 3xl step.
 *
 * The character ceiling is deliberately conservative: it counts characters, but
 * what actually overflows is rendered width, and a line of wide glyphs
 * ("designen") wraps well before a line of narrow ones. Wrapping strands a
 * single word on a second row, which reads as a mistake, so the ceiling is set
 * low enough that a line stays on one row.
 */
export const defaultChunkOptions: ChunkOptions = {
  // One word at a time, as every reference reel does. Three words asks the
  // viewer to read a line; one word asks nothing -- it arrives already read,
  // and lands on the syllable being spoken.
  maxWords: 1,
  maxChars: 18,
  gapSeconds: 0.6,
};

/** Sentence-ending punctuation is the most natural place to break. */
const endsSentence = (word: string): boolean => /[.!?…]["')\]]?\s*$/.test(word);

/**
 * Group words into caption lines.
 *
 * Breaks on, in order of priority: a sentence ending, a silence longer than
 * `gapSeconds`, then the word and character ceilings. Breaking on speech
 * rather than on a fixed word count keeps a line from straddling two thoughts.
 */
export const chunkWords = (
  words: TranscriptWord[],
  options: ChunkOptions = defaultChunkOptions,
): CaptionLine[] => {
  const lines: CaptionLine[] = [];
  let current: TranscriptWord[] = [];

  const flush = () => {
    if (current.length === 0) return;
    const first = current[0];
    const last = current[current.length - 1];
    if (!first || !last) return;
    lines.push({ words: current, start: first.start, end: last.end });
    current = [];
  };

  for (const word of words) {
    const previous = current[current.length - 1];
    const gap = previous ? word.start - previous.end : 0;
    const charCount = current.reduce((total, w) => total + w.word.length, 0);

    const tooLong =
      current.length >= options.maxWords ||
      charCount + word.word.length > options.maxChars;

    if (current.length > 0 && (gap >= options.gapSeconds || tooLong)) {
      flush();
    }

    current.push(word);

    if (endsSentence(word.word)) {
      flush();
    }
  }

  flush();
  return lines;
};

/** The line covering `time`, or the next one up, so there is never a blank hold. */
export const lineAt = (lines: CaptionLine[], time: number): CaptionLine | null => {
  for (const line of lines) {
    if (time >= line.start && time <= line.end) return line;
  }
  return null;
};

/** Index of the word being spoken at `time`, or -1 between words. */
export const activeWordIndex = (line: CaptionLine, time: number): number =>
  line.words.findIndex((word) => time >= word.start && time <= word.end);
