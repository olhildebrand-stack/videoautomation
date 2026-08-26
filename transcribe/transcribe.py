#!/usr/bin/env python3
"""Transcribe a video to word-level timestamps with faster-whisper.

Targets CUDA/float16 and falls back to CPU/int8 if the GPU path is unavailable,
reporting which one ran. Audio is decoded straight from the video container by
PyAV, so no separate ffmpeg extraction step is needed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import sysconfig
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

MODEL_SIZE = "large-v3"
LANGUAGE = "sv"
VOCABULARY_FILE = Path(__file__).parent / "vocabulary.txt"
CORRECTIONS_FILE = Path(__file__).parent / "corrections.txt"

# Preferred first, fallback second.
GPU_PLAN = ("cuda", "float16")
CPU_PLAN = ("cpu", "int8")


def find_cuda_dll_dirs(purelib: str) -> list[Path]:
    """Locate the DLL folders shipped by the nvidia-*-cu12 wheels.

    Split out from registration so it can be tested off Windows.
    """
    base = Path(purelib) / "nvidia"
    if not base.is_dir():
        return []
    return [path for path in sorted(base.glob("*/bin")) if any(path.glob("*.dll"))]


def prepend_to_path(directories: list[Path], environ: dict[str, str]) -> None:
    """Put the DLL directories at the front of PATH, in-process.

    add_dll_directory alone is not enough. It only affects DLLs resolved
    through LoadLibraryEx with the user-directories flag, which covers an
    extension module's static dependencies. CTranslate2 resolves cuBLAS and
    cuDNN lazily with a plain LoadLibrary, and that search consults PATH but
    NOT directories added via add_dll_directory — which is why registering the
    directories still failed with "cublas64_12.dll is not found".
    """
    if not directories:
        return
    existing = environ.get("PATH", "")
    addition = os.pathsep.join(str(directory) for directory in directories)
    environ["PATH"] = f"{addition}{os.pathsep}{existing}" if existing else addition


def register_cuda_dll_dirs() -> list[str]:
    """Make pip-installed cuBLAS/cuDNN findable on Windows.

    The nvidia-*-cu12 wheels drop these DLLs inside site-packages rather than
    on PATH. Both mechanisms below are needed — see prepend_to_path.
    """
    if sys.platform != "win32":
        return []
    directories = find_cuda_dll_dirs(sysconfig.get_paths()["purelib"])
    for directory in directories:
        os.add_dll_directory(str(directory))
    prepend_to_path(directories, os.environ)
    return [str(directory) for directory in directories]


def load_vocabulary(path: Path) -> list[str]:
    """Read the hotword list: one term per line, # comments and blanks ignored."""
    if not path.is_file():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            terms.append(stripped)
    return terms


def load_corrections(path: Path) -> list[tuple[str, str]]:
    """Read "WRONG => RIGHT" rules; # comments and blank lines ignored."""
    if not path.is_file():
        return []
    rules: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=>" not in stripped:
            continue
        wrong, _, right = stripped.partition("=>")
        wrong, right = wrong.strip(), right.strip()
        if wrong:
            rules.append((wrong, right))
    return rules


def corrections_for(args) -> list[tuple[str, str]]:
    """The shared rules, then any belonging to this recording alone.

    Order matters: rules apply in sequence to text the earlier ones have
    already changed, so the recording's own rules run last and can correct
    something a general rule got wrong.
    """
    rules = load_corrections(args.corrections)
    if args.extra_corrections:
        rules += load_corrections(args.extra_corrections)
    return rules


def apply_corrections(text: str, rules: list[tuple[str, str]]) -> tuple[str, dict[str, int]]:
    """Whole-word, case-sensitive replacement.

    Case-sensitive on purpose: "Cloud => Claude" must not rewrite a legitimate
    lowercase "cloud". Word-boundary anchored so it cannot corrupt a substring
    of a longer word.
    """
    counts: dict[str, int] = {}
    for wrong, right in rules:
        # Lookarounds rather than \b: a trailing \b after punctuation (as in
        # "ratt.") demands a following word character, so it never matches at
        # the end of a sentence. Assert only on the sides that are word-like.
        left = r"(?<!\w)" if wrong[:1].isalnum() or wrong[:1] == "_" else ""
        right_guard = r"(?!\w)" if wrong[-1:].isalnum() or wrong[-1:] == "_" else ""
        pattern = f"{left}{re.escape(wrong)}{right_guard}"
        text, n = re.subn(pattern, right.replace("\\", "\\\\"), text)
        if n:
            counts[f"{wrong} => {right}"] = counts.get(f"{wrong} => {right}", 0) + n
    return text, counts


def _align_shrink(
    window: list[dict[str, Any]],
    parts: list[str],
    replacement: list[str],
    trailing: str,
) -> list[dict[str, Any]] | None:
    """Map a shrinking rule onto the words, dropping only what disappeared.

    Returns None when the replacement is not a subsequence of the pattern; that
    is a genuine rewrite rather than a deletion, and the caller merges instead.
    """
    kept: list[dict[str, Any]] = []
    cursor = 0
    for entry, part in zip(window, parts):
        if cursor < len(replacement) and part == replacement[cursor]:
            leading = " " if entry["word"].startswith(" ") else ""
            kept.append({**entry, "word": f"{leading}{replacement[cursor]}"})
            cursor += 1
        elif kept:
            # Dropped. Its time is handed to the previous surviving word, so a
            # caption does not blank out over audio that is still playing.
            kept[-1] = {**kept[-1], "end": entry["end"]}
    if cursor != len(replacement) or not kept:
        return None
    if trailing:
        kept[-1] = {**kept[-1], "word": kept[-1]["word"] + trailing}
    return kept


def drop_deleted(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove words a rule deleted outright ("Textning.nu => ").

    Whisper credits its training data over the silence at the edges of speech,
    so a few tokens name no spoken sound at all. A rule with nothing on the
    right takes such a token out; its time is handed to the previous surviving
    word, so a caption does not blank out over audio that is still playing.
    """
    kept: list[dict[str, Any]] = []
    for entry in words:
        if entry["word"].strip():
            kept.append(entry)
        elif kept:
            kept[-1] = {**kept[-1], "end": entry["end"]}
    return kept


def apply_sequence_corrections(
    words: list[dict[str, Any]],
    rules: list[tuple[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply multi-token rules across the word list.

    Whisper regularly splits Swedish compounds into separate tokens, so a rule
    like "jätte rätt => jättelätt" can never match inside a single word entry.
    Matching tokens are merged into one entry spanning the first token's start
    to the last token's end, which keeps timing honest rather than inventing it.
    """
    sequence_rules = [
        (wrong.split(), right) for wrong, right in rules if len(wrong.split()) > 1
    ]
    if not sequence_rules:
        return words, {}

    def split_trailing_punctuation(token: str) -> tuple[str, str]:
        """Separate a token from any trailing punctuation.

        The last token of a phrase usually carries the sentence's punctuation
        ("formulär."), which would otherwise defeat an exact comparison against
        the rule's final word. The punctuation is carried over to the
        replacement rather than dropped.
        """
        stripped = token.strip()
        match = re.match(r"^(.*?)([^\w\s]*)$", stripped, re.UNICODE)
        return (match.group(1), match.group(2)) if match else (stripped, "")

    counts: dict[str, int] = {}
    result = words
    for parts, right in sequence_rules:
        merged: list[dict[str, Any]] = []
        index = 0
        while index < len(result):
            window = result[index : index + len(parts)]
            matches = len(window) == len(parts)
            trailing = ""
            if matches:
                for position, (entry, part) in enumerate(zip(window, parts)):
                    full = entry["word"].strip()
                    if full == part:
                        # An exact hit, punctuation included. A rule may name
                        # punctuation mid-phrase on purpose -- "göra mer. Och
                        # mycket" targets words Whisper invented, and the full
                        # stop is part of what identifies them.
                        continue
                    core, punctuation = split_trailing_punctuation(entry["word"])
                    if core != part:
                        matches = False
                        break
                    # Punctuation the rule did not ask for is only tolerable on
                    # the final token, where it is carried into the replacement.
                    if punctuation:
                        if position == len(parts) - 1:
                            trailing = punctuation
                        else:
                            matches = False
                            break
            if matches:
                replacement = right.split()
                if len(replacement) < len(parts):
                    # A shrinking rule is usually a mistranscription: Whisper
                    # wrote words that were never spoken. Merging the run into
                    # one token is right for a genuine compound ("jätte rätt"
                    # -> "jättelätt") but wrong here -- the surviving words are
                    # real and each needs its own timing for captions.
                    aligned = _align_shrink(window, parts, replacement, trailing)
                    if aligned is not None:
                        merged.extend(aligned)
                        key = f"{' '.join(parts)} => {right}"
                        counts[key] = counts.get(key, 0) + 1
                        index += len(parts)
                        continue
                if len(replacement) == len(parts):
                    # Same token count: rewrite in place so every word keeps
                    # its own timing. Merging would coarsen the timestamps this
                    # whole tool exists to produce.
                    for offset, (entry, new_word) in enumerate(
                        zip(window, replacement)
                    ):
                        leading = " " if entry["word"].startswith(" ") else ""
                        suffix = trailing if offset == len(parts) - 1 else ""
                        merged.append({**entry, "word": f"{leading}{new_word}{suffix}"})
                else:
                    leading = " " if window[0]["word"].startswith(" ") else ""
                    merged.append(
                        {
                            "word": f"{leading}{right}{trailing}",
                            "start": window[0]["start"],
                            "end": window[-1]["end"],
                            "probability": round(
                                min(entry["probability"] for entry in window), 4
                            ),
                        }
                    )
                key = f"{' '.join(parts)} => {right}"
                counts[key] = counts.get(key, 0) + 1
                index += len(parts)
            else:
                merged.append(result[index])
                index += 1
        result = merged
    return result, counts


def rebuild_segments(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Regroup words into segments on terminal punctuation.

    Needed after a correction that spans a segment boundary: the original
    grouping described text that no longer exists.
    """
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        current.append(word)
        if re.search(r"[.!?]['\")\]]?\s*$", word["word"]):
            segments.append(current)
            current = []
    if current:
        segments.append(current)

    return [
        {
            "id": index,
            "start": round(group[0]["start"], 3),
            "end": round(group[-1]["end"], 3),
            "text": "".join(w["word"] for w in group),
            "words": group,
        }
        for index, group in enumerate(segments)
    ]


def log(message: str) -> None:
    """Progress goes to stderr so stdout stays clean for JSON."""
    print(message, file=sys.stderr, flush=True)


@dataclass
class Backend:
    device: str
    compute_type: str

    @property
    def is_fallback(self) -> bool:
        return (self.device, self.compute_type) == CPU_PLAN


def is_gpu_failure(exc: BaseException) -> bool:
    """Whether an exception looks like 'this machine can't do CUDA'.

    CTranslate2 surfaces a missing driver, a missing cuBLAS/cuDNN DLL, an
    unsupported compute type, and an out-of-memory all as RuntimeError with
    differing text, so the message is the only thing to go on. Anything
    unrecognised is re-raised rather than silently downgraded to CPU.
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = (
        "cuda",
        "cudnn",
        "cublas",
        "cuvs",
        "gpu",
        "no kernel image",
        "out of memory",
        "device",
        "driver",
        "libcu",
    )
    return any(marker in text for marker in markers)


def load_model(model_size: str, device: str, compute_type: str, download_root: str | None):
    from faster_whisper import WhisperModel

    return WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=download_root,
    )


def transcribe_with(
    model: Any,
    audio_path: Path,
    beam_size: int,
    language: str | None,
    hotwords: str | None,
    verbatim: bool = False,
) -> tuple[Iterator[Any], Any]:
    return model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
        # Verbatim mode keeps the stumbles. Whisper's decoder is conditioned to
        # produce fluent text, so by default it silently smooths false starts
        # and repetitions out of the transcript -- while the audio still
        # contains them. For editing that is the worst case: a cut spanning a
        # dropped false start looks clean in the transcript and keeps the
        # blooper in the video. VAD is disabled with it for the same reason.
        vad_filter=not verbatim,
        condition_on_previous_text=not verbatim,
        word_timestamps=True,
        # Biases decoding toward known terms. Proper nouns and English words
        # inside Swedish speech are what Whisper most often reaches past.
        hotwords=hotwords,
    )


def run(
    audio_path: Path,
    model_size: str,
    beam_size: int,
    download_root: str | None,
    force_cpu: bool,
    language: str | None = LANGUAGE,
    vocabulary: list[str] | None = None,
    corrections: list[tuple[str, str]] | None = None,
    verbatim: bool = False,
) -> tuple[dict[str, Any], Backend]:
    """Transcribe, falling back from GPU to CPU on a GPU-shaped failure.

    The fallback covers loading *and* the first decode: a missing cuDNN often
    loads fine and only fails once a kernel actually runs, so consuming the
    first segment is part of the attempt.
    """
    if not force_cpu:
        registered = register_cuda_dll_dirs()
        for directory in registered:
            log(f"Registered CUDA DLL directory: {directory}")

    terms = vocabulary or []
    hotwords = " ".join(terms) if terms else None
    if terms:
        log(f"Vocabulary: {len(terms)} terms biased")
    if verbatim:
        log("Verbatim: VAD off, previous-text conditioning off")

    # Always report the rule count. Without this, "loaded but matched nothing"
    # and "never loaded at all" look identical from the console -- which is
    # exactly the ambiguity that made a failed correction pass hard to diagnose.
    rule_count = len(corrections) if corrections else 0
    log(f"Corrections: {rule_count} rules loaded")

    plans = [CPU_PLAN] if force_cpu else [GPU_PLAN, CPU_PLAN]

    for index, (device, compute_type) in enumerate(plans):
        backend = Backend(device, compute_type)
        is_last = index == len(plans) - 1
        try:
            log(f"Loading {model_size} on {device}/{compute_type} …")
            started = time.monotonic()
            model = load_model(model_size, device, compute_type, download_root)

            segments_iter, info = transcribe_with(
                model, audio_path, beam_size, language, hotwords, verbatim
            )

            # Consuming the generator is where decode errors actually surface.
            segments: list[Any] = []
            for segment in segments_iter:
                segments.append(segment)
                if len(segments) % 10 == 0:
                    log(f"  {len(segments)} segments … {segment.end:.1f}s")

            elapsed = time.monotonic() - started
            log(f"Done on {device}/{compute_type} in {elapsed:.1f}s.")
            return (
                build_output(
                    audio_path,
                    model_size,
                    backend,
                    info,
                    segments,
                    elapsed,
                    len(terms),
                    corrections,
                ),
                backend,
            )

        except Exception as exc:  # noqa: BLE001 - re-raised below when not GPU-shaped
            if is_last or not is_gpu_failure(exc):
                raise
            log("")
            log(f"!! CUDA path failed: {type(exc).__name__}: {exc}")
            log("!! Falling back to CPU/int8. This will be substantially slower.")
            log("")

    raise AssertionError("unreachable")


def build_output(
    audio_path: Path,
    model_size: str,
    backend: Backend,
    info: Any,
    segments: list[Any],
    elapsed: float,
    vocabulary_count: int = 0,
    corrections: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    rules = corrections or []
    applied: dict[str, int] = {}

    def correct(text: str) -> str:
        """Apply the rules, accumulating a tally across the whole transcript."""
        fixed, counts = apply_corrections(text, rules)
        for key, count in counts.items():
            applied[key] = applied.get(key, 0) + count
        return fixed

    words: list[dict[str, Any]] = []
    out_segments: list[dict[str, Any]] = []

    for segment in segments:
        segment_words = [
            {
                # Corrected per word so the flat list and the segment text
                # cannot drift apart, and timings stay attached.
                "word": correct(word.word),
                "start": round(word.start, 3),
                "end": round(word.end, 3),
                "probability": round(word.probability, 4),
            }
            for word in (segment.words or [])
        ]
        words.extend(segment_words)
        out_segments.append(
            {
                # Rebuilt from the corrected words so the flat list and the
                # segment text can never disagree after a merge.
                "text": "".join(entry["word"] for entry in segment_words)
                or correct(segment.text),
                "id": segment.id,
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "words": segment_words,
            }
        )

    # Multi-token rules run across the whole transcript, not per segment.
    # Whisper breaks segments at sentence ends, so a rule targeting an invented
    # full stop necessarily spans a boundary -- run per segment it can never
    # match. Segments are rebuilt afterwards, since the original grouping
    # described text that may no longer exist.
    words, sequence_counts = apply_sequence_corrections(words, rules)
    for key, count in sequence_counts.items():
        applied[key] = applied.get(key, 0) + count
    surviving = drop_deleted(words)
    if sequence_counts or len(surviving) != len(words):
        words = surviving
        out_segments = rebuild_segments(words)

    return {
        "source": str(audio_path),
        "vocabulary_terms": vocabulary_count,
        "corrections_applied": applied,
        "model": model_size,
        "device": backend.device,
        "compute_type": backend.compute_type,
        "used_fallback": backend.is_fallback,
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "duration": round(info.duration, 3),
        "duration_after_vad": round(getattr(info, "duration_after_vad", info.duration), 3),
        "transcribe_seconds": round(elapsed, 2),
        "word_count": len(words),
        "segments": out_segments,
        "words": words,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe a video to word-level timestamps (Swedish, large-v3).",
    )
    parser.add_argument("video", type=Path, help="video or audio file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="JSON output path (default: alongside the input, .words.json)",
    )
    parser.add_argument("--model", default=MODEL_SIZE, help=f"model size (default: {MODEL_SIZE})")
    parser.add_argument("--beam-size", type=int, default=5, help="beam size (default: 5)")
    parser.add_argument(
        "--language",
        default=LANGUAGE,
        help=f"ISO code, e.g. en or de (default: {LANGUAGE}); 'auto' to detect",
    )
    parser.add_argument(
        "--download-root",
        help="where to cache model weights (default: the HuggingFace cache)",
    )
    parser.add_argument(
        "--vocabulary",
        type=Path,
        default=VOCABULARY_FILE,
        help=f"hotword list, one term per line (default: {VOCABULARY_FILE.name})",
    )
    parser.add_argument(
        "--no-vocabulary",
        action="store_true",
        help="ignore the vocabulary file",
    )
    parser.add_argument(
        "--corrections",
        type=Path,
        default=CORRECTIONS_FILE,
        help=f"find/replace rules (default: {CORRECTIONS_FILE.name})",
    )
    parser.add_argument(
        "--extra-corrections",
        type=Path,
        default=None,
        help="more find/replace rules, applied after the main list. For rules "
             "that belong to one recording rather than to every one.",
    )
    parser.add_argument(
        "--no-corrections",
        action="store_true",
        help="ignore the corrections file",
    )
    parser.add_argument(
        "--verbatim",
        action="store_true",
        help="keep false starts and repetitions; disables VAD and previous-text "
             "conditioning. Use this for editing -- the default transcript omits "
             "stumbles that are still in the audio",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="skip the CUDA attempt and go straight to CPU/int8",
    )
    args = parser.parse_args()

    if not args.video.exists():
        log(f"error: no such file: {args.video}")
        return 2

    output_path = args.output or args.video.with_suffix(".words.json")

    try:
        result, backend = run(
            args.video,
            args.model,
            args.beam_size,
            args.download_root,
            args.cpu,
            None if args.language == "auto" else args.language,
            [] if args.no_vocabulary else load_vocabulary(args.vocabulary),
            [] if args.no_corrections else corrections_for(args),
            args.verbatim,
        )
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        log(f"error: {type(exc).__name__}: {exc}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    log("")
    if result["corrections_applied"]:
        for rule, count in result["corrections_applied"].items():
            log(f"Corrected {count}x  {rule}")
    else:
        log("No corrections matched.")
    log(f"Wrote {result['word_count']} words to {output_path}")
    if backend.is_fallback:
        log("NOTE: this ran on CPU/int8, not the GPU. See README.md → CUDA setup.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
