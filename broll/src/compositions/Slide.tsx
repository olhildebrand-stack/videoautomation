import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { caption, slide } from '../tokens';

/**
 * One carousel slide, rendered as a still.
 *
 * Two layouts, because the references only ever use two. A `cover` is the
 * photograph with the claim over it and nothing else competing. A `body` slide
 * is the dark ground carrying a label, a heading, a paragraph, and a picture of
 * whatever the paragraph is about.
 *
 * `emphasis` is the one clause per slide allowed to leave the text colour. The
 * references put exactly one there and it is always the point of the slide, so
 * it is a field rather than markup: you cannot accidentally colour three.
 */
export type SlideProps = {
  kind: 'cover' | 'body';
  /**
   * Absent on a body slide means the picture is a video the editor will lay
   * in: the ground is punched through where the card would be, and the still
   * is written with an alpha channel. Put the clip behind the PNG, filling the
   * frame, and the hole is the card.
   */
  image?: string;
  /** Where to hold the photograph while cropping it to 4:5, as `object-position`. */
  focus?: string;
  /** cover: the second, quieter line under the claim. body: the pill. */
  kicker?: string;
  headline: string;
  body?: string;
  emphasis?: string;
  handle?: string;
};

export const Slide: React.FC<SlideProps> = (props) =>
  props.kind === 'cover' ? <Cover {...props} /> : <Body {...props} />;

const Cover: React.FC<SlideProps> = ({ image, focus, headline, kicker, handle }) => (
  // A cover is the photograph, so it always names one.
  <AbsoluteFill style={{ backgroundColor: slide.ground }}>
    {image ? (
      <Img
        src={staticFile(image)}
        style={{
          width: '100%', height: '100%',
          objectFit: 'cover', objectPosition: focus ?? 'center',
        }}
      />
    ) : null}
    {/* The claim has to read over whatever the photograph happens to be. */}
    <AbsoluteFill
      style={{
        background: `linear-gradient(${slide.scrim}, transparent 55%, ${slide.scrim})`,
      }}
    />
    <AbsoluteFill
      style={{
        padding: slide.side,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      }}
    >
      <div>
        <div
          style={{
            fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
            fontSize: slide.coverSize, lineHeight: slide.lineHeight,
            letterSpacing: caption.letterSpacing, color: slide.headline,
            whiteSpace: 'pre-line',
          }}
        >
          {headline}
        </div>
        {kicker ? (
          <div
            style={{
              marginTop: slide.pill.paddingBlock,
              fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
              fontSize: slide.kickerSize, color: slide.accent,
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
  image, focus, kicker, headline, body, emphasis, handle,
}) => (
  <AbsoluteFill style={image ? { backgroundColor: slide.ground } : undefined}>
    {image ? null : <PunchedGround />}

    <AbsoluteFill
      style={{
        padding: slide.side,
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

      <div
        style={{
          marginTop: slide.pill.paddingInline,
          fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
          fontSize: slide.headlineSize, lineHeight: slide.lineHeight,
          letterSpacing: caption.letterSpacing,
          color: slide.headline, textAlign: 'center', whiteSpace: 'pre-line',
        }}
      >
        {headline}
      </div>

      {body ? (
        <div
          style={{
            marginTop: slide.pill.paddingBlock,
            fontFamily: caption.fontFamily, fontWeight: caption.fontWeight,
            fontSize: slide.bodySize, lineHeight: slide.bodyLineHeight,
            color: slide.body, textAlign: 'center',
          }}
        >
          {body}
          {emphasis ? <span style={{ color: slide.accent }}> {emphasis}</span> : null}
        </div>
      ) : null}
    </AbsoluteFill>

    {image ? (
      <div style={{ ...pictureBox, ...cardStyle }}>
        <Img
          src={staticFile(image)}
          style={{
            width: '100%', height: '100%',
            objectFit: 'cover', objectPosition: focus ?? 'center',
          }}
        />
      </div>
    ) : null}

    <div style={{ position: 'absolute', inset: slide.side, top: 'auto' }}>
      <Handle handle={handle} />
    </div>
  </AbsoluteFill>
);

/** The picture's place, shared by the card and the hole cut for a video. */
const pictureBox = {
  position: 'absolute',
  left: slide.side,
  right: slide.side,
  top: slide.picture.top,
  bottom: slide.picture.bottom,
} as const;

const cardStyle = {
  borderRadius: slide.card.radius,
  backgroundColor: slide.card.background,
  boxShadow: `0 ${slide.card.shadowDrop}px ${slide.card.shadowBlur}px ${slide.card.shadow}`,
  overflow: 'hidden',
} as const;

/**
 * The ground with the picture's rectangle missing from it.
 *
 * One path with two subpaths and an even-odd fill: the inner rounded rectangle
 * is never painted, so the still keeps a real hole rather than a dark patch
 * that would sit on top of the video.
 */
const PunchedGround: React.FC = () => {
  const x = slide.side;
  const y = slide.picture.top;
  const w = slide.width - slide.side * 2;
  const h = slide.height - slide.picture.top - slide.picture.bottom;
  const r = slide.card.radius;
  const hole =
    `M${x + r},${y} H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r}` +
    ` V${y + h - r} A${r},${r} 0 0 1 ${x + w - r},${y + h}` +
    ` H${x + r} A${r},${r} 0 0 1 ${x},${y + h - r}` +
    ` V${y + r} A${r},${r} 0 0 1 ${x + r},${y} Z`;

  return (
    <svg
      width={slide.width}
      height={slide.height}
      style={{ position: 'absolute', top: 0, left: 0 }}
    >
      <path
        fillRule="evenodd"
        fill={slide.ground}
        d={`M0,0 H${slide.width} V${slide.height} H0 Z ${hole}`}
      />
    </svg>
  );
};

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
