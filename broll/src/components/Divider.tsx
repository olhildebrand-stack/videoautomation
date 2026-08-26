import React from 'react';
import { borderWidth, color } from '../tokens';

/**
 * A 1px hairline. Never thicker, never doubled. The system is built from
 * stacked and divided rectangles.
 */
export const Divider: React.FC<{
  orientation?: 'horizontal' | 'vertical';
  opacity?: number;
}> = ({ orientation = 'horizontal', opacity = 1 }) => (
  <div
    style={{
      backgroundColor: color.seam,
      opacity,
      ...(orientation === 'horizontal'
        ? { width: '100%', height: borderWidth }
        : { width: borderWidth, alignSelf: 'stretch' }),
    }}
  />
);
