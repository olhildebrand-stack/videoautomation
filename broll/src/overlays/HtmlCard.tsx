import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { moveStyle } from './motion';
import { dimensions, safeZone } from '../tokens';

/**
 * A composition written for one beat, rendered as given.
 *
 * The fixed effects in this folder cover what recurs. This covers what does
 * not: a diagram that only makes sense for one sentence of one video, which
 * is not worth a component and is worth having.
 *
 * The markup is inlined by the pipeline rather than fetched at render time.
 * A missing file is then caught by the same asset check as every other cue,
 * instead of by Remotion 404ing mid-render and taking the whole thing down --
 * which is exactly how a missing screenshot cancelled a render earlier.
 *
 * `full` decides whether it may use the whole frame. Off by default: a beat
 * card sits inside the safe zone like everything else, and only something
 * deliberately covering the picture -- a background, a wash -- should be
 * allowed past it.
 */
export const HtmlCard: React.FC<{
  html: string;
  enter: number;
  leave?: number | null;
  full?: boolean;
}> = ({ html, enter, leave, full = false }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!html) return null;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        paddingTop: full ? 0 : safeZone.top,
        paddingBottom: full ? 0 : safeZone.bottom,
        paddingInline: full ? 0 : safeZone.side,
        ...moveStyle(frame, fps, enter, leave),
      }}
    >
      <div
        style={{
          width: full ? dimensions.width : '100%',
          height: full ? dimensions.height : '100%',
          // The markup is the operator's own; it decides its own layout.
          // Everything above only decides how much frame it is given.
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
};
