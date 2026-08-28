# pipeline

Raw video to a graded, captioned cut — stopping at three human checkpoints.

```
idea      (IDEAS.md: a topic, a hook number, a beat outline — before filming)
  → raw.mp4
  → transcribe
  → ⛔ CHECKPOINT 1: throughline
  → direct  (Claude decides what the video is, against DIRECTOR.md)
  → cut list (script lines mapped onto word timestamps)
  → ⛔ CHECKPOINT 2: cut list review
  → cut  →  re-transcribe  →  colour grade
  → hook shortlist (matched from the winning-hooks bank)
  → ⛔ CHECKPOINT 3: pick a hook, 1-N
  → captions
  → final.mp4
```

## Why three checkpoints

Everything except the editorial judgement is deterministic, and the judgement is
where a mistake is expensive. Stage 3 of `usingtranscript.txt` already asks
whether the throughline matches your intent — that is checkpoint 1. Checkpoint 2
shows exactly which words each script line matched, and how confidently, before
anything is cut or rendered. Checkpoint 3 is the hook: one line that decides
whether the other thirty seconds are watched at all, and the only place where
picking from a ranked shortlist beats accepting a default.

All three are cheap to look at and expensive to get wrong, which is the whole
argument for keeping them.

## Directing

```powershell
python pipeline\pipeline.py direct --project projects\ep01
```

Everything in this pipeline is deterministic except one decision, and that
decision was being made by hand, per video, in a chat window, where nothing
about it accumulated. `direct` makes it a stage: the transcript goes to Claude
with the rules in `pipeline/DIRECTOR.md`, and what comes back is checked against
the transcript it claims to describe before it becomes an edit script and an
overlay sheet.

Three files, three jobs:

| file | job |
| --- | --- |
| `brief.py` | assembles the question — takes, machine verdicts, assets, hooks, overlay vocabulary |
| `decision.py` | states the answer's shape, and every check that can be made of it |
| `director.py` | asks, checks, hands the failures back, writes the files |

**The unit is the take, not the sentence.** A take is one continuous run of
speech — one attempt at saying something. This matters because Whisper wrote
vas3's hook as a single fourteen-second sentence, six seconds of which were
false starts, and keeping "that sentence" kept the false starts with it. Every
attempt is now its own numbered row, and the director picks between them.

**The director never writes a time.** It names take numbers; the pipeline
measures the cut points from the audio. It never writes hook text either — it
picks from the shortlist by number. Both are enforced by the schema, not by
asking nicely: there is no `enter` field for it to fill in and no `text` field
under `hook`.

**Every take gets a decision.** Each one is either in a beat or in `drop` with a
reason, and the validator counts. A take left out silently is exactly how a
recording full of retakes shipped with every retake intact.

What gets checked before anything is written:

- every take number exists, and none is used twice
- no take is left undecided
- every overlay cue quotes words from a take that **survived** — resolved with
  the same code that will place it later, so a cue that fails here would have
  failed at render time, after the edit was committed
- `hook.pick` is a number in the shortlist

A failed check is handed back as a complaint and the whole decision is asked for
again — three times, then it stops and shows what is still wrong. A model that
has failed the same check twice is not one round away from passing it.

`<project>/decision.json` keeps the reasoning: why each take was dropped, what
each overlay is for, and a `risks` list addressed to you. Read that when a cut
looks wrong; it usually says why.

### Directing it yourself

```powershell
python pipeline\pipeline.py direct --project projects\ep01 --brief-only
python pipeline\director.py --project projects\ep01 --from-file projects\ep01\decision.json
```

The first writes `brief.md` to hand to Claude in a chat window; the second runs
a decision written by hand through exactly the same checks. A decision is not a
lesser kind of decision for not having come through the CLI.

### Training it

`pipeline/DIRECTOR.md` is the whole brief — role, structure, taste, and a
**Learned rules** section that grows. Every entry there came from one video
going wrong, and each one is a mistake that is now impossible to repeat. It is
the only file to edit when the director keeps getting the same thing wrong.

```powershell
python pipeline\director.py --project projects\ep01 --learn
```

After you have hand-edited the edit script, that says what you changed against
what the director chose — takes you cut, takes you put back, whether you
reordered. A difference that will recur belongs in `DIRECTOR.md`, written as
what to do instead. Without it the overruling happens in an editor and leaves
no trace.

### Cost

Measured, on Sonnet: about **$0.12–0.20 a video**, and a second call only if the
first fails a check. Most of that is fixed -- Claude Code's own system prompt is
~28k cache-write tokens whatever you ask it. The brief is ~4k on top and the
decision ~2k back.

Nothing else in the pipeline costs anything: transcription runs on your GPU,
ffmpeg and Remotion run locally. This one call is the only part that leaves the
machine, and it is cheaper than directing by hand in a chat window, where the
whole conversation is re-sent every turn and grows all day.

`--model opus` for a video worth more.

## Requirements

A real **ffmpeg** on PATH, with the `trim`, `atrim`, `concat`, `eq` and
`colortemperature` filters. `setup.ps1` checks for all five.

Remotion bundles its own ffmpeg, but that build is compiled `--disable-filters`
with a small allowlist: it has `trim` and `atrim` but not `eq` or
`colortemperature`, so it can cut but cannot grade. It is not a substitute.

```powershell
winget install Gyan.FFmpeg   # then reopen the terminal
```

## Use

```powershell
python pipeline\pipeline.py init "videos\raw.mp4" --project projects\ep01
```

That transcribes and stops at checkpoint 1, printing the transcript. From
there, `direct` (above) decides the shape and writes the beats for you. To do it
by hand instead, write them to `projects\ep01\edit-script.json`:

```json
[
  {"beat": "HOOK",    "line": "exact words from the transcript"},
  {"beat": "THE FIX", "line": "exact words from the transcript"},
  {"beat": "LANDING", "start": 18.4, "end": 24.3}
]
```

A beat may state `start` and `end` instead of a line. Matching infers cut
points from a transcript whose timings do not always separate a good take from
a discarded one; when it fights the data, stating the range is faster and
exact. **Explicit ranges bypass matching, silence removal and merging** — they
are taken as given. Get the numbers from `show.py --timings`.

That also means a stated range carries whatever head and tail were current when
it was written, and **retuning those defaults does not reach an edit script
already on disk**. `--retime` re-measures each stated range around the words it
actually covers, using the current settings:

```powershell
python pipeline\pipeline.py redo --project projects\ep01 --retime
```

`--retime` measures against the **audio**, not the transcript. That distinction
is the whole point of it — see *The transcript is not a clock* below. It
discards any adjustment made by ear beyond the tails, which is why it is opt-in
rather than automatic, and why the checkpoint prints what it took back:

```
  LANDING        76.07 ->   82.21  ( 6.14s)  match 1.00
    retimed from 75.55 -> 82.40  (-0.71s)
      speech runs +0.50s / +0.48s from where the transcript put it
      the transcript ended this cut inside the last word; the audio says
      where it really finishes
```

`--no-retime` goes back to taking the numbers as written; either flag rebuilds
the cut list from any stage, as `--max-gap` does.

### Per-beat overrides

Two settings a single beat can carry, when nothing global fits:

```json
{"beat": "LANDING", "start": 296.4, "end": 302.9, "retime": false}
{"beat": "THE POINT", "start": 142.0, "end": 146.1, "tail": 0.0}
```

**`"retime"`** takes an edge as written while every other beat is still
measured. `false` pins both ends; `"end"` pins the start and still measures the
end; `"start"` is the mirror.

`"end"` is usually the one you want. Where a discarded attempt sits just before
a beat, the audio search reaches back into it and pulls the cut open over words
that were meant to be gone — but pinning both ends also keeps whatever silence
the transcript left after the last word, which plays as a long pause before the
next beat. Checkpoint 2 says where a start needs pinning: a beat reporting
*"further out than drift explains"*, or whose `CUT` line carries words the
`script` line does not.

**`"tail"`** is how long to hold after the last word, in seconds, instead of the
0.15s default (0.3s on the final beat). Where the speaker stops to think, the
default is long enough to show them doing it — `"tail": 0.0` cuts on the word.

## A project's own terms and rules

Two optional files in a project, both read at transcription time:

| file | effect |
| --- | --- |
| `<project>/vocabulary.txt` | **replaces** `transcribe/vocabulary.txt` |
| `<project>/corrections.txt` | **adds to** `transcribe/corrections.txt` |

The difference is not an oversight. Hotwords bias the decoder, so a term the
recording never says is pure risk: fed in as a prompt, it comes back as text
over audio the model could not read. `aivoiceagents` — a Swedish video about
voice agents — produced takes beginning `TypeScript React GIS` and
`TypeScript React Textning.nu`, because `TypeScript` and `React` are in the
shared list for an entirely different video. A vocabulary that is *only* what
this recording says cannot do that.

A correction cannot misfire the same way. It is a find/replace on text that is
already there, so the shared rules stay useful and a project's rules are
appended — they run last, and can correct something a general rule got wrong.

Neither file is created for you. A project with no `vocabulary.txt` uses the
shared list, which is the right default until a recording proves otherwise.

## Transcription is verbatim

Whisper's decoder is conditioned to produce fluent text. Left to itself it
silently smooths false starts and repetitions out of the transcript **while the
audio still contains them** — which for editing is the worst possible failure:
the transcript reads clean, and the cut keeps the blooper.

`transcribe.py --verbatim` turns off `condition_on_previous_text` and the VAD
filter. The pipeline passes it on every transcription, raw and cut.

It is the root of every smeared stretch this project has fought:

| video | what the transcript said | what was there |
| --- | --- | --- |
| vas3 | one hook sentence, fourteen seconds | six seconds of it were false starts |
| aieditoradvancing | a problem sentence starting at 52.7s | the delivery ran 49.5–57.5 |
| aivoiceagents | "en businessgrej som alla hoppar på hemsidodesigning nu" | does not parse; the words between were dropped |

Turning the VAD off also removes most of the drift *The transcript is not a
clock* describes: timestamps are no longer mapped back through stripped
silence, so they stop sliding in proportion to how much was removed. Measuring
the audio still earns its place — it is right about the last consonant where
the transcript is approximate — but it corrects a smaller error now.

The cost is a messier transcript, and that is the point: an edit script has to
be written against what was said.

## The transcript is not a clock

Word timestamps say roughly where a word is. They are not accurate enough to
cut on, and the error is not constant.

`transcribe.py` runs with `vad_filter` on: the silence is stripped before
decoding and the timestamps are mapped back afterwards. That mapping
accumulates error in proportion to how much silence was removed — so on a
take-heavy recording the whole alignment slides progressively **early** as it
goes on.

Measured against the audio on the recording this pipeline was built for, at
-45dB. `stated` is what the edit script held; `speech` is where the sound
actually is.

| beat | stated start | speech starts | drift |
| --- | --- | --- | --- |
| HOOK | 9.05 | 9.04 | −0.01 |
| TESTKANIN | 27.98 | 27.88 | −0.10 |
| THE TAKE | 42.28 | 42.85 | **+0.57** |
| WHY | 61.28 | 61.76 | **+0.48** |
| LANDING | 75.55 | 76.12 | **+0.57** |

Zero for the first thirty seconds, then a flat half-second for everything
after. That is the shape of a remap error: it accumulates over the silence
removed and then holds.

The first two rows are near zero for a reason worth keeping — those two starts
came from `takes.py`, which measures the audio. The other three came from the
transcript. Two independent audio measurements agreeing to within 10ms, while
every transcript-derived number is half a second out, is the clearest statement
of the problem available.

Cutting at `word_end + 0.15` was therefore clean early in the recording and
landed *inside* the word later on: "video" came out as "vi", "själv" as "sjä",
"content" as "con". The same drift opens a cut before the speaker starts, heard
as a beat of silence at the head of every late segment.

**No tail value fixes this.** A larger one only hides it until the drift
catches up. 0.5s worked because it happened to exceed the drift, not because it
was right.

The audio has no such problem, so cut points are measured from it:

```powershell
python pipeline\edges.py "videos\raw.mp4" 42.28-49.24
```

```
stated      42.28 ->    49.24
speech      42.85 ->    49.45   (+0.57 / +0.21)
cut         42.80 ->    49.60   (head 0.05s, tail 0.15s)
```

`silencedetect` finds the boundary between speech and room tone directly, which
is what a cut point actually wants.

### The threshold is per recording

A voice declines through a sentence: the final syllable can sit 10–20dB below
the middle of the phrase. Set the threshold too deaf and that syllable reads as
silence, so the measurement *reproduces* the clipped word instead of correcting
it — which is exactly what -35dB did to "content". Too sensitive and room tone
reads as speech, running the cut into the next take.

Find this recording's floor before rebuilding:

```powershell
python pipeline\edges.py "videos\raw.mp4" --script pipeline\edit-scripts\clip.json --sweep
```

```
beat           stated      -30      -35      -40      -45      -50      -55
HOOK            14.42    14.14    14.16    14.16    14.18    14.18<   clamp
TESTKANIN       30.92    30.60    30.63    30.63    30.63    30.70    clamp
THE TAKE        49.24    49.29    49.32    49.35    49.45    49.45    clamp
WHY             67.30    67.31    67.32    67.33    67.35    67.96    clamp
LANDING         82.40    81.64    81.68    81.72    82.01    82.31    clamp
```

Take the most sensitive column before the numbers start climbing without end —
that is the floor of the room, and the edge below it is the real one. Then:

```powershell
python pipeline\pipeline.py redo --project projects\ep01 --retime --noise -45
```

The default is **-45dB**. `--min-silence` defaults to 0.14s, long enough not to
trip on the closure inside a plosive.

**Still on the transcript's clock:** matched lines (a beat with `line` rather
than `start`/`end`) and `--max-gap` silence removal. Both derive their cut
points from word timestamps and carry the same drift. Explicit ranges with
`--retime` are the path that does not.

Then:

```powershell
python pipeline\pipeline.py run --project projects\ep01
```

That prints the cut list and stops at checkpoint 2:

```
  HOOK+THE FIX    5.88 ->   15.25  ( 9.37s)  match 1.00
    script : Det är faktiskt jättelätt att sätta upp det också Ni kan ta den...
    matched: Det är faktiskt jättelätt att sätta upp det också. Ni kan ta den...
  LANDING         0.42 ->    3.49  ( 3.07s)  match 1.00
```

Each entry shows two lines. `script:` is what you asked for; **`CUT   :` is what
the segment actually contains**, rebuilt from the words the span covers. Those
differ when a merge sweeps up words between two beats, and the checkpoint says
so explicitly — the per-line match alone would look correct either way.

Lines marked `~` did not match exactly. A `.2` suffix on a beat name means
silence removal split that line at a pause; the checkpoint reports how long a
pause it removed. Edit `edit-script.json` and re-run to redo, or:

```powershell
python pipeline\pipeline.py approve --project projects\ep01
```

which cuts, re-transcribes and grades, then stops at checkpoint 3 with a
shortlist of hooks. Pick one by number and it renders through to `final.mp4`.

`python pipeline\pipeline.py status --project projects\ep01` says where you are.

### Rebuilding after a change

`run` only advances a pipeline; it never redoes work already done. A finished
project therefore ignores a new transcript, changed settings or updated code,
and says so rather than reporting a fresh success it did not perform.

Point it at a prepared script rather than copying files by hand — `copy` means
different things in cmd and PowerShell, and a failed copy silently reuses the
old script:

```powershell
python pipeline\pipeline.py redo --project projects\ep01 --edit-script pipeline\edit-scripts\clip.json
```

```powershell
python pipeline\pipeline.py redo --project projects\ep01                      # from the cut list
python pipeline\pipeline.py redo --project projects\ep01 --from transcribe    # from scratch
python pipeline\pipeline.py redo --project projects\ep01 --from hook         # re-match hooks
python pipeline\pipeline.py redo --project projects\ep01 --from captions      # re-render only
```

`--from hook` matches a fresh shortlist and asks again; `--from captions` keeps
the hook already picked and only lays the caption layer down again.

Changing `--max-gap` rebuilds the cut list on its own, from any stage.

## Hearing what the transcript could not place

```powershell
python pipeline\preview.py --project projects\ep01 --smeared
```

Writes one mp3 per continuous run of speech in every stretch the brief marks
**SPEECH NOT TRANSCRIBED HERE**, named by when it happens, and prints what the
transcript claims is in each:

```
previews\0034.84-0052.95.mp3  (18.11s)
    transcript has: Jag började det här projektet för två dagar sedan
```

An 18-second run holding three seconds of text is a stretch where several
attempts were made and Whisper wrote one of them down, in the wrong place.
Play it, find the attempt that runs clean, and pin a beat to it — that is how
`aieditoradvancing`'s problem sentence was recovered.

For a stretch you already have times for, the ranges still work directly:

```powershell
python pipeline\preview.py videos\raw.mp4 34.8-53.0 59.5-73.1
```

## Three passes over the audio, in order

Each one can only do what the one before it cannot, and each is bounded so it
cannot make the mistake the next one exists to catch.

1. **Measure around the stated range.** `edges.py measure` looks 1.2s either
   side for where speech runs, and refuses to move an edge more than 0.8s —
   past that it is not drift, it is a neighbouring take. This is what fixes a
   cut landing inside the last word.

2. **Climb off the noise floor.** A measurement that hits the drift clamp on
   both edges usually means the room itself is above the threshold, so the
   "speech run" never ends. `measure_best` climbs from −45dB until the answer
   stops clamping. A quiet room never climbs, because a less sensitive
   threshold misses the quiet sentence-final syllable the floor exists for.

3. **Trim inside the range that was chosen.** The two passes above take the
   *earliest* speech run overlapping the range, so a breath before the sentence
   counts as its onset — inside the drift budget, so nothing flags it, and the
   cut opens on a breath with the words a second later. `trim_to_speech` looks
   only within the range, where there is nothing to wander into: moving the
   start later or the end earlier can only remove something already inside.
   It also drops a sound at either edge that is under 0.35s and followed by a
   pause more than twice its own length — a breath, a click, a chair. A short
   first word is followed by a pause about its own length, not several times
   it, so it survives.

The last one measures against the head and tail the beat is *meant* to have,
not against zero: a cut is supposed to open 0.05s before the first word and
hold 0.15s after the last. Only what is left over is silence nobody asked for,
and checkpoint 2 says how much it took from which beat.

## What actually gets cut

Two levels.

**Macro — only the best parts.** Whatever beats you choose from
`usingtranscript.txt` are located in the word timestamps; everything else is
discarded. A five-minute raw with three good lines yields those three lines.

**Micro — silence removal.** Inside each kept segment, pauses longer than
0.30s are cut out. This is driven by word timestamps, not `silencedetect`: the
transcript already says exactly when speech starts and stops, whereas audio
thresholding trips on breaths and room tone and needs tuning per recording.

Tune it with `--max-gap`, and **set `--max-gap 0` to disable silence removal**.
A long pause is not always dead air: a beat before a punchline is deliberate,
and cutting it flattens the delivery. The checkpoint warns when it removes a
pause of 0.8s or more.

A removed pause is collapsed to ~0.12s rather than to nothing.

Room around a sentence is **0.15s after** and **0.05s before**, settled by ear:
0.5 dragged, 0.2 was still loose. The final cut of the video gets **0.3s**:
everywhere else a tail is a beat between sentences, but at the very end it is
all that stands between the last consonant and black. Whisper's word-end
timestamps under-report, so a tail measured from them is shorter than it looks,
and the last range is set past the final word rather than relative to it.

The head is the riskier of the two. Word-*start* timestamps run late as often
as word-ends run short, and what the head buys is the attack of the first
consonant — so if a cut ever opens on a clipped plosive, raise `DEFAULT_HEAD`,
not the tail.

Cutting every pause makes delivery sound gabbled and strips the beats a
listener needs — the aim is tightening, not compression. Pieces shorter than
0.20s are dropped, since they read as a stutter at the join. The run reports how
much it removed.

**Filler words** are opt-in. Put one per line in `<project>/fillers.txt`:

```
öh
ehm
```

Per project, not global, and off by default: "typ" and "liksom" are filler in
one recording and load-bearing in the next, so the list is yours to curate.

## The on-screen hook

The hook holds for five seconds, white on a black bar at the top. It is the
last thing decided and the first thing seen, so it is matched against the
**finished cut** rather than the raw recording.

### It is matched, never written

There are two banks and they are not interchangeable:

- `pipeline/hooks/onscreen-hooks.md` — **on-screen** hooks, the text card on
  the frame, three to eight words. This is the one checkpoint 3 matches
  against.
- `pipeline/hooks/winning-hooks.md` — **verbal** hooks, the sentence spoken
  over the opening seconds. Chosen before the camera is on, at the idea stage.

Both are the complete, intentional set: nothing is added, removed or modified,
and nothing in this pipeline invents hook text. Match the tightest-fitting
source and change as few words as possible — usually one noun, with the
structure around it untouched. Carry the source's punctuation across; a
trailing `...` and QUOTED CAPS are what make a card read as a confession or an
overheard objection rather than a headline. Word-for-word is a normal outcome.

Both banks are prose, so there is nothing in them to score. Checkpoint 3 is a
judgement stage like the director: the bank goes to Claude and a shortlist
comes back, each option carrying the source it was matched from. An answer
quoting a source that is not in the bank is refused — that is "only these"
enforced rather than asserted.

If `claude` is not on PATH the gate still opens. Match one by hand from the
bank, put it in `<project>/hook.txt`, and pick it with `hook 0`.

### topic.txt

A recording can spend ninety seconds on a system without once naming the tools
it is built from, so the transcript alone is not enough to match against.
`<project>/topic.txt` says what the video is *about*, in plain prose; a blank
one is written for you the first time you reach the gate.

### Picking

```powershell
python pipeline\pipeline.py hooks --count 10 --project projects\ep01   # see more
python pipeline\pipeline.py hook 2 --project projects\ep01             # pick #2
python pipeline\pipeline.py hook 0 --project projects\ep01             # use hook.txt as written
```

Each option shows which bank hook it came from and how many words changed.
`approve` does **not** work at this gate — a choice between five hooks is not a
yes/no, so it asks for a number rather than guessing.

The pick is written to `<project>/hook.txt` (which is also the escape hatch for
a hook you wrote yourself, via `hook 0`), and the whole shortlist to
`<project>/hooks.txt`, so a rejected option can be recovered without a
regeneration that might rank differently.

## Overlays

`<project>/overlays.json` says what appears on screen and when. A cue names a
**phrase you say**, never a time:

```json
[
  {"kind": "emojiRow", "emoji": [
    {"emoji": "\u2702\ufe0f", "cue": "klipp"},
    {"emoji": "\U0001F3A5", "cue": "b-roll"}]},

  {"kind": "dualGraph", "until": "end", "series": [
    {"label": "K", "direction": "rising",  "colour": "green",
     "cue": "kvaliteten pa min content hojas"},
    {"label": "A", "direction": "falling", "colour": "lightBlue",
     "cue": "behova gora mycket mindre"}]}
]
```

The phrase is resolved against the cut transcript's word timestamps, so a sheet
written for one take survives a re-record, a re-cut and a reorder. Timestamps
would not: on this pipeline the edit moves every time it runs.

Kinds: `wordStack`, `emojiRow`, `image`, `chat`, `dualGraph`, `flash`,
`iconRow`, `terminal`, `clip`, `html`.

**`html`** is the escape hatch. The fixed kinds cover what recurs; this covers
what does not -- a diagram that only makes sense for one sentence of one video,
which is not worth a component and is worth having. Point `htmlFile` at a file
in the project's assets and it is inlined at cue-resolution time, so a missing
one is reported with the other assets rather than cancelling the render.

**B-roll needs no sheet entry at all.** Drop a clip in
`<project>/assets/broll/` named after the phrase it illustrates --
`hemsidor.mp4`, `motion-design.mp4` -- and it plays when that phrase is said.
Hyphens and underscores read as spaces. An explicit sheet entry for the same
phrase wins, so the convention is a default rather than a rule.

The split worth keeping in mind: interface and typography are better generated
(they re-render when the content changes, and sit correctly at 1080x1920).
Anything real -- an actual account, an actual product's UI -- is better
captured. A mockup of a real docs page is worse than the real docs page.
Timing keys are `hold` (seconds after the phrase ends, the default),
`until: "end"`, `until: "<another phrase>"` -- which leaves as that phrase
BEGINS, for handing the screen to what comes next -- or
`untilEndOf: "<a phrase>"`, which stays through it and leaves as it ends. Reach
for the second where the effect should be over by the time a sentence is:
naming the next sentence's first word ends it a fraction inside that sentence.

**Files** — `src` and `replyVideo` name a file in `<project>/assets/`. They are
staged into `broll/public` at render time; assets belong with the project, not
in a build directory.

**Nothing is guessed.** A cue whose phrase was not said, or whose file is not
there, is dropped and named at the checkpoint. Both used to be found on
playback, and a missing image failed the entire Remotion render several
thousand lines of stack trace deep.

## Order of operations

Grading runs **before** captions. A colour grade applied over the caption layer
would shift `flare` and `void`, and the brand colours would stop being the exact
values CYANVOID fixes.

Within cutting: fillers are dropped first, so the holes they leave are then seen
as pauses; tightening runs next; merging runs last, rejoining anything the two
split needlessly.

## Sentences

`sentences.py` groups words into sentences and classifies each one. Two failure
modes cover almost all of what a raw take contains:

| verdict | test |
| --- | --- |
| truncated | no terminal punctuation, or an ellipsis |
| superseded | a later sentence says nearly the same thing — a retake |

On a real recording this identified all five bloopers, and the survivors were
the sentences in the hand-made edit.

```powershell
python pipeline\sentences_report.py "clip.words.json"
```

prints the verdicts and emits a ready `edit-script.json` of explicit ranges.

A sentence is a unit of meaning, not of continuous sound: clamping exposes
discarded takes as silence *inside* the sentence that contains them, so a
sentence is split at gaps over `--max-gap`. The hook in that recording is one
sentence spanning 14.4s, of which 7 are false starts.

Only the final piece of a sentence gets the trailing room. A half-second break
mid-sentence is a hole, not a landing.

### When a sentence fragments

More than two pieces, or a piece under about a second, means the alignment
through that stretch is unreliable and the split is a guess. The report says
so and names the ranges. Export them and listen:

```powershell
python pipeline\preview.py "videos\clip.mp4" 0.18-14.42 22.8-30.92
```

Each range is written to `previews/` as its own file, so the question is
"which of these sounds right" rather than scrubbing for a boundary.

To find the boundary itself, ask the audio rather than the transcript:

```powershell
python pipeline\takes.py "videos\clip.mp4" 0.18-14.42 --expect 6
```

Where a line was recorded several times, Whisper's alignment smears across the
attempts and cannot say where one ends and the next begins. The audio can:
retakes are separated by the pause the speaker leaves before starting again.
`takes.py` reports the speech runs in a range and picks the **last one long
enough to hold the line** — last because a speaker who restarts does so
because the previous attempt failed, and long enough because a false start is
by definition shorter than the line it abandons.

It prints a ready `edit-script` entry. Confirm it with `preview.py` before
using it.

## Two cleanups before matching

Both distort the *timeline* rather than the text, so neither is visible in a
transcript you read.

**Swallowed audio.** Where speech exists that Whisper does not transcribe — a
false start it smooths away — the neighbouring word absorbs the time instead of
leaving a gap. In one real recording the word "short" spans **eight seconds**,
thirteen times a plausible length, with two discarded takes inside it. Silence
removal cannot see that: it looks for gaps between words, and there is no gap.

Words far longer than their length allows are trimmed back, keeping the end
(which the following word anchors). The swallowed time becomes an ordinary gap,
and silence removal cuts it like any other dead air. On that recording it took
the hook from 13.8s to 7.1s.

**Hallucinated hotwords.** Vocabulary biasing can backfire: the terms fed in as
a prompt get emitted as transcript text over audio the model cannot read,
arriving as a run of words at probability 0.00. Words below a 0.05 confidence
floor are dropped — the weakest genuine word in that recording scores 0.37, so
the floor is nowhere near real speech.

Both are reported when they fire.

## How lines are matched

`cutlist.py` maps each script line back onto word timestamps. The edit prompt
requires exact words from the transcript, so matching is usually exact — but
punctuation, casing and the odd dropped filler make a strict string comparison
too brittle. So matching runs on normalised tokens, tries an exact run first,
then falls back to the best-scoring window, and **reports its confidence**. A
line below the similarity floor is reported as a miss rather than cut wrongly.

Swedish letters are preserved during normalisation — only case and punctuation
are dropped, since "formulär" and "formular" are different words.

Segments are emitted in **script order, not source order**, because the edit
deliberately moves the landing line to the end. Segments contiguous in the
source are merged, including where padding makes them overlap — cutting those
separately would duplicate a sliver of speech at the seam.

## Padding

Each segment is padded slightly so a cut does not clip the attack of the first
word or the tail of the last. That padding is **clamped to the neighbouring
words**: it captures the silence around a phrase and never reaches into
adjacent speech.

Without the clamp, padding alone reinstates words the script deliberately
dropped. On a fast stumble ("...göra *mer. Och* mycket mindre...") 0.12s of
tail padding reaches into the next word and 0.08s of head padding reaches back
into the one before, so the excluded speech ends up in the cut even when the
segments correctly stay split.

## Cutting

`ffmpeg_ops.py` uses a `trim`/`concat` filter graph in a single pass. That is
frame-accurate at arbitrary cut points; stream copy would snap each cut to the
nearest keyframe and drift by up to a GOP.

## Grading

The default is a restrained lift for talking-head footage — slight contrast,
mild saturation, a small cool bias that sits with the Cyan Void palette rather
than fighting it. No LUT, so there is nothing to ship or version.

For a real look, drop a `.cube` in and pass it as `Grade(lut=...)`; it is applied
last, so it grades the corrected image rather than the raw one. See the
`ffmpeg-color-grading-chromakey` skill in `.claude/skills/` for filter recipes.

## Captions

The caption step runs Remotion's `CaptionedVideo` composition, which layers the
graded video under word-level captions. Both inputs are copied into
`broll/public` because `staticFile` cannot reach outside it, and props are
passed via a **file** rather than an inline JSON argument — a JSON string on the
command line is mangled by Windows PowerShell's native-argument quoting.

The composition caps its length at the video's real duration. Taking length from
the transcript alone means a stale or mis-offset transcript ends the clip in
black; the footage is the ground truth.

Captions get a `slab` panel behind them by default. Over busy footage `bone`
alone loses legibility, and CYANVOID rules out the usual fixes — no drop shadow,
no glow, no outline. A solid slab is a surface sitting on the ground, which the
system already allows. Pass `backdrop: false` for clean footage.

If Remotion cannot fetch its own Chrome, set `REMOTION_BROWSER_EXECUTABLE` to a
Chromium binary and the pipeline passes it through.

## Checking the layout in pixels

```powershell
python pipeline\verify.py --project projects\ep01
python pipeline\verify.py --project projects\ep01 --at 3.2 --at 11.7
```

Two placement bugs got through code review, typechecking and the whole test
suite: a chat window that grew as messages arrived until it sat in the caption
band, and a row pinned to the top of frame that centred itself instead, because
a flex row takes its vertical alignment from `alignItems` and the pin was on
`justifyContent`. Both were invisible in the source and obvious in the pixels.

So `verify.py` renders the overlay layer over a flat magenta ground — magenta
because black is a legitimate fill, and a ground the design might genuinely
paint cannot be told from one it did not — and measures the bounding box of
everything that is not that colour against the safe zone read from `tokens.ts`.
It samples the midpoint of every cue and the moment just after each child of
one lands, so a chip is measured once it has actually arrived. Frames that
measure clean are deleted; a frame that breached is the only evidence of what
went wrong, so it stays.

Exit codes: `0` clean, `1` something drew outside the safe zone, `2` nothing
rendered or a sampled frame failed to render. The last case matters — a frame
that never rendered was never checked, and used to be skipped silently while
the run reported that every sampled frame passed. The usual cause is a frame
past the end of the composition, which means the props and the footage disagree
about how long the video is.

It runs `broll/node_modules/.bin/remotion`, never `npx`: on Windows npx is
`npx.cmd`, which `subprocess` cannot resolve without a shell. That path is
`remotion_ops.command()`, used by the render step too, so there is one spelling
of it.

## Tests

```powershell
pip install pytest
python -m pytest pipeline -q
```

399 tests: token normalisation, exact and approximate matching, script-order
preservation, miss reporting, padding and merge behaviour, silence and filler
removal, speech-edge measurement, cue resolution, hook matching, blooper
detection, safe-zone measurement, that grading precedes captions, and that each
gate actually blocks.
