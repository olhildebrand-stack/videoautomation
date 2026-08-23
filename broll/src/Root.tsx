import React from 'react';
import { Composition } from 'remotion';
import './fonts';
import { Conversation } from './compositions/Conversation';
import { StatBlock } from './compositions/StatBlock';
import { TitleCard } from './compositions/TitleCard';
import { clipDurationInFrames, dimensions, fps } from './tokens';

/**
 * Every composition shares the project frame rate, dimensions, and clip length
 * from tokens.ts. Clips run two to three seconds — long enough to read, short
 * enough to cut against speech.
 */
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="TitleCard"
      component={TitleCard}
      durationInFrames={clipDurationInFrames}
      fps={fps}
      width={dimensions.width}
      height={dimensions.height}
      defaultProps={{
        kicker: 'Cyan Void / 01',
        headline: 'Hierarchy is brightness',
      }}
    />
    <Composition
      id="Conversation"
      component={Conversation}
      durationInFrames={clipDurationInFrames}
      fps={fps}
      width={dimensions.width}
      height={dimensions.height}
      defaultProps={{
        label: 'Thread / 0412',
        messages: [
          { text: 'Can you cut this to three seconds?', side: 'incoming' as const },
          { text: 'Already rendering.', side: 'outgoing' as const },
          { text: 'Ship it.', side: 'incoming' as const },
        ],
      }}
    />
    <Composition
      id="StatBlock"
      component={StatBlock}
      durationInFrames={clipDurationInFrames}
      fps={fps}
      width={dimensions.width}
      height={dimensions.height}
      defaultProps={{
        stats: [
          { label: 'Clips', value: '128' },
          { label: 'Render', value: '04:12' },
          { label: 'Drops', value: '00' },
        ],
      }}
    />
  </>
);
