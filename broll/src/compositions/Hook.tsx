import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { caption, fontSize, hook, safeZone, space } from '../tokens';

/**
 * The hook card: white on a solid black bar across the top.
 *
 * Holds for `hook.seconds` and then cuts. It does not fade: it is a title card
 * competing with the first seconds of speech, and a fade reads as hesitation
 * where the point is to state the claim and get out of the way.
 */
export const Hook: React.FC<{ text: string; seconds?: number }> = ({
  text,
  seconds = hook.seconds,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!text || frame >= seconds * fps) {
    return null;
  }

  const size = fontSize['2xl'];

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-start',
        alignItems: 'center',
        paddingTop: safeZone.top,
        paddingInline: safeZone.side,
      }}
    >
      <div
        style={{
          maxWidth: '100%',
          backgroundColor: hook.background,
          color: hook.fill,
          paddingBlock: space['2'],
          paddingInline: space['3'],
          borderRadius: hook.radius,
          fontFamily: caption.fontFamily,
          fontWeight: caption.fontWeight,
          fontSize: size,
          lineHeight: caption.lineHeight,
          letterSpacing: caption.letterSpacing,
          textAlign: 'center',
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
