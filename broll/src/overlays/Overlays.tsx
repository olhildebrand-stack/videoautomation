import React from 'react';
import { AbsoluteFill } from 'remotion';
import { ChatWindow } from './ChatWindow';
import { EmojiRow } from './EmojiRow';
import { Flash } from './Flash';
import { ChipRow } from './ChipRow';
import { HtmlCard } from './HtmlCard';
import { IconRow } from './IconRow';
import { ImageCard } from './ImageCard';
import { ScreenClip } from './ScreenClip';
import { Terminal } from './Terminal';
import { DualGraph } from './DualGraph';
import { WordStack } from './WordStack';
import type { OverlayCue } from './types';

/**
 * Every cue in the sheet, layered over the footage in the order given.
 *
 * Each effect owns its own timing and renders as nothing outside it, so cues
 * can overlap freely -- the emoji row is still up while the next word lands,
 * and the two letter graphs are deliberately on screen together.
 */
export const Overlays: React.FC<{ cues: OverlayCue[] }> = ({ cues }) => (
  <AbsoluteFill>
    {cues.map((cue, index) => (
      <One key={`${cue.kind}-${cue.cue}-${index}`} cue={cue} />
    ))}
  </AbsoluteFill>
);

const One: React.FC<{ cue: OverlayCue }> = ({ cue }) => {
  switch (cue.kind) {
    case 'wordStack':
      return (
        <WordStack
          words={cue.words ?? cue.cue.split(/\s+/)}
          colour={cue.colour}
          line={cue.line}
          lineColour={cue.lineColour}
          enter={cue.enter}
          leave={cue.leave}
        />
      );

    case 'emojiRow':
      return <EmojiRow beats={cue.emoji ?? []} leave={cue.leave} />;

    case 'image':
      return cue.src ? (
        <ImageCard src={cue.src} enter={cue.enter} leave={cue.leave} />
      ) : null;

    case 'chat':
      return (
        <ChatWindow
          prompt={cue.prompt ?? ''}
          replyVideo={cue.replyVideo}
          replyText={cue.replyText}
          appears={cue.enter}
          types={cue.types}
          replies={cue.replies}
          leave={cue.leave}
        />
      );

    case 'dualGraph':
      return <DualGraph series={cue.series ?? []} leave={cue.leave} />;

    case 'chipRow':
      return (
        <ChipRow
          chips={cue.chips ?? []}
          enter={cue.enter}
          leave={cue.leave}
          reveal={cue.reveal}
          row={cue.row}
        />
      );

    case 'html':
      return (
        <HtmlCard
          html={cue.html ?? ''}
          enter={cue.enter}
          leave={cue.leave}
          full={cue.full}
        />
      );

    case 'iconRow':
      return (
        <IconRow
          slots={cue.slots ?? []}
          question={cue.question}
          enter={cue.enter}
          leave={cue.leave}
        />
      );

    case 'terminal':
      return (
        <Terminal
          lines={cue.lines ?? []}
          enter={cue.enter}
          leave={cue.leave}
          linesPerSecond={cue.linesPerSecond}
          finishes={cue.finishes}
          title={cue.title}
        />
      );

    case 'clip':
      return cue.src ? (
        <ScreenClip src={cue.src} enter={cue.enter} leave={cue.leave} />
      ) : null;

    // Drawn by nothing: CaptionedVideo reads push cues and scales the
    // footage. Listed so an unknown-kind fallthrough stays an error.
    case 'push':
      return null;

    case 'flash':
      return <Flash at={cue.enter} />;

    default:
      return null;
  }
};
