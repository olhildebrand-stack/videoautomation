import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { Frame } from '../components/Frame';
import { MessageRow } from '../components/MessageRow';
import { Mono } from '../components/Text';
import { fadeIn, fadeInOut, stateChange } from '../motion';
import { beatInFrames, holdInFrames, space, tempoFrames } from '../tokens';

export type Message = {
  text: string;
  side: 'incoming' | 'outgoing';
};

/**
 * Messages arrive one per beat. The final message lands on the inversion — a
 * solid flare fill with the text knocked out in void — which is the frame you
 * cut to.
 */
export const Conversation: React.FC<{
  label: string;
  messages: Message[];
}> = ({ label, messages }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  /** Each message enters one beat after the one above it. */
  const entryFrame = (index: number) => (index + 1) * beatInFrames;
  /** The inversion completes with a hold still to run before the exit. */
  const landingFrame =
    durationInFrames - tempoFrames.out - tempoFrames.state - holdInFrames;
  const lastIndex = messages.length - 1;

  return (
    <Frame>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: space['2'],
          // Both sides share one column, so the thread reads as two people
          // talking rather than two edges of the frame.
          width: '100%',
          opacity: fadeInOut(frame, 0, durationInFrames),
        }}
      >
        <div style={{ marginBottom: space['2'] }}>
          <Mono>{label}</Mono>
        </div>
        {messages.map((message, index) => (
          <MessageRow
            key={message.text}
            side={message.side}
            opacity={fadeIn(frame, entryFrame(index))}
            landed={index === lastIndex ? stateChange(frame, landingFrame) : 0}
          >
            {message.text}
          </MessageRow>
        ))}
      </div>
    </Frame>
  );
};
