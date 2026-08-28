# Directing the idea

The stage before the director. It turns "I want to post something" into the
thing `pipeline.py` already knows how to consume: a topic, a hook picked from
the bank by number, and a beat outline in the director's own vocabulary.

It is not a separate product. The editing pipeline has a front end missing,
and this is it — which is why it lives here, beside the banks it has to read,
rather than in a repository of its own.

## What it outputs

Two files per idea, both tracked, both outliving the `projects/` directory
they get copied into — which is gitignored, and is where a good topic file
used to go to die.

| file | what it is | who reads it |
| --- | --- | --- |
| `topics/<name>.txt` | what the video is about. `--topic` already reads it | `hookgen.py`, then the director |
| `outlines/<name>.md` | `needs`, a format, a hook **number**, and the beats | the operator, at the camera |

The outline's header is the part that decides whether the idea gets made:
`needs` is the honest list of what has to be filmed or captured, `format` is a
name from the formats bank or `-` for a talking head, and `hook` is a number
from the hooks bank — never hook text.

```
python pipeline\idea.py new   <name>    a blank topic and a blank outline
python pipeline\idea.py hooks <name>    rank the bank against the topic
python pipeline\idea.py check <name>    every rule below, enforced
```

`hooks` is the same matcher checkpoint 3 uses, run with no transcript, because
at idea time there is no recording. The topic file alone is enough to rank
against — and a subject the bank holds no hook for is worth discovering before
the shoot rather than after it, which is the only reason to match this early.

`check` is the part that makes the rules below real rather than written down.
It fails on an unanswered `BRAND.md`, a hook that is text instead of a number,
a hook number the bank does not contain, a format not in the formats bank, an
outline that does not run `HOOK` → `LANDING`, an empty beat, an idea that does
not say what it needs filmed, and any timing written into a beat name or the
header. It says nothing about what the beats *say* — that is judgement, and it
is what the conversation in this file is for.

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

**Hooks come from the bank.** `pipeline/hooks/bank.json` holds hooks that
won. Match one, never write one, and change no more than three words. If
nothing in the bank fits, say so and offer to grow the bank — do not quietly
invent a hook and present it as matched. `hookgen.py` already does the
matching against a topic; call it rather than re-implementing it.

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
