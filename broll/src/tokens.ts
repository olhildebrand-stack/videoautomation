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
/**
 * A format's type sizes were tuned on one canvas and have to hold their
 * presence on the other. The same 86px headline fills a quarter of a 4:5
 * frame and a sixth of a 9:16 one -- identical in pixels, and visibly
 * smaller. `typeScale` buys that back. It stops at 1.3 rather than the 1.42
 * the heights imply, because the frames are the same 1080 wide and a longer
 * headline starts to wrap.
 */
export const slideShapes = {
  carousel: {
    typeScale: 1,
    height: 1350,
    insetTop: 0,
    insetBottom: 0,
    picture: { top: 660, bottom: 132 },
  },
  story: {
    typeScale: 1.3,
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
  /**
   * White. Every reference slide, in every one of the six formats, sets its
   * type in white -- there is no second text colour shared between them. A
   * format that wants an accent declares its own below.
   */
  ink: overlay.ink,
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
  /**
   * White type over a photograph, held up by a shadow rather than by more
   * scrim -- which is how the reference reels do it, and it costs the picture
   * nothing. A darker gradient buys the same legibility by covering half the
   * photograph, which is not a trade worth making.
   */
  lift: '0 4px 24px #000000A6',
  pill: {
    radius: 999,
    paddingBlock: 14,
    paddingInline: 40,
    size: 40,
  },
  coverSize: 92,
  handleSize: 30,
} as const;

/**
 * The three formats, each read off its own reference set.
 *
 * They are meant to look like different posts, not one template recoloured, so
 * a format owns its palette, its weights, its alignment and its furniture. The
 * only thing all three share is white type and the 76px side margin.
 *
 *   textured  `over(1)`, `over(4)`, `over(6)` -- black paper, everything
 *             centred, a terracotta pill over an extra-bold headline, a
 *             semibold paragraph with one clause in the same terracotta.
 *   blurred   `send it(1)`, `send it(3)` -- the cover photo blurred behind the
 *             set, everything left and low, a huge ghosted italic step number
 *             behind a tight extra-bold headline, and the paragraph in
 *             *regular* weight. No accent colour anywhere.
 *   labels    `1787344402523`, `1787344487860` -- the photograph untouched and
 *             the text small, in the app's own black boxes, each line its own
 *             box. No accent, no handle, no dots: the app draws none.
 */
export const slideFormat = {
  /** D: text in the app's own black label boxes, over the photograph. */
  labels: {
    align: 'left',
    /**
     * No scrim. The reference stories darken nothing -- the boxes are what
     * makes the text legible, and a scrim is the tell that a design tool was
     * involved.
     */
    scrim: 'transparent',
    accent: null,
    /**
     * Small, and only semibold. The reference stories set this at a fraction
     * of the size a designed slide would, in the app's own text weight -- a
     * quote about a remote closer runs fifty characters across one line, which
     * is half the size this format shipped at. Big and extra-bold is how a
     * label box stops reading as typed and starts reading as a graphic, which
     * loses the only thing the format is for.
     */
    headline: {
      family: 'Inter', weight: 600, size: 28,
      tracking: '-0.01em', leading: 1.28,
    },
    /** Same box, same weight, one step down: the app has no headline role. */
    body: {
      family: 'Inter', weight: 600, size: 26,
      tracking: '-0.01em', leading: 1.28,
    },
    box: '#000000',
    /**
     * The offer's own colour. Every reference that has something to give away
     * puts that line -- and only that line -- in a coloured box while the rest
     * stay black: the box is doing the work an accent colour would do in a
     * designed slide. `emphasis` is the line that gets it.
     */
    emphasisBox: '#1A7A4E',
    radius: 8,
    paddingBlock: 10,
    paddingInline: 18,
    gap: 8,
    /**
     * Between one field and the next, rather than between two lines of the
     * same one. The reference sets the offer well clear of the statement above
     * it; at the line gap the coloured box reads as a fourth line of the same
     * sentence rather than as the separate thing it is.
     */
    groupGap: 34,
  },
  /** C: the cover photograph, blurred, behind every slide in the set. */
  blurred: {
    align: 'left',
    /**
     * Enough to stop the photograph competing, not enough to erase it. At 34
     * the ground turned to grey mud and every slide of every set looked the
     * same; the reference still reads as a person on a hillside.
     */
    blurPx: 20,
    /**
     * A gradient, not a flat wash: the card sits in the light half and the
     * paragraph in the dark half, which is what holds regular-weight white
     * type over a photograph.
     */
    scrim: 'linear-gradient(#0A0F1440, #0A0F1466 38%, #0A0F14F2)',
    accent: null,
    /** Tight enough that the words read as one object, as the reference does. */
    headline: {
      family: 'Inter', weight: 800, size: 88,
      tracking: '-0.035em', leading: 1.04,
    },
    /** Regular. The one weight contrast that makes this format not the others. */
    body: {
      family: 'Inter', weight: 400, size: 44,
      tracking: '0em', leading: 1.36,
    },
    step: {
      family: 'Inter', weight: 800, size: 128,
      colour: '#FFFFFF52',
    },
    card: { radius: 16, height: 0.31 },
    /** The simulated `<` `>` the reference draws at the card's sides. */
    arrow: { size: 62, glyph: 30, background: '#FFFFFF40', ink: '#1A1A1A' },
    dot: '#FFFFFF59',
    dotOn: '#FFFFFF',
    dotSize: 12,
    dotGap: 14,
  },
  /** A: a texture as the ground, and the pill above the headline. */
  textured: {
    align: 'center',
    /** The texture is lifted off pure black so it reads as a surface. */
    scrim: '#00000073',
    /**
     * Terracotta. Read off `over(1)`'s pill and `over(4)`'s "100K in 6 Months"
     * -- the one colour the reference set uses, and the reason this format is
     * recognisable from a thumbnail.
     */
    accent: '#CE6A4C',
    onAccent: '#FFFFFF',
    headline: {
      family: 'Inter', weight: 800, size: 82,
      tracking: '-0.02em', leading: 1.08,
    },
    /** Semibold, and nearly as large as the headline, as the reference sets it. */
    body: {
      family: 'Inter', weight: 600, size: 54,
      tracking: '-0.01em', leading: 1.2,
    },
    pill: {
      radius: 999,
      paddingBlock: 16,
      paddingInline: 44,
      size: 44,
    },
  },
  /**
   * F: a dim moving background and a stack of text over it, no boxes at all.
   * From the five `bdp-frame-*.jpg` -- frames lifted out of the BDP reels,
   * which are only videos because they had music on them.
   *
   * The whole format is the weight ladder: a tight bold headline, a light
   * list under it, a bold payoff with one word in the accent and underlined.
   * It carries far more text than a still slide would, which works because
   * the background moves and the reader has the clip to read it.
   */
  stack: {
    align: 'left',
    /** Warm light has to survive this, so it darkens rather than desaturates. */
    scrim: 'linear-gradient(#000000D9, #00000099 30%, #000000A6 70%, #000000E6)',
    accent: '#F0562E',
    headline: {
      family: 'Inter', weight: 800, size: 62,
      tracking: '-0.03em', leading: 1.1,
    },
    body: {
      family: 'Inter', weight: 400, size: 50,
      tracking: '0em', leading: 1.22,
    },
    /** The payoff, back in bold, with the accent word underlined. */
    payoff: {
      family: 'Inter', weight: 800, size: 50,
      tracking: '-0.02em', leading: 1.2,
    },
    top: 0.17,
    gap: 54,
  },
  /**
   * The cover of a carousel, from `Comment GUIDE and I'll send it.jpg`.
   *
   * The photograph is sharp -- the blurring starts on the slide after this
   * one -- and the title is a ladder of four different cuts, each line set
   * differently from the last: bold, bold italic, serif, bracketed italic.
   * Two cards sit under it at slight angles, overlapping.
   */
  titled: {
    align: 'left',
    /**
     * Heavier than the reference needed. Its cover photo was a mid-blue sky;
     * a pale building behind white type gives the title nothing to sit on,
     * and the serif line is the first to go because it is the thinnest.
     */
    scrim: 'linear-gradient(#0A0F14A6, #0A0F1466 46%, #0A0F1499)',
    accent: null,
    headline: {
      family: 'Inter', weight: 800, size: 112,
      tracking: '-0.035em', leading: 1.04,
    },
    /** Second line, indented, italic. */
    kicker: {
      family: 'Inter', weight: 800, size: 62,
      tracking: '-0.02em', leading: 1.1,
    },
    /** Third line. The one serif in the project. */
    serif: {
      family: 'Playfair Display', weight: 700, size: 84,
      tracking: '0em', leading: 1.06,
    },
    /** Fourth line, in brackets. */
    body: {
      family: 'Inter', weight: 400, size: 38,
      tracking: '0em', leading: 1.2,
    },
    card: { radius: 18, tilt: -5, width: 0.4, height: 0.16 },
    /**
     * One screenshot instead of two cards: centred, straight, and contained
     * rather than cropped -- a terminal screenshot is mostly whitespace and a
     * cover crop would cut the half that carries the commands.
     */
    shot: { radius: 14, background: '#0D0D0F', pad: 22, top: 0.37 },
    /**
     * Commands set as live text rather than a screenshot. A capture of a
     * terminal is pixels, and this one has to be read at arm's length on a
     * phone -- scaled up it softens, and scaled to fit it is unreadable.
     *
     * Not scaled by the shape either. Monospace is bound by the frame's
     * width, not its height: 58 characters at 47px would need 1400px of a
     * 1080px canvas. Wrapping at the spaces is what buys the size back.
     */
    terminal: {
      family: 'IBM Plex Mono', weight: 400, size: 36,
      tracking: '0em', leading: 1.65,
      ink: '#E8E8EA',
      background: '#0D0D0F',
      radius: 18,
      padBlock: 64,
      padInline: 46,
      top: 0.55,
    },
  },
  /**
   * B's before/after variant, from `Comment GUIDE and I'll send it over(4).jpg`.
   *
   * An italic line, a huge accent number, a parenthetical, then two cards
   * stacked down the right with a circle drawn round the number on each --
   * red on the before, green on the after -- and the two dates down the left
   * with an arrow between them. The drawn-on quality is the point: it reads
   * as annotated rather than designed.
   */
  beforeafter: {
    align: 'center',
    scrim: 'linear-gradient(#000000B3, #00000073 45%, #000000CC)',
    accent: '#CE6A4C',
    /** The italic line above the number. */
    kicker: {
      family: 'Inter', weight: 800, size: 66,
      tracking: '-0.02em', leading: 1.1,
    },
    headline: {
      family: 'Inter', weight: 800, size: 108,
      tracking: '-0.03em', leading: 1,
    },
    body: {
      family: 'Inter', weight: 400, size: 38,
      tracking: '0em', leading: 1.2,
    },
    /** The two dates down the left, either side of the arrow. */
    label: {
      family: 'Inter', weight: 800, size: 54,
      tracking: '0em', leading: 1,
    },
    card: { radius: 22, width: 0.56, height: 0.16, gap: 34 },
    /** Runs the whole way from the first date to the second. */
    arrow: { weight: 7, head: 22, offset: 54, clear: 22 },
    /**
     * A sequence down the middle, in place of the two cards. The commands are
     * set in the mono because that is what they are -- typed, not spoken --
     * and an arrow between each says the order is the point.
     */
    steps: {
      family: 'IBM Plex Mono', weight: 400, size: 46,
      tracking: '0em', leading: 1.2,
      gap: 26, arrow: 30, arrowWeight: 4, dim: '#FFFFFF8C',
    },
  },
  /**
   * E's blob variant, from `639735492_...jpg`.
   *
   * Screenshots scattered at slight angles over a photograph, with white
   * caption boxes carrying black text at the bottom. The scatter is the
   * whole idea -- a neat grid would say "here is my evidence, arranged",
   * and this says "there is more where this came from".
   */
  collage: {
    align: 'center',
    /**
     * The ground is blurred here, where in the other photo formats it is not:
     * the screenshots are the subject, and a sharp photograph behind them
     * competes with every one of them at once.
     */
    blurPx: 18,
    scrim: '#00000059',
    accent: null,
    /** Black on white, the inverse of every other format's caption. */
    caption: {
      family: 'Inter', weight: 800, size: 46,
      tracking: '-0.01em', leading: 1.18,
    },
    box: '#FFFFFF',
    onBox: '#111111',
    radius: 16,
    paddingBlock: 20,
    paddingInline: 30,
    gap: 18,
    shot: {
      radius: 14,
      shadow: '#00000073',
      /**
       * Measured off `701537468`, which is the same 9:16 as this canvas, so
       * the fractions carry over directly.
       *
       * Portrait, because a screenshot of a phone is portrait -- a landscape
       * box crops the evidence to a strip. No two the same size and no two
       * aligned: the overlap is what does the scattering, not the angle, so
       * the tilts stay under two degrees.
       */
      boxes: [
        { x: 0.06, y: 0.13, w: 0.48, h: 0.34, tilt: -1.5 },
        { x: 0.47, y: 0.18, w: 0.44, h: 0.29, tilt: 1 },
        { x: 0.18, y: 0.325, w: 0.43, h: 0.29, tilt: -0.5 },
      ],
    },
    /**
     * The green chip laid over the number inside a screenshot. It is the whole
     * difference between a collage and a proof collage: without it the reader
     * has to find the figure in someone else's dashboard, and they will not.
     *
     * Placed by hand, because only the person who took the screenshot knows
     * where in it the number is.
     */
    chip: {
      background: '#3FDD52',
      ink: '#0A0A0A',
      radius: 10,
      paddingBlock: 12,
      paddingInline: 22,
      size: 52,
      shadow: '0 6px 18px #00000059',
    },
  },
  /* ---------------------------------------------------------------------
   * The seven above all do the same thing underneath: a photograph, and type
   * on top of it. These seven do not. Five carry no photograph at all, two
   * put one behind glass, and three set their type on paper rather than on
   * the dark. None of them is read off a reference -- they are what the
   * reference set has no example of.
   * ------------------------------------------------------------------- */

  /**
   * One number, big enough to be the picture.
   *
   * Sized so a four-character figure fills the frame edge to edge and a
   * longer one runs past it and is clipped -- which is the point. A figure
   * that sits comfortably inside its margins reads as a headline that happens
   * to be large; one that the frame cannot contain reads as a quantity.
   * Nothing else competes: a mono label above, one line below.
   */
  ticker: {
    ground: '#0B0B0C',
    ink: '#FFFFFF',
    accent: '#F0562E',
    /**
     * An optional ground, blurred either way and now by about the same amount.
     * Both started far higher and came down by eye: at 30 the photograph was a
     * smear with nothing left to recognise, which reads as a mistake rather
     * than as depth. What the blur has to do is soften the ground enough that
     * the figure sits in front of it -- not erase what is behind.
     */
    blur: { photo: 11, texture: 12 },
    /**
     * A photograph only. A texture has no competing detail to put behind
     * glass, and this on top of the vignette took a ground of mean luma 37
     * down to nothing -- the texture was rendering, and was simply invisible.
     */
    scrim: '#0B0B0C99',
    /**
     * Darkens the corners and leaves the middle alone, so the figure sits in
     * the one part of the frame the ground has been cleared out of.
     */
    vignette:
      'radial-gradient(ellipse at 50% 46%,' +
      ' #00000000 26%, #00000080 72%, #000000CC 100%)',
    figure: {
      family: 'Inter', weight: 800, size: 480,
      tracking: '-0.06em', leading: 0.82,
    },
    label: {
      family: 'IBM Plex Mono', weight: 400, size: 34,
      tracking: '0.22em', leading: 1.2,
    },
    body: {
      family: 'Inter', weight: 400, size: 46,
      tracking: '0em', leading: 1.3,
    },
  },
  /**
   * The conversation itself, drawn rather than screenshotted.
   *
   * A screenshot of a thread carries someone's battery percentage, their
   * unread count and their wallpaper; drawn, it carries only what was said.
   * The cost is that it is no longer evidence, so this is for a thread worth
   * reading, not a thread worth proving.
   */
  thread: {
    blurPx: 8,
    /**
     * Near-neutral, and ten points lighter than it was. At 85% the photograph
     * behind had gone from quiet to absent. A strongly warm scrim was worse
     * still: over a warm-lit room it read as an orange filter laid over the
     * whole slide. The warmth belongs to the photograph -- this only has to
     * get out of its way.
     */
    scrim: '#131110BF',
    ink: '#FFFFFF',
    /**
     * Neutral, not warm. A brown bubble on a warm ground melts into it, and
     * the bubbles are the subject; they have to sit clearly on top of the
     * room rather than share its colour.
     */
    them: '#2B2B2E',
    me: '#0F7A5A',
    radius: 30,
    /** The one corner that stays tight, which is what makes it a bubble. */
    tail: 8,
    gap: 18,
    width: 0.78,
    body: {
      family: 'Inter', weight: 400, size: 42,
      tracking: '0em', leading: 1.28,
    },
    name: {
      family: 'Inter', weight: 800, size: 30,
      tracking: '0em', leading: 1.2,
    },
    /**
     * The sender's name is blurred wherever it appears. A real thread has a
     * real person in it, and posting their name to a story calls them out; a
     * made-up name reads as made up. Blurred, it still says someone you know
     * sent this.
     */
    redact: { blurPx: 7, background: '#FFFFFF1A', radius: 6, padInline: 10 },
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
