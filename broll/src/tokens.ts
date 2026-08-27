/**
 * Every colour, duration and spacing this project draws with.
 *
 * This file is the ONLY place permitted to contain a raw hex value, a raw
 * duration, or a raw spacing number. Every component imports from here.
 * `npm run lint:tokens` enforces that mechanically.
 *
 * The point is consistency between videos, not a brand to obey: the values
 * below were arrived at by watching renders, and a new one is added here when
 * a clip needs it rather than written inline. This file began as CYAN VOID's
 * invariants; those limits were dropped, and only the discipline stayed.
 */

/* ------------------------------------------------------------------ colour */

/**
 * The ground and the text ladder every clip starts from: `flare` reads first,
 * `bone` second, `ash` recedes. Colour beyond this -- a green line, a red one,
 * a logo's own -- is added where a clip needs it, not withheld.
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

/** `--accent` is an alias of `--flare`: the default emphasis, not the only one. */
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

/**
 * Caption styling for talking-head video.
 *
 * DEPARTS FROM CYANVOID.md, deliberately and on instruction. Burned-in
 * captions over footage are white with a black outline, in a bold grotesque --
 * the short-form convention, and what the reference the brief supplied uses.
 * The Cyan Void ladder assumes a controlled void ground; over live footage the
 * flare/bone pair loses legibility, and the spec's remedies (a slab panel) were
 * rejected as looking boxed-in.
 *
 * Confined to captions. Nothing else may use these values.
 */
export const caption = {
  /** "Classic" in the Edits app. Inter ExtraBold is the chosen match. */
  fontFamily: 'Inter',
  fontWeight: 800,
  fill: '#FFFFFF',
  stroke: '#000000',
  /** Stroke scales with the type, so it holds at any size. */
  strokeRatio: 0.08,
  letterSpacing: '-0.01em',
  lineHeight: 1.15,
  /**
   * Measured off the reference reels: every one of them sets captions in
   * uppercase, one word at a time. At a single word a line has room for the
   * extra width caps cost, and the shape of the block stops changing between
   * cuts -- which is most of why the style reads as deliberate.
   */
  transform: 'uppercase',
} as const;

/**
 * Platform-safe insets for vertical video, in px at 1080x1920.
 *
 * Instagram and TikTok draw their own furniture over the frame: the header and
 * status bar along the top, the caption, handle and action rail along the
 * bottom and right. Anything inside these bands is liable to be covered, and
 * a caption half behind a Follow button is worse than no caption.
 *
 * The bottom is the largest because it carries the most: caption text, the
 * audio ticker, and the button column. Values are the conservative end of the
 * range rather than the average -- being 30px too cautious costs nothing,
 * being 30px too bold loses a word.
 */
export const safeZone = {
  top: 220,
  bottom: 450,
  side: 100,
} as const;

/* ---------------------------------------------------------------- overlays */

/**
 * The overlay layer: emoji, graphs, screenshots and mockups cut in over the
 * talking head, each triggered by a phrase in the speech.
 *
 * THIS LAYER IS NOT GOVERNED BY CYANVOID.md. The spec fixes a six-colour
 * brightness ladder, radius 0, fade-only motion and one easing curve, and
 * rules out emoji and photographic content. Every effect here breaks at least
 * one of those, on instruction. What survives from that discipline is the rule
 * that made it work: these values live here and nowhere else, so the fifth
 * video looks like the first.
 */
export const overlay = {
  /** Rising, good, winning. */
  green: '#22C55E',
  /** Falling, losing, put out of business. */
  red: '#EF4444',
  /** Effort and workload -- falling is good here, so it is not red. */
  lightBlue: '#38BDF8',
  ink: '#FFFFFF',
  shadow: '#000000',
} as const;

export type OverlayColour = keyof typeof overlay;

/**
 * Enter rising, leave falling. The one gesture the whole overlay layer uses:
 * a short fade paired with a short vertical travel, up on the way in and
 * continuing down on the way out.
 *
 * CYANVOID forbids exactly this ("Fade, do not travel"). It is the house style
 * for this layer now.
 */
export const overlayMotion = {
  inMs: 260,
  outMs: 200,
  /** How far it travels, in px at 1080 wide. Enough to read as a rise. */
  travel: 48,
  /** Between one element and the next in a sequence. */
  stagger: 140,
} as const;

/**
 * The push-in on a beat that has to land harder than the rest.
 *
 * Not an overlay: this scales the footage itself, so it is the one effect that
 * touches the picture rather than sitting on it. Reserved for a hook -- used
 * anywhere else it stops reading as emphasis and starts reading as drift.
 *
 * Snap in, HOLD, snap out. The first version crept in across the whole
 * sentence on a quart curve, which was watched and rejected: a zoom that
 * arrives slowly reads as a camera drifting, and by the time it has arrived
 * the line it was emphasising is over. The emphasis is in the jump, and in
 * being already there while the words land.
 */
export const zoom = {
  /**
   * How far in. Chosen by watching: 1.08 was invisible as a snap, and the
   * whole effect is meant to be felt.
   */
  scale: 1.2,
  /** cubic-bezier(0.895, 0.03, 0.685, 0.22) -- the standard quartIn. */
  easing: [0.895, 0.03, 0.685, 0.22],
  /** Getting there. Fast enough to read as a punch, slow enough to be a move. */
  inMs: 300,
  /**
   * Coming back out, finishing ON the leave rather than starting there, so
   * the picture is already normal when the next beat cuts in.
   */
  outMs: 300,
  /**
   * Blur at the fastest point of the ramp, in px, falling to nothing while the
   * push is held. Not real motion blur -- a directionless blur that tracks the
   * rate of change, which at this speed reads as one and costs nothing.
   * Deliberately small: it is there to take the hard edge off a fast scale,
   * not to be seen.
   */
  blurPx: 3,
} as const;

/** Emoji rendered as type, sized off the same scale as everything else. */
export const emojiSize = {
  row: 132,
  solo: 220,
} as const;

/** A screenshot or photo dropped into the frame. */
export const imageCard = {
  radius: 32,
  /** Share of the frame width it occupies. */
  widthRatio: 0.72,
} as const;

/** The fake Claude chat: a light window, not the Cyan Void ground. */
export const chat = {
  background: '#FFFFFF',
  panel: '#F4F4F5',
  border: '#E4E4E7',
  text: '#18181B',
  muted: '#71717A',
  radius: 20,
  windowRadius: 28,
  /** How fast the fake prompt types itself, in characters per second. */
  typeCps: 22,
} as const;

/** The white flash when the camera "takes a picture" of the screen. */
export const flash = {
  colour: '#FFFFFF',
  /** Up fast, down slower: a shutter, not a strobe. */
  upMs: 90,
  downMs: 320,
} as const;

/**
 * Generated screen content, used as b-roll.
 *
 * The reference reels cut away to a full-frame screen recording every couple
 * of seconds. Recording one by hand is a manual step per video, which is the
 * thing this project exists to remove -- so the screen is rendered instead.
 * Deterministic, correct at 1080x1920 without cropping a 16:9 capture, and
 * re-renders when the content changes.
 */
export const terminal = {
  background: '#0C0C10',
  chrome: '#1A1A20',
  border: '#2A2A33',
  text: '#D4D4DC',
  dim: '#6E6E7A',
  accent: '#22C55E',
  warn: '#F59E0B',
  fontFamily: 'IBM Plex Mono',
  fontSize: 34,
  lineHeight: 1.55,
  padding: 44,
  radius: 24,
  /** Lines revealed per second. Fast enough to feel live, slow enough to read. */
  linesPerSecond: 7,
  /** The three window dots. Recognisable enough to place the frame instantly. */
  dots: ['#FF5F57', '#FEBC2E', '#28C840'],
  /**
   * A card in the middle of the frame rather than the whole of it. Full frame
   * covers the speaker completely, which is right when the screen IS the
   * point and wrong when it is illustrating what someone is saying -- there
   * the face has to stay.
   */
  heightShare: 0.34,
} as const;

/**
 * The logo row, measured off the AI-stack reel, which has no cuts at all --
 * the whole video is one take with this row changing above it.
 *
 * The blur is the mechanism: a logo nobody has named yet is present but
 * unreadable, so the viewer knows something is coming and cannot read ahead.
 * Naming it brings it into focus. Nothing is drawn behind or under the mark:
 * a box around it and a word beneath it both say what the caption is already
 * saying.
 */
export const iconCard = {
  /** The square each logo is fitted into. Holds the row's layout still, so a
   * logo coming into focus never shifts its neighbours. */
  size: 190,
  gap: 26,
  /** How unreadable an unnamed icon is. Enough to hide a logo entirely. */
  blur: 22,
  /** The snap into focus. Faster than the fades: it is a reveal, not an entry. */
  focusMs: 220,
} as const;

/**
 * A row of plain chips under the hook: white box, black text, no icon.
 *
 * The same reveal as the icon row -- blurred until named, then snapped into
 * focus -- for a video whose topics are words rather than products. Blurred
 * rather than absent so the viewer can see there are three of them and cannot
 * read ahead to which.
 */
export const chip = {
  background: '#FFFFFF',
  text: '#111111',
  radius: 18,
  fontSize: 40,
  paddingBlock: 16,
  paddingInline: 26,
  gap: 16,
  /**
   * Clearance under the hook card. The hook is two lines at its longest, and
   * this leaves room for that rather than for the shortest possible one --
   * a chip row overlapping the hook is worse than one sitting slightly low.
   */
  belowHook: 300,
  /**
   * The drop to a second row. A video can carry two rows at once -- vas3 holds
   * the three steps across the whole clip while two file names come and go
   * inside one section -- and the second cannot sit on top of the first. One
   * chip is 40px of text plus 16px of padding either side; 100 clears that
   * with a gap.
   */
  rowOffset: 100,
} as const;

/** The question the three cards are answering, in a pill under them. */
export const questionPill = {
  background: '#FFFFFF',
  text: '#18181B',
  radius: 14,
  fontSize: 46,
  paddingBlock: 14,
  paddingInline: 26,
  /**
   * Share of frame height it sits at. The reference puts this at 0.70 -- but
   * that reel carries no word captions, and ours do, at 0.76. Sitting above
   * them keeps both readable; matching the reference exactly would put a
   * subtitle through the middle of the question.
   */
  atHeight: 0.58,
} as const;

/** Graph lines drawn behind or beside a word. */
export const graph = {
  strokeWidth: 14,
  widthRatio: 0.62,
  heightRatio: 0.18,
  /**
   * Fallback only. A line normally draws across the whole time its cue is on
   * screen, so the decline happens at the speed of the sentence describing it.
   * Drawn in a fixed 620ms it was over before the second word landed and read
   * as a squiggle behind the text rather than as a trend.
   */
  drawMs: 620,
  /** The axes that make a line read as a graph rather than as a stroke. */
  axis: '#71717A',
  axisWidth: 4,
  labelSize: 76,
} as const;

/**
 * The hook card: white on a solid black bar, top of frame.
 *
 * DEPARTS FROM CYANVOID.md, deliberately and on instruction. The spec allows
 * exactly one rounded corner in the system -- `radiusMsg`, on b-roll message
 * rows -- and says a frame containing any other is wrong. The hook card is the
 * second, for the same reason the captions were the first: it is not a Cyan
 * Void surface but a platform one, matching the reference the brief supplied,
 * where the hook sits in a rounded plate.
 *
 * Confined to the hook card. `radius` stays 0 everywhere else.
 */
export const hook = {
  fill: '#FFFFFF',
  background: '#000000',
  seconds: 5,
  /** Read at 1080 wide. Large enough to register, short of a pill. */
  radius: 24,
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
  '20': spacingBase * 20,
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
/**
 * The carousel slide: a still, not a clip.
 *
 * 4:5, the shape every reference slide is in. Two layouts only -- a cover,
 * which is a photograph with the claim over it, and a body slide, which is a
 * dark ground carrying one heading, one paragraph, and one picture of the
 * thing being described. Nothing else earned a place: the references run six
 * or seven slides on those two.
 */
/**
 * The two shapes a slide is posted in, and the only thing that differs between
 * them.
 *
 * A carousel is a true 4:5 -- Instagram's largest portrait, and an even number
 * of rows, which matters because a slide carrying video is encoded as yuv420p
 * and an odd height comes out a pixel short of its neighbours.
 *
 * A story is 9:16 with the platform's own furniture over it: the profile row
 * at the top and the reply box at the bottom. `inset` keeps everything clear of
 * both, so nothing that has to be read sits under a button.
 */
export const slideShapes = {
  carousel: {
    height: 1350,
    insetTop: 0,
    insetBottom: 0,
    picture: { top: 660, bottom: 132 },
  },
  story: {
    height: 1920,
    insetTop: 250,
    insetBottom: 300,
    /**
     * Proportionally taller than the carousel's, not the same band on a longer
     * canvas. Scaling 4:5's numbers to 9:16 leaves the picture stranded in the
     * middle with black above and below it, reading as a mistake rather than a
     * composition.
     */
    picture: { top: 890, bottom: 440 },
  },
} as const;

export type SlideShape = keyof typeof slideShapes;

export const slide = {
  width: 1080,
  /** The default, and what a bare `remotion still Slide` renders. */
  height: slideShapes.carousel.height,
  /** Type never comes closer than this to an edge. */
  side: 76,
  ground: color.void,
  /** The pill, and the one clause per slide that carries the point. */
  accent: overlay.lightBlue,
  onAccent: color.void,
  headline: overlay.ink,
  body: color.flare,
  /**
   * Where the picture sits, the same on every body slide of a shape -- as it is
   * on every reference slide. Fixed rather than flowed: a slide whose picture
   * starts wherever its paragraph happened to end reads as a different
   * template, and the hole punched for a video has to be somewhere nameable.
   */
  picture: slideShapes.carousel.picture,
  /** The screenshot sits on a light card, as every reference slide does. */
  card: {
    background: overlay.ink,
    radius: 28,
    /** Lifts the card off the ground without a border. */
    shadow: '#00000066',
    shadowBlur: 60,
    shadowDrop: 18,
  },
  /** A photograph needs the ground darkened where type sits over it. */
  scrim: '#060607CC',
  pill: {
    radius: 999,
    paddingBlock: 14,
    paddingInline: 40,
    size: 40,
  },
  headlineSize: 84,
  bodySize: 46,
  coverSize: 92,
  kickerSize: 38,
  handleSize: 30,
  lineHeight: 1.12,
  bodyLineHeight: 1.28,
} as const;

/**
 * What differs between the three formats, from `howtocutvideo/FORMATS.md`.
 *
 * The type, the margins and the accent are shared -- that is what makes two
 * sequences in different formats still look like one account. Only the ground
 * and the furniture change.
 */
export const slideFormat = {
  /** D: text in the app's own black label boxes, over the photograph. */
  labels: {
    box: '#000000E6',
    radius: 10,
    paddingBlock: 16,
    paddingInline: 26,
    gap: 14,
    scrim: '#00000026',
  },
  /** C: the cover photograph, blurred, behind every slide in the set. */
  blurred: {
    blurPx: 34,
    /** Darkened as well as blurred, or white type will not hold over it. */
    scrim: '#0A0F14B3',
    /** The step number, sitting behind the headline. */
    stepColour: '#FFFFFF40',
    stepSize: 132,
    dot: '#FFFFFF59',
    dotOn: '#FFFFFF',
    dotSize: 12,
    dotGap: 14,
  },
  /** A: a texture as the ground, and the pill above the headline. */
  textured: {
    /** The texture is lifted off pure black so it reads as a surface. */
    scrim: '#00000073',
  },
} as const;

export type SlideFormat = keyof typeof slideFormat;

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

/**
 * Gap between successive elements entering. One idea per beat.
 *
 * Derived, not chosen: it equals the enter duration, so each element settles
 * exactly as the next starts. That satisfies the motion-design skill's 1/3 rule
 * (with three elements, at most one may be in active motion at a time) while
 * keeping a three-element sequence at 400ms, inside the skill's 500ms stagger
 * cap. CYANVOID.md does not speak to stagger, so the skill governs here.
 */
export const beatInFrames = tempoFrames.in;

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
  caption,
  hook,
  safeZone,
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
  slide,
  slideShapes,
  slideFormat,
  clipDurationInFrames,
  emphasis,
  resting,
  cssVariables,
} as const;

export default tokens;
