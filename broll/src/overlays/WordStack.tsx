import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { GraphLine } from './GraphLine';
import { moveStyle, staggerFrames } from './motion';
import { caption, dimensions, overlay, safeZone, space } from '../tokens';
import type { OverlayColour } from '../tokens';

/**
 * Words landing one at a time, stacked, over a graph line.
 *
 * The words arrive on the beat of the phrase being spoken -- one per word,
 * each staying up as the next lands, so the finished sentence is on screen
 * together. The line behind them carries the argument the words are making:
 * "short form content editor" over a falling red line is the business going
 * under, without saying so.
 */
export const WordStack: React.FC<{
  words: string[];
  colour?: OverlayColour;
  /** Omit for words with no graph behind them. */
  line?: 'rising' | 'falling';
  lineColour?: OverlayColour;
  /** Absolute frame the first word lands on. */
  enter?: number;
  /** Absolute frame the whole stack starts leaving. */
  leave?: number | null;
}> = ({
  words,
  colour = 'green',
  line,
  lineColour,
  enter = 0,
  leave,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        paddingInline: safeZone.side,
      }}
    >
      {line ? (
        <GraphLine
          direction={line}
          colour={lineColour ?? (line === 'falling' ? 'red' : 'green')}
          enter={enter}
          leave={leave}
          // Wider and taller than the standalone default: here it is a
          // backdrop the words sit on, so it has to outrun them.
          widthRatio={0.92}
          heightRatio={0.42}
          // Drawn across the whole phrase, not in a fixed moment: the decline
          // is the point, and it has to be slow enough to watch.
          drawFrames={leave == null ? undefined : leave - enter}
        />
      ) : null}

      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: space['1'],
        }}
      >
        {words.map((word, index) => (
          <div
            key={`${word}-${index}`}
            style={{
              ...moveStyle(frame, fps, enter + staggerFrames(index, fps), leave),
              fontFamily: caption.fontFamily,
              fontWeight: caption.fontWeight,
              // Sized off the frame rather than the type scale: this is the
              // one element meant to fill the screen.
              fontSize: dimensions.width * 0.15,
              lineHeight: caption.lineHeight,
              letterSpacing: caption.letterSpacing,
              color: overlay[colour],
              textTransform: 'uppercase',
              textAlign: 'center',
            }}
          >
            {word}
          </div>
        ))}
      </div>
    </div>
  );
};
