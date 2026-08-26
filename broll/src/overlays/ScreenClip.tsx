import React from 'react';
import {
  OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import { move } from './motion';
import { color } from '../tokens';

/**
 * Real footage cut in over the frame: a screen recording, a second camera.
 *
 * Full frame, covering the talking head entirely, which is what the reference
 * reels do at every cut. The footage plays from its own first frame each time
 * it appears, so the same file can be cut in twice without the second use
 * starting halfway through.
 *
 * Fades rather than cuts, on the same gesture as everything else in this
 * layer -- and `objectFit: cover` because a 16:9 capture in a 9:16 frame is
 * cropped, never letterboxed. Frame what matters in the middle.
 */
export const ScreenClip: React.FC<{
  src: string;
  enter: number;
  leave?: number | null;
}> = ({ src, enter, leave }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity } = move(frame, fps, enter, leave);

  if (opacity <= 0) return null;

  return (
    <Sequence from={enter} durationInFrames={Infinity} layout="none">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          opacity,
          backgroundColor: color.void,
        }}
      >
        <OffthreadVideo
          src={staticFile(src)}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>
    </Sequence>
  );
};
