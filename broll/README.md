# broll

Short Cyan Void b-roll clips, rendered with [Remotion](https://remotion.dev).

## The one rule

`src/tokens.ts` is the only file allowed to contain a raw hex value, a raw
duration, or the easing curve. Everything else imports from it.

That is enforced mechanically, not by convention:

```bash
npm run lint:tokens   # fails on any raw #hex, 000ms, cubic-bezier(), rgb()
npm run typecheck     # tsc --strict
npm test              # caption chunking logic
npm run check         # all three
```

The type system carries the rest: `Mono` only accepts the 11–12px sizes the
spec permits, `tone` only accepts the six colour tokens, and `radiusMsg` is
imported by exactly one component.

## Run

```bash
npm install
npm start     # Remotion Studio on http://localhost:3000
```

## Render

```bash
npx remotion render Conversation out/Conversation.mp4
npx remotion still  TitleCard    out/TitleCard.png --frame=45
```

## Compositions

| Id | What it is |
| --- | --- |
| `TitleCard` | Kicker, hairline, display headline. Three staggered beats. |
| `Conversation` | Message rows; the last one lands on the flare inversion. |
| `StatBlock` | Divided columns, numerals in the mono layer. |
| `Captions` | Word-level captions from a `transcribe/` JSON. |

### Captions

Drop a `.words.json` produced by `transcribe/` into
`broll/public/transcripts/`, then point `TRANSCRIPT` in `src/Root.tsx` at it.
The composition reads its own length from the transcript, so the clip is
exactly as long as the speech.

The spoken word takes the one gesture — a solid `flare` fill with the text
knocked out in `void`. That is already CYANVOID's whole vocabulary for
"active", so caption highlighting invents no new idiom.

`src/captions/chunk.ts` groups words into lines, breaking on a sentence
ending, then a silence over `gapSeconds`, then the word and character
ceilings. The defaults (3 words / 18 chars) are tuned for 1080-wide vertical
at the `3xl` step: the ceiling counts characters but what overflows is
rendered width, so it is set low enough that a line never wraps and strands a
single word on a second row.

`offsetSeconds` shifts the transcript against the video if they drift.

### Safe zone

Instagram and TikTok draw their own furniture over the frame — header and
status bar along the top, caption, handle and action rail along the bottom and
right. `safeZone` in `tokens.ts` keeps both the captions and the hook clear of
it: 220px top, 450px bottom, 100px each side at 1080×1920.

Values are the cautious end of each published range. Being 30px too careful
costs nothing; being 30px too bold puts a word behind a Follow button.

All three are **1080×1920 vertical** at 30fps, three seconds long — change
`dimensions`, `fps`, and `clipDurationInFrames` in `src/tokens.ts` to retarget
every composition at once.

## Structure

```
src/tokens.ts        every brand value, and nothing else has any
src/motion.ts        the one easing curve; fadeIn / fadeOut / stateChange
src/fonts.ts         the four families, self-hosted from public/fonts
src/components/      Frame, Text (Display/UI/Mono/Body/Inverted), Divider, MessageRow
src/compositions/    the clips
scripts/check-tokens.mjs   the guard
```

## Fonts

The four families are self-hosted in `public/fonts` — one weight each, latin
subset. Renders are deterministic and work offline; they never depend on a CDN
round-trip or fall back to a system face mid-frame. To refresh them, re-download
the woff2 for the weight named in `src/tokens.ts` (`font.<role>.fontWeight`).

## Where this departs from CYANVOID.md, and why

Three additions live in a separately labelled block in `src/tokens.ts`. The
colours, the four font roles, the scale ratios, the radius rule, the 8px grid,
the easing curve, and the tempos are all untouched.

**`videoScale = 2`.** The spec's type scale is sized for a 1440×900 surface read
at desk distance. A 1080×1920 clip is watched on a phone about 390pt wide — a
2.77× downscale that puts the 12px mono layer at roughly 4pt and body text at
7pt on the actual device. Unreadable. The scale is therefore multiplied by one
uniform factor, preserving every ratio exactly; `fontSizeSpec` keeps the literal
spec values alongside it. Set `videoScale` to 1 for pixel-exact spec sizes on a
desktop-sized surface.

**`beatInFrames` / `holdInFrames`.** The spec fixes how long a transition takes,
but not how long to wait between beats or how long a landed state holds before
the cut. These are gaps between beats, never transition durations — the brand
tempo is untouched.

**`displayLineHeight`.** CYANVOID fixes line-height for body text only. At 1080
wide a headline wraps, so the display face needs a defined one.

## Vertical sizing note

At 1080 wide, a single long word sets the ceiling for the display face: `4xl`
overruns the frame padding on anything longer than about nine characters, so
`TitleCard` defaults to `3xl` and takes a `size` prop for short headlines.
`StatBlock` stacks its rows rather than placing them side by side — read
top-to-bottom they scan with the frame, and each value gets the full column
width instead of a third of it.
