# stories

One folder per carousel. `slides.json` is the whole definition: which format
the set uses, the words on each slide, and where the crop sits on the picture.
`python pipeline/slides.py --story stories/<set>` renders it to `out/`.

**The pictures are not in the repository, and neither are the renders.** A
`slides.json` names a file — `01-cover.jpg`, `02.jpg` — that lives next to it
on the machine that took the photograph. That is the split: the definitions
are the tool and are committed; the photographs are the operator's own
material and stay on the operator's machine, along with everything under
`out/`.

So a fresh clone has every set's words and no set's pictures. `python
pipeline/formats.py --check` still passes — it reads the definitions, which
are all here. Rendering a set means dropping your own photographs in beside
its `slides.json`, at the filenames it already names.

`stories/formats/` is the catalogue: one folder per entry in
`pipeline/formats/bank.json`, which is what `--check` verifies against. Read
`python pipeline/formats.py` for what each format is and when to reach for it.
