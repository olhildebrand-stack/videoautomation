import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { ease, framesFor } from './motion';
import { flash } from '../tokens';

/**
 * The screen blowing out white, once.
 *
 * Up fast and down slow, which is what a camera flash does and what a strobe
 * does not. It covers the cut underneath it: whatever changes during the white
 * is not seen changing, which is the entire point of using one.
 */
export const Flash: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const up = framesFor(flash.upMs, fps);
  const down = framesFor(flash.downMs, fps);
  const opacity = interpolate(
    frame,
    [at, at + up, at + up + down],
    [0, 1, 0],
    { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );

  if (opacity <= 0) return null;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundColor: flash.colour,
        opacity,
      }}
    />
  );
};
