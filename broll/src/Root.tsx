import React from 'react';
import { Composition, staticFile } from 'remotion';
import './fonts';
import { Captions, transcriptDurationInFrames } from './compositions/Captions';
import { CaptionedVideo } from './compositions/CaptionedVideo';
import type { Transcript, TranscriptWord } from './captions/types';
import { Conversation } from './compositions/Conversation';
import { Slide } from './compositions/Slide';
import { StatBlock } from './compositions/StatBlock';
import { TitleCard } from './compositions/TitleCard';
import { clipDurationInFrames, dimensions, fps, slide } from './tokens';

/**
 * Every composition shares the project frame rate, dimensions, and clip length
 * from tokens.ts. Clips run two to three seconds — long enough to read, short
 * enough to cut against speech.
 */
/**
 * Defaults for interactive use in the studio. The pipeline overrides both via
 * --props, so it never has to edit this file to render a project.
 */
const TRANSCRIPT = 'transcripts/sample.words.json';
const VIDEO = 'video/cut.mp4';

const loadTranscript = async (name: string): Promise<TranscriptWord[]> => {
  const response = await fetch(staticFile(name));
  if (!response.ok) {
    throw new Error(`Cannot read ${name} (HTTP ${response.status}). ` +
      `Place the .words.json under broll/public/transcripts/.`);
  }
  const data = (await response.json()) as Transcript;
  return data.words ?? [];
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Captions"
      component={Captions}
      fps={fps}
      width={dimensions.width}
      height={dimensions.height}
      durationInFrames={clipDurationInFrames}
      defaultProps={{
        words: [] as TranscriptWord[],
        offsetSeconds: 0,
        transcriptFile: TRANSCRIPT,
      }}
      calculateMetadata={async ({ props }) => {
        const words = await loadTranscript(props.transcriptFile ?? TRANSCRIPT);
        return {
          props: { ...props, words },
          durationInFrames: transcriptDurationInFrames(words, fps),
        };
      }}
    />
    <Composition
      id="CaptionedVideo"
      component={CaptionedVideo}
      fps={fps}
      width={dimensions.width}
      height={dimensions.height}
      durationInFrames={clipDurationInFrames}
      defaultProps={{
        videoFile: VIDEO,
        words: [] as TranscriptWord[],
        offsetSeconds: 0,
        transcriptFile: TRANSCRIPT,
        videoDurationSeconds: 0,
        hookText: '',
      }}
      calculateMetadata={async ({ props }) => {
        const words = await loadTranscript(props.transcriptFile ?? TRANSCRIPT);
        const fromTranscript = transcriptDurationInFrames(words, fps);
        // The video is the ground truth for length. A transcript that runs
        // past its own footage -- a stale file, a mis-set offset -- would
        // otherwise leave the clip ending in black.
        const fromVideo = props.videoDurationSeconds
          ? Math.round(props.videoDurationSeconds * fps)
          : 0;
        return {
          props: { ...props, words },
          durationInFrames: fromVideo
            ? Math.min(fromTranscript, fromVideo)
            : fromTranscript,
        };
      }}
    />
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
      id="Slide"
      component={Slide}
      // A still. One frame is the whole thing.
      durationInFrames={1}
      fps={fps}
      width={slide.width}
      height={slide.height}
      defaultProps={{
        kind: 'body' as const,
        image: '',
        headline: 'Headline',
        body: 'Body copy.',
        emphasis: 'The point.',
        handle: '',
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
