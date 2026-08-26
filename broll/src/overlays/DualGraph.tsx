import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { ease, move } from './motion';
import { caption, dimensions, graph, overlay } from '../tokens';
import type { OverlayColour } from '../tokens';

/**
 * One chart, two lines crossing: quality climbing while effort falls.
 *
 * Two separate mini-graphs did not work -- side by side they read as two
 * unrelated strokes, and the comparison is the whole argument of the sentence.
 * In one pair of axes the crossing does the work: more out, less in, visible
 * at a glance without a word of explanation.
 *
 * The axes matter more than they look like they should. A line on its own is a
 * stroke; the same line against an origin is a graph.
 *
 * Each line arrives on its own cue and draws across the time that cue is on
 * screen, so it declines at the speed of the sentence describing it.
 */
export type GraphSeries = {
  label: string;
  direction: 'rising' | 'falling';
  colour: OverlayColour;
  /** Absolute frame the line starts drawing. */
  enter: number;
};

export const DualGraph: React.FC<{
  series: GraphSeries[];
  /** Absolute frame the whole chart leaves. Both lines go together. */
  leave?: number | null;
  /** Frames each line takes to draw. Defaults to the span to `leave`. */
  drawFrames?: number;
}> = ({ series, leave, drawFrames }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const width = dimensions.width * 0.74;
  const height = dimensions.height * 0.30;
  const pad = graph.strokeWidth * 2;
  const labelGap = graph.labelSize * 0.9;

  // The chart appears with its first line and holds until the last one goes.
  const first = Math.min(...series.map((s) => s.enter));
  const axes = move(frame, fps, first, leave);

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
          position: 'relative',
          width: width + labelGap,
          height,
          opacity: axes.opacity,
          transform: `translateY(${axes.translateY}px)`,
        }}
      >
        <svg
          width={width + labelGap}
          height={height}
          viewBox={`0 0 ${width + labelGap} ${height}`}
          style={{ overflow: 'visible' }}
        >
          {/* Origin at the bottom left, the way every graph anyone has ever
              seen is drawn. */}
          <path
            d={`M ${labelGap} ${pad} L ${labelGap} ${height - pad} L ${width + labelGap - pad} ${height - pad}`}
            fill="none"
            stroke={graph.axis}
            strokeWidth={graph.axisWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {series.map((line, index) => (
            <Series
              key={`${line.label}-${index}`}
              line={line}
              frame={frame}
              fps={fps}
              leave={leave}
              drawFrames={
                drawFrames ?? (leave ?? durationInFrames) - line.enter
              }
              left={labelGap}
              width={width}
              height={height}
              pad={pad}
            />
          ))}
        </svg>

        {/* Labels sit at each line's origin -- K low, A high -- so which line
            is which is settled before either has moved. */}
        {series.map((line, index) => (
          <Label
            key={`label-${line.label}-${index}`}
            line={line}
            frame={frame}
            fps={fps}
            leave={leave}
            height={height}
            pad={pad}
          />
        ))}
      </div>
    </div>
  );
};

const Series: React.FC<{
  line: GraphSeries;
  frame: number;
  fps: number;
  leave?: number | null;
  drawFrames: number;
  left: number;
  width: number;
  height: number;
  pad: number;
}> = ({ line, frame, fps, leave, drawFrames, left, width, height, pad }) => {
  const low = height - pad * 2;
  const high = pad * 2;
  const x0 = left + pad;
  const x1 = left + width - pad;
  const [from, to] = line.direction === 'rising' ? [low, high] : [high, low];

  // A bend, not a diagonal: a straight line reads as a ruler.
  const d = `M ${x0} ${from} C ${left + width * 0.45} ${from}, ${left + width * 0.55} ${to}, ${x1} ${to}`;

  const length = width * 2;
  const drawn = interpolate(
    frame,
    [line.enter, line.enter + Math.max(1, drawFrames)],
    [length, 0],
    { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const { opacity } = move(frame, fps, line.enter, leave);

  return (
    <path
      d={d}
      fill="none"
      stroke={overlay[line.colour]}
      strokeWidth={graph.strokeWidth}
      strokeLinecap="round"
      strokeDasharray={length}
      strokeDashoffset={drawn}
      opacity={opacity}
    />
  );
};

const Label: React.FC<{
  line: GraphSeries;
  frame: number;
  fps: number;
  leave?: number | null;
  height: number;
  pad: number;
}> = ({ line, frame, fps, leave, height, pad }) => {
  const { opacity, translateY } = move(frame, fps, line.enter, leave);
  const top = line.direction === 'rising' ? height - pad * 2 : pad * 2;

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top,
        transform: `translateY(calc(-50% + ${translateY}px))`,
        opacity,
        fontFamily: caption.fontFamily,
        fontWeight: caption.fontWeight,
        fontSize: graph.labelSize,
        lineHeight: 1,
        color: overlay[line.colour],
      }}
    >
      {line.label}
    </div>
  );
};
