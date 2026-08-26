#!/usr/bin/env python3
"""Print the sentence-level analysis of a transcript.

    python sentences_report.py clip.words.json [--tail 0.5]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cutlist import Word, clamp_slack, drop_hallucinations  # noqa: E402
from sentences import (  # noqa: E402
    DEFAULT_TAIL, analyse, keepers, sentence_ranges,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path)
    parser.add_argument("--tail", type=float, default=DEFAULT_TAIL)
    parser.add_argument("--max-gap", type=float, default=0.30,
                        help="split a sentence at silence longer than this")
    args = parser.parse_args()

    if not args.json_file.is_file():
        candidate = args.json_file.with_suffix(".words.json")
        if candidate.is_file():
            args.json_file = candidate
        else:
            print(f"error: no such file: {args.json_file}", file=sys.stderr)
            return 2

    data = json.loads(args.json_file.read_text(encoding="utf-8"))
    words = [
        Word(w["word"], w["start"], w["end"], w.get("probability", 1.0))
        for w in data["words"]
    ]
    words, hallucinated = drop_hallucinations(words)
    if hallucinated:
        print(f"dropped {len(hallucinated)} near-zero-confidence words\n")
    words, clamped = clamp_slack(words)
    for word in clamped:
        print(f"clamped {word.word.strip()!r} ({word.end - word.start:.1f}s)")
    if clamped:
        print()

    sentences = analyse(words)
    kept = keepers(sentences)
    # The last kept sentence ends the video, so it gets the longer tail.
    final_sentence = kept[-1] if kept else None
    kept_total = 0.0
    suspect: list[tuple[int, int, float, float, float]] = []
    print(f"{'#':>3} {'verdict':<22} {'range':>15} {'len':>6}  text")
    for sentence in sentences:
        pieces = sentence_ranges(sentence, words, tail=args.tail,
                                 max_gap=args.max_gap,
                                 is_final=sentence is final_sentence)
        mark = "   " if sentence.is_blooper else " * "
        length = sum(b - a for a, b in pieces)
        if not sentence.is_blooper:
            kept_total += length
        span = f"{pieces[0][0]:>6.2f}->{pieces[-1][1]:>6.2f}"
        print(f"{sentence.index:>3}{mark}{sentence.verdict:<22} "
              f"{span} {length:>6.2f}  {sentence.text[:58]}")
        if len(pieces) > 1:
            removed = sum(pieces[i + 1][0] - pieces[i][1]
                          for i in range(len(pieces) - 1))
            print(f"{'':>3}   {'':<22} {len(pieces)} pieces, "
                  f"{removed:.2f}s of silence inside removed")

            # Fragmentation is a warning sign, not a result. Two jump cuts
            # inside one sentence, or a piece too short to be more than a word
            # or two, means Whisper's alignment through that stretch is not
            # trustworthy -- and these are the cuts most likely to sound wrong.
            shortest = min(b - a for a, b in pieces)
            if len(pieces) > 2 or shortest < 1.2:
                suspect.append((sentence.index, len(pieces), shortest,
                                pieces[0][0], pieces[-1][1]))
                print(f"{'':>3}   {'':<22} ^^ CHECK BY EAR: "
                      f"{len(pieces)} cuts, shortest piece {shortest:.2f}s")

    print()
    print(f"{len(kept)} of {len(sentences)} sentences kept, {kept_total:.1f}s total")
    print()
    print("edit-script.json for those sentences, in transcript order:")
    entries = []
    for sentence in kept:
        pieces = sentence_ranges(sentence, words, tail=args.tail,
                                 max_gap=args.max_gap,
                                 is_final=sentence is final_sentence)
        for position, (start, end) in enumerate(pieces):
            beat = f"S{sentence.index}"
            if len(pieces) > 1:
                beat = f"{beat}.{position + 1}"
            entries.append({"beat": beat, "start": start, "end": end,
                            "line": sentence.text})
    print(json.dumps(entries, ensure_ascii=False, indent=2))

    if suspect:
        print()
        print("Listen to these before cutting -- the alignment there is weak,")
        print("and an automatic split is a guess:")
        for index, count, shortest, start, end in suspect:
            print(f"  S{index}: {start:.2f}-{end:.2f} in the source, "
                  f"{count} pieces, shortest {shortest:.2f}s")
        print()
        print("If a split sounds wrong, replace that sentence's entries with one")
        print("range covering the take you want. Explicit ranges are taken as given.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
