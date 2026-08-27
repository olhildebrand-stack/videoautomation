import React from 'react';
import { Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { ease, framesFor, moveStyle } from './motion';
import {
  caption, dimensions, iconCard, questionPill, safeZone,
} from '../tokens';

export type IconSlot = {
  /** What this logo is, for the sheet to read. Never drawn: the mark is the
   * whole point, and a word under it says twice what the caption already
   * says once. */
  name: string;
  /** A file in the project's assets, or an emoji if there is no logo to hand. */
  src?: string;
  emoji?: string;
  /** Absolute frame this one comes into focus. */
  enter: number;
};

/**
 * A row of logos, each snapping into focus as it is named.
 *
 * The blur is the whole idea. A logo that has not been named yet is on screen
 * but unreadable: the viewer knows a third one is coming and cannot read ahead
 * to it. Naming it snaps it into focus. Fading it in instead would give away
 * how many are left by the empty space.
 *
 * The row holds its layout from the first frame, so a card coming into focus
 * does not shift its neighbours.
 */
export const IconRow: React.FC<{
  slots: IconSlot[];
  question?: string;
  /** Absolute frame the row appears, blurred. */
  enter: number;
  leave?: number | null;
}> = ({ slots, question, enter, leave }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <div
        style={{
          position: 'absolute',
          top: safeZone.top,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          gap: iconCard.gap,
          ...moveStyle(frame, fps, enter, leave),
        }}
      >
        {slots.map((slot, index) => (
          <Card key={`${slot.name}-${index}`} slot={slot} frame={frame} fps={fps} />
        ))}
      </div>

      {question ? (
        <div
          style={{
            position: 'absolute',
            top: dimensions.height * questionPill.atHeight,
            left: 0,
            right: 0,
            display: 'flex',
            justifyContent: 'center',
            paddingInline: safeZone.side,
            ...moveStyle(frame, fps, enter, leave),
          }}
        >
          <div
            style={{
              backgroundColor: questionPill.background,
              color: questionPill.text,
              borderRadius: questionPill.radius,
              paddingBlock: questionPill.paddingBlock,
              paddingInline: questionPill.paddingInline,
              fontFamily: caption.fontFamily,
              fontWeight: caption.fontWeight,
              fontSize: questionPill.fontSize,
              textAlign: 'center',
            }}
          >
            {question}
          </div>
        </div>
      ) : null}
    </div>
  );
};

const Card: React.FC<{ slot: IconSlot; frame: number; fps: number }> = ({
  slot, frame, fps,
}) => {
  // Blurred until named, then snapped into focus. Nothing moves.
  const focus = interpolate(
    frame,
    [slot.enter, slot.enter + framesFor(iconCard.focusMs, fps)],
    [iconCard.blur, 0],
    { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );

  return (
    // A fixed square, fitted rather than filled. The square is what holds the
    // row's layout still; the source files agree on nothing, so sizing by one
    // dimension let a tall logo tower over a wide one.
    <div
      style={{
        width: iconCard.size,
        height: iconCard.size,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        filter: `blur(${focus}px)`,
      }}
    >
      {slot.src ? (
        <Img
          src={staticFile(slot.src)}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      ) : (
        <div style={{ fontSize: iconCard.size * 0.8, lineHeight: 1 }}>
          {slot.emoji ?? '⬛'}
        </div>
      )}
    </div>
  );
};
