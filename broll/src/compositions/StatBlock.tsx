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
 * Divided rectangles, numbers in the mono layer, hairlines between. Each column
 * fades in one beat after the last — nothing slides.
 */
export const StatBlock: React.FC<{ stats: Stat[] }> = ({ stats }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  return (
    <Frame>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: space['6'] }}>
        {stats.map((stat, index) => (
          <React.Fragment key={stat.label}>
            {index > 0 ? <Divider orientation="vertical" /> : null}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: space['2'],
                opacity: fadeInOut(frame, index * beatInFrames, durationInFrames),
              }}
            >
              <Mono>{stat.label}</Mono>
              <Display size="3xl" tone="flare">
                {stat.value}
              </Display>
            </div>
          </React.Fragment>
        ))}
      </div>
    </Frame>
  );
};
