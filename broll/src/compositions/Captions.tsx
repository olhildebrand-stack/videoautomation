import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { chunkWords, defaultChunkOptions, lineAt } from '../captions/chunk';
import type { ChunkOptions } from '../captions/chunk';
import type { TranscriptWord } from '../captions/types';
import { caption, color, fontSize, safeZone, space, tempoFrames } from '../tokens';

/**
 * Burned-in captions: white, black-outlined, one line at a time.
 *
 * The outline rather than a panel behind the text. `paintOrder: 'stroke fill'`
 * draws the stroke underneath the glyph so the letterforms stay their true
 * weight; the default paint order thickens them from the inside and the type
 * turns to mush at this size.
 */
export const Captions: React.FC<{
  words: TranscriptWord[];
  chunkOptions?: ChunkOptions;
  offsetSeconds?: number;
  transparent?: boolean;
  transcriptFile?: string;
  /** Type size in px. */
  size?: number;
}> = ({
  words,
  chunkOptions = defaultChunkOptions,
  offsetSeconds = 0,
  transparent = false,
  size = fontSize['3xl'],
}) => {
  const frame = useCurrentFrame();
  const { fps: videoFps } = useVideoConfig();
  const time = frame / videoFps - offsetSeconds;

  const lines = React.useMemo(
    () => chunkWords(words, chunkOptions),
    [words, chunkOptions],
  );
  const line = lineAt(lines, time);
  const ground = transparent ? 'transparent' : color.void;

  if (!line) {
    return <AbsoluteFill style={{ backgroundColor: ground }} />;
  }


  return (
    <AbsoluteFill
      style={{
        backgroundColor: ground,
        justifyContent: 'flex-end',
        alignItems: 'center',
        // Sit the whole caption block inside the safe zone, rather than
        // padding from the frame edge and hoping.
        paddingTop: safeZone.top,
        paddingBottom: safeZone.bottom,
        paddingInline: safeZone.side,
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          columnGap: space['2'],
          rowGap: space['1'],
          fontFamily: caption.fontFamily,
          fontWeight: caption.fontWeight,
          letterSpacing: caption.letterSpacing,
          lineHeight: caption.lineHeight,
          fontSize: size,
          textTransform: caption.transform,
          WebkitTextStrokeWidth: size * caption.strokeRatio,
          WebkitTextStrokeColor: caption.stroke,
          paintOrder: 'stroke fill',
        }}
      >
        {/* Every word solid white. Dimming the unspoken ones with opacity
            makes the footage show through the glyphs and the stroke alike,
            which over busy video reads as a rendering fault rather than
            emphasis. The line changing on time is the sync cue. */}
        {line.words.map((word) => (
          <span key={`${word.start}-${word.word}`} style={{ color: caption.fill }}>
            {word.word.trim()}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** Frames a transcript occupies, for sizing a composition. */
export const transcriptDurationInFrames = (
  words: TranscriptWord[],
  videoFps: number,
): number => {
  const last = words[words.length - 1];
  return last ? Math.ceil(last.end * videoFps) + tempoFrames.out : videoFps;
};
