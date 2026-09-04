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
  /**
   * labels: a second, quieter line held at the FOOT of the frame and centred,
   * away from the stack at the top. The reference stories put a smaller box
   * down there for an aside -- a second way in, a note -- which reads as an
   * afterthought precisely because it is not in the main column.
   */
  foot?: string;
  /** collage, titled, beforeafter: the screenshots they scatter or stack. */
  images?: string[];
  /**
   * collage: the figures called out of those screenshots, each placed where
   * its number actually is, as a fraction of the frame.
   */
  chips?: { text: string; x: number; y: number }[];
  /** thread: what was said, and by whom. */
  messages?: { text: string; from?: string; mine?: boolean }[];
  /** beforeafter: a sequence down the middle, in place of the two cards. */
  steps?: string[];
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
  if (props.format === 'ticker') return <Ticker {...props} />;
  if (props.format === 'thread') return <Thread {...props} />;
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

const typeOf = (role: Role, scale = 1): React.CSSProperties => ({
  fontFamily: role.family,
  fontWeight: role.weight,
  fontSize: role.size * scale,
  letterSpacing: role.tracking,
  lineHeight: role.leading,
  whiteSpace: 'pre-line',
});

/*
 * Note the `||` at every call site below, never `??`. A slide that names no
 * picture is given `image: ""` rather than having the key omitted, so that a
 * composition's defaultProps cannot leak into it -- and `"" ?? background` is
 * `""`, which silently drops the ground.
 */
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
    <Fill src={image || background} focus={focus} />
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
        <Fill src={background || image} focus="center" blur={B.blurPx} />
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
  image, background, focus, headline, body, emphasis, foot, shape,
}) => {
  const geometry = shapeOf(shape);
  // A newline starts a new box, it does not wrap inside one. The references
  // stack short boxes -- "7", "and", "90" one under another -- and a box that
  // held all three would be a different thing entirely. Text long enough to
  // wrap still wraps inside its own box; that is a paragraph, and a paragraph
  // is what a box holds.
  const boxes = [
    { text: headline, box: L.box, role: L.headline },
    { text: body, box: L.box, role: L.body },
    { text: emphasis, box: L.emphasisBox, role: L.body },
  ].flatMap(({ text, box, role }, group) =>
    (text || '').split('\n').filter(Boolean)
      .map((line, i) => ({ line, box, role, opens: i === 0 && group > 0 })));
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image || background} focus={focus} />
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
        {boxes.map(({ line, box, role, opens }, index) => (
          <div
            key={index}
            style={{
              marginTop: opens ? L.groupGap - L.gap : 0,
              backgroundColor: box,
              borderRadius: L.radius,
              paddingBlock: L.paddingBlock,
              paddingInline: L.paddingInline,
              ...typeOf(role, geometry.typeScale),
              color: slide.ink,
              textAlign: L.align,
            }}
          >
            {line}
          </div>
        ))}
      </div>
      {foot ? (
        <div
          style={{
            position: 'absolute',
            left: slide.side, right: slide.side,
            bottom: geometry.insetBottom + slide.side,
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            gap: L.gap,
          }}
        >
          {foot.split('\n').filter(Boolean).map((line, index) => (
            <div
              key={index}
              style={{
                backgroundColor: L.box,
                borderRadius: L.radius,
                paddingBlock: L.paddingBlock,
                paddingInline: L.paddingInline,
                ...typeOf(L.body, geometry.typeScale),
                color: slide.ink,
                textAlign: 'center',
              }}
            >
              {line}
            </div>
          ))}
        </div>
      ) : null}
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
      <Fill src={image || background} focus={focus} />
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
  step, of, steps,
}) => {
  const geometry = shapeOf(shape);
  const shots = images ?? [];
  const scale = geometry.typeScale;
  // Measured down the safe area, not the whole frame. A story's safe area is
  // 1370 tall against the carousel's 1350, so the same fractions put the
  // ladder and the screenshot in the same place on both.
  const safe = geometry.height - geometry.insetTop - geometry.insetBottom;
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image || background} focus={focus} />
      <AbsoluteFill style={{ background: Ti.scrim }} />

      <div
        style={{
          position: 'absolute',
          left: slide.side, right: slide.side,
          top: geometry.insetTop + safe * 0.1,
          textAlign: Ti.align, textShadow: slide.lift, color: slide.ink,
        }}
      >
        <div style={typeOf(Ti.headline, scale)}>{headline}</div>
        {kicker ? (
          <div
            style={{ ...typeOf(Ti.kicker, scale), fontStyle: 'italic', marginLeft: '8%' }}
          >
            {kicker}
          </div>
        ) : null}
        {emphasis ? (
          <div style={{ ...typeOf(Ti.serif, scale), marginLeft: '14%' }}>{emphasis}</div>
        ) : null}
        {body ? (
          <div
            style={{ ...typeOf(Ti.body, scale), fontStyle: 'italic', marginLeft: '16%' }}
          >
            {body}
          </div>
        ) : null}
      </div>

      {/* Commands are typed, so they are set rather than photographed --
          sharp at any size, and centred instead of ragged left. */}
      {steps?.length ? (
        <div
          style={{
            position: 'absolute',
            left: slide.side, right: slide.side,
            top: geometry.insetTop + safe * Ti.terminal.top,
            backgroundColor: Ti.terminal.background,
            borderRadius: Ti.terminal.radius,
            paddingBlock: Ti.terminal.padBlock,
            paddingInline: Ti.terminal.padInline,
            boxShadow: `0 ${slide.card.shadowDrop}px ${slide.card.shadowBlur}px ${slide.card.shadow}`,
            ...typeOf(Ti.terminal),
            color: Ti.terminal.ink,
            textAlign: 'center',
          }}
        >
          {steps.join('\n\n')}
        </div>
      ) : null}

      {/* Two screenshots scatter; one is the subject and sits straight. */}
      {shots.length === 1 ? (
        <div
          style={{
            position: 'absolute',
            left: slide.side, right: slide.side,
            top: geometry.insetTop + safe * Ti.shot.top,
            backgroundColor: Ti.shot.background,
            borderRadius: Ti.shot.radius,
            padding: Ti.shot.pad,
            boxShadow: `0 ${slide.card.shadowDrop}px ${slide.card.shadowBlur}px ${slide.card.shadow}`,
          }}
        >
          {/* Contained, not cropped: a terminal screenshot is mostly
              whitespace, and a cover crop cuts the half with the commands. */}
          {/* The card takes its height from the screenshot rather than
              imposing one: a terminal capture is wide and short, and a fixed
              box leaves it stranded in the middle of empty card. */}
          <Img
            src={staticFile(shots[0] ?? '')}
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
        </div>
      ) : (
        shots.map((src, index) => (
          <Card
            key={src}
            src={src}
            radius={Ti.card.radius}
            style={{
              position: 'absolute',
              left: slide.side * (index === 0 ? 0.8 : 5.2),
              top: geometry.insetTop + safe * (index === 0 ? 0.42 : 0.39),
              width: slide.width * Ti.card.width,
              height: geometry.height * Ti.card.height,
              transform: `rotate(${Ti.card.tilt + index * 3}deg)`,
            }}
          />
        ))
      )}

      {shots.length > 1 ? (
        <PageArrow
          side="right"
          centre={geometry.insetTop + safe * 0.48}
        />
      ) : null}
      {/* Dots are a carousel's affordance. A story has no dots -- it has an
          arrow that says another slide is coming. */}
      {of && shape === 'story' ? (
        step && step < of ? (
          <div
            style={{
              position: 'absolute', right: slide.side,
              bottom: slide.side + geometry.insetBottom,
            }}
          >
            <NextArrow />
          </div>
        ) : null
      ) : of ? (
        <Dots step={step} of={of} shape={shape} />
      ) : null}
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
  shape, steps,
}) => {
  const geometry = shapeOf(shape);
  const shots = images ?? [];
  const [was, became] = (emphasis ?? '').split('/');
  const scale = geometry.typeScale;
  const cardH = geometry.height * BA.card.height;
  const top = geometry.insetTop + geometry.height * 0.42;
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image || background} focus={focus} />
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
            style={{
              ...typeOf(BA.kicker, scale), fontStyle: 'italic', color: slide.ink,
            }}
          >
            {kicker}
          </div>
        ) : null}
        {headline ? (
          <div style={{ ...typeOf(BA.headline, scale), color: BA.accent }}>
            {headline}
          </div>
        ) : null}
        {/* The parenthetical is unscaled: it is subordinate to the line above
            it and stays small, as it does in the reference. Grown with the
            rest it wraps, and a wrapped aside reads as a second thought. */}
        {body ? (
          <div style={{ ...typeOf(BA.body), color: slide.ink }}>{body}</div>
        ) : null}
      </div>

      {steps?.length ? <Sequence steps={steps} shape={shape} /> : null}

      {shots.map((src, index) => (
        <Card
          key={src}
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
      ))}

      {/* The two dates, aligned to the card each one names, with the arrow
          running the whole way down between them -- it is the distance that
          says how long this took, so a glyph sitting next to one of them
          says nothing. */}
      {was ? <Stamp text={was} y={top + cardH * 0.4} /> : null}
      {became ? (
        <Stamp text={became} y={top + cardH * 1.4 + BA.card.gap} />
      ) : null}
      {was && became ? (
        <LongArrow
          from={top + cardH * 0.4 + BA.label.size + BA.arrow.clear}
          to={top + cardH * 1.4 + BA.card.gap - BA.arrow.clear}
        />
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

/**
 * A sequence down the middle of the frame, one step per line with an arrow
 * between. It replaces the two cards rather than sitting beside them: the
 * claim is the order, and there is nothing to photograph.
 */
const Sequence: React.FC<{ steps: string[]; shape?: SlideShape }> = ({
  steps, shape,
}) => (
  <AbsoluteFill
    style={{
      paddingTop: shapeOf(shape).insetTop,
      paddingBottom: shapeOf(shape).insetBottom,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      textShadow: slide.lift,
    }}
  >
    {steps.map((name, index) => (
      <React.Fragment key={name}>
        {index ? (
          <div
            style={{
              color: BA.steps.dim, lineHeight: 1,
              marginBlock: BA.steps.gap * 0.4,
            }}
          >
            <svg width={BA.steps.arrow} height={BA.steps.arrow} viewBox="0 0 30 30">
              <path
                d="M15 2 V26 M7 19 L15 27 L23 19"
                stroke={BA.steps.dim} strokeWidth={BA.steps.arrowWeight}
                fill="none" strokeLinecap="round" strokeLinejoin="round"
              />
            </svg>
          </div>
        ) : null}
        <div style={{ ...typeOf(BA.steps, shapeOf(shape).typeScale), color: slide.ink }}>
          {name}
        </div>
      </React.Fragment>
    ))}
  </AbsoluteFill>
);

/** One of the two dates. */
const Stamp: React.FC<{ text: string; y: number }> = ({ text, y }) => (
  <div
    style={{
      position: 'absolute', left: slide.side, top: y,
      ...typeOf(BA.label), color: slide.ink, textShadow: slide.lift,
    }}
  >
    {text}
  </div>
);

/**
 * The arrow between the two dates: a long line starting under the first and
 * ending, head and all, just above the second. Its length is the point.
 */
const LongArrow: React.FC<{ from: number; to: number }> = ({ from, to }) => {
  const x = slide.side + BA.arrow.offset;
  const head = BA.arrow.head;
  // A round cap and a mitred point both paint past the coordinate they are
  // drawn at, so the box is grown by the stroke on every side and the path
  // inset into it. Drawn flush, the tip of the arrow gets shaved off.
  const pad = BA.arrow.weight;
  const span = to - from;
  return (
    <svg
      width={slide.width} height={span + pad * 2}
      style={{ position: 'absolute', left: 0, top: from - pad }}
    >
      <path
        d={`M${x},${pad} V${span + pad}` +
           ` M${x - head},${span + pad - head} L${x},${span + pad}` +
           ` L${x + head},${span + pad - head}`}
        stroke={slide.ink}
        strokeWidth={BA.arrow.weight}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

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
  image, background, focus, headline, body, images, chips, shape,
}) => {
  const geometry = shapeOf(shape);
  const shots = images ?? [];
  const lines = [headline, body].filter(Boolean) as string[];
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image || background} focus={focus} blur={Co.blurPx} />
      <AbsoluteFill style={{ backgroundColor: Co.scrim }} />

      {/* Three places, filled in order. A fourth screenshot has nowhere to go
          that does not bury one of the first three, and the reference never
          shows more than three. */}
      {Co.shot.boxes.map((box, index) => {
        const src = shots[index];
        return src ? (
          <Card
            key={src}
            src={src}
            radius={Co.shot.radius}
            style={{
              position: 'absolute',
              left: slide.width * box.x,
              top: geometry.height * box.y,
              width: slide.width * box.w,
              height: geometry.height * box.h,
              transform: `rotate(${box.tilt}deg)`,
            }}
          />
        ) : null;
      })}

      {/* Over the screenshots, under the captions: a chip is an annotation on
          the evidence, not part of the sentence about it. */}
      {(chips ?? []).map((chip) => (
        <div
          key={chip.text}
          style={{
            position: 'absolute',
            left: slide.width * chip.x,
            top: geometry.height * chip.y,
            backgroundColor: Co.chip.background, color: Co.chip.ink,
            borderRadius: Co.chip.radius,
            paddingBlock: Co.chip.paddingBlock,
            paddingInline: Co.chip.paddingInline,
            fontFamily: Co.caption.family, fontWeight: Co.caption.weight,
            fontSize: Co.chip.size, letterSpacing: Co.caption.tracking,
            boxShadow: Co.chip.shadow,
          }}
        >
          {chip.text}
        </div>
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

/* --------------------------------------------------------- format: ticker  */

const K = slideFormat.ticker;

/**
 * One number, big enough to be the picture.
 *
 * Sized to fill the frame edge to edge, and clipped when the figure is long
 * enough to run past it. Nothing else on the slide competes.
 */
const Ticker: React.FC<SlideProps> = ({
  image, background, focus, kicker, headline, body, shape,
}) => {
  const geometry = shapeOf(shape);
  const ground = image || background;
  return (
    <AbsoluteFill style={{ backgroundColor: K.ground }}>
      {ground ? (
        <>
          {/* Both are blurred, a texture far less. Only a photograph is
              darkened: a scrim took a texture of mean luma 37 to black. */}
          <Fill
            src={ground}
            focus={focus}
            blur={image ? K.blur.photo : K.blur.texture}
          />
          {image ? <AbsoluteFill style={{ backgroundColor: K.scrim }} /> : null}
          <AbsoluteFill style={{ background: K.vignette }} />
        </>
      ) : null}
      <AbsoluteFill
        style={{
          paddingTop: geometry.insetTop + slide.side,
          paddingBottom: geometry.insetBottom + slide.side,
          paddingInline: slide.side,
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          textShadow: ground ? slide.lift : undefined,
        }}
      >
        <div style={{ ...typeOf(K.label), color: K.ink, textTransform: 'uppercase' }}>
          {kicker}
        </div>
        {/* Clipped on purpose: the figure runs past both edges. */}
        <div style={{ overflow: 'hidden', marginInline: -slide.side }}>
          <div
            style={{
              ...typeOf(K.figure), color: K.accent,
              whiteSpace: 'nowrap', paddingInline: slide.side * 0.4,
            }}
          >
            {headline}
          </div>
        </div>
        <div style={{ ...typeOf(K.body), color: K.ink }}>{body}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* --------------------------------------------------------- format: thread  */

const Th = slideFormat.thread;

/**
 * The conversation itself, drawn rather than screenshotted.
 *
 * A screenshot of a thread carries someone's battery percentage, their unread
 * count and their wallpaper. Drawn, it carries only what was said -- at the
 * cost of no longer being evidence, so this is for a thread worth reading
 * rather than a thread worth proving.
 */
const Thread: React.FC<SlideProps> = ({
  image, background, focus, headline, messages, shape,
}) => {
  const geometry = shapeOf(shape);
  return (
    <AbsoluteFill style={{ backgroundColor: slide.ground }}>
      <Fill src={image || background} focus={focus} blur={Th.blurPx} />
      <AbsoluteFill style={{ backgroundColor: Th.scrim }} />
      <AbsoluteFill
        style={{
          paddingTop: geometry.insetTop + slide.side,
          paddingBottom: geometry.insetBottom + slide.side,
          paddingInline: slide.side,
          display: 'flex', flexDirection: 'column', justifyContent: 'center',
          gap: Th.gap,
        }}
      >
        {headline ? (
          <div
            style={{
              ...typeOf(Th.name), color: Th.ink, opacity: 0.7,
              textAlign: 'center', marginBottom: slide.side * 0.4,
            }}
          >
            {headline}
          </div>
        ) : null}
        {(messages ?? []).map((message, index) => (
          <div
            key={index}
            style={{
              alignSelf: message.mine ? 'flex-end' : 'flex-start',
              maxWidth: `${Th.width * 100}%`,
              backgroundColor: message.mine ? Th.me : Th.them,
              color: Th.ink,
              borderRadius: Th.radius,
              borderBottomRightRadius: message.mine ? Th.tail : Th.radius,
              borderBottomLeftRadius: message.mine ? Th.radius : Th.tail,
              padding: slide.side * 0.42,
            }}
          >
            {message.from ? <Redacted name={message.from} /> : null}
            <div style={typeOf(Th.body)}>{message.text}</div>
          </div>
        ))}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/**
 * The sender's name, blurred.
 *
 * A real thread has a real person in it, and putting their name on a story
 * calls them out; inventing one reads as invented. Blurred, it still says
 * that someone you know sent this.
 */
const Redacted: React.FC<{ name: string }> = ({ name }) => (
  <div
    style={{
      display: 'inline-block',
      backgroundColor: Th.redact.background,
      borderRadius: Th.redact.radius,
      paddingInline: Th.redact.padInline,
      filter: `blur(${Th.redact.blurPx}px)`,
      ...typeOf(Th.name),
    }}
  >
    {name}
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
