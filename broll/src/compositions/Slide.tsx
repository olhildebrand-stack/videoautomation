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
  /** collage, titled, beforeafter: the screenshots they scatter or stack. */
  images?: string[];
  handle?: string;
  /**
   * This slide's picture is a video: cut the card's rectangle out of the
   * ground so the clip laid behind the still shows through it.
   */
  punch?: boolean;
  /** blurred: which dot is lit, 1-based. Absent hides the row. */
  step?: number;
  of?: number;
};

const shapeOf = (shape?: SlideShape) => slideShapes[shape ?? 'carousel'];

export const Slide: React.FC<SlideProps> = (props) => {
  if (props.format === 'labels') return <Labels {...props} />;
  if (props.format === 'blurred') return <Blurred {...props} />;
  if (props.format === 'stack') return <Stack {...props} />;
  if (props.format === 'titled') return <Titled {...props} />;
  if (props.format === 'beforeafter') return <BeforeAfter {...props} />;
  if (props.format === 'collage') return <Collage {...props} />;
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
        textAlign: T.align,
      }}
    >
      <div>
        <div
          style={{
            ...typeOf(T.headline), fontSize: slide.coverSize,
            color: slide.ink, textShadow: slide.lift,
          }}
        >
          {headline}
        </div>
        {kicker ? (
          <div
            style={{
              marginTop: T.pill.paddingBlock,
              ...typeOf(T.body), fontSize: T.pill.size, color: T.accent,
              textShadow: slide.lift,
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
  punch,
}) => (
  // Opaque only when nothing else supplies a ground. A background is a full-
  // bleed Fill; on a punched slide PunchedGround is the ground, and painting
  // behind it would fill in the hole the video has to show through.
  <AbsoluteFill
    style={punch || background ? undefined : { backgroundColor: slide.ground }}
  >
    {background ? (
      <>
        <Fill src={background} />
        <AbsoluteFill style={{ backgroundColor: T.scrim }} />
      </>
    ) : null}
    {punch && !background ? <PunchedGround shape={shape} /> : null}

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
  punch,
}) => {
  const geometry = shapeOf(shape);
  const inset = slide.side * 1.8;
  const card = {
    x: inset,
    y: geometry.insetTop + slide.side * 1.4,
    w: slide.width - inset * 2,
    h: geometry.height * B.card.height,
  };
  return (
    // Opaque only when the blurred photograph is the whole ground. On a punched
    // slide the frame has to stay clear where the clip shows through.
    <AbsoluteFill style={punch ? undefined : { backgroundColor: slide.ground }}>
      {/* The ground is cut away where the card would be, so a clip laid behind
          the still shows through it and the furniture still draws around it. */}
      <AbsoluteFill
        style={
          punch
            ? { clipPath: hole(slide.width, geometry.height, card, B.card.radius) }
            : undefined
        }
      >
        <Fill src={background ?? image} focus="center" blur={B.blurPx} />
        <AbsoluteFill style={{ background: B.scrim }} />
      </AbsoluteFill>

      {image ? (
        <Card
          src={image}
          focus={focus}
          radius={B.card.radius}
          style={{
            position: 'absolute',
            left: card.x, top: card.y, width: card.w, height: card.h,
          }}
        />
      ) : null}
      {image || punch ? (
        <>
          <PageArrow side="left" centre={card.y + card.h / 2} />
          <PageArrow side="right" centre={card.y + card.h / 2} />
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

/* ---------------------------------------------------------- format: stack  */

const S = slideFormat.stack;

/**
 * A stack of text over a dim photograph, and nothing else.
 *
 * The format is the weight ladder. A tight bold headline, the list under it
 * in a light weight so it reads as detail rather than as more headline, and
 * the payoff back in bold with one accent word underlined.
 */
const Stack: React.FC<SlideProps> = ({
  image, background, focus, headline, body, emphasis, shape,
}) => {
  const geometry = shapeOf(shape);
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image ?? background} focus={focus} />
      <AbsoluteFill style={{ background: S.scrim }} />
      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          top: geometry.insetTop + geometry.height * S.top,
          textAlign: S.align,
          display: 'flex', flexDirection: 'column', gap: S.gap,
          textShadow: slide.lift,
        }}
      >
        <div style={{ ...typeOf(S.headline), color: slide.ink }}>{headline}</div>
        {body ? (
          <div style={{ ...typeOf(S.body), color: slide.ink }}>{body}</div>
        ) : null}
        {emphasis ? (
          <div style={{ ...typeOf(S.payoff), color: slide.ink }}>
            <Underlined text={emphasis} colour={S.accent} />
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/**
 * The payoff line, with whatever follows the last `|` in the accent colour and
 * underlined -- which is how every one of the BDP frames marks its last words.
 */
const Underlined: React.FC<{ text: string; colour: string }> = ({ text, colour }) => {
  const cut = text.lastIndexOf('|');
  if (cut < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, cut)}
      <span style={{ color: colour, textDecoration: 'underline' }}>
        {text.slice(cut + 1)}
      </span>
    </>
  );
};

/* --------------------------------------------------------- format: titled  */

const Ti = slideFormat.titled;

/**
 * A carousel cover: the photograph sharp, and the title set as a ladder.
 *
 * Each line is a different cut -- bold, bold italic, serif, bracketed italic --
 * which is what stops four lines of title reading as one grey block. The cards
 * below sit at slight angles and overlap.
 */
const Titled: React.FC<SlideProps> = ({
  image, background, focus, headline, kicker, emphasis, body, images, shape,
  step, of,
}) => {
  const geometry = shapeOf(shape);
  const shots = images ?? [];
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image ?? background} focus={focus} />
      <AbsoluteFill style={{ background: Ti.scrim }} />

      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          top: geometry.insetTop + geometry.height * 0.14,
          textAlign: Ti.align, textShadow: slide.lift, color: slide.ink,
        }}
      >
        <div style={typeOf(Ti.headline)}>{headline}</div>
        {kicker ? (
          <div style={{ ...typeOf(Ti.kicker), fontStyle: 'italic', marginLeft: '8%' }}>
            {kicker}
          </div>
        ) : null}
        {emphasis ? (
          <div style={{ ...typeOf(Ti.serif), marginLeft: '14%' }}>{emphasis}</div>
        ) : null}
        {body ? (
          <div style={{ ...typeOf(Ti.body), fontStyle: 'italic', marginLeft: '16%' }}>
            {body}
          </div>
        ) : null}
      </div>

      {shots.map((src, index) => (
        <Card
          key={src}
          src={src}
          radius={Ti.card.radius}
          style={{
            position: 'absolute',
            left: slide.side * (index === 0 ? 0.8 : 5.2),
            top: geometry.insetTop + geometry.height * (index === 0 ? 0.42 : 0.39),
            width: slide.width * Ti.card.width,
            height: geometry.height * Ti.card.height,
            transform: `rotate(${Ti.card.tilt + index * 3}deg)`,
          }}
        />
      ))}

      {shots.length ? (
        <PageArrow
          side="right"
          centre={geometry.insetTop + geometry.height * 0.48}
        />
      ) : null}
      {of ? <Dots step={step} of={of} shape={shape} /> : null}
    </AbsoluteFill>
  );
};

/* ---------------------------------------------------- format: beforeafter  */

const BA = slideFormat.beforeafter;

/**
 * The before and the after, annotated.
 *
 * An italic line, the number that changed set huge in the accent, a
 * parenthetical under it, then the two screenshots down the right with a
 * circle drawn round the figure on each -- red on what it was, green on what
 * it became -- and the two dates down the left with an arrow between them.
 */
const BeforeAfter: React.FC<SlideProps> = ({
  image, background, focus, kicker, headline, body, emphasis, images, handle,
  shape,
}) => {
  const geometry = shapeOf(shape);
  const shots = images ?? [];
  const [was, became] = (emphasis ?? '').split('/');
  const cardH = geometry.height * BA.card.height;
  const top = geometry.insetTop + geometry.height * 0.42;
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image ?? background} focus={focus} />
      <AbsoluteFill style={{ background: BA.scrim }} />

      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          top: geometry.insetTop + slide.side,
          textAlign: BA.align, textShadow: slide.lift,
        }}
      >
        {kicker ? (
          <div
            style={{ ...typeOf(BA.kicker), fontStyle: 'italic', color: slide.ink }}
          >
            {kicker}
          </div>
        ) : null}
        <div style={{ ...typeOf(BA.headline), color: BA.accent }}>{headline}</div>
        {body ? (
          <div style={{ ...typeOf(BA.body), color: slide.ink }}>{body}</div>
        ) : null}
      </div>

      {shots.map((src, index) => (
        <React.Fragment key={src}>
          <Card
            src={src}
            radius={BA.card.radius}
            style={{
              position: 'absolute',
              right: slide.side,
              top: top + index * (cardH + BA.card.gap),
              width: slide.width * BA.card.width,
              height: cardH,
            }}
          />
          <Ring
            colour={index === 0 ? BA.ring.was : BA.ring.became}
            cx={slide.width - slide.side - slide.width * BA.card.width * 0.32}
            cy={top + index * (cardH + BA.card.gap) + cardH * 0.55}
            rx={slide.width * 0.11}
            ry={cardH * 0.3}
          />
        </React.Fragment>
      ))}

      {/* The two dates, aligned to the middle of the card each one names. */}
      {was ? <Stamp text={was} y={top + cardH * 0.4} /> : null}
      {became ? (
        <Stamp text={became} y={top + cardH * 1.1 + BA.card.gap} arrow />
      ) : null}

      <div
        style={{
          position: 'absolute', left: slide.side, right: slide.side,
          bottom: slide.side + geometry.insetBottom,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}
      >
        <Handle handle={handle} />
        {handle ? <NextArrow /> : null}
      </div>
    </AbsoluteFill>
  );
};

/** One of the two dates, with the arrow that runs down to the next one. */
const Stamp: React.FC<{ text: string; y: number; arrow?: boolean }> = ({
  text, y, arrow,
}) => (
  <div
    style={{
      position: 'absolute', left: slide.side, top: y,
      ...typeOf(BA.label), color: slide.ink, textShadow: slide.lift,
    }}
  >
    {arrow ? <div style={{ marginBottom: BA.card.gap }}>{'\u2193'}</div> : null}
    {text}
  </div>
);

/** A circle drawn round the figure that changed, by hand rather than by grid. */
const Ring: React.FC<{
  colour: string; cx: number; cy: number; rx: number; ry: number;
}> = ({ colour, cx, cy, rx, ry }) => (
  <svg
    width={slide.width} height={rx * 4}
    style={{ position: 'absolute', left: 0, top: cy - rx * 2 }}
  >
    <ellipse
      cx={cx} cy={rx * 2} rx={rx} ry={ry}
      fill="none" stroke={colour} strokeWidth={BA.ring.weight}
      strokeLinecap="round" transform={`rotate(-4 ${cx} ${rx * 2})`}
    />
  </svg>
);

/* -------------------------------------------------------- format: collage  */

const Co = slideFormat.collage;

/**
 * The evidence, scattered.
 *
 * Screenshots at slight angles on an irregular black mask over a photograph,
 * with white caption boxes carrying black text at the bottom -- the inverse of
 * every other format's caption, and the reason it reads as a different post.
 */
const Collage: React.FC<SlideProps> = ({
  image, background, focus, headline, body, images, shape,
}) => {
  const geometry = shapeOf(shape);
  const shots = images ?? [];
  const lines = [headline, body].filter(Boolean) as string[];
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image ?? background} focus={focus} />
      <AbsoluteFill style={{ backgroundColor: Co.scrim }} />

      <Blob top={geometry.insetTop} height={geometry.height} />

      {shots.map((src, index) => (
        <Card
          key={src}
          src={src}
          radius={Co.shot.radius}
          style={{
            position: 'absolute',
            left: slide.side * (0.9 + index * 1.5),
            top: geometry.insetTop + geometry.height * (0.05 + index * 0.15),
            width: slide.width * 0.46,
            height: geometry.height * 0.18,
            transform: `rotate(${Co.shot.tilts[index % Co.shot.tilts.length]}deg)`,
          }}
        />
      ))}

      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          bottom: geometry.insetBottom + slide.side * 1.4,
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          gap: Co.gap,
        }}
      >
        {lines.map((line) => (
          <div
            key={line}
            style={{
              backgroundColor: Co.box, color: Co.onBox,
              borderRadius: Co.radius,
              paddingBlock: Co.paddingBlock, paddingInline: Co.paddingInline,
              ...typeOf(Co.caption), textAlign: Co.align,
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/**
 * The irregular black mask the screenshots sit on.
 *
 * Drawn with a cubic on every side rather than as a rounded rectangle: a
 * rectangle would read as a panel, and the point of this shape is that it
 * looks torn out by hand.
 */
const Blob: React.FC<{ top: number; height: number }> = ({ top, height }) => {
  const x = slide.side * 0.5;
  const w = slide.width - x * 2;
  const y = top + height * 0.02;
  const h = height * 0.6;
  return (
    <svg
      width={slide.width} height={height}
      style={{ position: 'absolute', top: 0, left: 0 }}
    >
      <path
        fill={Co.blob}
        d={`M${x},${y + h * 0.1}` +
           ` C${x + w * 0.06},${y - h * 0.05} ${x + w * 0.6},${y + h * 0.04} ${x + w},${y}` +
           ` C${x + w * 1.04},${y + h * 0.4} ${x + w * 0.96},${y + h * 0.7} ${x + w},${y + h}` +
           ` C${x + w * 0.6},${y + h * 1.05} ${x + w * 0.2},${y + h * 0.94} ${x},${y + h * 0.98}` +
           ` C${x - w * 0.04},${y + h * 0.6} ${x + w * 0.03},${y + h * 0.35} ${x},${y + h * 0.1} Z`}
      />
    </svg>
  );
};

/** The carousel page dots, shared by the formats that simulate them. */
const Dots: React.FC<{ step?: number; of: number; shape?: SlideShape }> = ({
  step, of, shape,
}) => (
  <div
    style={{
      position: 'absolute', left: 0, right: 0,
      bottom: slide.side + shapeOf(shape).insetBottom,
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
);

/* ------------------------------------------------------------------ pieces */

/** One rounded rectangle as an SVG subpath. */
const roundedRect = (x: number, y: number, w: number, h: number, r: number) =>
  `M${x + r},${y} H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r}` +
  ` V${y + h - r} A${r},${r} 0 0 1 ${x + w - r},${y + h}` +
  ` H${x + r} A${r},${r} 0 0 1 ${x},${y + h - r}` +
  ` V${y + r} A${r},${r} 0 0 1 ${x + r},${y} Z`;

/**
 * A clip that removes the picture's rectangle from whatever it is put on.
 *
 * The textured format can punch its ground with one flat SVG shape because
 * that ground is a flat colour. A blurred ground is a photograph, so the hole
 * has to be cut out of the painted layers themselves -- an even-odd clip over
 * the frame with the card's rectangle as the second subpath.
 */
const hole = (
  width: number, height: number, box: { x: number; y: number; w: number; h: number },
  radius: number,
) =>
  `path(evenodd, "M0,0 H${width} V${height} H0 Z ` +
  `${roundedRect(box.x, box.y, box.w, box.h, radius)}")`;

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
  const hole = roundedRect(x, y, w, h, slide.card.radius);

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
