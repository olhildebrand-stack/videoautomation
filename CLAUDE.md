# videoautomation

Cyan Void b-roll, rendered with Remotion. See `broll/README.md` for the project.

## Working agreement

**Do it, don't instruct it.** Anything that can be done in the session is done
without asking: writing code, installing dependencies, running tests, rendering,
committing, and pushing to `main`. Do not hand the user a list of commands to run
when the work can be carried out directly, and do not ask permission for the
routine parts of a task the user has already asked for.

**Always say explicitly what is left for the user, and where.** The user works on
Windows; the agent session runs in an ephemeral Linux container that cannot reach
that machine. So a handful of steps genuinely can only happen on their side:

- installing or running anything on the Windows machine (`winget`, local `npm`,
  local `python`, GPU drivers)
- anything needing the RTX 3070 — there is no GPU in the session
- opening a local URL such as the Remotion studio on `localhost`

When a step falls into that set, say so plainly, give the exact directory and the
exact command, and say what the expected output is. Never leave the user to infer
that something is their job.

**Collapse those steps to as few as possible.** `setup.ps1` at the repo root is a
one-command, re-runnable setup for both halves of the project. Prefer extending it
over adding new manual instructions to a README.

**Network limits in the session** (report them rather than working around):
`huggingface.co` and `remotion.media` are blocked by the egress policy, so model
weights and Remotion's Chrome download are unavailable here. Renders in-session
use `--browser-executable=/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell`.

## The editorial brain is a stage, not a chat

`python pipeline\pipeline.py direct --project <project>` hands the transcript to
Claude with `pipeline/DIRECTOR.md` and turns what comes back into an edit script
and an overlay sheet, checked before either is written. That is the only part of
the pipeline that needs judgement, and it now accumulates:

- **Corrections go in `pipeline/DIRECTOR.md`**, under *Learned rules*, written
  as what to do instead. Not in a chat reply, not in this file. A rule there
  applies to every future video; a rule in a chat applies to none.
- `python pipeline\director.py --project <project> --learn` says what the
  operator changed after the director decided. A difference that will recur is
  a rule that has not been written yet.
- The rules are prose for a reader, not a config. Say what went wrong and what
  to do instead, and keep the entry that made it necessary.

## The motion-design skill is guidance, and nothing overrules it

`.claude/skills/motion-design/` is the LottieFiles motion-design skill, vendored
from `github.com/lottiefiles/motion-design-skill` @ `f9a8a04` (MIT). Follow it.

It used to be overruled by `CYANVOID.md` on colour, easing, overshoot and what
may appear on screen. **Those brand limits were removed** -- the vocabulary this
project actually needs is green and red graph lines, emoji, screenshots, chat
mockups and logos, all of which CYANVOID forbade outright. `CYANVOID.md` is kept
as history. It does not govern anything, and no design question should be
answered by quoting it.

What survived that decision is the token rule below, which is not brand policing:
it is what makes one video look like the last one.

The parts of the skill worth naming, because the components are built to them:

- **Stagger budget.** Total stagger under 500ms. `beatInFrames` is derived from
  this.
- **The 1/3 rule (elements).** With three or more elements, at most one third
  may be in active motion at once -- which is why `beatInFrames` equals the
  enter duration: each element settles as the next starts.
- **The 8-step checklist and decision framework** for planning a new clip, and
  its **narrative structure** -- setup, action, resolution within a clip.

The durations and the easing curve in `tokens.ts` are this project's, arrived at
by watching renders. They are defaults to design with, not laws to cite.

## The formats bank

`pipeline/formats/bank.json` holds every slide format that exists. A sequence
picks one by name; nothing writes a new layout. It is the hooks bank's rule
applied to design, and for the same reason: a format that has been rendered,
looked at and corrected beats a better idea nobody has seen.

`python pipeline\formats.py` says what each one is and when to reach for it.
`--check` fails if the bank has drifted from `slideFormat` in `tokens.ts` or
from the samples in `stories/formats/`. Growing the bank means building the
format, rendering one, and adding the entry -- in that order.

## The token rule

`broll/src/tokens.ts` is the only file allowed to contain a raw hex value, a raw
duration, or the easing curve. `npm run lint:tokens` enforces it. Run
`npm run check` (typecheck + guard) before committing.

## Working style

### Simplicity first
- Write the minimum code that solves the stated problem.
- No features, options, or config that weren't asked for.
- No abstractions for something used once.
- No error handling for cases that can't occur.
- If the solution runs long and could be a third the size, rewrite it before showing me.

### Surgical changes
- Change only what the request requires. Every changed line should trace back to it.
- Don't reformat, rename, or "improve" nearby code.
- Match the existing style even if you'd write it differently.
- If you spot unrelated dead code, mention it — don't remove it.
- Do remove imports or variables that your own change orphaned.

### Verify, don't assume
- Turn the task into a concrete success check before starting: what should be true when it's done.
- For anything multi-step, give me a short numbered plan with a check per step.
- Then run the checks yourself and loop until they pass, instead of handing me something untested.
