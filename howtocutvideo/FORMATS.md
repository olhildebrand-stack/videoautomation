# Formats, read off the references

Every file in `imagereferences/` and `backgroundreferences/`, grouped by what
it actually is rather than by filename. Six formats, not one. Each entry says
what is on screen, what makes it work, and which files it came from -- so a new
sequence can be built from a named format instead of from memory.

The rule that runs through all of them: **one format per sequence, one
background per sequence.** Mixing them inside a set is what makes a set look
like separate posts.

---

## A. Textured card

`over.jpg`, `over(1)`, `over(3)`, `over(5)`, `over(6)` — 4:5

Dark textured ground, the mark centred at the top, an accent pill naming the
section, a bold headline, two or three lines of body with exactly one clause in
the accent colour, then a light screenshot card filling the lower half. Handle
bottom-left, arrow bottom-right.

**Why it works.** The card is the proof and the text is the claim, always in
that order, always in the same place. Six slides of it read as one document.

**Variants worth keeping.** `over(3)` sets the body as two bullets instead of a
paragraph, and puts the screenshot inside a phone mockup rather than a flat
card — the phone is right when the thing being shown is itself a phone screen.

## B. Photo cover, heavy scrim

`over(2)`, `over(4)`, `send it(5)` — 4:5

The creator's own photo full-bleed, darkened, with the claim set large over the
upper third. No card, no pill. Usually the first or last slide of a set.

**Variants.** `over(4)` is a before/after: an italic line, then a huge
accent-coloured number, then a parenthetical, then two floating UI cards with
hand-drawn circles and a JANUARY → July arrow between them. That drawn-on
quality is doing a lot of work — it reads as annotated rather than designed.

## C. Blurred own photo as ground

`send it.jpg`, `send it(1)`, `(2)`, `(3)`, `(4)` — 4:5

**The same cover photo, blurred and darkened, behind every slide in the set.**
A light UI card floats in the upper half; below it a large ghosted step number
(`01/`, `02/`) sits behind the headline; body copy in a lighter weight under
that. Page dots at the bottom, simulated `<` `>` arrows at the sides.

**Why it works.** No texture asset needed and the set is unmistakably one piece,
because the ground is literally the same photograph the cover used. The blur
means it never competes with the card.

**This is the one to reach for when the student has a good photo and no brand
assets** — which is most students.

## D. Story labels

`1787344402523`, `1787344487860` — 9:16

A real Instagram story: photo full-bleed, and every line of text in a **black
rounded label box**, stacked and left-aligned, exactly as the app's own text
tool draws them. Sometimes a second box lower down, positioned to point at
something in the photo.

**Why it works.** It looks like it was typed in the app, not made in a design
tool, which on stories is the point. Nothing to design and nothing to get
wrong.

## E. Proof collage

`1787407646408`, `558420468`, `639735492`, `639800251`, `701537468` — 9:16

Screenshots of DMs, dashboards or chats scattered at slight angles over a
darkened photo of the creator, with white rounded caption boxes at the bottom
carrying black text.

**Variants.** `701537468` puts green highlight chips over the numbers inside the
screenshots. `639735492` masks the collage behind an irregular black blob rather
than aligning it. `1787407646408` uses a single WhatsApp thread instead of a
collage, with the caption boxes reading as a caption under it.

**Why it works.** The screenshots are evidence, and scattering them says
"there's more where this came from" in a way a neat grid does not.

## F. Video with a text stack

all five `comment BDP` mp4s — 4:5, moving. A frame is lifted out of each as
`bdp-frame-0..4.jpg` beside them, since the layout is what matters and these
are only videos because they had music on them.

A dim, warm-lit moving background — the creator walking, a room, a bar — with a
left-aligned text block over it: a bold headline where one or two words carry
the accent colour, then a small list or a few short lines, then a payoff line.
White text with a soft shadow, no boxes at all.

**Variants.** The first is a single huge accent number as the hero
(`$53 000`) with two small lines under it. The others are dense: a heading, a
five-item list, a total, and a closing line — far more text than a still slide
would carry, which works because the reader has the whole clip to read it.

**Why it works.** The background moves so it holds attention while the eye
reads; the text never moves, so it stays readable.

---

## Backgrounds

Use one per sequence, never mixed.

| File | What it is | Use it for |
| --- | --- | --- |
| `7710b61a…jpg` | Near-black woven linen, almost flat | The quietest ground. When the screenshots are busy |
| `Freebie-…-02.webp` | Dark grunge concrete, soft and even | The default. Texture you feel rather than see |
| `Freebie-…-03.webp` | Dark grunge, lighter mottling top-left | Closest to the reference set's own paper. Most character |
| `SL-072622…jpg` | Black with a thin grey grid | Technical subjects. Reads as a blueprint or a plan |

A background is optional. Formats B, C, D and E have none — the photograph is
the ground. Only A wants one.

---

## What is built

Seven formats, each named in `broll/src/tokens.ts` under `slideFormat` and
rendered by `broll/src/compositions/Slide.tsx`. A format is chosen once per
sequence in the folder's `slides.json`, never per slide.

| `format` | from | what it is |
| --- | --- | --- |
| `textured` | A | centred, terracotta pill, card, texture ground |
| `blurred` | C | the cover photo blurred behind the set, step numbers, dots |
| `labels` | D | the photo untouched, small text in the app's black boxes |
| `stack` | F | a weight ladder over a dim photo, no boxes at all |
| `titled` | C's cover | a sharp photo and a four-cut title ladder over angled cards |
| `beforeafter` | B's `over(4)` | a huge accent number, two cards, a long arrow between the dates |
| `collage` | E's `639735492` | screenshots scattered over the photo, white caption boxes |

One of each is rendered into `stories/formats/out/`, built from the sources in
`stories/formats/<name>/`.

**What the words in the references say is not part of the format.** They are
someone else's captions. Only the layout, the type and the colour carry over.
