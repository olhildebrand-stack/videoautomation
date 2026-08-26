import React from 'react';
import {
  OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';
import { framesFor, moveStyle } from './motion';
import { caption, chat, dimensions, safeZone, space } from '../tokens';

/**
 * A mocked-up chat, typing a prompt and getting a video back.
 *
 * Not a screen recording. A recording of the real thing would be illegible at
 * this size and would date the moment the interface changes; a mockup shows
 * the one exchange the sentence is about and nothing else.
 *
 * Three beats, each an absolute frame:
 *
 *   appears  the empty window arrives
 *   types    the prompt writes itself, then enter is pressed
 *   replies  the answer comes back carrying a video
 */
export const ChatWindow: React.FC<{
  prompt: string;
  /** Path under broll/public/ for the video the reply carries. */
  replyVideo?: string;
  replyText?: string;
  appears: number;
  types?: number;
  replies?: number;
  leave?: number | null;
}> = ({
  prompt,
  replyVideo,
  replyText = '',
  appears,
  types,
  replies,
  leave,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const width = dimensions.width - safeZone.side * 2;

  // The prompt writes itself a character at a time. Enter lands when the last
  // character does -- a pause before it would read as hesitation, and the
  // sentence being spoken over this does not wait.
  const typedChars =
    types === undefined
      ? 0
      : Math.max(0, Math.min(prompt.length,
          Math.round(((frame - types) / fps) * chat.typeCps)));
  const typed = prompt.slice(0, typedChars);
  const sent = types !== undefined && typedChars >= prompt.length;
  const answering = replies !== undefined && frame >= replies;

  // A caret only while there is typing left to do.
  const caret = types !== undefined && frame >= types && !sent;

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        // Held clear of the caption band. The window is the tallest thing the
        // overlay layer puts on screen and the one most likely to reach into a
        // subtitle. The row direction is why the vertical pin is alignItems
        // and the horizontal centring is justifyContent, not the other way
        // round -- swapping them silently centres it again.
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: safeZone.top + space['6'],
        paddingInline: safeZone.side,
      }}
    >
      <div
        style={{
          ...moveStyle(frame, fps, appears, leave),
          width,
          // Fixed. A window that grows as messages arrive shifts under the
          // viewer mid-sentence, which reads as a layout bug rather than a
          // conversation.
          height: dimensions.height * 0.42,
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: chat.background,
          borderRadius: chat.windowRadius,
          border: `2px solid ${chat.border}`,
          overflow: 'hidden',
          fontFamily: caption.fontFamily,
          color: chat.text,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: space['3'],
            padding: space['4'],
            // Messages stack up from the composer, the way a real thread does.
            flex: 1,
            justifyContent: 'flex-end',
            overflow: 'hidden',
          }}
        >
          {sent ? (
            <Bubble align="end">{prompt}</Bubble>
          ) : null}

          {answering ? (
            <Bubble align="start">
              {replyVideo ? (
                <div
                  style={{
                    ...moveStyle(frame, fps, replies as number, leave),
                    borderRadius: chat.radius,
                    overflow: 'hidden',
                    width: width * 0.34,
                    // The reply is a video, so it plays. A still would read as
                    // an attachment; a moving frame reads as a finished edit.
                    aspectRatio: '9 / 16',
                  }}
                >
                  <OffthreadVideo
                    src={staticFile(replyVideo)}
                    startFrom={0}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                </div>
              ) : replyText ? (
                replyText
              ) : (
                // No file, and none needed: what the beat has to say is "a
                // video came back", which a video-message bubble says on its
                // own. Requiring an asset here was an invention of mine.
                <VideoMessage width={width * 0.34} />
              )}
            </Bubble>
          ) : null}
        </div>

        {/* The composer. It empties once the prompt is sent. */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: space['2'],
            margin: space['3'],
            padding: `${space['3']}px ${space['4']}px`,
            backgroundColor: chat.panel,
            borderRadius: chat.radius,
            fontSize: dimensions.width * 0.035,
            color: sent || typedChars === 0 ? chat.muted : chat.text,
            minHeight: dimensions.width * 0.06,
          }}
        >
          {sent || typedChars === 0 ? 'Skriv ett meddelande' : typed}
          {caret ? <Caret frame={frame} fps={fps} /> : null}
        </div>
      </div>
    </div>
  );
};

/** Reads as a video without being one. */
const VideoMessage: React.FC<{ width: number }> = ({ width }) => (
  <div
    style={{
      width,
      aspectRatio: '9 / 16',
      borderRadius: chat.radius,
      backgroundColor: chat.text,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}
  >
    <div
      style={{
        width: 0,
        height: 0,
        borderTop: `${width * 0.09}px solid transparent`,
        borderBottom: `${width * 0.09}px solid transparent`,
        borderLeft: `${width * 0.15}px solid ${chat.background}`,
        marginLeft: width * 0.04,
      }}
    />
  </div>
);

const Bubble: React.FC<{ align: 'start' | 'end'; children: React.ReactNode }> = ({
  align,
  children,
}) => (
  <div style={{ display: 'flex', justifyContent: align === 'end' ? 'flex-end' : 'flex-start' }}>
    <div
      style={{
        backgroundColor: chat.panel,
        borderRadius: chat.radius,
        padding: `${space['2']}px ${space['3']}px`,
        fontSize: dimensions.width * 0.036,
        maxWidth: '80%',
      }}
    >
      {children}
    </div>
  </div>
);

/** Blinks on the half second, the way every text caret does. */
const Caret: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const period = framesFor(1000, fps);
  const on = frame % period < period / 2;
  return (
    <span style={{ opacity: on ? 1 : 0, marginLeft: 2 }}>|</span>
  );
};
