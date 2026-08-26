import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { ease, framesFor, move } from './motion';
import { dimensions, graph, overlay } from '../tokens';
import type { OverlayColour } from '../tokens';

/**
 * A line that draws itself, rising or falling.
 *
 * Deliberately not a chart: no axes, no gridlines, no numbers. It says
 * "up" or "down" and nothing else, which is all a viewer takes from a graph on
 * screen for two seconds anyway.
 *
 * The drawing is a dash-offset animation, so the line arrives left to right
 * the way it would be drawn by hand.
 */
export const GraphLine: React.FC<{
  direction: 'rising' | 'falling';
  colour?: OverlayColour;
  enter?: number;
  leave?: number | null;
  /** Nudges the line off centre, for stacking two of them. */
  offsetY?: number;
  /** Overrides the default share of the frame, when it sits inside something. */
  widthRatio?: number;
  heightRatio?: number;
  /**
   * How many frames the line takes to draw. Pass the length of the cue so the
   * decline happens at the speed of the sentence describing it -- a line drawn
   * in a fifth of a second is a squiggle, not a trend.
   */
  drawFrames?: number;
}> = ({
  direction,
  colour = 'green',
  enter = 0,
  leave,
  offsetY = 0,
  widthRatio = graph.widthRatio,
  heightRatio = graph.heightRatio,
  drawFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const width = dimensions.width * widthRatio;
  const height = dimensions.height * heightRatio;
  const pad = graph.strokeWidth;

  // A slight curve rather than a straight diagonal: a bend reads as a trend,
  // a straight line reads as a ruler.
  const low = height - pad;
  const high = pad;
  const path =
    direction === 'rising'
      ? `M ${pad} ${low} C ${width * 0.42} ${low}, ${width * 0.55} ${high}, ${width - pad} ${high}`
      : `M ${pad} ${high} C ${width * 0.42} ${high}, ${width * 0.55} ${low}, ${width - pad} ${low}`;

  // Any length longer than the path works; the dash just has to outrun it.
  const length = width * 2;
  const span = drawFrames ?? framesFor(graph.drawMs, fps);
  const drawn = interpolate(
    frame,
    [enter, enter + span],
    [length, 0],
    { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );

  const { opacity, translateY } = move(frame, fps, enter, leave);

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{
        position: 'absolute',
        opacity,
        transform: `translateY(${translateY + offsetY}px)`,
        overflow: 'visible',
      }}
    >
      <path
        d={path}
        fill="none"
        stroke={overlay[colour]}
        strokeWidth={graph.strokeWidth}
        strokeLinecap="round"
        strokeDasharray={length}
        strokeDashoffset={drawn}
      />
    </svg>
  );
};
