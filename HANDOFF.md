# Brief: taking over the `videoautomation` system

## Read this part before anything else

**Where the code is:**

```
https://github.com/olhildebrand-stack/videoautomation
git clone https://github.com/olhildebrand-stack/videoautomation.git
```

**The repository is public, and it carries the tool and nothing else.** Clone it
without asking anyone. What it deliberately does not carry: photographs, the
renders made from them, and the reference footage the editorial thinking was
read off. Those stay on the operator's machine — see `stories/README.md` and
`howtocutvideo/README.md` for what is missing from each and why. Everything
that runs is here.

**Where to paste this brief: Claude Code, in a terminal, inside the clone.**

```bash
git clone https://github.com/olhildebrand-stack/videoautomation.git
cd videoautomation
claude          # then paste this file as your first message
```

Not claude.ai in a browser tab, and not any chat window without a filesystem.
Everything below refers to real files — `pipeline/README.md`,
`broll/src/tokens.ts`, `pipeline/DIRECTOR.md` — and a chat Claude has no way to
open them. It will either say the folders do not exist or, worse, guess at what
they contain. If you have hit that already, that is the whole explanation: the
brief is fine, it was just read somewhere it cannot reach the code.

### If you are reading this without the repository yet

It is still worth reading. What survives without a filesystem:

- §0–§2 — what the system is, how the pipeline runs, and **what you need
  installed**. Work out now whether you have an NVIDIA GPU, a real ffmpeg, Node
  and Python; those decide whether this is a weekend or a fortnight.
- §3 — the warnings. Every one of these is true whether or not you can see the
  code, and §3.1 (it is hardcoded to Swedish) may decide whether you want the
  system at all.
- §5, §8, §9 — failure modes, what to ask the author, and the honest summary.

What does **not** work until you have the clone: §6, the first-run checklist.
Every step there runs a command against a real file. Do not let a chat Claude
walk you through it from memory — it will invent paths.

---

## 0. What you are looking at

This brief tells Claude what the system is, what state it is in, what is missing
because it lived on the original author's machine, and what to do first.
Everything below is written to be read by an agent and acted on.

This repository turns a raw talking-head recording into a finished vertical
short — cut, graded, captioned, with motion-design overlays — in one pipeline
that stops at three human checkpoints. It was built by one person for their own
channel, on Windows with an RTX 3070, for **Swedish-language** video. It works.
It is also unfinished in specific ways, and it is tuned to that one person's
voice, room, niche and machine. Treat it as a working system with a strong
opinion, not a product.

Four parts:

| directory | what it is |
| --- | --- |
| `transcribe/` | faster-whisper wrapper. Word-level timestamps, verbatim mode, hotword vocabulary, deterministic corrections. Python + venv. |
| `pipeline/` | the orchestrator. Transcribe → direct → cut → grade → hook → captions → overlays → `final.mp4`. Python, no venv of its own. |
| `broll/` | the renderer. Remotion (React + TypeScript). Captions, overlays, title cards, carousel slides. |
| `stories/` | still-image carousels for posting, rendered through the same Remotion components. Definitions only — the photographs are not in the repository. |

Read, in this order, before touching anything: `CLAUDE.md`, `pipeline/README.md`
(the long one, and the most valuable file in the repo), `transcribe/README.md`,
`broll/README.md`, `pipeline/DIRECTOR.md`.

---

## 1. The pipeline, end to end

```
raw.mp4
  → transcribe (verbatim, word timestamps)
  → ⛔ CHECKPOINT 1: is this the video you meant to make?
  → direct   (Claude decides shape, against pipeline/DIRECTOR.md)
  → cut list (beats mapped onto word timestamps, then measured against audio)
  → ⛔ CHECKPOINT 2: exactly what each beat will contain
  → cut → re-transcribe → colour grade
  → hook shortlist (matched from a bank of hooks that already worked)
  → ⛔ CHECKPOINT 3: pick a hook by number
  → captions + overlays
  → final.mp4
```

Commands (all run from the repo root; the author is on Windows PowerShell):

```powershell
python pipeline\pipeline.py init "videos\raw.mp4" --project projects\ep01
python pipeline\pipeline.py direct --project projects\ep01
python pipeline\pipeline.py run    --project projects\ep01     # advance to next gate
python pipeline\pipeline.py approve --project projects\ep01    # pass a gate
python pipeline\pipeline.py hook 2 --project projects\ep01     # pick hook #2
python pipeline\pipeline.py status --project projects\ep01
python pipeline\pipeline.py redo   --project projects\ep01 --from transcribe
```

Design rules that are load-bearing, and that you should not "improve":

- **The unit of editing is the take, not the sentence.** A take is one
  continuous run of speech — one attempt. Whisper writes three attempts as one
  sentence; keeping that sentence keeps all three attempts in the video.
- **The director never writes a timestamp and never writes hook text.** It names
  take *numbers* and picks a hook by *number*. This is enforced by the JSON
  schema in `pipeline/decision.py`, not by asking politely.
- **Every take gets a decision** — kept in a beat, or dropped with a reason. The
  validator counts. Silent omission is how a video shipped with every retake in it.
- **Overlay cues name a phrase you say, never a time.** So a cue sheet survives a
  re-record, a re-cut and a reorder. `<project>/overlays.json`.
- **Cut points are measured from the audio, not read off the transcript.**
  Whisper's word timestamps drift by up to half a second on take-heavy
  recordings. `pipeline/edges.py` finds the real speech edges with `silencedetect`.
- **Grading runs before captions**, so the grade never shifts caption colours.
- **`broll/src/tokens.ts` is the only file allowed a raw hex, a raw duration, or
  the easing curve.** `npm run lint:tokens` enforces it. Run `npm run check`
  (typecheck + token guard + unit tests) before every commit that touches `broll/`.

---

## 2. What it needs to run

| requirement | why | if missing |
| --- | --- | --- |
| **Node LTS + npm** | Remotion renders everything | nothing renders |
| **Real ffmpeg on PATH** with `trim`, `atrim`, `concat`, `eq`, `colortemperature` | cutting and grading | **Remotion's bundled ffmpeg is NOT enough** — it is built `--disable-filters` and has no `eq`/`colortemperature`. It can cut, it cannot grade. |
| **Python 3.11+** | the whole pipeline | nothing runs |
| **NVIDIA GPU, CUDA 12 driver (566.xx+)** | `large-v3` at float16, 8–15× realtime | falls back to CPU/int8: roughly realtime *or worse*, and **measurably less accurate** (int8 is lossy). A 5-minute raw becomes a coffee break. |
| **~3 GB disk for model weights** | first run downloads `large-v3` into the HuggingFace cache | first transcription fails |
| **`claude` CLI on PATH** (`npm install -g @anthropic-ai/claude-code`) | the `direct` stage shells out to `claude -p` | `direct` refuses; use `--brief-only` and hand the brief to a chat window instead |
| **Remotion's Chromium** | rendering | if it cannot download one, set `REMOTION_BROWSER_EXECUTABLE` to a Chromium binary and the pipeline passes it through |

`setup.ps1` at the repo root does both halves and verifies them — venv, deps,
CUDA wheels, ffmpeg filter check, `npm install`, `npm run check`. It is safe to
re-run. `.\setup.ps1 -RepairCuda` force-reinstalls the CUDA wheels when the DLLs
will not load.

**Cost:** the `direct` stage is the only thing that leaves the machine. Measured
at about **$0.12–0.20 per video** on Sonnet. Everything else — transcription,
ffmpeg, Remotion — runs locally and costs nothing.

---

## 3. Warnings. Read all of these before you touch a line.

### 3.1 It is hardcoded to Swedish

This is the single biggest thing to know, and it is not a config flag.

- `transcribe/transcribe.py` has `LANGUAGE = "sv"` as its default.
- **`pipeline/pipeline.py` never passes `--language` at all**, so every
  transcription the pipeline runs is Swedish, with no way to change it from the
  CLI.
- `pipeline/hooks/bank.json` stores each hook twice — `en` (English, used for the
  word-count rule) and `sv` (Swedish) — and **the `sv` field is what renders on
  screen**. `pipeline/hookgen.py` line ~198 onwards.
- `pipeline/cutlist.py` preserves Swedish letters through normalisation on purpose.
- The example topics, edit scripts and overlay sheets in `pipeline/topics/`,
  `pipeline/edit-scripts/` and `pipeline/overlay-sheets/` are all Swedish.

**If the new owner speaks English**, this is a real port, not a setting. The
minimum honest change list:

1. Add a `--language` flag to `pipeline.py`, thread it into `transcribe()`, and
   store it in `PipelineState` so `redo` keeps it.
2. Decide what `hookgen.py` renders. Either make the on-screen field
   configurable, or repoint it at `en` and stop maintaining `sv`.
3. Rewrite `pipeline/hooks/bank.json` (see 3.2).
4. Empty `transcribe/vocabulary.txt` and `transcribe/corrections.txt` and rebuild
   them from your own recordings (see 3.3).

Do this as one deliberate change with tests, not as a patch mid-video.

### 3.2 The hook bank is someone else's niche

`pipeline/hooks/bank.json` holds **38 hooks** that already worked — for a Swedish
channel about Claude, agents, "clawdbot", and AI tooling. The system *never
invents hook text*; it ranks bank entries against the project's `topic.txt` and
may swap at most one phrase (more than three changed words is refused).

For a different niche the rankings will be weak-to-useless, and the failure is
quiet: it will confidently offer a hook about AI agents for a video about
something else. Two ways out:

- `python pipeline\pipeline.py hook 0 --project projects\ep01` uses
  `<project>/hook.txt` exactly as written. That is the escape hatch, and it is a
  legitimate answer.
- Or rebuild the bank with hooks that actually worked for *your* content. The
  `_readme` key inside `bank.json` documents the entry shape (`en`, `sv`, `tags`,
  `slots`, `entities`). **Adding an entry is the only sanctioned way the
  vocabulary grows.** Do not let the model start writing hooks; that rule is the
  point of the whole file.

### 3.3 The tuning is one person's voice, one person's room

Every one of these is a number that was arrived at by watching and listening to
one specific setup. They are defaults to re-derive, not constants:

- **`-45 dB` noise floor** (`pipeline/edges.py: DEFAULT_NOISE_DB`). Your room is
  not their room. Find yours before trusting any cut:
  `python pipeline\edges.py "videos\raw.mp4" --script <script>.json --sweep`, then
  take the most sensitive column before the numbers start climbing without end.
  Too deaf and a quiet final syllable reads as silence and gets clipped ("content"
  → "con"); too sensitive and room tone reads as speech and the cut runs into the
  next take.
- **`0.15s` tail, `0.05s` head, `0.3s` on the final cut**, `--max-gap 0.30`
  silence removal, `0.14s` minimum silence. All settled by ear on one voice.
- **`transcribe/vocabulary.txt`** (21 lines) and **`corrections.txt`** (95 lines)
  are that channel's proper nouns and that speaker's mishearings. The vocabulary
  is *actively dangerous* to inherit: hotwords bias the decoder, so a term your
  recording never says can be emitted as text over audio the model cannot read. A
  Swedish video about voice agents came back with "TypeScript React GIS" in it,
  because those words were in the shared list for a different video. **Start your
  vocabulary empty and add only what your own recordings prove.** Corrections are
  safer — they are find/replace on text that already exists — but they are still
  someone else's spellings.
- **`pipeline/DIRECTOR.md` → Learned rules.** Eight entries, every one born from a
  specific video going wrong on that channel. They encode that speaker's habits
  (how they restart a line, how they trail off) and that operator's taste (`push`
  is for hooks only; `wordStack` is banned outright). Keep them at first — they
  are hard-won and cost nothing — but expect some to be wrong for a different
  speaker, and rewrite them as *what to do instead* when they are.

### 3.4 There are no worked examples in the repository

`.gitignore` excludes `videos/`, `projects/`, `previews/`, `broll/out/` and all
staged render inputs. That is correct — they are large and regenerable — but it
means **you get the machine and none of the mileage**. There is no finished
project directory to read, no `decision.json` from a real video, no `final.mp4`
to compare against, and no state file showing what a healthy run looks like.

What you *do* get, and should read as your examples:

- `pipeline/edit-scripts/*.json` — three real edit scripts.
- `pipeline/overlay-sheets/*.json` — two real overlay sheets.
- `pipeline/topics/*.txt` — three real `topic.txt` files.
- `pipeline/animations/*.json` + the `.gif` beside each — saved, paste-ready
  overlay cues with a rendered preview of what each one looks like. This is the
  best single reference for the overlay vocabulary.
- `transcribe/sample/test-sv.mp4` and `broll/public/transcripts/sample.words.json`
  — a tiny end-to-end sanity input.
- `howtocutvideo/` — the findings written from analysing the reference reels and
  the walkthrough tutorial. This is the editorial thinking behind the whole
  thing. The footage and the transcript it was read off are not in the
  repository; `howtocutvideo/README.md` says where they are.

**Assume the original author knows things this repository does not say.** Much of
the operating knowledge — which takes to trust, how the checkpoints feel in
practice, what a good `topic.txt` looks like for a given video, what the grade
should look like on their camera — accumulated in local sessions, local project
folders and their head. When something behaves in a way the docs do not explain,
the docs are more likely incomplete than the code is wrong. Ask them; do not
reverse-engineer and then "fix" it.

### 3.5 Windows-first, in ways that will bite on macOS or Linux

The whole thing is written for PowerShell on Windows and says so:

- Paths in every doc are `pipeline\pipeline.py`, venv at
  `transcribe\.venv\Scripts\python.exe`. `python_for_transcribe()` in
  `pipeline.py` checks both `Scripts/python.exe` and `bin/python`, so the venv
  lookup is portable — most of the surrounding documentation is not.
- `setup.ps1` and `transcribe.ps1` are PowerShell only. There is **no** shell
  equivalent. On macOS/Linux you are doing setup by hand.
- Remotion is invoked as `broll/node_modules/.bin/remotion`, never `npx`, because
  on Windows `npx` is `npx.cmd` and `subprocess` cannot resolve it without a
  shell. Do not "simplify" this back to `npx`.
- Props are passed to Remotion via a **file**, never an inline JSON argument,
  because PowerShell mangles native-argument quoting. Same warning.
- The director's prompt goes to `claude -p` on **stdin**, never as an argument:
  on Windows `claude` is a `.cmd` shim, cmd.exe refuses a command line over 8191
  characters, and a brief is ~12k. This worked on Linux and failed on the only
  machine that mattered.
- Windows PowerShell 5.1 turns a native command's stderr into a terminating
  error; `setup.ps1` works around this in three places. PowerShell 7 is
  recommended and the script says so on startup.

### 3.6 Sharp edges and rough spots

- **`wordStack` still exists in the renderer but is banned by a learned rule.**
  `broll/src/overlays/WordStack.tsx` is live code the director is forbidden to
  propose. Do not delete it, and do not resurrect it without being asked by name.
- **`CYANVOID.md` is dead.** The brand limits were removed deliberately (commit
  `63c0e6a`) because the vocabulary this project needs — green and red graph
  lines, emoji, screenshots, chat mockups, logos — is exactly what CYANVOID
  forbade. It is kept as history and **governs nothing**. Never answer a design
  question by quoting it. What survived is the token rule in §1, the palette in
  `tokens.ts` itself, and the motion-design skill in §4.
- **Doc drift.** `pipeline/README.md` claims 399 tests; there are **487** (plus 25
  skipped without ffmpeg). `transcribe/README.md` claims 60; there are **97**.
  Small, but a sign the docs lag the code — verify claims against the code before
  relying on them.
- **`stories/` carousels are half-manual.** A slide whose picture is a video
  renders as `NN-overlay.png` with the card punched out; the operator drops the
  clip behind that PNG in an editor. That step is not automated and is not going
  to be.
- **Explicit ranges in an edit script are frozen.** A beat written as
  `{"start": …, "end": …}` bypasses matching, silence removal and merging, and
  carries whatever head/tail defaults were current when it was written. Retuning
  the defaults **does not reach an edit script already on disk** — use
  `redo --retime` to re-measure, and know that it discards any adjustment made
  by ear.
- **No CI, no Python linter, no formatter.** The tests are the only automated
  check on the Python side, and nothing runs them for you.
- **`redo` never redoes work `run` already did.** A finished project ignores a new
  transcript, changed settings or updated code and says so, rather than reporting
  a success it did not perform. That is deliberate; reach for `redo --from <stage>`.

---

## 4. The skills that come with the repository, and the one that does not

Two Claude skills are **vendored into `.claude/skills/` and committed** — 21
files in all — so cloning the repository gets them with no install step. Your
Claude will pick them up automatically. They are not decoration; one of them is
now the design authority for the whole renderer.

### `motion-design` — the design authority

The LottieFiles motion-design skill (MIT), vendored from
`github.com/lottiefiles/motion-design-skill` @ `f9a8a04`. `CLAUDE.md` says
plainly: **follow it, and nothing overrules it.**

That wording exists because something used to. `CYANVOID.md` — the old brand
spec — overruled this skill on colour, easing, overshoot and what was allowed on
screen. Those limits were deleted (commit `63c0e6a`) once it became clear the
vocabulary the videos actually need is green and red graph lines, emoji,
screenshots, chat mockups and logos, all of which CYANVOID forbade outright.
CYANVOID is history now. The skill is the standard.

The components in `broll/src/` are literally built to these numbers, so changing
them is a renderer-wide change, not a preference:

- **Stagger budget: total stagger under 500ms.** `beatInFrames` in `tokens.ts`
  is derived from this.
- **The 1/3 rule.** With three or more elements, at most one third may be in
  active motion at once — which is *why* `beatInFrames` equals the enter
  duration: each element settles as the next one starts.
- **The 8-step checklist and the decision framework** (`director/`) for planning
  a new clip, and its **narrative structure** — setup, action, resolution inside
  a single clip.

Also inside it: `patterns/` (entrance-exit, multi-element, state-feedback,
ambient-continuous), `reference/timing-easing-tables.md`,
`reference/quality-checklist.md`, `reference/troubleshooting.md`, and the
`director/` set on choreography, Disney principles and emotion mapping.

**The one place the skill does not have the last word** is the actual duration
values and the easing curve in `broll/src/tokens.ts`. Those are this project's,
arrived at by watching renders. `CLAUDE.md` is explicit that they are "defaults
to design with, not laws to cite" — so tune them by watching a render, not by
quoting a table at them.

### `ffmpeg-color-grading-chromakey` — the grading reference

A complete colour-manipulation and green-screen skill: `chromakey`/`colorkey`,
LUT application via `lut3d`, curves and levels, colour balance, colour-space
handling and HDR tone mapping. `pipeline/README.md` points at it for filter
recipes.

The pipeline's own grade is deliberately modest — slight contrast, mild
saturation, a small cool bias, **no LUT**, so there is nothing to ship or
version. For a real look, drop a `.cube` file in and pass it as `Grade(lut=...)`
in `pipeline/ffmpeg_ops.py`; it is applied last, so it grades the corrected
image rather than the raw one. That is the moment to open this skill.

Note its first section is a set of Windows path rules — another sign of the
machine this was built on.

### The plugin that is *not* vendored

`.claude/settings.json` enables `compound-engineering@compound-engineering-plugin`
from the third-party marketplace `EveryInc/compound-engineering-plugin`. Unlike
the two skills above, **it is a reference, not a copy** — the code lives in
someone else's repository, and your Claude may prompt to install it from that
marketplace on first run.

Nothing in the pipeline depends on it. If the new owner does not want a
third-party marketplace enabled in their sessions, deleting the
`extraKnownMarketplaces` and `enabledPlugins` blocks from `.claude/settings.json`
is safe and breaks nothing. If they do want it, it is worth asking the original
author what it was doing for them — that is local knowledge this repository does
not carry.

### Skills are also the right place to put what you learn

Nothing stops the new owner from adding their own skill under `.claude/skills/`
for their half of the work. But note the ordering this project already has, and
keep it: **corrections to editorial judgement go in `pipeline/DIRECTOR.md` under
*Learned rules*, not into a skill and not into a chat reply.** A skill teaches
technique; `DIRECTOR.md` accumulates what went wrong on a specific video and what
to do instead. Do not blur the two.

---

## 5. Known failure modes, and what they actually mean

Learn these; they are most of the debugging surface.

| symptom | cause | fix |
| --- | --- | --- |
| Transcript reads clean but the cut keeps a blooper | Whisper's fluency conditioning smoothed false starts out of the *text* while leaving them in the *audio* | The pipeline passes `--verbatim` everywhere now. If you see this, something is transcribing without it. |
| A word spans 8 seconds | swallowed audio — a false start the decoder never wrote down, absorbed by the neighbouring word | handled automatically; long words are trimmed back so silence removal can see the gap. It is reported when it fires. |
| A run of words at 0.00 confidence | hallucinated hotwords — vocabulary terms emitted over audio the model cannot read | words under 0.05 confidence are dropped. Also: shrink your vocabulary (§3.3). |
| Cut lands *inside* the last word ("content" → "con") | transcript timestamp drift, which accumulates and then holds | `--retime`, and find your noise floor with `edges.py --sweep`. A bigger tail only hides it. |
| A beat opens on a breath or a beat of silence | speech-edge search reached into a neighbouring take, or a pinned start kept the silence behind it | per-beat `"retime": "end"` pins the start and still measures the end. Checkpoint 2 tells you which beats need it. |
| `Library cublas64_12.dll is not found or cannot be loaded` (file is plainly there) | CTranslate2 resolves cuBLAS/cuDNN lazily via `LoadLibrary`, which reads `PATH` but not `add_dll_directory` | `transcribe.py` does both at startup. If it still fails: `.\setup.ps1 -RepairCuda`. |
| Setup looks green, transcription runs on CPU anyway | a CUDA device can be visible while the DLLs are unloadable | `setup.ps1` prints `verdict=cuda_ready` only when the libraries genuinely load. Check `"compute_type"` in the output JSON before blaming the model for a bad transcript. |
| ffmpeg is present, grading fails | it is Remotion's bundled build, without `eq`/`colortemperature` | install a real ffmpeg: `winget install Gyan.FFmpeg`, then reopen the terminal. |
| Remotion render dies thousands of stack frames deep | historically, a missing overlay asset | now a cue whose file is absent, or whose phrase was never said, is dropped and named at the checkpoint. Nothing is guessed. |
| An overlay sits behind the Instagram UI | `safeZone` in `tokens.ts` — 220px top, 450px bottom, 100px sides at 1080×1920 | `python pipeline\verify.py --project <p>` renders the overlay layer over flat magenta and measures the bounding box. Exit 0 clean, 1 breach, 2 nothing rendered. |
| A stretch marked **SPEECH NOT TRANSCRIBED HERE** | several attempts were made and Whisper wrote one of them down, in the wrong place | `python pipeline\preview.py --project <p> --smeared` writes one mp3 per run of speech. Listen, find the clean attempt, pin a beat to it. `takes.py` finds the boundaries the transcript could not. |

---

## 6. What to do first, in order, with a check for each step

Do not start a video until steps 1–5 are green.

1. **Read the docs.** `CLAUDE.md`, `pipeline/README.md`, `transcribe/README.md`,
   `broll/README.md`, `pipeline/DIRECTOR.md`. Add
   `.claude/skills/motion-design/SKILL.md` before you touch anything that moves
   on screen (§4).
   *Check:* you can explain, without looking, why the unit is the take and not
   the sentence, and why cut points come from the audio.

2. **Install prerequisites and run setup.**
   ```powershell
   .\setup.ps1
   ```
   *Check:* the summary prints `Setup completed.` with `verdict=cuda_ready` and
   `required filters present (trim, atrim, concat, eq, colortemperature)`. Any
   red line is a real blocker — fix it now, not later.

3. **Run the tests.**
   ```powershell
   pip install pytest
   python -m pytest pipeline -q
   cd transcribe; python -m pytest -q; cd ..
   cd broll; npm run check; cd ..
   ```
   *Check:* pipeline `487 passed` (25 skip without ffmpeg on PATH — with ffmpeg
   installed they should run), transcribe `97 passed`, and `npm run check` clean
   across typecheck, token guard and unit tests.

4. **Transcribe the sample.**
   ```powershell
   .\transcribe.ps1 "transcribe\sample\test-sv.mp4"
   transcribe\.venv\Scripts\python.exe transcribe\show.py "transcribe\sample\test-sv.mp4"
   ```
   *Check:* a `.words.json` appears beside the input, and `show.py` reports
   `device: cuda`, `compute_type: float16`, `used_fallback: false`. If it says
   CPU/int8, stop and fix CUDA — every downstream decision rests on transcript
   quality.

5. **Render something.**
   ```powershell
   cd broll; npm start        # Remotion Studio on http://localhost:3000
   ```
   *Check:* the studio opens and `Captions`, `CaptionedVideo`, `TitleCard`,
   `Conversation`, `Slide` and `StatBlock` all preview. Then render one still:
   `npx remotion still TitleCard out/TitleCard.png --frame=45`.
   **This is a step only the owner can do — it needs their machine, their GPU and
   a browser on localhost.**

6. **Do one real video end to end, with a short throwaway recording.** 30–60
   seconds, deliberately including a false start and a retake, so you see what
   the checkpoints are for.
   ```powershell
   python pipeline\pipeline.py init "videos\test.mp4" --project projects\test
   python pipeline\pipeline.py direct --project projects\test
   python pipeline\pipeline.py run --project projects\test
   ```
   *Check:* checkpoint 2 shows a `CUT :` line for every beat that matches the
   `script:` line, and `<project>/decision.json` explains why each take was
   dropped. Read the `risks` list — it is addressed to you.

7. **Only then** decide about the language port (§3.1) and the hook bank (§3.2).
   Do them as separate, tested changes.

---

## 7. How to work in this repository

The house rules, from `CLAUDE.md`. Follow them; they are why the codebase reads
the way it does.

- **Do it, don't instruct it.** Write the code, install the dependency, run the
  test, render the clip, commit. Do not hand back a list of commands for work
  that could have been done in the session.
- **But say plainly what only the owner can do**, and where. Anything on their
  Windows machine, anything needing the GPU, anything on `localhost`. Give the
  exact directory, the exact command and the expected output. Never leave them to
  infer that something is their job.
- **Simplicity first.** The minimum code that solves the stated problem. No
  options nobody asked for, no abstraction for something used once, no error
  handling for cases that cannot occur.
- **Surgical changes.** Every changed line traces back to the request. Do not
  reformat, rename or improve nearby code. Match the existing style. Mention dead
  code; do not remove it. Do remove imports your own change orphaned.
- **Verify, don't assume.** Turn the task into a concrete success check before
  starting, give a numbered plan with a check per step, then run the checks
  yourself and loop until they pass.
- **Corrections to the director go in `pipeline/DIRECTOR.md` under *Learned
  rules*, written as what to do instead** — never in a chat reply. A rule there
  applies to every future video; a rule in a chat applies to none. Keep the entry
  that made it necessary. `python pipeline\director.py --project <p> --learn` says
  what the operator changed after the director decided; a difference that will
  recur is a rule that has not been written yet.
- **Run `npm run check` in `broll/` before committing anything under it**, and the
  pytest suites before committing anything under `pipeline/` or `transcribe/`.

### The commentary style

Comments and docstrings in this codebase explain *why*, and usually name the
specific video that made the rule necessary. That is deliberate — it is how the
system accumulates. Match it. A comment that restates the code is noise here; a
comment that says "this is what `aieditoradvancing` did to us" is the point.

---

## 8. Questions worth asking the original author before starting

These are the things the repository cannot tell you:

1. Is there a finished `projects/` directory you can send over as a reference —
   state file, `decision.json`, edit script, overlay sheet, and the `final.mp4`?
   One worked example is worth more than any amount of reading.
2. What noise floor does your room actually use, and did you ever change the head
   and tail defaults?
3. Which of the eight learned rules in `DIRECTOR.md` are about *you* (your speech
   habits) versus about *the tooling* (Whisper's behaviour)? The second kind
   transfers; the first kind does not.
4. Which hooks in the bank are yours-only versus generally good? Are any of them
   ones you would drop now?
5. Is anything in `howtocutvideo/findings.md` and `tutorial-findings.md`
   superseded by what you have learned since?
6. What is the grade meant to look like? The default is a restrained lift with a
   small cool bias and no LUT — was that a decision or a placeholder?

---

## 9. The honest summary

**What works well:** transcription (fast, accurate, verbatim, with a real fix for
the hotword and DLL problems), cut-point measurement from audio, the three
checkpoints, cue-by-phrase overlays, the token rule, the pixel-level safe-zone
verifier, and a genuinely good test suite. The reasoning is written down
everywhere, which is rare and makes the system learnable.

**What is unfinished or borrowed:** the Swedish hardcoding, the hook bank's
niche, the per-room tuning, the missing worked examples, the Windows-only setup
scripts, the half-manual carousel step, the absent CI, and documentation that has
started to lag the code.

**What will actually cost you time:** the language port if you speak English, and
rebuilding the tuning and the hook bank for your own voice and your own niche.
Budget for those two properly. Everything else is a working system that will do
what it says.
