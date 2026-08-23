import React from 'react';
import { AbsoluteFill } from 'remotion';
import { color, space } from '../tokens';

/**
 * The ground. Every frame starts here: solid `void`, generous negative space,
 * no gradient and no vignette.
 */
export const Frame: React.FC<{
  children: React.ReactNode;
  /** Padding step on the 8px grid. */
  padding?: number;
}> = ({ children, padding = space['12'] }) => (
  <AbsoluteFill
    style={{
      backgroundColor: color.void,
      padding,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
    }}
  >
    {children}
  </AbsoluteFill>
);
