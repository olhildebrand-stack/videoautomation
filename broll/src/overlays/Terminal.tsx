import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { moveStyle } from './motion';
import { dimensions, safeZone, terminal } from '../tokens';

/**
 * A terminal filling the frame, output arriving line by line.
 *
 * This is b-roll, generated rather than captured. The reference reels cut to a
 * full-frame screen every couple of seconds; recording one by hand would be a
 * manual step per video, and the point of this project is that there are none.
 *
 * Lines are revealed on a clock, and the view scrolls once they outgrow the
 * frame, so a long run still ends on its last line rather than starting off
 * the bottom.
 */
export const Terminal: React.FC<{
  lines: string[];
  enter: number;
  leave?: number | null;
  /**
   * Overrides the pacing. Left out, the lines are spread evenly across the
   * time the clip is on screen, which is what a cue-anchored clip wants.
   */
  linesPerSecond?: number;
  /**
   * Absolute frame the output should have finished by, if that is not when
   * the clip leaves. Pacing to a sentence and holding past it are two
   * different moments.
   */
  finishes?: number | null;
  title?: string;
}> = ({
  lines,
  enter,
  leave,
  linesPerSecond,
  finishes,
  title = 'pipeline.py',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Paced to fill the time it is on screen, unless told otherwise. A fixed
  // rate is the wrong default: the clip is cued to a sentence and leaves on
  // another, so its length is decided by speech, and a rate chosen once ran
  // the whole output in the first second of a five-second window and then sat
  // there finished. Falls back to the fixed rate when it stays to the end,
  // where there is no span to divide.
  const ends = finishes ?? leave;
  const span = ends === undefined || ends === null ? null : (ends - enter) / fps;
  const rate =
    linesPerSecond ??
    (span && span > 0 ? lines.length / span : terminal.linesPerSecond);

  const elapsed = Math.max(0, (frame - enter) / fps);
  const shown = Math.min(lines.length, Math.floor(elapsed * rate) + 1);

  const cardWidth = dimensions.width - safeZone.side * 2;
  const cardHeight = Math.round(dimensions.height * terminal.heightShare);

  const rowHeight = terminal.fontSize * terminal.lineHeight;
  const bodyHeight = cardHeight - terminal.padding * 2;
  const visibleRows = Math.floor(bodyHeight / rowHeight);
  // Scroll only once the output outgrows the frame, so a short run sits still.
  const firstRow = Math.max(0, shown - visibleRows);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          ...moveStyle(frame, fps, enter, leave),
          width: cardWidth,
          height: cardHeight,
          backgroundColor: terminal.background,
          borderRadius: terminal.radius,
          border: `2px solid ${terminal.border}`,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            paddingTop: 18,
            paddingInline: terminal.padding,
            paddingBottom: 18,
            backgroundColor: terminal.chrome,
            borderBottom: `2px solid ${terminal.border}`,
            fontFamily: terminal.fontFamily,
            fontSize: terminal.fontSize * 0.8,
            color: terminal.dim,
          }}
        >
          {terminal.dots.map((colour) => (
            <Dot key={colour} colour={colour} />
          ))}
          <span style={{ marginLeft: 12 }}>{title}</span>
        </div>

        <div
          style={{
            flex: 1,
            padding: terminal.padding,
            paddingBottom: safeZone.bottom,
            fontFamily: terminal.fontFamily,
            fontSize: terminal.fontSize,
            lineHeight: terminal.lineHeight,
            color: terminal.text,
            overflow: 'hidden',
            whiteSpace: 'pre',
          }}
        >
          {lines.slice(firstRow, shown).map((line, index) => (
            <div key={firstRow + index} style={{ color: colourFor(line) }}>
              {line || ' '}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/** Terminals are read at a glance; colour is what makes that possible. */
const colourFor = (line: string): string => {
  if (/^\s*(!|error|warning)/i.test(line)) return terminal.warn;
  if (/^={2,}|CHECKPOINT|^\s*\+|approve|placed|Done/i.test(line)) {
    return terminal.accent;
  }
  if (/^\s*(#|NOTE:)/.test(line)) return terminal.dim;
  return terminal.text;
};

const Dot: React.FC<{ colour: string }> = ({ colour }) => (
  <span
    style={{
      width: 20, height: 20, borderRadius: '50%', backgroundColor: colour,
      display: 'inline-block',
    }}
  />
);
