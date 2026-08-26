/**
 * Generate public/transcripts/sample.words.json.
 *
 * SYNTHETIC TIMINGS. The text is real output from transcribe/, but the per-word
 * timings here are evenly distributed, not measured. It exists so the Captions
 * composition renders out of the box; point the composition at a real
 * .words.json for anything that matters.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

const TEXT =
  'Min Claude kan nu göra custom formulär med designen av min brand ' +
  'consistently. Det är faktiskt jättelätt att sätta upp det också. ' +
  'Alla svaren hamnar i Google Sheets. Alla bilder hamnar i Google Drive.';

const WORDS_PER_SECOND = 2.6;
const tokens = TEXT.split(/\s+/).filter(Boolean);

let cursor = 0.3;
const words = tokens.map((token) => {
  const duration = token.length / (WORDS_PER_SECOND * 4);
  const entry = {
    word: ` ${token}`,
    start: Number(cursor.toFixed(3)),
    end: Number((cursor + duration).toFixed(3)),
    probability: 0.95,
  };
  // A beat after sentence-ending punctuation, so chunking has a gap to find.
  cursor += duration + (/[.!?]$/.test(token) ? 0.45 : 0.08);
  return entry;
});

const out = join(ROOT, 'public', 'transcripts', 'sample.words.json');
mkdirSync(dirname(out), { recursive: true });
writeFileSync(
  out,
  JSON.stringify(
    {
      _note: 'SYNTHETIC timings for demo purposes. Real text, invented timing.',
      language: 'sv',
      word_count: words.length,
      words,
    },
    null,
    2,
  ),
  'utf8',
);
console.log(`wrote ${words.length} words to ${out}`);
