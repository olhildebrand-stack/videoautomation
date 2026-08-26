import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile } from 'remotion';
import { Captions } from './Captions';
import { Hook } from './Hook';
import { Overlays } from '../overlays/Overlays';
import { usePush, usePushBlur } from '../overlays/push';
import type { OverlayCue } from '../overlays/types';
import type { ChunkOptions } from '../captions/chunk';
import type { TranscriptWord } from '../captions/types';
import { color } from '../tokens';

/**
 * The cut video with captions burned over it.
 *
 * Captions are applied to the *graded* video, never the other way round: a
 * colour grade applied over the captions would shift `flare` and `void` and
 * the brand colours would no longer be the exact values CYANVOID fixes.
 */
export const CaptionedVideo: React.FC<{
  videoFile: string;
  words: TranscriptWord[];
  chunkOptions?: ChunkOptions;
  offsetSeconds?: number;
  /** Set by the pipeline via --props; read in calculateMetadata. */
  transcriptFile?: string;
  /** Text of the hook card. Omitted or empty means no card. */
  hookText?: string;
  /** Set by the pipeline; caps the clip at the footage's real length. */
  videoDurationSeconds?: number;
  /** Cue sheet, with every time already resolved to a frame. */
  cues?: OverlayCue[];
}> = ({
  videoFile,
  words,
  chunkOptions,
  offsetSeconds = 0,
  hookText = '',
  cues = [],
}) => {
  // Only the footage scales. Scaling the whole frame would take the captions
  // and the hook card with it, which is the opposite of what a push is for.
  const scale = usePush(cues);
  const blur = usePushBlur(cues);
  return (
  <AbsoluteFill style={{ backgroundColor: color.void }}>
    <AbsoluteFill style={{
      transform: `scale(${scale})`,
      filter: blur > 0.01 ? `blur(${blur.toFixed(2)}px)` : undefined,
    }}>
      <OffthreadVideo src={staticFile(videoFile)} />
    </AbsoluteFill>
    {/* Overlays sit over the footage and under the captions: a word landing
        behind a subtitle would be unreadable, and the subtitle is the one
        thing that must never be obscured. */}
    <Overlays cues={cues} />
    {/* The captions layer paints its own ground, so it is transparent here. */}
    <AbsoluteFill>
      <Captions
        words={words}
        chunkOptions={chunkOptions}
        offsetSeconds={offsetSeconds}
        transparent
      />
    </AbsoluteFill>
    <Hook text={hookText} />
  </AbsoluteFill>
  );
};
