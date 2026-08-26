# sample

`test-sv.mp4` — 11.9s, 640×360, 114 KB. Synthetic Swedish speech (espeak-ng)
over a flat `--void` frame. Committed so the pipeline can be verified without
hunting for a real clip.

Spoken text:

> Hej och välkommen till avsnitt ett. Idag ska vi prata om hur man automatiserar
> videoredigering med hjälp av maskininlärning. Det tar ungefär tio minuter.

Run it:

```powershell
.\transcribe.ps1 transcribe\sample\test-sv.mp4
```

It is synthetic speech, so expect imperfect wording — the point is to prove
CUDA, VAD, and word timestamps all work end to end, not to measure accuracy.
Judge it on: the run reporting `cuda/float16`, a word count in the tens, and
timestamps that advance monotonically across roughly 12 seconds.
