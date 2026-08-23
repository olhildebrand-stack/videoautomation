/**
 * CYAN VOID — brand invariants, machine-readable.
 *
 * This file is the ONLY place in this project permitted to contain a raw hex
 * value, a raw duration, or a raw spacing number. Every component imports from
 * here. `npm run lint:tokens` enforces that mechanically.
 *
 * Everything below is a hard constraint, not a preference. Do not extend,
 * alias, or interpolate these values.
 */

/* ------------------------------------------------------------------ colour */

/**
 * Hierarchy is brightness, never hue. `flare` reads first, `bone` second,
 * `ash` recedes. Never signal importance with a colour change — only with a
 * position on that ladder.
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

/** `--accent` is an alias of `--flare`. There is no second accent colour. */
export const accent = color.flare;

export type ColorToken = keyof typeof color;

/* -------------------------------------------------------------------- type */

/** The four roles. There are no others. */
export const font = {
  /** Headers only, two or three per frame at most. */
  display: {
    fontFamily: 'Allerta Stencil',
    fontWeight: 400,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  /** Anything actionable. */
  ui: {
    fontFamily: 'Rajdhani',
    fontWeight: 600,
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  /** Anything that names, counts, or labels. Sizes 11–12px only. */
  mono: {
    fontFamily: 'IBM Plex Mono',
    fontWeight: 400,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
  },
  /** Running text only. Sentence case. */
  body: {
    fontFamily: 'IBM Plex Sans',
    fontWeight: 400,
    letterSpacing: 'normal',
    textTransform: 'none',
    lineHeight: 1.6,
  },
} as const;

export type FontRole = keyof typeof font;

/**
 * The type scale exactly as CYANVOID.md writes it, in design px.
 *
 * These are the reference values. Nothing renders them directly — see
 * `videoScale` below for why, and `fontSize` for what components actually use.
 */
export const fontSizeSpec = {
  xs: 11,
  sm: 12,
  md: 14,
  lg: 16,
  xl: 20,
  '2xl': 28,
  '3xl': 42,
  '4xl': 68,
  '5xl': 104,
} as const;

export type FontSizeToken = keyof typeof fontSizeSpec;

/**
 * CYANVOID.md's scale is sized for a 1440x900 design surface read at desk
 * distance. This project renders 1080x1920 short-form, watched on a phone
 * roughly 390pt wide — a 2.77x downscale, which puts the 12px mono layer at
 * about 4pt and body text at about 7pt on the actual device. Unreadable.
 *
 * So the scale is multiplied by one uniform factor for the video medium. Every
 * ratio in the spec is preserved exactly and the scale stays closed — this is a
 * change of viewing distance, not a new set of sizes. Set to 1 for
 * pixel-exact spec values on a desktop-sized surface.
 */
export const videoScale = 2;

/** The scale as rendered. This is what components consume. */
export const fontSize = {
  xs: fontSizeSpec.xs * videoScale,
  sm: fontSizeSpec.sm * videoScale,
  md: fontSizeSpec.md * videoScale,
  lg: fontSizeSpec.lg * videoScale,
  xl: fontSizeSpec.xl * videoScale,
  '2xl': fontSizeSpec['2xl'] * videoScale,
  '3xl': fontSizeSpec['3xl'] * videoScale,
  '4xl': fontSizeSpec['4xl'] * videoScale,
  '5xl': fontSizeSpec['5xl'] * videoScale,
} as const;

/** The mono layer is restricted to the spec's 11–12px steps. */
export const monoFontSize = {
  xs: fontSize.xs,
  sm: fontSize.sm,
} as const;

/** The four families, for `@remotion/google-fonts`. */
export const fontFamilies = [
  'Allerta Stencil',
  'Rajdhani',
  'IBM Plex Mono',
  'IBM Plex Sans',
] as const;

/* ---------------------------------------------------------------- geometry */

/** Zero, every corner, every element. */
export const radius = 0;

/**
 * The single exception: 6px, permitted ONLY on individual message rows inside a
 * conversation component, and ONLY in b-roll. Not on the container the messages
 * sit in. Not on cards, panels, inputs, buttons, avatars, or badges.
 *
 * Consume this through `<MessageRow>` — nothing else should import it.
 */
export const radiusMsg = 6;

/** Borders and dividers are 1px hairlines. Never thicker, never doubled. */
export const borderWidth = 1;
export const border = `${borderWidth}px solid ${color.seam}`;

/** All spacing is a multiple of 8. */
export const spacingBase = 8;

/** Named steps on the 8px grid. */
export const space = {
  '1': spacingBase * 1,
  '2': spacingBase * 2,
  '3': spacingBase * 3,
  '4': spacingBase * 4,
  '5': spacingBase * 5,
  '6': spacingBase * 6,
  '8': spacingBase * 8,
  '10': spacingBase * 10,
  '12': spacingBase * 12,
  '16': spacingBase * 16,
} as const;

export type SpaceToken = keyof typeof space;

/** Arbitrary steps on the same grid: `spacing(3)` → `24`. */
export const spacing = (steps: number): number => steps * spacingBase;

/* ------------------------------------------------------------------ motion */

/** The curve never changes. Only the durations do. */
export const easingBezier = [0.32, 0.72, 0, 1] as const;

/** The same curve as a CSS string, for non-Remotion surfaces. */
export const easingCss = `cubic-bezier(${easingBezier.join(', ')})`;

/** Interfaces, sites, anything the user drives. Milliseconds. */
export const productTempoMs = {
  out: 180,
  in: 240,
  state: 200,
} as const;

/** Short-form video, cut against speech. Anything rendered to video. */
export const brollTempoMs = {
  out: 90,
  in: 120,
  state: 100,
} as const;

export type TempoPhase = keyof typeof brollTempoMs;
export type TempoMs = typeof brollTempoMs;

/**
 * Everything in this project renders to video, so `brollTempoMs` is the tempo.
 * Product timings read as sluggish here. Do not invent a third tempo, and do
 * not blend the two within a single clip.
 */
export const tempoMs = brollTempoMs;

/* ------------------------------------------------------------------- video */

/** Frame rate for every composition. Durations convert against this. */
export const fps = 30;

/** Vertical short-form. */
export const dimensions = {
  width: 1080,
  height: 1920,
} as const;

/** Clips are on screen for two or three seconds total. */
export const clipDurationInFrames = fps * 3;

/** Milliseconds to whole frames, never rounding a visible beat down to zero. */
export const msToFrames = (ms: number, rate: number = fps): number =>
  Math.max(1, Math.round((ms / 1000) * rate));

/** The tempo, pre-converted to frames at the project frame rate. */
export const tempoFrames = {
  out: msToFrames(tempoMs.out),
  in: msToFrames(tempoMs.in),
  state: msToFrames(tempoMs.state),
} as const;

/* --------------------------------------------------------- editorial timing */

/*
 * CYANVOID.md fixes the duration of a transition; it does not say how long to
 * wait between one beat and the next, or how long a landed state should hold
 * before the clip cuts. Those are editorial, not brand, so they live here —
 * separately labelled — rather than being invented inline in a composition.
 *
 * They are gaps between beats, not transition durations: they do not replace
 * the tempo above, and they must never be used as one.
 */

/** Gap between successive elements entering. One idea per beat. */
export const beatInFrames = Math.round(fps * 0.35);

/** How long a landed state holds on screen before the exit begins. */
export const holdInFrames = Math.round(fps * 0.6);

/**
 * Leading for the display face. CYANVOID.md fixes line-height for body text
 * only; at 1080 wide a headline wraps, so it needs a defined one. Tight, so a
 * two-line headline still reads as a single block.
 */
export const displayLineHeight = 1.05;

/* ----------------------------------------------------------- the one gesture */

/**
 * Emphasis is a solid flare fill with the text knocked out in void. That is the
 * entire vocabulary for active, selected, checked, and hovered — and in b-roll,
 * the beat a message lands on. No glow, no scale, no shadow, no border
 * animation, no colour shift.
 */
export const emphasis = {
  backgroundColor: color.flare,
  color: color.void,
} as const;

/** The resting state the inversion cuts away from. */
export const resting = {
  backgroundColor: color.slab,
  color: color.bone,
} as const;

/* --------------------------------------------------------------------- css */

/** Drop into a `:root` block. Names match the custom properties in CYANVOID.md. */
export const cssVariables = {
  '--void': color.void,
  '--slab': color.slab,
  '--seam': color.seam,
  '--ash': color.ash,
  '--bone': color.bone,
  '--flare': color.flare,
  '--accent': accent,
  '--radius-msg': `${radiusMsg}px`,
} as const;

export const tokens = {
  color,
  accent,
  font,
  fontSizeSpec,
  videoScale,
  fontSize,
  monoFontSize,
  fontFamilies,
  radius,
  radiusMsg,
  border,
  borderWidth,
  spacingBase,
  space,
  easingBezier,
  easingCss,
  productTempoMs,
  brollTempoMs,
  tempoMs,
  tempoFrames,
  beatInFrames,
  holdInFrames,
  displayLineHeight,
  fps,
  dimensions,
  clipDurationInFrames,
  emphasis,
  resting,
  cssVariables,
} as const;

export default tokens;
