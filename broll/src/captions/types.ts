export type TranscriptWord = {
  word: string;
  start: number;
  end: number;
  probability: number;
};

export type Transcript = {
  words: TranscriptWord[];
  device?: string;
  compute_type?: string;
  language?: string;
  word_count?: number;
};

/** A group of words shown on screen together. */
export type CaptionLine = {
  words: TranscriptWord[];
  start: number;
  end: number;
};
