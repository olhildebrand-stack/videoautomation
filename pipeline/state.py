#!/usr/bin/env python3
"""Pipeline state, persisted so a run can stop at a gate and resume later."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class Stage(str, Enum):
    """Ordered. Each gate stage waits for a human before the next runs."""

    NEW = "new"
    TRANSCRIBED_RAW = "transcribed_raw"
    GATE_THROUGHLINE = "gate_throughline"          # checkpoint 1
    THROUGHLINE_APPROVED = "throughline_approved"
    GATE_CUTLIST = "gate_cutlist"                  # checkpoint 2
    CUTLIST_APPROVED = "cutlist_approved"
    CUT = "cut"
    TRANSCRIBED_CUT = "transcribed_cut"
    # Grading precedes captions deliberately: a grade applied over the caption
    # layer would shift flare and void, and the brand colours would no longer
    # be the exact values CYANVOID fixes.
    GRADED = "graded"
    # The hook is the last thing decided and the first thing seen, so it is
    # chosen against the finished cut rather than the raw recording.
    GATE_HOOK = "gate_hook"                        # checkpoint 3
    HOOK_CHOSEN = "hook_chosen"
    CAPTIONED = "captioned"
    DONE = "done"


ORDER = list(Stage)

# The three points that wait for a person: a wrong throughline, a bad match and
# a weak hook each cost more to discover after the render than before it.
GATES = {Stage.GATE_THROUGHLINE, Stage.GATE_CUTLIST, Stage.GATE_HOOK}


@dataclass
class PipelineState:
    source: str
    stage: str = Stage.NEW.value
    raw_transcript: str = ""
    throughline: str = ""
    edit_script: list[dict] = field(default_factory=list)
    cutlist: list[dict] = field(default_factory=list)
    cut_video: str = ""
    cut_transcript: str = ""
    graded_video: str = ""
    captioned_video: str = ""
    final_video: str = ""
    # Re-measure explicit ranges around the words they cover, instead of
    # taking them as written. Off by default: a stated range is the operator's
    # call, and silently moving it would defeat the reason for stating one.
    retime: bool = False
    # Silence threshold for that measurement, in dB. Every recording has its
    # own noise floor; `edges.py --sweep` finds this one's.
    noise_db: float = -45.0
    # Whether the overlay layer runs at all. Off ships the cut, the grade and
    # the captions on their own, without deleting the cue sheet that a later
    # pass will want back.
    overlays: bool = True
    # The cues as resolved for the last render, so a frame can be checked
    # afterwards against exactly what was drawn.
    cue_snapshot: list[dict] = field(default_factory=list)
    # The shortlist offered at checkpoint 3, and the one picked from it.
    hook_candidates: list[dict] = field(default_factory=list)
    hook: str = ""
    # True when the bank's best candidate scored as noise.
    hook_weak: bool = False
    notes: list[str] = field(default_factory=list)
    # Pauses longer than this are cut. 0 disables silence removal, which is
    # what you want when a long pause is deliberate rather than dead air.
    max_gap: float = 0.30

    @property
    def stage_enum(self) -> Stage:
        return Stage(self.stage)

    def advance_to(self, stage: Stage) -> None:
        self.stage = stage.value

    def is_at_gate(self) -> bool:
        return self.stage_enum in GATES


def state_path(project: Path) -> Path:
    return project / "pipeline.json"


def load(project: Path) -> PipelineState | None:
    path = state_path(project)
    if not path.is_file():
        return None
    return PipelineState(**json.loads(path.read_text(encoding="utf-8")))


def save(project: Path, state: PipelineState) -> None:
    project.mkdir(parents=True, exist_ok=True)
    state_path(project).write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8"
    )
