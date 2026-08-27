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
  image: string;
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
  <AbsoluteFill style={{ backgroundColor: slide.ground }}>
    <Img
      src={staticFile(image)}
      style={{
        width: '100%', height: '100%',
        objectFit: 'cover', objectPosition: focus ?? 'center',
      }}
    />
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
  <AbsoluteFill
    style={{
      backgroundColor: slide.ground, padding: slide.side,
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

    {/* Takes whatever height is left, so a longer paragraph shrinks the
        picture rather than pushing it off the slide. */}
    <div
      style={{
        flex: 1, alignSelf: 'stretch',
        marginTop: slide.pill.paddingInline,
        marginBottom: slide.handleSize * 2,
        borderRadius: slide.card.radius,
        backgroundColor: slide.card.background,
        boxShadow: `0 ${slide.card.shadowDrop}px ${slide.card.shadowBlur}px ${slide.card.shadow}`,
        overflow: 'hidden',
      }}
    >
      <Img
        src={staticFile(image)}
        style={{
          width: '100%', height: '100%',
          objectFit: 'cover', objectPosition: focus ?? 'center',
        }}
      />
    </div>

    <div style={{ position: 'absolute', inset: slide.side, top: 'auto' }}>
      <Handle handle={handle} />
    </div>
  </AbsoluteFill>
);

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
