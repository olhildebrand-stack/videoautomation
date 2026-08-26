/**
 * A cue: something you say, and what appears when you say it.
 *
 * `cue` is the phrase, matched against the cut transcript's word timestamps by
 * the pipeline, which fills in `enter` and `leave` in frames. Nothing here
 * carries a time written by hand -- that is the point. The same cue sheet
 * against a re-recorded take lands in the right place without being touched.
 */
export type OverlayKind =
  | 'wordStack'
  | 'emojiRow'
  | 'image'
  | 'chat'
  | 'dualGraph'
  | 'chipRow'
  | 'html'
  | 'iconRow'
  | 'terminal'
  | 'clip'
  | 'push'
  | 'flash';

export type OverlayCue = {
  kind: OverlayKind;
  /**
   * The spoken phrase this hangs on. Kept for the checkpoint to report.
   *
   * A sheet may write `from: "start"` instead, for an effect that has to fire
   * on the clip's first frame -- the mirror of `until: "end"`. The pipeline
   * resolves both to frames, so neither reaches here.
   */
  cue: string;
  /** Filled in by the pipeline from the word timestamps. */
  enter: number;
  /**
   * Absent OR null means it stays until the clip ends. The pipeline sends null
   * for `until: "end"`, and treating that as a number crashed the render.
   */
  leave?: number | null;

  // -- per kind ------------------------------------------------------------
  /** wordStack: the words, landing one at a time. Defaults to the cue. */
  words?: string[];
  colour?: 'green' | 'red' | 'lightBlue' | 'ink';
  line?: 'rising' | 'falling';
  lineColour?: 'green' | 'red' | 'lightBlue' | 'ink';

  /** emojiRow: each entry carries its own cue, resolved to its own frame. */
  emoji?: { emoji: string; cue: string; enter: number }[];

  /** image and clip: path under broll/public/. */
  src?: string;

  /**
   * push: how far into the picture, as a multiplier. Defaults to the token.
   * This kind draws nothing -- CaptionedVideo reads it and scales the footage.
   */
  scale?: number;

  /**
   * chipRow: plain words in white boxes under the hook, each revealed as it is
   * said. Every chip carries its own cue.
   */
  chips?: { text: string; cue: string; enter: number }[];
  /**
   * chipRow: how a box arrives. 'blur' (the default) shows every box from the
   * first frame, unreadable, and sharpens each as it is named -- for a list
   * the video is about to walk through. 'enter' fades each in as it is named
   * and nothing before -- for boxes naming things that do not exist yet when
   * the sentence starts.
   */
  reveal?: 'blur' | 'enter';
  /**
   * chipRow: which row this one occupies. 0 (the default) sits under the hook;
   * 1 sits under a row that is already on screen. Two rows can be up at once.
   */
  row?: number;

  /**
   * html: markup written for this one beat, inlined by the pipeline from a
   * file in the project's assets. `full` lets it past the safe zone, for
   * something deliberately covering the picture.
   */
  html?: string;
  full?: boolean;

  /**
   * iconRow: three verdicts side by side, each revealed as it is named. The
   * question they answer sits in a pill below them.
   */
  slots?: {
    tone?: 'bad' | 'good' | 'great';
    name: string;
    src?: string;
    emoji?: string;
    cue: string;
    enter: number;
  }[];
  question?: string;

  /**
   * terminal: the output to play, line by line. Generated b-roll -- the
   * reference reels cut to a full-frame screen every couple of seconds, and
   * recording one by hand is the manual step this project exists to remove.
   */
  lines?: string[];
  linesPerSecond?: number;
  title?: string;
  /**
   * terminal: absolute frame the output should have finished by, from the
   * `finishBy` phrase. The clip still leaves on `leave` -- pacing to the
   * sentence and holding past it are two different moments.
   */
  finishes?: number;

  /** chat: the prompt that types itself, and the video that comes back. */
  prompt?: string;
  replyVideo?: string;
  replyText?: string;
  /** chat: absolute frames for the typing and the reply. */
  types?: number;
  replies?: number;

  /**
   * dualGraph: the lines sharing one pair of axes. Each carries its own cue,
   * so quality can start climbing a sentence before effort starts falling, and
   * they leave together because the crossing is the point.
   */
  series?: {
    label: string;
    direction: 'rising' | 'falling';
    colour: 'green' | 'red' | 'lightBlue' | 'ink';
    cue: string;
    enter: number;
  }[];
};
