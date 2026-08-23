/**
 * Enforces the one rule this project cannot express in the type system:
 * nothing outside src/tokens.ts may write a raw hex value, a raw duration, or
 * the easing curve by hand.
 *
 * Run with `npm run lint:tokens`.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { extname, join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const SOURCE_DIRS = ['src', 'scripts'];
const SOURCE_EXTS = new Set(['.ts', '.tsx', '.mjs', '.js', '.jsx', '.css']);

/** The single file permitted to hold literal brand values. */
const TOKENS_FILE = join('src', 'tokens.ts');
/** This checker necessarily contains the patterns it searches for. */
const SELF = join('scripts', 'check-tokens.mjs');

const RULES = [
  {
    name: 'raw hex colour',
    pattern: /#[0-9a-fA-F]{3,8}\b/g,
    hint: 'import the colour from tokens.ts (color.void, color.flare, …)',
  },
  {
    name: 'raw ms duration',
    pattern: /\b\d+\s*ms\b/g,
    hint: 'use tempoMs / tempoFrames from tokens.ts',
  },
  {
    name: 'hand-written easing curve',
    pattern: /cubic-bezier\s*\(/g,
    hint: 'use easing from motion.ts, or easingCss from tokens.ts',
  },
  {
    name: 'raw rgb()/hsl() colour',
    pattern: /\b(?:rgba?|hsla?)\s*\(/g,
    hint: 'import the colour from tokens.ts',
  },
];

const walk = (dir) => {
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (SOURCE_EXTS.has(extname(entry))) out.push(full);
  }
  return out;
};

const files = SOURCE_DIRS.flatMap((dir) => {
  const full = join(ROOT, dir);
  try {
    return walk(full);
  } catch {
    return [];
  }
});

const violations = [];

for (const file of files) {
  const rel = relative(ROOT, file);
  if (rel === TOKENS_FILE || rel === SELF) continue;

  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, index) => {
    // Comments explain the constraints, so they may name the values.
    const code = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '');
    for (const rule of RULES) {
      rule.pattern.lastIndex = 0;
      const match = rule.pattern.exec(code);
      if (match) {
        violations.push(
          `${rel}:${index + 1}  ${rule.name} "${match[0]}"\n    → ${rule.hint}`,
        );
      }
    }
  });
}

if (violations.length > 0) {
  console.error(
    `\ntokens: ${violations.length} violation(s). ` +
      `Only ${TOKENS_FILE} may contain literal brand values.\n`,
  );
  for (const violation of violations) console.error(`  ${violation}\n`);
  process.exit(1);
}

console.log(
  `tokens: clean — ${files.length} files checked, ` +
    `every brand value comes from ${TOKENS_FILE}.`,
);
