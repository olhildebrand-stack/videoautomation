/**
 * CYAN VOID — brand invariants, machine-readable.
 *
 * Generated from CYANVOID.md. These values are hard constraints, not defaults:
 * do not extend, alias, or interpolate them. If a surface needs a value that is
 * not in this file, the surface is wrong.
 */

/* ------------------------------------------------------------------ colour */

/**
 * Hierarchy is brightness, never hue. `flare` reads first, `bone` second,
 * `ash` recedes. There is no second accent colour in the system.
 */
export const color = {
  /** Ground. Every frame starts here. */
  void: '#060607',
  /** Surfaces and panels sitting on the ground. */
  slab: '#101012',
  /** Every 1px border and divider. */
  seam: '#1E1E21',
  /** Labels, metadata, timestamps. Deliberately fails contrast for body text. */
  ash: '#5E7B86',
  /** Body text and ordinary content. */
  bone: '#A6D2E2',
  /** Headlines, emphasis, and the inverted fill. */
  flare: '#DAF5FF',
} as const;

/** `--accent` is an alias of `--flare`. There is no other accent. */
export const accent = color.flare;

export type ColorToken = keyof typeof color;

/* -------------------------------------------------------------------- type */

export const font = {
  /** Headers only, two or three per frame at most. */
  display: {
    family: 'Allerta Stencil',
    weight: 400,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  /** Anything actionable. */
  ui: {
    family: 'Rajdhani',
    weight: 600,
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  /** Anything that names, counts, or labels. Sizes 11–12px only. */
  mono: {
    family: 'IBM Plex Mono',
    weight: 400,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
  },
  /** Running text only. */
  body: {
    family: 'IBM Plex Sans',
    weight: 400,
    letterSpacing: 'normal',
    textTransform: 'none',
    lineHeight: 1.6,
  },
} as const;

export type FontRole = keyof typeof font;

/** The whole type scale, in px. Stay on it. */
export const fontSize = [11, 12, 14, 16, 20, 28, 42, 68, 104] as const;

export type FontSize = (typeof fontSize)[number];

/** The four families, for a Google Fonts request. */
export const fontFamilies = [
  'Allerta Stencil',
  'Rajdhani',
  'IBM Plex Mono',
  'IBM Plex Sans',
] as const;

/* ---------------------------------------------------------------- geometry */

/** Zero, everywhere, on every element. */
export const radius = 0;

/**
 * The single exception. Permitted only on individual message rows inside a
 * conversation component, and only in motion b-roll. Never in product UI, never
 * on the container, never on anything else.
 */
export const radiusMsg = '6px';

/** Borders and dividers are 1px hairlines. Never thicker, never doubled. */
export const border = `1px solid ${color.seam}` as const;
export const borderWidth = 1;

/** All spacing is a multiple of 8. */
export const spacingBase = 8;

/** `spacing(3)` → `'24px'`. */
export const spacing = (steps: number): string => `${steps * spacingBase}px`;

/* ------------------------------------------------------------------ motion */

/** The curve never changes. Only the durations do. */
export const easing = 'cubic-bezier(0.32, 0.72, 0, 1)';

/** Interfaces, sites, anything the user drives. */
export const productTempo = {
  out: 180,
  in: 240,
  state: 200,
} as const;

/** Short-form video, cut against speech. Anything rendered to video. */
export const brollTempo = {
  out: 90,
  in: 120,
  state: 100,
} as const;

export type Tempo = typeof productTempo | typeof brollTempo;
export type TempoName = keyof typeof productTempo;

/** `transition('in', brollTempo)` → `'120ms cubic-bezier(0.32, 0.72, 0, 1)'`. */
export const transition = (
  phase: TempoName,
  tempo: Tempo = productTempo,
): string => `${tempo[phase]}ms ${easing}`;

/* ----------------------------------------------------------- the one gesture */

/**
 * Emphasis is a solid flare fill with the text knocked out in void. That is the
 * entire vocabulary for active, selected, checked, and hovered. No glow, no
 * scale, no shadow, no border animation, no colour shift.
 */
export const emphasis = {
  background: color.flare,
  color: color.void,
} as const;

/* ---------------------------------------------------------------- css vars */

/** Drop into a `:root` block. Matches the custom property names in CYANVOID.md. */
export const cssVariables = {
  '--void': color.void,
  '--slab': color.slab,
  '--seam': color.seam,
  '--ash': color.ash,
  '--bone': color.bone,
  '--flare': color.flare,
  '--accent': accent,
  '--radius-msg': radiusMsg,
} as const;

export const tokens = {
  color,
  accent,
  font,
  fontSize,
  fontFamilies,
  radius,
  radiusMsg,
  border,
  borderWidth,
  spacingBase,
  easing,
  productTempo,
  brollTempo,
  emphasis,
  cssVariables,
} as const;

export default tokens;
