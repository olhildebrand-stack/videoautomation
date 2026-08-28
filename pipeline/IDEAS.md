# Directing the idea

The stage before the director. It turns "I want to post something" into the
thing `pipeline.py` already knows how to consume: a topic, a hook matched from
the swipe file, and a beat outline in the director's own vocabulary.

It is not a separate product. The editing pipeline has a front end missing,
and this is it — which is why it lives here, beside the banks it has to read,
rather than in a repository of its own.

## What it outputs

Two files per idea, both tracked, both outliving the `projects/` directory
they get copied into — which is gitignored, and is where a good topic file
used to go to die.

| file | what it is | who reads it |
| --- | --- | --- |
| `topics/<name>.txt` | what the video is about, in plain prose | `hookgen.py`, then the director |
| `outlines/<name>.md` | `needs`, a format, both hooks, and the beats | the operator, at the camera |

The outline's header is the part that decides whether the idea gets made:
`needs` is the honest list of what has to be filmed or captured, `format` is a
name from the formats bank or `-` for a talking head, and the two hooks are
matched text — `verbal` from `hooks/winning-hooks.md`, the sentence spoken over
the opening seconds, and `onscreen` from `hooks/onscreen-hooks.md`, the three-
to-eight-word card on the frame. Both carry the `from:` line naming the source
they were matched from, because that line is what makes "matched, not written"
checkable.

The verbal hook belongs here rather than at checkpoint 3, and that is the
point of deciding it now: it is the first thing said on camera, so it has to
be known before the camera is on. Checkpoint 3 picks the on-screen card
against the finished cut, which is why `onscreen` here is a first choice
rather than the final one.

```
python pipeline\idea.py new   <name>    a blank topic and a blank outline
python pipeline\idea.py check <name>    every rule below, enforced
```

`check` is the part that makes the rules below real rather than written down.
It fails on an unanswered `BRAND.md`, a hook with no source line, a source
that does not appear in its bank **verbatim** — the same check `hookgen.py`
makes, and the one that catches an invented hook presented as a match — a
format not in the formats bank, an outline that does not run `HOOK` →
`LANDING`, an empty beat, an idea that does not say what it needs filmed, and
any timing written into a beat name or the header. It says nothing about
whether the hook is a *good* match: that is judgement, and it is what the
conversation in this file is for.

The beat outline is the point of the whole stage. An idea written as prose has
to be reverse-engineered into beats by whoever records it, and that is where
a good idea turns into a rambling take with four false starts. Written as
beats, the recording is a list of things to say once each.

**It never writes timings.** Same rule as the director: the pipeline measures
time from the audio. An outline that says "10 seconds on the problem" is
guessing at a number the machine will overrule.

## The two ways in

**"This is the idea I have."** The idea is fixed; the work is shaping it. Find
the beats, match a hook, say what has to be on screen, say what has to be
filmed. Push back only where the idea cannot survive the format — a claim
with no evidence, a story that needs four photographs the operator does not
have.

**"Give me some ideas."** Produce several, grounded in what the operator
actually does and has. An idea nobody can film is not an idea. Every one has
to name what it needs — talking head only, a screen recording, a screenshot,
a photograph — because that is what decides whether it gets made this week or
never.

## The rules it inherits

These are not restated here because they are enforced elsewhere. They bind
this stage anyway.

**Hooks come from the banks, and there are two.**
`pipeline/hooks/winning-hooks.md` is 1050+ proven *verbal* hooks — the spoken
opening sentence. `pipeline/hooks/onscreen-hooks.md` is the *on-screen* hook,
the three-to-eight-word text card. An idea needs both, and one will not do the
other's job. Match the tightest-fitting source in the right bank and change as
few words as possible — usually one noun. Never write one, and never add to,
remove from, or modify either file. If nothing fits, say so — do not quietly
invent a hook and present it as matched.

**A story picks a format from the bank first.** `pipeline/formats/bank.json`,
and `CLAUDE.md` says to offer the formats before asking what the story is
about. The format decides how many photographs the operator has to go and
take, which is the expensive part. An idea for a story is not finished until
a format is chosen.

**A video is 23–70 seconds.** `DIRECTOR.md` has the reasoning. An idea that
needs two minutes is either two ideas or one that has not been cut yet.

## Before it produces anything

`ideas/BRAND.md` has to be filled in. Until it is, everything this stage
produces is a guess about somebody generic, and generic is the one thing that
reliably does not get watched.

Fill it by asking — once, in a conversation, not as a form. The questions are
in the file. They are deliberately things the operator already knows the
answer to: what they do, who it is for, what they can show. Nothing that asks
them to invent a strategy or name an angle, because that is the output of this
stage, not its input.

## Where the material goes

`ideas/sources/` holds what the operator feeds in — swipe files, transcripts
of reels that worked, notes on what a niche responds to, anything. Read it,
and turn what recurs into a rule below rather than re-reading it every time.

## Learned rules

Corrections go here, written as what to do instead. A rule here applies to
every future idea; a rule in a chat applies to none. Keep the case that made
each one necessary — a rule without its reason gets argued with later.

- **2026-08-28 — a hook is never an announcement about the operator.** The
  reel that died opened *"Jag fick nyss en till referens..."* — I just got
  another referral. It held 4 seconds of 19 (21%) against 54% for the reel
  that worked, and its 9x deficit in reach followed from that: the platform
  distributes what holds people, so the video was dead before its content was
  judged. Neither bank contains a source that announces the speaker's own good
  news, and the nearest thing, *"I just uninstalled OpenClaw"*, is an action
  with a reveal rather than a status update. A hook is about something in the
  world with stakes in it. What happened to the operator this week is not a
  hook, however good the week was.

- **2026-08-28 — a video with nothing on screen has to carry a claim the
  audience does not already believe.** Talking head alone is legitimate —
  three of the ten reference reels are exactly that — but it spends the whole
  video on the claim, so the claim has to be worth it. The reel that died
  paired no artifact with *referrals are the warmest customers*, which every
  business owner it was aimed at already believed. The reel that worked paired
  a system on screen with a claim that had a victim in it. Before proposing a
  talking-head idea, say what the viewer believes now and what they believe
  after. If those are the same sentence, the idea needs an artifact or it
  needs a better claim.

- **2026-08-28 — one road per video.** `ideas/BRAND.md` answer 3 wants one
  thought: *I want to hire this guy*. Three roads reach it — he can build,
  that would work in my business, I need to move on this — and all three are
  wanted across the account. In a single video they compete: proving
  competence, sparking application and creating urgency need different beats,
  different evidence and different landings. Pick the road in the outline and
  let the other two go. A video that takes all three arrives nowhere.

- **2026-08-28 — grade a posted video on retention, and read the drop.**
  `performance.json` is where the numbers go and `python pipeline\perf.py`
  prints them beside the beats each video was made of; `--check` names any
  video the pipeline edited whose numbers were never kept.
  Views are the last thing to look at, not the first: they are downstream of
  how long the video held people. Where the drop happens says which half
  failed — inside the first few seconds it is the hook, later it is the body —
  and those are different fixes. Answer 5 of `BRAND.md` is where what gets
  learned goes, so record watch time against length, not just views, and say
  which half you think died. n is currently 2, which is why every rule above
  is a hypothesis worth re-testing rather than a law.

- **2026-08-28 — the on-screen bank is two people's niches, and only two of
  the five are the operator's.** `hooks/onscreen-hooks.md` came from the
  operator's mentor's dashboard and its 45 examples are grouped under five
  headings. **2. websites / offer**, **3. AI cold-calling / remodeler leads**
  and **5. websites / remodelers** are the mentor's — a client-services
  business the operator is not in. **1. video editing / Claude** and **4. the
  Claude workflow itself** are subjects the operator has built content around,
  and they are not the niche either: `ideas/BRAND.md` answer 1 says the niche
  is custom AI systems for Swedish businesses, and the editing pipeline is a
  demonstration of that rather than the thing being sold.

  This session read the five headings as one account's range and reported back
  that three fifths of the channel was remodeler lead-gen, then corrected to
  the other two headings and was wrong again. Both errors run the same
  direction: an idea stage that takes its subject from the bank writes for
  whoever the bank's examples were written for.

  So: the bank is for *matching structures*, never for inferring who is
  watching. A hook source proves a shape worked, not that its subject is the
  operator's subject — which is the whole reason the same source gets reused
  across five niches in that file. Take the audience from `ideas/BRAND.md` and
  nowhere else.
