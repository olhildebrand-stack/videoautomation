# What the reference reels actually do

Measured with `pipeline/analyse.py` across the ten reels in `videoreferences/`,
plus reading a frame from every shot.

## They are two different videos, not one style

| | reels | cuts/min | contrast | what it is |
| --- | --- | --- | --- | --- |
| **Unbroken** | 3 of 10 | 0 | 1–5 | one continuous take, overlays only |
| **Intercut** | 5 of 10 | 10–25 | 8–63 | talking head alternating with full-frame screen recordings |

The median across all ten is 7 cuts/min, and that number describes none of
them. Averaging the set would have produced a target no reel in it hits.

## The cuts are b-roll, not jump cuts

This is the finding that matters. In the intercut reels the contrast figure
runs 59–63 against 1–5 for the unbroken ones, because the picture is
alternating between a dim face and a bright screen. Reading the frames
confirms it: every cut goes to a **full-frame screen recording** — a docs page,
a dashboard, a chat, a pricing table — held for one to three seconds, then back
to the face.

They are not cutting the talking head to tighten it. They are cutting away from
it to show the thing being described.

That is why our 27s cut holds 5–7 second shots and theirs hold 2: not a
different setting, a different amount of material. Matching the rhythm means
having screen recordings to cut to.

## Length

23, 31, 31, 40, 50, 52, 61, 63, 65, 70 seconds. Median 51.

Four of the ten run over a minute, and the longest is 70s. The pipeline's
target band had been 25-60 before this was measured, which would have called
those four too long -- including the two closest in subject to what we make.
`brief.TARGET_SECONDS` is now the measured range.

## Captions

One word at a time, uppercase, white with a dark edge, centred, sitting
72–81% down the frame (median 76%).

Ours already sat at 76.6% — the position was right and the chunking was not.
`maxWords` is now 1 and `caption.transform` is uppercase.

Worth knowing: 76% down puts the caption inside the bottom band our `safeZone`
reserves for Instagram's own furniture. These creators use more of the frame
than we allow ourselves. Whether that costs them a covered word on some
devices, the reels cannot say.

## The hook card

Dark rounded plate, white text, two lines, top of frame — which is what we
built, before any of these were measured.

## Section labels

The list reels put a numbered label top-centre over the face — "2. Opal",
"3. Mixboard" — appearing with each new item. We have no equivalent. Worth
adding as a cue kind if a video is ever structured as a list.

## Grade

Brightness median 118, saturation median 10 across the set. That saturation is
low; these are not punchy grades, they are flat and bright. Ours has not been
measured against it yet -- `analyse.py projects/vas/final.mp4` answers that in
one command.
