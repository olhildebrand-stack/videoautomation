import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { slide, slideFormat, slideShapes } from '../tokens';
import type { SlideFormat, SlideShape } from '../tokens';

/**
 * One slide of a carousel or a story.
 *
 * Three formats, each read off its own reference set in
 * `howtocutvideo/FORMATS.md`. They are meant to look like different posts, so
 * a format owns its palette, its weights, its alignment and its furniture --
 * the only things all three share are white type and the side margin.
 *
 *   textured  black paper, centred, terracotta pill, semibold paragraph
 *   blurred   the cover photo blurred behind the set, left and low, regular
 *             paragraph under a tight extra-bold headline
 *   labels    the photograph untouched, small text in the app's black boxes
 *
 * A format is chosen once per sequence, never per slide. So is a background.
 */
export type SlideProps = {
  kind: 'cover' | 'body';
  format?: SlideFormat;
  shape?: SlideShape;
  /**
   * Absent on a body slide means the picture is a video the editor will lay
   * in: the ground is punched through where the card would be, and the still
   * is written with an alpha channel.
   */
  image?: string;
  /** The one ground for the whole sequence: a texture, or the cover photo. */
  background?: string;
  /** Where to hold a photograph while cropping it, as `object-position`. */
  focus?: string;
  /** cover: the second, quieter line. body: the pill, or the step number. */
  kicker?: string;
  headline: string;
  body?: string;
  /** The one clause per slide allowed to leave the text colour. */
  emphasis?: string;
  handle?: string;
  /** blurred: which dot is lit, 1-based. Absent hides the row. */
  step?: number;
  of?: number;
};

const shapeOf = (shape?: SlideShape) => slideShapes[shape ?? 'carousel'];

export const Slide: React.FC<SlideProps> = (props) => {
  if (props.format === 'labels') return <Labels {...props} />;
  if (props.format === 'blurred') return <Blurred {...props} />;
  return props.kind === 'cover' ? <Cover {...props} /> : <Body {...props} />;
};

/* ------------------------------------------------------------ shared parts */

/** A format's type role, spread into a style. */
type Role = {
  family: string;
  weight: number;
  size: number;
  tracking: string;
  leading: number;
};

const typeOf = (role: Role): React.CSSProperties => ({
  fontFamily: role.family,
  fontWeight: role.weight,
  fontSize: role.size,
  letterSpacing: role.tracking,
  lineHeight: role.leading,
  whiteSpace: 'pre-line',
});

const Fill: React.FC<{ src?: string; focus?: string; blur?: number }> = ({
  src, focus, blur,
}) => (src ? (
  <Img
    src={staticFile(src)}
    style={{
      width: '100%', height: '100%',
      objectFit: 'cover', objectPosition: focus || 'center',
      // Scaled up before blurring: a blur samples past the edges and would
      // otherwise leave a soft transparent border all the way round.
      ...(blur ? { filter: `blur(${blur}px)`, transform: 'scale(1.12)' } : {}),
    }}
  />
) : null);

const Handle: React.FC<{ handle?: string }> = ({ handle }) =>
  handle ? (
    <div
      style={{
        fontFamily: 'Inter', fontWeight: 800,
        fontSize: slide.handleSize, color: slide.ink,
      }}
    >
      {handle}
    </div>
  ) : null;

const Card: React.FC<{
  src?: string; focus?: string; radius?: number; style: React.CSSProperties;
}> = ({ src, focus, radius, style }) => (
  <div
    style={{
      ...style,
      borderRadius: radius ?? slide.card.radius,
      backgroundColor: slide.card.background,
      boxShadow: `0 ${slide.card.shadowDrop}px ${slide.card.shadowBlur}px ${slide.card.shadow}`,
      overflow: 'hidden',
    }}
  >
    <Img
      src={staticFile(src ?? '')}
      style={{
        width: '100%', height: '100%',
        objectFit: 'cover', objectPosition: focus || 'center',
      }}
    />
  </div>
);

/* ------------------------------------------------------- format: textured  */

const T = slideFormat.textured;

/**
 * The cover of a textured set: the photograph, darkened top and bottom, with
 * the claim centred over it. `over(4)` is the reference -- the headline is the
 * whole slide, and the kicker under it is the parenthetical.
 */
const Cover: React.FC<SlideProps> = ({
  image, background, focus, headline, kicker, handle, shape,
}) => (
  <AbsoluteFill style={{ backgroundColor: slide.ground }}>
    <Fill src={image ?? background} focus={focus} />
    {/* Held, not faded, across the band the type sits in. A gradient that is
        already transparent by the headline leaves white type on whatever the
        photograph happens to be -- and a phone photo is as often a bright
        kitchen as a dark beach. */}
    <AbsoluteFill
      style={{
        background:
          `linear-gradient(${slide.scrim}, ${slide.scrim} 42%,` +
          ` transparent 64%, ${slide.scrim})`,
      }}
    />
    <AbsoluteFill
      style={{
        padding: slide.side,
        paddingTop: slide.side + shapeOf(shape).insetTop,
        paddingBottom: slide.side + shapeOf(shape).insetBottom,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        textAlign: T.align,
      }}
    >
      <div>
        <div style={{ ...typeOf(T.headline), fontSize: slide.coverSize, color: slide.ink }}>
          {headline}
        </div>
        {kicker ? (
          <div
            style={{
              marginTop: T.pill.paddingBlock,
              ...typeOf(T.body), fontSize: T.pill.size, color: T.accent,
            }}
          >
            {kicker}
          </div>
        ) : null}
      </div>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}
      >
        <Handle handle={handle} />
        {handle ? <NextArrow /> : null}
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);

/**
 * A body slide of a textured set.
 *
 * Everything centred, in this order and always in this place: pill, headline,
 * paragraph, card. `over(1)` and `over(6)` are six slides of exactly this, and
 * that is what makes them read as one document.
 */
const Body: React.FC<SlideProps> = ({
  image, background, focus, kicker, headline, body, emphasis, handle, shape,
}) => (
  <AbsoluteFill style={background ? undefined : { backgroundColor: slide.ground }}>
    {background ? (
      <>
        <Fill src={background} />
        <AbsoluteFill style={{ backgroundColor: T.scrim }} />
      </>
    ) : null}
    {image || background ? null : <PunchedGround shape={shape} />}

    <AbsoluteFill
      style={{
        padding: slide.side,
        paddingTop: slide.side + shapeOf(shape).insetTop,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        textAlign: T.align,
      }}
    >
      {kicker ? (
        <div
          style={{
            backgroundColor: T.accent, color: T.onAccent,
            borderRadius: T.pill.radius,
            paddingBlock: T.pill.paddingBlock,
            paddingInline: T.pill.paddingInline,
            fontFamily: T.headline.family, fontWeight: T.headline.weight,
            fontSize: T.pill.size,
          }}
        >
          {kicker}
        </div>
      ) : null}
      <div
        style={{
          marginTop: T.pill.paddingInline, ...typeOf(T.headline), color: slide.ink,
        }}
      >
        {headline}
      </div>
      {body ? (
        <div
          style={{
            marginTop: T.pill.paddingBlock, ...typeOf(T.body), color: slide.ink,
          }}
        >
          {body}
          {emphasis ? <span style={{ color: T.accent }}> {emphasis}</span> : null}
        </div>
      ) : null}
    </AbsoluteFill>

    {image ? <Card src={image} focus={focus} style={pictureBox(shape)} /> : null}

    <div
      style={{
        position: 'absolute', left: slide.side, right: slide.side,
        bottom: slide.side + shapeOf(shape).insetBottom,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}
    >
      <Handle handle={handle} />
      {handle ? <NextArrow /> : null}
    </div>
  </AbsoluteFill>
);

/** The swipe arrow the reference set draws in the bottom-right of every slide. */
const NextArrow: React.FC = () => (
  <svg width={slide.handleSize * 3} height={slide.handleSize} viewBox="0 0 90 30">
    <path
      d="M0 15 H78 M64 3 L78 15 L64 27"
      stroke={slide.ink}
      strokeWidth={5}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/* -------------------------------------------------------- format: blurred  */

const B = slideFormat.blurred;

/**
 * The cover photograph, blurred, behind every slide in the set.
 *
 * It costs no asset -- the sequence already contains the picture -- and the
 * set reads as one piece because the ground literally is the same photograph
 * the cover used. Everything sits left and low, under a card in the light half
 * of the gradient.
 */
const Blurred: React.FC<SlideProps> = ({
  image, background, focus, kicker, headline, body, handle, shape, step, of,
}) => {
  const geometry = shapeOf(shape);
  const cardTop = geometry.insetTop + slide.side * 1.4;
  const cardHeight = geometry.height * B.card.height;
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={background ?? image} focus="center" blur={B.blurPx} />
      <AbsoluteFill style={{ background: B.scrim }} />

      {image ? (
        <>
          <Card
            src={image}
            focus={focus}
            radius={B.card.radius}
            style={{
              position: 'absolute',
              left: slide.side * 1.8, right: slide.side * 1.8,
              top: cardTop, height: cardHeight,
            }}
          />
          <PageArrow side="left" centre={cardTop + cardHeight / 2} />
          <PageArrow side="right" centre={cardTop + cardHeight / 2} />
        </>
      ) : null}

      {/* Anchored to the bottom, not the top: the copy varies in length and
          growing downwards ran it into the handle. Growing upwards it runs
          towards the card, where a collision is visible and is a copy
          problem rather than a layout one. */}
      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          bottom: geometry.insetBottom + slide.side + slide.handleSize * 2.4,
          textAlign: B.align,
        }}
      >
        {/* The step number sits behind the headline's first line, overlapping
            it, exactly as the reference does -- so it reads as a watermark on
            the slide rather than as a line of its own. */}
        {kicker ? (
          <div
            style={{
              fontFamily: B.step.family, fontWeight: B.step.weight,
              fontStyle: 'italic', fontSize: B.step.size, color: B.step.colour,
              lineHeight: 1,
            }}
          >
            {kicker}
          </div>
        ) : null}
        <div
          style={{
            ...typeOf(B.headline), color: slide.ink,
            marginTop: kicker ? -B.step.size * 0.42 : 0,
            marginLeft: kicker ? B.step.size * 0.34 : 0,
          }}
        >
          {headline}
        </div>
        {body ? (
          <div
            style={{
              ...typeOf(B.body), color: slide.ink,
              marginTop: slide.side * 0.6,
            }}
          >
            {body}
          </div>
        ) : null}
      </div>

      <div
        style={{
          position: 'absolute', left: slide.side, right: slide.side,
          bottom: slide.side + geometry.insetBottom,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}
      >
        <Handle handle={handle} />
        {of ? (
          <div
            style={{
              position: 'absolute', left: 0, right: 0,
              display: 'flex', justifyContent: 'center', gap: B.dotGap,
            }}
          >
            {Array.from({ length: of }, (_, index) => (
              <div
                key={index}
                style={{
                  width: B.dotSize, height: B.dotSize, borderRadius: B.dotSize,
                  backgroundColor: index + 1 === step ? B.dotOn : B.dot,
                }}
              />
            ))}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/** The simulated carousel chevrons the reference draws beside the card. */
const PageArrow: React.FC<{ side: 'left' | 'right'; centre: number }> = ({
  side, centre,
}) => (
  <div
    style={{
      position: 'absolute',
      [side]: slide.side * 0.4,
      top: centre - B.arrow.size / 2,
      width: B.arrow.size, height: B.arrow.size,
      borderRadius: B.arrow.size,
      backgroundColor: B.arrow.background,
      color: B.arrow.ink,
      fontFamily: B.body.family, fontWeight: B.headline.weight,
      fontSize: B.arrow.glyph,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}
  >
    {side === 'left' ? '<' : '>'}
  </div>
);

/* --------------------------------------------------------- format: labels  */

const L = slideFormat.labels;

/**
 * The photograph, and the text in the app's own black label boxes.
 *
 * It reads as typed in the app rather than made in a design tool, which on a
 * story is the point. Each line is its own box, so a short line does not
 * stretch to the width of a long one, and the type is small -- the reference
 * stories set it at a fraction of the size a designed slide would.
 */
const Labels: React.FC<SlideProps> = ({
  image, background, focus, headline, body, emphasis, shape,
}) => {
  const geometry = shapeOf(shape);
  const lines = [headline, body, emphasis].filter(Boolean) as string[];
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image ?? background} focus={focus} />
      <AbsoluteFill style={{ backgroundColor: L.scrim }} />
      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          top: geometry.insetTop + slide.side,
          display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
          gap: L.gap,
        }}
      >
        {lines.map((line, index) => (
          <div
            key={index}
            style={{
              backgroundColor: L.box,
              borderRadius: L.radius,
              paddingBlock: L.paddingBlock,
              paddingInline: L.paddingInline,
              ...typeOf(index === 0 ? L.headline : L.body),
              color: slide.ink,
              textAlign: L.align,
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ pieces */

/** The picture's place, shared by the card and the hole cut for a video. */
const pictureBox = (shape?: SlideShape): React.CSSProperties => ({
  position: 'absolute',
  left: slide.side,
  right: slide.side,
  top: shapeOf(shape).picture.top,
  bottom: shapeOf(shape).picture.bottom,
});

/**
 * The ground with the picture's rectangle missing from it.
 *
 * One path with two subpaths and an even-odd fill: the inner rounded rectangle
 * is never painted, so the still keeps a real hole rather than a dark patch
 * that would sit on top of the video.
 */
const PunchedGround: React.FC<{ shape?: SlideShape }> = ({ shape }) => {
  const geometry = shapeOf(shape);
  const x = slide.side;
  const y = geometry.picture.top;
  const w = slide.width - slide.side * 2;
  const h = geometry.height - geometry.picture.top - geometry.picture.bottom;
  const r = slide.card.radius;
  const hole =
    `M${x + r},${y} H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r}` +
    ` V${y + h - r} A${r},${r} 0 0 1 ${x + w - r},${y + h}` +
    ` H${x + r} A${r},${r} 0 0 1 ${x},${y + h - r}` +
    ` V${y + r} A${r},${r} 0 0 1 ${x + r},${y} Z`;

  return (
    <svg
      width={slide.width}
      height={geometry.height}
      style={{ position: 'absolute', top: 0, left: 0 }}
    >
      <path
        fillRule="evenodd"
        fill={slide.ground}
        d={`M0,0 H${slide.width} V${geometry.height} H0 Z ${hole}`}
      />
    </svg>
  );
};
