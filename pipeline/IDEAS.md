# Directing the idea

The stage before the director. It turns "I want to post something" into the
thing `pipeline.py` already knows how to consume: a topic, a hook matched from
the swipe file, and a beat outline in the director's own vocabulary.

It is not a separate product. The editing pipeline has a front end missing,
and this is it — which is why it lives here, beside the banks it has to read,
rather than in a repository of its own.

## What it outputs

Whatever it produces has to land as something the next stage takes without
translation:

| file | what it is | who reads it |
| --- | --- | --- |
| `topic.txt` | what the video is about, in a sentence or two | `brief.py`, then the director |
| a hook | the tightest fit from `pipeline/hooks/winning-hooks.md` | checkpoint 3 |
| a beat outline | `HOOK`, `PROBLEM`, …, `LANDING` — names, not timings | the operator, when recording |

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

**Hooks come from the swipe file.** `pipeline/hooks/winning-hooks.md` holds
1050+ proven hooks and is the complete, intentional set — only those. All of
them have equal weight, so match against any category; take the
tightest-fitting hook and change as few words as possible. Never write one,
and never add to, remove from, or modify the file. If nothing in it fits, say
so — do not quietly invent a hook and present it as matched.

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

*(Nothing yet. The first correction goes here.)*
