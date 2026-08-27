import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { caption, slide, slideFormat, slideShapes } from '../tokens';
import type { SlideFormat, SlideShape } from '../tokens';

/**
 * One slide of a carousel or a story.
 *
 * Three formats, read off the reference sets in `howtocutvideo/FORMATS.md`.
 * They share the type, the margins and the accent -- that is what makes two
 * sequences in different formats still look like the same account -- and
 * differ only in what the type sits on and what furniture surrounds it.
 *
 *   textured  a texture as the ground, a pill, and the picture on a light card
 *   blurred   the cover photograph, blurred, behind every slide in the set
 *   labels    the app's own black label boxes over the photograph itself
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

const Fill: React.FC<{ src?: string; focus?: string; blur?: number }> = ({
  src, focus, blur,
}) => (src ? (
  <Img
    src={staticFile(src)}
    style={{
      width: '100%', height: '100%',
      objectFit: 'cover', objectPosition: focus ?? 'center',
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
        fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
        fontSize: slide.handleSize, color: slide.body,
      }}
    >
      {handle}
    </div>
  ) : null;

const Card: React.FC<{ src?: string; focus?: string; style: React.CSSProperties }> = ({
  src, focus, style,
}) => (
  <div
    style={{
      ...style,
      borderRadius: slide.card.radius,
      backgroundColor: slide.card.background,
      boxShadow: `0 ${slide.card.shadowDrop}px ${slide.card.shadowBlur}px ${slide.card.shadow}`,
      overflow: 'hidden',
    }}
  >
    <Img
      src={staticFile(src ?? '')}
      style={{
        width: '100%', height: '100%',
        objectFit: 'cover', objectPosition: focus ?? 'center',
      }}
    />
  </div>
);

/* ------------------------------------------------------- format: textured  */

const Cover: React.FC<SlideProps> = ({
  image, background, focus, headline, kicker, handle, shape,
}) => (
  <AbsoluteFill style={{ backgroundColor: slide.ground }}>
    <Fill src={image ?? background} focus={focus} />
    <AbsoluteFill
      style={{
        background: `linear-gradient(${slide.scrim}, transparent 55%, ${slide.scrim})`,
      }}
    />
    <AbsoluteFill
      style={{
        padding: slide.side,
        paddingTop: slide.side + shapeOf(shape).insetTop,
        paddingBottom: slide.side + shapeOf(shape).insetBottom,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      }}
    >
      <div>
        <div style={{ ...headlineStyle, fontSize: slide.coverSize }}>{headline}</div>
        {kicker ? (
          <div
            style={{
              marginTop: slide.pill.paddingBlock,
              ...bodyStyle, fontSize: slide.kickerSize, color: slide.accent,
              textAlign: 'left',
            }}
          >
            {kicker}
          </div>
        ) : null}
      </div>
      <Handle handle={handle} />
    </AbsoluteFill>
  </AbsoluteFill>
);

const Body: React.FC<SlideProps> = ({
  image, background, focus, kicker, headline, body, emphasis, handle, shape,
}) => (
  <AbsoluteFill style={background ? undefined : { backgroundColor: slide.ground }}>
    {background ? (
      <>
        <Fill src={background} />
        <AbsoluteFill style={{ backgroundColor: slideFormat.textured.scrim }} />
      </>
    ) : null}
    {image || background ? null : <PunchedGround shape={shape} />}

    <AbsoluteFill
      style={{
        padding: slide.side,
        paddingTop: slide.side + shapeOf(shape).insetTop,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
      }}
    >
      {kicker ? (
        <div
          style={{
            backgroundColor: slide.accent, color: slide.onAccent,
            borderRadius: slide.pill.radius,
            paddingBlock: slide.pill.paddingBlock,
            paddingInline: slide.pill.paddingInline,
            fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
            fontSize: slide.pill.size, textTransform: 'uppercase',
          }}
        >
          {kicker}
        </div>
      ) : null}
      <div style={{ marginTop: slide.pill.paddingInline, ...headlineStyle }}>
        {headline}
      </div>
      {body ? (
        <div style={{ marginTop: slide.pill.paddingBlock, ...bodyStyle }}>
          {body}
          {emphasis ? <span style={{ color: slide.accent }}> {emphasis}</span> : null}
        </div>
      ) : null}
    </AbsoluteFill>

    {image ? <Card src={image} focus={focus} style={pictureBox(shape)} /> : null}

    <div
      style={{
        position: 'absolute', left: slide.side, right: slide.side,
        bottom: slide.side + shapeOf(shape).insetBottom,
      }}
    >
      <Handle handle={handle} />
    </div>
  </AbsoluteFill>
);

/* -------------------------------------------------------- format: blurred  */

/**
 * The cover photograph, blurred, behind every slide in the set.
 *
 * It costs no asset -- the sequence already contains the picture -- and the
 * set reads as one piece because the ground literally is the same photograph
 * the cover used.
 */
const Blurred: React.FC<SlideProps> = ({
  image, background, focus, kicker, headline, body, emphasis, handle, shape,
  step, of,
}) => {
  const geometry = shapeOf(shape);
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={background ?? image} focus="center" blur={slideFormat.blurred.blurPx} />
      <AbsoluteFill style={{ backgroundColor: slideFormat.blurred.scrim }} />

      {image ? (
        <Card
          src={image}
          focus={focus}
          style={{
            position: 'absolute',
            left: slide.side, right: slide.side,
            top: geometry.insetTop + slide.side,
            height: geometry.height * 0.3,
          }}
        />
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
        }}
      >
        {kicker ? (
          <div
            style={{
              fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
              fontSize: slideFormat.blurred.stepSize,
              color: slideFormat.blurred.stepColour,
              lineHeight: 1, fontStyle: 'italic',
            }}
          >
            {kicker}
          </div>
        ) : null}
        <div
          style={{
            ...headlineStyle, textAlign: 'left',
            marginTop: kicker ? -slide.pill.size : 0,
          }}
        >
          {headline}
        </div>
        {body ? (
          <div
            style={{
              ...bodyStyle, textAlign: 'left',
              marginTop: slide.pill.paddingInline,
            }}
          >
            {body}
            {emphasis ? (
              <>
                {'\n\n'}
                <span style={{ color: slide.accent }}>{emphasis}</span>
              </>
            ) : null}
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
          <div style={{ display: 'flex', gap: slideFormat.blurred.dotGap }}>
            {Array.from({ length: of }, (_, index) => (
              <div
                key={index}
                style={{
                  width: slideFormat.blurred.dotSize,
                  height: slideFormat.blurred.dotSize,
                  borderRadius: slideFormat.blurred.dotSize,
                  backgroundColor: index + 1 === step
                    ? slideFormat.blurred.dotOn
                    : slideFormat.blurred.dot,
                }}
              />
            ))}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------- format: labels  */

/**
 * The photograph, and the text in the app's own black label boxes.
 *
 * It reads as typed in the app rather than made in a design tool, which on a
 * story is the point. Each line is its own box, so a short line does not stretch
 * to the width of a long one.
 */
const Labels: React.FC<SlideProps> = ({
  image, background, focus, headline, body, emphasis, handle, shape,
}) => {
  const geometry = shapeOf(shape);
  const lines = [headline, body, emphasis].filter(Boolean) as string[];
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image ?? background} focus={focus} />
      <AbsoluteFill style={{ backgroundColor: slideFormat.labels.scrim }} />
      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          top: geometry.insetTop + slide.side,
          display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
          gap: slideFormat.labels.gap,
        }}
      >
        {lines.map((line, index) => (
          <div
            key={index}
            style={{
              backgroundColor: slideFormat.labels.box,
              borderRadius: slideFormat.labels.radius,
              paddingBlock: slideFormat.labels.paddingBlock,
              paddingInline: slideFormat.labels.paddingInline,
              fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
              fontSize: index === 0 ? slide.bodySize : slide.kickerSize,
              lineHeight: slide.bodyLineHeight,
              color: index === lines.length - 1 && lines.length > 1
                ? slide.accent : slide.headline,
              whiteSpace: 'pre-line',
            }}
          >
            {line}
          </div>
        ))}
      </div>
      <div
        style={{
          position: 'absolute', left: slide.side,
          bottom: slide.side + geometry.insetBottom,
        }}
      >
        <Handle handle={handle} />
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ pieces */

const headlineStyle: React.CSSProperties = {
  fontFamily: caption.fontFamily,
  fontWeight: caption.fontWeight,
  fontSize: slide.headlineSize,
  lineHeight: slide.lineHeight,
  letterSpacing: caption.letterSpacing,
  color: slide.headline,
  textAlign: 'center',
  whiteSpace: 'pre-line',
};

const bodyStyle: React.CSSProperties = {
  fontFamily: caption.fontFamily,
  fontWeight: caption.fontWeight,
  fontSize: slide.bodySize,
  lineHeight: slide.bodyLineHeight,
  color: slide.body,
  textAlign: 'center',
  whiteSpace: 'pre-line',
};

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
