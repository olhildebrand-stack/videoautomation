import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { ease, framesFor, moveStyle } from './motion';
import { caption, chip, iconCard, safeZone } from '../tokens';

export type Chip = {
  text: string;
  /** Absolute frame this one comes into focus. */
  enter: number;
};

/**
 * Words in white boxes under the hook, each arriving as it is said.
 *
 * Two ways of arriving, because the row is used for two different jobs.
 *
 * `blur` (the default) shows every box from the first frame, unreadable, and
 * sharpens each as it is named. That is for a list the video is about to walk
 * through: the viewer can see that three topics are coming and cannot read
 * ahead to what they are. Appearing one at a time would give the count away by
 * the empty space, and showing them sharp from the start gives away the whole
 * video in the first second.
 *
 * `enter` fades each box in as it is named and nothing before. That is for
 * boxes naming things that do not exist yet when the sentence starts -- two
 * files being written, one after the other -- where showing a waiting slot
 * would promise something the viewer has no way to guess.
 *
 * Either way the row holds its layout from the first frame, so a box arriving
 * never shifts its neighbours sideways. With `enter` that means the first box
 * sits where it will sit once they are all there, not centred alone.
 */
export const ChipRow: React.FC<{
  chips: Chip[];
  /** Absolute frame the row appears. */
  enter: number;
  leave?: number | null;
  reveal?: 'blur' | 'enter';
  /** 0 sits under the hook; 1 sits under a row that is already there. */
  row?: number;
}> = ({ chips, enter, leave, reveal = 'blur', row = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const perChip = reveal === 'enter';

  return (
    <div
      style={{
        position: 'absolute',
        top: safeZone.top + chip.belowHook + row * chip.rowOffset,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'flex-start',
        flexWrap: 'wrap',
        gap: chip.gap,
        paddingInline: safeZone.side,
        // With per-chip entry the row is layout only: animating both would
        // square the fade and double the travel on every box.
        ...(perChip ? {} : moveStyle(frame, fps, enter, leave)),
      }}
    >
      {chips.map((entry, index) => (
        <One
          key={`${entry.text}-${index}`}
          chip={entry}
          frame={frame}
          fps={fps}
          leave={perChip ? leave : undefined}
          perChip={perChip}
        />
      ))}
    </div>
  );
};

const One: React.FC<{
  chip: Chip;
  frame: number;
  fps: number;
  leave?: number | null;
  perChip: boolean;
}> = ({ chip: entry, frame, fps, leave, perChip }) => {
  const blur = perChip
    ? 0
    : interpolate(
        frame,
        [entry.enter, entry.enter + framesFor(iconCard.focusMs, fps)],
        [iconCard.blur, 0],
        { easing: ease, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
      );

  return (
    <div
      style={{
        backgroundColor: chip.background,
        color: chip.text,
        borderRadius: chip.radius,
        paddingBlock: chip.paddingBlock,
        paddingInline: chip.paddingInline,
        fontFamily: caption.fontFamily,
        fontWeight: caption.fontWeight,
        fontSize: chip.fontSize,
        lineHeight: 1.1,
        whiteSpace: 'nowrap',
        // The box stays sharp; only the word inside it is unreadable, so the
        // row reads as three waiting slots rather than three smudges.
        filter: `blur(${blur}px)`,
        // They leave together, on the row's own leave, however they arrived.
        ...(perChip ? moveStyle(frame, fps, entry.enter, leave) : {}),
      }}
    >
      {entry.text}
    </div>
  );
};
