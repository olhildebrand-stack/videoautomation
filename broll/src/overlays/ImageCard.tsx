import React from 'react';
import { Img, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { moveStyle } from './motion';
import { dimensions, imageCard } from '../tokens';

/**
 * A screenshot dropped into the middle of the frame, corners rounded.
 *
 * The file lives in `broll/public/` and is named relative to it, the same way
 * the footage and transcripts are. Height is left to the image so a screenshot
 * of any shape keeps its proportions -- only the width is fixed, as a share of
 * the frame.
 */
export const ImageCard: React.FC<{
  /** Path under broll/public/, e.g. "images/instagram.png". */
  src: string;
  enter?: number;
  leave?: number | null;
  widthRatio?: number;
}> = ({ src, enter = 0, leave, widthRatio = imageCard.widthRatio }) => {
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
      }}
    >
      <div style={moveStyle(frame, fps, enter, leave)}>
        <Img
          src={staticFile(src)}
          style={{
            width: dimensions.width * widthRatio,
            height: 'auto',
            borderRadius: imageCard.radius,
            display: 'block',
          }}
        />
      </div>
    </div>
  );
};
