# What the Claude-editing tutorial does, against what we do

Notes from the 28-minute walkthrough in `claude-editing-tutorial.txt`.

His stack: Claude Code as orchestrator, **video-use** for trimming, and
**hyperframes** for motion graphics (HTML-based, with a timeline GUI).
Remotion is the alternative he passed over — video-use ships a Remotion skill
and he prefers hyperframes' look.

## Where he arrived at the same answer we did

**Anchor words.** He describes the beat timeline as "what word is the anchor —
what word is going to trigger the scene to start". That is our cue sheet,
independently arrived at. Strong signal the phrase-anchored model is right and
not a quirk of how we got here.

**Word-boundary snapping with a lead.** His tool offers to "snap to word
boundaries with 50 millisecond leads". Our `DEFAULT_HEAD` is 0.05s and our
cut points clamp to word boundaries. Same problem, same shape of answer.

**Trim first, animate second.** He is explicit that the transcript with
per-word timestamps has to exist before any animation is placed. Our pipeline
re-transcribes the cut for exactly this reason.

## Where we are ahead

**We measure cut points from the audio; he measures them from the transcript.**
He switched transcription provider — to ElevenLabs, because he finds it "better
at finding the right moments to cut". That is treating a timestamp-accuracy
problem by shopping for better timestamps. We hit the same wall (a cut landing
inside "video", leaving "vi") and fixed it with `edges.py`: `silencedetect`
against the audio, which does not care which model produced the transcript. Our
fix survives a provider change; his is a provider change.

**Blooper detection is deterministic here.** `sentences.py` classifies
truncated and superseded takes by rule. His runs through Claude on every video,
which costs tokens and can decide differently on the same input twice.

**A cue sheet is a file; his direction is a conversation.** Re-cut the video and
our sheet still lands, because it names phrases. His beats are re-described.

**The token rule is enforced, not advised.** He recommends a per-video-type
"design philosophy markdown" so a style repeats. Good instinct, but a document
nothing checks drifts. `npm run lint:tokens` fails the build.

## Where he is ahead, and what is worth taking

**Screenshot verification — take this.** He tells Claude to screenshot the
scene and check it, because "sometimes it'll come back and say I've done this
but it doesn't look good at all". This is exactly what has been happening by
hand all session: rendering a still, measuring bright pixel rows, catching the
chat window sitting in the caption band and the flex row centring itself. Doing
it by hand means it happens when someone remembers. It should be a stage.

**Plan before build.** He reviews a beat plan — anchor word, timing, contents —
and revises before anything renders. Our checkpoint 2 shows a cut list, but
nothing shows the *overlay* plan before the render. The cue report at the
caption stage is close; it just arrives after the decision rather than before.

**Taste calls.** His tool asks targeted questions: a trailing "so" at 42:20 --
natural breath, or cut? Our checkpoints present data and leave the operator to
notice. Asking the specific question is better.

**A timeline GUI** for nudging beats. Genuinely useful, and a large build. Our
phrase anchoring means timing is derived rather than hand-set, which removes
most of the need — but not the wish to see it.

## Costs

He reports ~238,000 tokens for one video, and says the fix is being specific up
front so it does not explore wrong paths. Our per-video token cost is close to
zero: the pipeline is code, and Claude is only involved in choosing beats.
