import React from 'react';
import { color, font, fontSize, radiusMsg, space } from '../tokens';

/**
 * The single radius exception, and the only component allowed to import
 * `radiusMsg`.
 *
 * A conversation rendered entirely in hard rectangles reads as a system log
 * rather than as two people talking, and in b-roll the viewer has roughly one
 * second to recognise what they are looking at. The 6px lives here and travels
 * nowhere else — not to the container these rows sit in, not to cards, panels,
 * inputs, buttons, avatars, or badges.
 *
 * `landed` (0 → 1) cross-fades the flare fill with the text knocked out in
 * void. That inversion is the beat you cut to — never a zoom or a push.
 */
export const MessageRow: React.FC<{
  children: React.ReactNode;
  side: 'incoming' | 'outgoing';
  /** 0 → 1 across the state change. */
  landed?: number;
  opacity?: number;
}> = ({ children, side, landed = 0, opacity = 1 }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: side === 'outgoing' ? 'flex-end' : 'flex-start',
      opacity,
    }}
  >
    <div
      style={{
        position: 'relative',
        maxWidth: '68%',
        paddingBlock: space['2'],
        paddingInline: space['3'],
        borderRadius: radiusMsg,
        backgroundColor: color.slab,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: color.flare,
          opacity: landed,
        }}
      />
      {/* The two treatments cross-fade, so the text never passes through an
          illegible mid-blend. Opacity is the only property that moves. */}
      <div style={{ ...font.body, position: 'relative', fontSize: fontSize.lg }}>
        <div style={{ color: color.bone, opacity: 1 - landed }}>{children}</div>
        <div style={{ position: 'absolute', inset: 0, color: color.void, opacity: landed }}>
          {children}
        </div>
      </div>
    </div>
  </div>
);
