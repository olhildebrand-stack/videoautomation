import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { Frame } from '../components/Frame';
import { Divider } from '../components/Divider';
import { Display, Mono } from '../components/Text';
import { fadeInOut } from '../motion';
import { beatInFrames, space } from '../tokens';

export type Stat = {
  label: string;
  value: string;
};

/**
 * Stacked rows, divided by hairlines, numbers in the mono layer. Each row fades
 * in one beat after the last — nothing slides.
 *
 * Vertical stacking is not just a fit constraint: read top-to-bottom, the rows
 * scan in the same direction as the frame, and each value gets the full column
 * width instead of a third of it.
 */
export const StatBlock: React.FC<{ stats: Stat[] }> = ({ stats }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  return (
    <Frame>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {stats.map((stat, index) => (
          <div
            key={stat.label}
            style={{ opacity: fadeInOut(frame, index * beatInFrames, durationInFrames) }}
          >
            {index > 0 ? <Divider /> : null}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: space['1'],
                paddingBlock: space['4'],
              }}
            >
              <Mono>{stat.label}</Mono>
              <Display size="3xl" tone="flare">
                {stat.value}
              </Display>
            </div>
          </div>
        ))}
      </div>
    </Frame>
  );
};
