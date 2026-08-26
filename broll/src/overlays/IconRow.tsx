import React from 'react';
import { Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { ease, framesFor, moveStyle } from './motion';
import {
  caption, dimensions, iconCard, questionPill, safeZone, verdict,
} from '../tokens';
import type { VerdictTone } from '../tokens';

export type IconSlot = {
  /** Absent where the icons are not a verdict, and nothing is set above them. */
  tone?: VerdictTone;
  /** The app's name, set small under the icon. */
  name: string;
  /** A file in the project's assets, or an emoji if there is no logo to hand. */
  src?: string;
  emoji?: string;
  /** Absolute frame this one comes into focus. */
  enter: number;
};

/**
 * Three verdicts side by side, each revealed as it is named.
 *
 * The blur is the whole idea. An icon that has not been named yet is on screen
 * but unreadable: the viewer knows a third answer is coming and cannot read
 * ahead to it. Naming it snaps it into focus. Fading it in instead would give
 * away how many are left by the empty space.
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
  const named = frame >= slot.enter;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {slot.tone ? (
        <div
          style={{
            fontFamily: caption.fontFamily,
            fontWeight: caption.fontWeight,
            fontSize: iconCard.labelSize,
            color: verdict[slot.tone],
            marginBottom: 6,
            textTransform: 'uppercase',
          }}
        >
          {slot.tone}
        </div>
      ) : null}
      <div
        style={{
          width: iconCard.size,
          height: iconCard.size,
          borderRadius: iconCard.radius,
          backgroundColor: iconCard.background,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          // The card stays sharp; only what is inside it is unreadable.
          filter: `blur(${focus}px)`,
        }}
      >
        {slot.src ? (
          // A fixed square with the logo fitted inside it. Sizing by width
          // alone let a tall logo tower over a wide one, since the source
          // files agree on nothing.
          <Img
            src={staticFile(slot.src)}
            style={{
              width: iconCard.size * 0.52,
              height: iconCard.size * 0.52,
              objectFit: 'contain',
            }}
          />
        ) : (
          <div style={{ fontSize: iconCard.size * 0.46, lineHeight: 1 }}>
            {slot.emoji ?? '⬛'}
          </div>
        )}
        <div
          style={{
            fontFamily: caption.fontFamily,
            fontWeight: caption.fontWeight,
            fontSize: iconCard.nameSize,
            color: iconCard.text,
            textTransform: 'uppercase',
            opacity: named ? 1 : 0.9,
          }}
        >
          {slot.name}
        </div>
      </div>
    </div>
  );
};
