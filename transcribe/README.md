# transcribe

Word-level timestamps from a video, via
[faster-whisper](https://github.com/SYSTRAN/faster-whisper).

`large-v3`, Swedish, VAD on, word timestamps on. Targets CUDA/float16 and falls
back to CPU/int8 if the GPU path fails, telling you which one ran.

## Setup (Windows, RTX 3070)

From the repo root, one command — it is safe to re-run:

```powershell
.\setup.ps1
```

That creates the venv, installs faster-whisper and the CUDA libraries, and
reports whether a CUDA device was actually detected.

### What it does about CUDA, and why

`faster-whisper` runs on CTranslate2, **not** PyTorch — so a working
`torch.cuda` proves nothing here, and PyTorch is not needed at all. CTranslate2
4.x needs **cuBLAS** and **cuDNN 9** for CUDA 12.

`setup.ps1` installs `nvidia-cublas-cu12` and `nvidia-cudnn-cu12==9.*`, which
ship those DLLs inside the venv — no system CUDA install required.

Those wheels drop the DLLs in `site-packages`, not on PATH, which normally means
editing PATH every session. `transcribe.py` handles it at startup instead, so
**no manual PATH changes are needed**. It does two things, and both are
required:

- `os.add_dll_directory` — covers DLLs resolved through `LoadLibraryEx`, i.e. an
  extension module's static dependencies.
- prepending the same directories to `PATH` in-process — CTranslate2 resolves
  cuBLAS and cuDNN *lazily* with a plain `LoadLibrary`, and that search consults
  `PATH` but **not** directories added via `add_dll_directory`.

Registering the directories alone looks like it should work and does not; the
symptom is `Library cublas64_12.dll is not found or cannot be loaded` even
though the file is plainly sitting in the registered folder.

### If CUDA still will not load

```powershell
.\setup.ps1 -RepairCuda
```

That force-reinstalls the CUDA wheels with no cache, which fixes a truncated or
partial download. `setup.ps1` verifies the DLLs actually load, not merely that a
device is visible, and prints `verdict=cuda_ready` when the GPU path is genuinely
usable.

Your driver must be new enough for CUDA 12 (566.xx or later is comfortable).

## Run

From the repo root:

```powershell
.\transcribe.ps1 "C:\path\to\clip.mp4"
```

That wrapper uses this project's virtualenv, so nothing needs activating. Or
call the script directly if you prefer:

```powershell
transcribe\.venv\Scripts\python.exe transcribe\transcribe.py "C:\path\to\clip.mp4"
```

**The first run downloads `large-v3`, about 3 GB**, into the HuggingFace cache
(`%USERPROFILE%\.cache\huggingface`). Later runs start immediately. Use
`--download-root` to put the weights somewhere else.

Writes `clip.words.json` next to the input. Options:

| Flag | Meaning |
| --- | --- |
| `-o PATH` | output path (default: input with `.words.json`) |
| `--model` | model size (default `large-v3`) |
| `--beam-size` | beam size (default 5) |
| `--language` | ISO code, e.g. `en`, `de` (default `sv`); `auto` to detect |
| `--vocabulary` | hotword list (default `vocabulary.txt`) |
| `--no-vocabulary` | ignore the vocabulary file |
| `--corrections` | find/replace rules (default `corrections.txt`) |
| `--no-corrections` | ignore the corrections file |
| `--verbatim` | keep false starts; use this for editing (see below) |
| `--timings` | (show.py) per-word timings and gaps |
| `--download-root` | where to cache weights (default: the HuggingFace cache) |
| `--cpu` | skip CUDA, go straight to CPU/int8 |

Progress goes to stderr, so `stdout` stays clean if you pipe it.

The video is decoded straight from its container by PyAV — no separate ffmpeg
extraction step, and no intermediate wav.

## Output

```json
{
  "device": "cuda",
  "compute_type": "float16",
  "used_fallback": false,
  "language": "sv",
  "duration": 61.44,
  "word_count": 214,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 1.5,
      "text": " Hej och välkommen.",
      "words": [
        { "word": " Hej", "start": 0.0, "end": 0.4, "probability": 0.98 }
      ]
    }
  ],
  "words": [
    { "word": " Hej", "start": 0.0, "end": 0.4, "probability": 0.98 }
  ]
}
```

`words` is the flat list across the whole file — usually what you want for
caption timing. `segments[].words` is the same data grouped by segment.

Words keep faster-whisper's leading space, so `"".join(w["word"] for w in words)`
reconstructs the transcript. Timestamps are in seconds, rounded to milliseconds.

## Accuracy: the vocabulary file

`vocabulary.txt` is a list of terms, one per line, passed to Whisper as
*hotwords* to bias decoding. Proper nouns and English technical words spoken
inside Swedish are the usual failures — Whisper reaches for a Swedish-sounding
word instead, so **Claude** comes back as *Cloud* and **jättelätt** as
*jätterätt*.

Add anything that recurs in your content and comes back wrong. Comments (`#`)
and blank lines are ignored, and the count used is recorded in the JSON as
`vocabulary_terms`.

## Accuracy: the corrections file

Hotwords are a *soft* bias. Against a close acoustic match they lose — Swedish
"Claude" and "Cloud" are near-identical to the model, and biasing alone does not
reliably win.

`corrections.txt` is the deterministic backstop, applied after transcription:

```
Cloud => Claude
jätterätt => jättelätt
```

Matching is **case-sensitive and whole-word**, so `Cloud => Claude` rewrites the
proper noun while leaving a legitimate lowercase "cloud computing" alone, and
never corrupts a longer word like "Cloudflare". Terms ending in punctuation
(`rätt. => rätt`) match correctly at end of sentence.

**Multi-word rules work too**, which matters because Whisper regularly splits
Swedish compounds and because grammar fixes span words:

- Same token count in and out (`en formulär => ett formulär`) rewrites in
  place, so **every word keeps its own timestamp**.
- Fewer tokens out than in behaves one of two ways, and the difference
  matters. When the replacement is a **subsequence** of the pattern
  (`göra mer. Och mycket mindre => göra mycket mindre`) the rule is a
  *deletion*: Whisper wrote words that were never spoken, the surviving words
  are real, and each keeps its own timing. The removed words' time is handed to
  the word before them so a caption does not blank out over audio that is still
  playing. Otherwise it is a genuine rewrite (`jätte rätt => jättelätt`, one
  spoken compound) and the tokens merge into one entry.

  A pattern may contain punctuation mid-phrase on purpose — the full stop in
  `mer.` is part of what identifies the invented run.

- **Nothing on the right removes the words outright** (`Textning.nu =>`). Over
  the silence at the edges of speech Whisper sometimes credits its training
  data — a subtitle site's name, a stray "TypeScript React" — naming no spoken
  sound at all. There is nothing to rewrite it to, so the token goes and its
  time is handed to the word before it. Reach for this only when the audio
  really is silent there; a mishearing of something spoken wants a rewrite.

Trailing punctuation on the final token is matched and carried over, so
`en formulär => ett formulär` fires on "…den en formulär." Punctuation
*inside* the phrase blocks the match, since "en, formulär" is two clauses
rather than the phrase being corrected. Corrections apply to both the
flat word list and the segment text, so the two cannot drift, and **timestamps
are untouched** — only the token text changes.

Every applied rule is tallied in the JSON under `corrections_applied` and
printed at the end of a run, so a correction is never silent.

### Changing a rule without re-transcribing

Corrections are applied when a transcript is written, so an existing
`.words.json` will not pick up a rule added afterwards — and a stale transcript
makes a working rule look broken.

```powershell
transcribe\.venv\Scripts\python.exe transcribe\recorrect.py "clip.mp4"
```

re-applies `corrections.txt` to the transcript in place, keeping a `.bak`. Add
`--dry-run` to see what would change first. Corrections are text-level, so
spending a GPU transcription on one is pure waste.

Reach for `vocabulary.txt` first — it steers the model, which is better than
overriding it. Use `corrections.txt` when biasing has already failed.

Note that **CPU/int8 is measurably less accurate than GPU/float16** — int8 is a
lossy quantisation. If a transcript looks poor, check `"compute_type"` in the
JSON before blaming the model: a run that fell back to CPU is not a fair test.

## Inspecting a transcript

```powershell
transcribe\.venv\Scripts\python.exe transcribe\show.py "clip.mp4"
transcribe\.venv\Scripts\python.exe transcribe\show.py "clip.mp4" --find Cloud Claude jätte
```

Pass either the transcript JSON or the video it came from — given a media file
it reads the sibling `.words.json`.

Prints the device actually used, the term and correction counts, the full
transcript, and where any search term occurs with its timestamp and confidence.

Use it before writing a correction rule. A rule that matches nothing and a rule
that never loaded look identical from the transcribe output alone, and rules
must be written against the literal text — Whisper may have produced `Cloude`
rather than `Cloud`, or split a compound into two tokens.

## Verbatim mode, and why editing needs it

Whisper's decoder is conditioned to produce *fluent* text. By default it
silently smooths false starts and repetitions out of the transcript — while the
audio still contains them.

For reading a transcript that is what you want. For **editing** it is the worst
possible failure: a cut whose span covers a dropped false start looks perfectly
clean in the transcript and keeps the blooper in the finished video. There is no
word to exclude, because the word was never written down.

The tell is speaking rate. If a line spans far longer than its word count
implies, there is audio in that span with no words against it:

```powershell
transcribe\.venv\Scripts\python.exe transcribe\show.py "clip.mp4" --timings
```

That prints every word with the gap before it, marking any gap of 0.35s or more.

```powershell
.\transcribe.ps1 "clip.mp4" --verbatim
```

disables VAD and previous-text conditioning, so stumbles appear as words and can
be cut deliberately.

## The fallback

Two distinct GPU failure modes are handled, because they surface at different
moments:

1. **At load** — no driver, no device, unsupported compute type.
2. **At first decode** — a missing `cudnn_ops64_9.dll` loads fine and only
   fails once a kernel actually runs.

Both fall back to CPU/int8 and print a clear notice to stderr; `used_fallback`
in the JSON records it. Errors that are *not* GPU-shaped are re-raised rather
than silently downgraded, so a typo'd path doesn't quietly cost you a 20-minute
CPU run.

## Notes for an RTX 3070

`large-v3` at float16 needs roughly 4.5–5 GB of VRAM, which fits your 8 GB with
room to spare. Expect somewhere around 8–15× realtime on the GPU. On CPU/int8 it
is far slower — think roughly realtime or worse — which is why the fallback is
loud rather than silent.

If you hit `CUDA out of memory` with other things on the GPU, `--model medium`
or `distil-large-v3` will cut the footprint substantially.

## Tests

```powershell
pip install pytest
python -m pytest test_transcribe.py -q
```

60 tests cover the fallback logic, error classification, option pass-through,
language selection, vocabulary and hotword biasing, single- and multi-token
corrections, output shape, CUDA DLL discovery, and PATH prepending. They stub the model, so they need no
weights and no GPU.

## A word placed at the wrong time

Where Whisper heard speech but could not time it, a word can carry a timestamp
seconds from when it was said. The cut is chosen by ear and by audio, so the
sound is right -- the word simply falls outside the range, and its caption goes
missing. `retime.py` says where it really was:

```
python show.py clip.words.json --find AI      # what the transcript claims
python retime.py clip.words.json --at 0.0 --start 0.65 --end 0.72
```

The word is named by the time the transcript currently gives it, which stays
unambiguous where the same word appears several times. `--end` is optional.
The previous transcript is kept as `.words.json.bak`, and the segments are
rebuilt so the flat word list and the segment text cannot disagree.

Reach for this only where the transcript is demonstrably wrong about *when* --
a smeared stretch the pipeline already flagged. It is not a way to nudge a
caption that is merely early.
