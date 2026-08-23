# broll

Short Cyan Void b-roll clips, rendered with [Remotion](https://remotion.dev).

## The one rule

`src/tokens.ts` is the only file allowed to contain a raw hex value, a raw
duration, or the easing curve. Everything else imports from it.

That is enforced mechanically, not by convention:

```bash
npm run lint:tokens   # fails on any raw #hex, 000ms, cubic-bezier(), rgb()
npm run typecheck     # tsc --strict
npm run check         # both
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

All three are 1920×1080 at 30fps, three seconds long — change `dimensions`,
`fps`, and `clipDurationInFrames` in `src/tokens.ts` to retarget every
composition at once (1080×1920 for vertical).

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

## Two values that are not from CYANVOID.md

The spec fixes how long a transition takes, but not how long to wait between
beats or how long a landed state holds before the cut. Those are editorial, so
they live in a separately labelled block in `src/tokens.ts` as `beatInFrames`
and `holdInFrames`. They are gaps between beats, never transition durations —
the brand tempo is untouched.
