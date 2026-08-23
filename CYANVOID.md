# Cyan Void — non-negotiables

Paste this block at the top of any prompt that generates a design, a frame, or
a motion sequence. Everything below is a hard constraint, not a preference.

---

## Colours — exact hex, no substitutions

| Token | Hex | Use |
| --- | --- | --- |
| `--void` | `#060607` | Ground. Every frame starts here. |
| `--slab` | `#101012` | Surfaces and panels sitting on the ground. |
| `--seam` | `#1E1E21` | Every 1px border and divider. |
| `--ash` | `#5E7B86` | Labels, metadata, timestamps. Non-essential text only. |
| `--bone` | `#A6D2E2` | Body text and ordinary content. |
| `--flare` | `#DAF5FF` | Headlines, emphasis, and the inverted fill. |

`--accent` is an alias of `--flare`. There is no second accent colour anywhere
in the system.

**Hierarchy is brightness, never hue.** `flare` reads first, `bone` second,
`ash` recedes. Never signal importance with a colour change — only with a
position on that ladder.

`--ash` deliberately fails contrast for body text. It is for labels only. Do
not promote it.

## Fonts — four roles, no others

| Role | Face | Treatment |
| --- | --- | --- |
| Display | **Allerta Stencil** 400 | uppercase, letter-spacing `0.08em`. Headers only, two or three per frame at most. |
| UI | **Rajdhani** 600 | uppercase, letter-spacing `0.05em`. Anything actionable. |
| Mono | **IBM Plex Mono** 400 | uppercase, letter-spacing `0.12em`, 11–12px. Anything that names, counts, or labels. |
| Body | **IBM Plex Sans** 400 | sentence case, line-height 1.6. Running text only. |

All four are on Google Fonts. The mono layer is what makes the system read as
*instrumented* rather than decorated — use it for anything numeric.

**Type scale.** `11 / 12 / 14 / 16 / 20 / 28 / 42 / 68 / 104`. Stay on it.

## Radius — zero, with one named exception

```
border-radius: 0
```

Every corner, every element, in every product surface. The system is built from
stacked and divided rectangles — no circles, no diagonals, no pills.

**The single exception:**

```
--radius-msg: 6px
```

Permitted **only** on individual message rows inside a conversation component,
and **only** in motion b-roll. Not in product UI. Not on the container the
messages sit in. Not on cards, panels, inputs, buttons, avatars, badges, or
anything else, ever.

The exception exists because a conversation rendered entirely in hard rectangles
reads as a system log rather than as two people talking, and in b-roll the
viewer has roughly one second to recognise what they're looking at. Outside that
one recognition problem, the exception has no justification — so it does not
travel.

If a frame contains a rounded corner that is not a message row in b-roll, the
frame is wrong.

## Motion — one easing, two tempos

```
cubic-bezier(0.32, 0.72, 0, 1)
```

Fast out of the gate, long settle, **no overshoot on anything carrying text**.
The curve never changes. Only the durations do.

**Product tempo** — interfaces, sites, anything the user drives:

| Duration | Applies to |
| --- | --- |
| `180ms` | Out / exit |
| `240ms` | In / enter |
| `200ms` | State and colour change |

**Broll tempo** — short-form video, cut against speech:

| Duration | Applies to |
| --- | --- |
| `90ms` | Out / exit |
| `120ms` | In / enter |
| `100ms` | State and colour change |

Broll clips are on screen for two or three seconds total and are competing with
the pace of the voiceover. Product timings read as sluggish there. Use the
broll tempo for anything rendered to video; use product timings everywhere else.
Do not invent a third tempo, and do not blend them within a single clip.

Everything else about motion is unchanged at both tempos:

- **Fade, do not travel.** Transitions cross-fade. Movement is reserved for
  objects being directly dragged, never for reveals.
- **One idea per beat.** A single property changes at a time. Never fade and
  slide and scale together.
- **No overshoot, no bounce, no spring** — at any duration.
- `prefers-reduced-motion` collapses to a cross-fade — never to nothing.

## Geometry

- Borders and dividers are **1px hairlines**. Never thicker, never doubled.
- **8px spacing base.** All spacing is a multiple of 8.
- Generous negative space. Emptiness with intent, not sparse decoration.

## The one gesture

Emphasis is a **solid `--flare` fill with the text knocked out in `--void`**.
That is the entire vocabulary for "active", "selected", "checked", "hovered".

No glow. No scale. No shadow. No border animation. No colour shift.

In b-roll this is also how a message lands — the beat you are cutting to is the
inversion, not a zoom or a push.

## Never

- Glows, drop shadows, gradients on surfaces
- Rounded corners anywhere except `--radius-msg` on b-roll message rows
- Glitch, scanlines, CRT curvature, chromatic aberration
- Neon, acid green, or any second accent hue
- Blackletter, skulls, distressed or grunge texture
- Scroll-jacking, parallax, reveal-on-scroll
- Bounce, elastic, or spring easing
- Emoji as structure, centred everything, decorative numbering

---

## Copy-paste block

```
CYAN VOID — brand invariants. Do not deviate.

--void:  #060607   /* ground        */
--slab:  #101012   /* surfaces      */
--seam:  #1E1E21   /* 1px borders   */
--ash:   #5E7B86   /* labels only   */
--bone:  #A6D2E2   /* body text     */
--flare: #DAF5FF   /* emphasis      */

radius 0 everywhere · borders 1px only · spacing multiples of 8
sole exception --radius-msg: 6px, b-roll message rows only, nowhere else
hierarchy by brightness, never hue · no second accent colour
display Allerta Stencil .08em · ui Rajdhani 600 .05em
mono IBM Plex Mono .12em 11-12px · body IBM Plex Sans 400
easing cubic-bezier(.32,.72,0,1) — never changes
product tempo 180ms out / 240ms in / 200ms state
broll tempo    90ms out / 120ms in / 100ms state
emphasis = solid flare fill, text knocked out in void — nothing else
one idea per beat · fade, do not travel · generous negative space
never: glow, gradient, glitch, scanlines, neon, bounce easing, overshoot
```

## Files

| File | What it is |
| --- | --- |
| `cyan-void-tasker.svg` | The homepage, 1440×900, fonts embedded |
| `cyan-void-daily.svg` | The day planner, 1440×900, fonts embedded |
| `cyan-void-non-negotiables.svg` | Reference sheet: colours, type, radius, motion curve |
| `tokens.json` | The same values, machine-readable |
| `build-svg.mjs` | Regenerates the SVGs (`node build-svg.mjs`) |
| `fonts/` | The four woff2 files, as embedded |

The SVGs embed all four typefaces as base64 woff2, so they render correctly on
any machine without the fonts installed. Note that some motion tools (After
Effects in particular) ignore webfonts embedded in SVG — for those, install the
four families locally, or convert text to outlines on import. Remotion renders
in a browser and is unaffected — load the four families from Google Fonts
normally, no outlining required.
