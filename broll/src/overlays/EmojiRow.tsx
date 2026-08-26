import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { moveStyle } from './motion';
import { emojiSize, safeZone, space } from '../tokens';

/** One emoji and the frame it lands on. */
export type EmojiBeat = { emoji: string; enter: number };

/**
 * Emoji arriving one at a time, left to right, all staying up.
 *
 * Each lands on its own cue -- scissors on "klipp", ABC on "captions" -- and
 * none of them leave until the last has arrived and the whole row goes
 * together. The row is what the sentence adds up to; dropping each emoji as
 * the next appeared would show the list one item at a time and never show the
 * list.
 *
 * Positions are fixed from the start, so an emoji does not shuffle sideways
 * when its neighbour appears.
 */
export const EmojiRow: React.FC<{
  beats: EmojiBeat[];
  /** Absolute frame the whole row starts leaving. */
  leave?: number | null;
  size?: number;
}> = ({ beats, leave, size = emojiSize.row }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: space['5'],
        paddingInline: safeZone.side,
      }}
    >
      {beats.map((beat, index) => (
        <div
          key={`${beat.emoji}-${index}`}
          style={{
            ...moveStyle(frame, fps, beat.enter, leave),
            fontSize: size,
            lineHeight: 1,
          }}
        >
          {beat.emoji}
        </div>
      ))}
    </div>
  );
};
