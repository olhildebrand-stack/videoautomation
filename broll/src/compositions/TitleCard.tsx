import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { Frame } from '../components/Frame';
import { Divider } from '../components/Divider';
import { Display, Mono } from '../components/Text';
import { fadeInOut } from '../motion';
import { beatInFrames, space } from '../tokens';

/**
 * One headline, one label, one hairline. Each beat lands on its own — the
 * label, then the rule, then the headline, staggered by the state tempo.
 */
export const TitleCard: React.FC<{
  kicker: string;
  headline: string;
}> = ({ kicker, headline }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const beat = (index: number) =>
    fadeInOut(frame, index * beatInFrames, durationInFrames);

  return (
    <Frame>
      <div style={{ display: 'flex', flexDirection: 'column', gap: space['4'] }}>
        <div style={{ opacity: beat(0) }}>
          <Mono>{kicker}</Mono>
        </div>
        <div style={{ opacity: beat(1) }}>
          <Divider />
        </div>
        <div style={{ opacity: beat(2) }}>
          <Display size="4xl">{headline}</Display>
        </div>
      </div>
    </Frame>
  );
};
