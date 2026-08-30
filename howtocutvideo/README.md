# howtocutvideo

What was learned from watching other people's videos, and nothing of the
videos themselves.

`findings.md`, `tutorial-findings.md` and `FORMATS.md` are the output of that
watching: what the reference reels actually do, where the walkthrough tutorial
agreed with us and where it did not, and the six slide formats read off the
screenshots. Those are ours and they are committed. `FORMATS.md` in
particular is a spec — `broll/src/compositions/Slide.tsx` points at it.

**The material they were read off is not committed.** The reels, the
screenshots, the background textures and the tutorial transcript are other
people's work, studied locally and never redistributed from here. They live
in `videoreferences/`, `imagereferences/`, `backgroundreferences/` and
`claude-editing-tutorial.txt` on the machine that downloaded them, and
`.gitignore` keeps them there.

The cost is worth naming: a session that only sees the repository — a cloud
session, or a fresh clone — cannot re-analyse the footage, only read what was
already written down. `python pipeline/analyse.py` needs the files, so run it
on the machine that has them, and write what it tells you into the .md files
here so the next session inherits it.
