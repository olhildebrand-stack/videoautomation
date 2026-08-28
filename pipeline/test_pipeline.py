"""Tests for the pipeline state machine and its three gates."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as p  # noqa: E402
from state import GATES, ORDER, PipelineState, Stage, load, save  # noqa: E402


def test_stages_are_ordered_and_unique():
    assert len(ORDER) == len(set(ORDER))
    assert ORDER[0] is Stage.NEW and ORDER[-1] is Stage.DONE


def test_exactly_three_gates_and_they_are_the_agreed_ones():
    assert GATES == {Stage.GATE_THROUGHLINE, Stage.GATE_CUTLIST, Stage.GATE_HOOK}


def test_state_round_trips(tmp_path):
    state = PipelineState(source="a.mp4", notes=["x"])
    save(tmp_path, state)
    assert load(tmp_path).source == "a.mp4"
    assert load(tmp_path).notes == ["x"]


def test_load_returns_none_when_absent(tmp_path):
    assert load(tmp_path) is None


def test_is_at_gate_only_at_gates():
    assert PipelineState("a", Stage.GATE_THROUGHLINE.value).is_at_gate()
    assert PipelineState("a", Stage.GATE_CUTLIST.value).is_at_gate()
    assert not PipelineState("a", Stage.CUT.value).is_at_gate()


# --- gate behaviour ---------------------------------------------------------

def _transcript(tmp_path: Path, text: str) -> Path:
    words, cursor = [], 0.5
    for token in text.split():
        words.append({"word": f" {token}", "start": round(cursor, 3),
                      "end": round(cursor + 0.3, 3), "probability": 0.95})
        cursor += 0.4
    path = tmp_path / "raw.words.json"
    path.write_text(json.dumps({"words": words}), encoding="utf-8")
    return path


TEXT = "Det är faktiskt jättelätt att sätta upp det. Alla svaren hamnar i Google Sheets."


def test_throughline_gate_blocks_without_an_edit_script(tmp_path, capsys):
    state = PipelineState(source="raw.mp4", stage=Stage.GATE_THROUGHLINE.value,
                          raw_transcript=str(_transcript(tmp_path, TEXT)))
    assert p.step(state, tmp_path) is False, "must not advance past the gate"
    assert "CHECKPOINT 1 of 3" in capsys.readouterr().out
    assert state.stage == Stage.GATE_THROUGHLINE.value


def test_throughline_gate_passes_once_the_script_exists(tmp_path):
    (tmp_path / "edit-script.json").write_text(
        json.dumps([{"beat": "HOOK", "line": "Alla svaren hamnar i Google Sheets"}]),
        encoding="utf-8")
    state = PipelineState(source="raw.mp4", stage=Stage.GATE_THROUGHLINE.value,
                          raw_transcript=str(_transcript(tmp_path, TEXT)))
    assert p.step(state, tmp_path) is True
    assert state.stage == Stage.THROUGHLINE_APPROVED.value


def test_a_line_not_in_the_transcript_blocks_rather_than_guessing(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(_transcript(tmp_path, TEXT)),
        edit_script=[{"beat": "HOOK", "line": "ord som inte alls finns i detta transkript"}],
    )
    assert p.step(state, tmp_path) is False
    assert "not found in the transcript" in capsys.readouterr().out


def test_cutlist_gate_blocks_until_approved(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(_transcript(tmp_path, TEXT)),
        edit_script=[{"beat": "HOOK", "line": "Alla svaren hamnar i Google Sheets"}],
    )
    assert p.step(state, tmp_path) is True
    assert state.stage == Stage.GATE_CUTLIST.value
    assert p.step(state, tmp_path) is False, "second gate must hold"
    out = capsys.readouterr().out
    assert "CHECKPOINT 2 of 3" in out
    assert "CUT   :" in out, "the operator must see what the cut will contain"


def test_cutlist_gate_warns_when_outside_the_target_length(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{"beat": "HOOK", "text": "x", "matched_text": "x",
                  "start": 0.0, "end": 3.0, "duration": 3.0, "score": 1.0}],
    )
    p.step(state, tmp_path)
    assert "the ten reference reels run" in capsys.readouterr().out


def test_cutlist_gate_flags_an_approximate_match(tmp_path, capsys):
    """Flagged only when the wording genuinely differs, not on score alone."""
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{"beat": "HOOK", "text": "det jag ville saga",
                  "matched_text": "y", "actual_text": "nagot helt annat",
                  "start": 0.0, "end": 70.0, "duration": 70.0, "score": 0.81}],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "wording differs" in out
    assert "~ " in out


def test_done_is_terminal(tmp_path):
    assert p.step(PipelineState("a", Stage.DONE.value), tmp_path) is False


def test_grading_precedes_captions():
    """A grade over the caption layer would shift flare and void."""
    assert ORDER.index(Stage.GRADED) < ORDER.index(Stage.CAPTIONED)


def test_load_fillers_reads_the_project_list(tmp_path):
    (tmp_path / "fillers.txt").write_text("# note\n\növ\nliksom\n", encoding="utf-8")
    assert p.load_fillers(tmp_path) == {"öv", "liksom"}


def test_load_fillers_absent_is_empty(tmp_path):
    assert p.load_fillers(tmp_path) == set()


def test_silence_removal_shortens_the_cutlist(tmp_path, capsys):
    """A long pause inside a chosen line is cut out before the render."""
    words, cursor = [], 0.0
    for index, token in enumerate("Alla svaren hamnar i Google Sheets".split()):
        words.append({"word": f" {token}", "start": round(cursor, 3),
                      "end": round(cursor + 0.3, 3), "probability": 0.95})
        cursor += 3.0 if index == 2 else 0.4      # one long pause mid-line
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")

    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "HOOK", "line": "Alla svaren hamnar i Google Sheets"}],
    )
    assert p.step(state, tmp_path) is True
    assert "Silence: removed" in capsys.readouterr().out
    assert len(state.cutlist) > 1, "the pause splits the line into pieces"


def test_cut_display_shows_swallowed_words_not_the_script_line(tmp_path, capsys):
    """A merge that swept up excluded words must be visible at the checkpoint.

    matched_text is the per-line matches concatenated, so it looks correct even
    when the span covers words the script dropped. The CUT line is rebuilt from
    the words the span actually covers, which is the only honest view.
    """
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{
            "beat": "A+B", "text": "behöva göra mycket mindre",
            "matched_text": "behöva göra mycket mindre",
            "actual_text": "behöva göra mer. Och mycket mindre",
            "start": 0.0, "end": 70.0, "duration": 70.0, "score": 1.0,
        }],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "mer. Och" in out, "the swallowed words must be shown"
    assert "differs from the script line" in out


def test_cut_display_stays_quiet_when_the_span_matches(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{
            "beat": "A", "text": "behöva göra mycket mindre",
            "matched_text": "behöva göra mycket mindre",
            "actual_text": "Behöva göra mycket mindre.",   # case/punctuation only
            "start": 0.0, "end": 70.0, "duration": 70.0, "score": 1.0,
        }],
    )
    p.step(state, tmp_path)
    assert "differs from the script line" not in capsys.readouterr().out


def test_silence_split_is_labelled_with_the_pause_removed(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[
            {"beat": "HOOK", "text": "x", "matched_text": "x", "actual_text": "x",
             "start": 0.22, "end": 10.16, "duration": 9.94, "score": 1.0},
            {"beat": "HOOK.2", "text": "x", "matched_text": "x", "actual_text": "x",
             "start": 11.36, "end": 14.04, "duration": 2.68, "score": 1.0},
        ],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "split: 1.20s" in out
    assert "may be deliberate" in out, "a long pause should warn, not just report"


def test_max_gap_zero_disables_silence_removal(tmp_path, capsys):
    words, cursor = [], 0.0
    for index, token in enumerate("Alla svaren hamnar i Google Sheets".split()):
        words.append({"word": f" {token}", "start": round(cursor, 3),
                      "end": round(cursor + 0.3, 3), "probability": 0.95})
        cursor += 3.0 if index == 2 else 0.4
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")

    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript), max_gap=0.0,
        edit_script=[{"beat": "HOOK", "line": "Alla svaren hamnar i Google Sheets"}],
    )
    assert p.step(state, tmp_path) is True
    assert "removal disabled" in capsys.readouterr().out
    assert len(state.cutlist) == 1, "the pause must survive intact"


def test_silence_split_pieces_are_not_reported_as_mismatches(tmp_path, capsys):
    """Each piece holds part of the line; only the reassembled whole matters."""
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[
            {"beat": "HOOK", "text": "sätta varenda short form content editor",
             "matched_text": "", "actual_text": "sätta varenda short",
             "start": 0.0, "end": 10.0, "duration": 10.0, "score": 1.0},
            {"beat": "HOOK.2", "text": "sätta varenda short form content editor",
             "matched_text": "", "actual_text": "form content editor",
             "start": 11.2, "end": 14.0, "duration": 2.8, "score": 1.0},
        ],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "differs from the script line" not in out
    assert "split:" in out


def test_approximate_score_with_exact_wording_is_explained(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{"beat": "WHY", "text": "den ska ha allting",
                  "matched_text": "", "actual_text": "Den ska ha allting.",
                  "start": 0.0, "end": 70.0, "duration": 70.0, "score": 0.94}],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "match-window artifact" in out
    assert "wording differs" not in out


# --- a finished pipeline must not silently no-op -----------------------------

def test_run_on_a_finished_pipeline_says_nothing_was_rebuilt(tmp_path, capsys):
    """It printed 'Done' and looked successful while ignoring new code."""
    save(tmp_path, PipelineState(source="raw.mp4", stage=Stage.DONE.value,
                                 final_video="final.mp4"))
    assert p.run(tmp_path) == 0
    out = capsys.readouterr().out
    assert "Already finished" in out
    assert "nothing to do" in out
    assert "redo" in out


def test_max_gap_rebuilds_even_after_the_run_finished(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.DONE.value, max_gap=0.30,
        raw_transcript=str(_transcript(tmp_path, TEXT)),
        edit_script=[{"beat": "HOOK", "line": "Alla svaren hamnar i Google Sheets"}],
    )
    save(tmp_path, state)
    p.run(tmp_path, max_gap=0.6)
    out = capsys.readouterr().out
    assert "rebuilding the cut list" in out
    assert "CHECKPOINT 2" in out, "a rebuild must stop at the gate again"
    reloaded = load(tmp_path)
    assert reloaded.max_gap == 0.6
    assert reloaded.stage == Stage.GATE_CUTLIST.value


def test_an_unchanged_max_gap_does_not_rebuild(tmp_path, capsys):
    save(tmp_path, PipelineState(source="raw.mp4", stage=Stage.DONE.value, max_gap=0.30))
    p.run(tmp_path, max_gap=0.30)
    assert "rebuilding the cut list" not in capsys.readouterr().out


@pytest.mark.parametrize("where,expected", [
    ("cutlist", Stage.THROUGHLINE_APPROVED),
    ("transcribe", Stage.NEW),
    ("grade", Stage.TRANSCRIBED_CUT),
    # 'hook' re-matches the shortlist and asks again; 'captions' keeps the
    # hook already picked and only re-renders.
    ("hook", Stage.GRADED),
    ("captions", Stage.HOOK_CHOSEN),
])
def test_redo_rewinds_to_the_named_stage(tmp_path, where, expected, monkeypatch):
    save(tmp_path, PipelineState(source="raw.mp4", stage=Stage.DONE.value))
    monkeypatch.setattr(p, "run", lambda *a, **k: 0)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "redo", "--project", str(tmp_path), "--from", where])
    p.main()
    assert load(tmp_path).stage == expected.value


# --- explicit time ranges ---------------------------------------------------

def test_explicit_range_is_used_verbatim(tmp_path, capsys):
    """Stated ranges bypass matching, silence removal and merging."""
    words, cursor = [], 0.0
    for token in "ett två tre fyra fem sex".split():
        words.append({"word": f" {token}", "start": round(cursor, 3),
                      "end": round(cursor + 0.3, 3), "probability": 0.95})
        cursor += 0.4
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")

    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "HOOK", "start": 0.0, "end": 1.5}],
    )
    assert p.step(state, tmp_path) is True
    assert len(state.cutlist) == 1
    entry = state.cutlist[0]
    assert entry["start"] == 0.0 and entry["end"] == 1.5
    assert "explicit range" in capsys.readouterr().out


def test_explicit_range_reports_the_words_it_covers(tmp_path):
    words = [{"word": f" {t}", "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 0.95} for i, t in enumerate("ett två tre".split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "A", "start": 0.0, "end": 0.9}],
    )
    p.step(state, tmp_path)
    assert "ett" in state.cutlist[0]["actual_text"]
    assert "tre" not in state.cutlist[0]["actual_text"]


def test_explicit_and_matched_beats_keep_script_order(tmp_path):
    words = [{"word": f" {t}", "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 0.95}
             for i, t in enumerate("alfa brava charlie delta".split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[
            {"beat": "B", "line": "charlie delta"},
            {"beat": "A", "start": 0.0, "end": 0.9},
        ],
    )
    p.step(state, tmp_path)
    assert [e["beat"] for e in state.cutlist] == ["B", "A"]


def test_long_split_is_labelled_as_untranscribed_not_a_pause(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[
            {"beat": "HOOK", "text": "x", "matched_text": "", "actual_text": "x",
             "start": 0.0, "end": 3.4, "duration": 3.4, "score": 1.0},
            {"beat": "HOOK.2", "text": "x", "matched_text": "", "actual_text": "x",
             "start": 9.14, "end": 10.16, "duration": 1.02, "score": 1.0},
        ],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "likely untranscribed audio" in out
    assert "may be deliberate" not in out


def test_overlapping_explicit_ranges_are_trimmed_not_duplicated(tmp_path, capsys):
    """Two ranges that overlap would cut the same speech twice."""
    words = [{"word": f" {t}", "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 0.95} for i, t in enumerate("ett två tre fyra".split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "A", "start": 0.0, "end": 1.2},
                     {"beat": "B", "start": 1.0, "end": 2.0}],
    )
    p.step(state, tmp_path)
    assert state.cutlist[1]["start"] == 1.2, "the later range starts where the first ended"
    assert "trimmed 0.20s overlap" in capsys.readouterr().out


def test_non_overlapping_explicit_ranges_are_left_alone(tmp_path, capsys):
    words = [{"word": f" {t}", "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 0.95} for i, t in enumerate("ett två tre fyra".split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "A", "start": 0.0, "end": 0.9},
                     {"beat": "B", "start": 1.4, "end": 2.0}],
    )
    p.step(state, tmp_path)
    assert state.cutlist[1]["start"] == 1.4
    assert "trimmed" not in capsys.readouterr().out


# --- --edit-script ----------------------------------------------------------

def test_edit_script_is_copied_into_the_project(tmp_path, capsys):
    """Removes a copy step whose syntax differs between cmd and PowerShell."""
    source = tmp_path / "prepared.json"
    source.write_text(json.dumps([{"beat": "A", "start": 0.0, "end": 1.0}]),
                      encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert p.install_edit_script(project, source) is True
    installed = json.loads((project / "edit-script.json").read_text(encoding="utf-8"))
    assert installed == [{"beat": "A", "start": 0.0, "end": 1.0}]
    assert "1 beats" in capsys.readouterr().out


def test_a_missing_edit_script_is_reported_not_ignored(tmp_path, capsys):
    assert p.install_edit_script(tmp_path, tmp_path / "nope.json") is False
    assert "no such edit script" in capsys.readouterr().out


def test_omitting_the_flag_leaves_the_project_untouched(tmp_path):
    existing = tmp_path / "edit-script.json"
    existing.write_text('[{"beat": "KEEP"}]', encoding="utf-8")
    assert p.install_edit_script(tmp_path, None) is True
    assert json.loads(existing.read_text(encoding="utf-8")) == [{"beat": "KEEP"}]


def test_redo_installs_the_script_before_rebuilding(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    save(project, PipelineState(source="raw.mp4", stage=Stage.DONE.value))
    source = tmp_path / "prepared.json"
    source.write_text(json.dumps([{"beat": "A", "start": 0.0, "end": 1.0}]),
                      encoding="utf-8")
    monkeypatch.setattr(p, "run", lambda *a, **k: 0)
    monkeypatch.setattr(p.sys, "argv", [
        "p", "redo", "--project", str(project), "--edit-script", str(source)])
    p.main()
    assert (project / "edit-script.json").is_file()


def test_the_edit_script_is_re_read_on_every_rebuild(tmp_path, capsys):
    """A rewind lands after the gate that loads it, so a cached copy goes stale.

    Installing a new script then appeared to do nothing: the run reported the
    new file and rebuilt from the old beats.
    """
    words = [{"word": f" {t}", "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 0.95} for i, t in enumerate("ett två tre fyra".split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")

    (tmp_path / "edit-script.json").write_text(
        json.dumps([{"beat": "NEW", "start": 0.0, "end": 1.0}]), encoding="utf-8")

    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "STALE", "line": "ett två"}],
    )
    p.step(state, tmp_path)
    assert [e["beat"] for e in state.cutlist] == ["NEW"]
    assert state.edit_script[0]["beat"] == "NEW"


def test_an_absent_script_file_leaves_the_state_copy_alone(tmp_path):
    """Nothing on disk is not a reason to discard what the gate already read."""
    words = [{"word": " ett", "start": 0.0, "end": 0.4, "probability": 0.95},
             {"word": " två", "start": 0.5, "end": 0.9, "probability": 0.95}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript),
        edit_script=[{"beat": "FROM_STATE", "line": "ett två"}],
    )
    p.step(state, tmp_path)
    assert state.cutlist[0]["beat"] == "FROM_STATE"


def test_explicit_ranges_are_flagged_as_such(tmp_path):
    """The display treats them differently, so the flag must actually be set."""
    words = [{"word": f" {t}", "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 0.95} for i, t in enumerate("ett två tre fyra".split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    (tmp_path / "edit-script.json").write_text(
        json.dumps([{"beat": "A", "start": 0.0, "end": 1.0, "line": "ett två"}]),
        encoding="utf-8")
    state = PipelineState(source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript))
    p.step(state, tmp_path)
    assert state.cutlist[0]["explicit"] is True


def test_an_explicit_range_does_not_warn_about_wording(tmp_path, capsys):
    """A stated range was chosen because the timings are unreliable there;
    comparing the cut against those same timings proves nothing."""
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{"beat": "HOOK", "text": "the whole spoken line",
                  "matched_text": "", "actual_text": "only the tail",
                  "explicit": True,
                  "start": 0.0, "end": 70.0, "duration": 70.0, "score": 1.0}],
    )
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "differs from the script line" not in out
    assert "set by ear" in out


def test_a_matched_beat_still_warns(tmp_path, capsys):
    state = PipelineState(
        source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
        cutlist=[{"beat": "HOOK", "text": "the whole spoken line",
                  "matched_text": "", "actual_text": "something else entirely",
                  "explicit": False,
                  "start": 0.0, "end": 70.0, "duration": 70.0, "score": 1.0}],
    )
    p.step(state, tmp_path)
    assert "differs from the script line" in capsys.readouterr().out


# --- the on-screen hook -----------------------------------------------------

def test_hook_is_read_from_the_project(tmp_path):
    (tmp_path / "hook.txt").write_text(
        "# the chosen one\nReplaced My Video Editor with Claude Code\n",
        encoding="utf-8")
    assert p.load_hook(tmp_path) == "Replaced My Video Editor with Claude Code"


def test_a_missing_hook_file_is_blank_not_an_error(tmp_path):
    assert p.load_hook(tmp_path) == ""


def test_only_the_first_non_comment_line_is_used(tmp_path):
    """The file doubles as a shortlist; the top line is the pick."""
    (tmp_path / "hook.txt").write_text(
        "# candidates\nFirst choice\nSecond choice\n", encoding="utf-8")
    assert p.load_hook(tmp_path) == "First choice"


# --- checkpoint 3: the hook -------------------------------------------------

def _graded(tmp_path, transcript="Jag bygger ett system som klipper video åt mig."):
    """A pipeline sitting at GRADED, i.e. one step from the hook gate."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    words = tmp_path / "cut.words.json"
    words.write_text(
        json.dumps({"words": [{"word": w + " ", "start": i, "end": i + 1,
                               "probability": 1.0}
                              for i, w in enumerate(transcript.split())]}),
        encoding="utf-8")
    state = PipelineState(source="raw.mp4", stage=Stage.GRADED.value,
                          cut_transcript=str(words),
                          graded_video=str(tmp_path / "graded.mp4"))
    save(tmp_path, state)
    return state


def test_grading_leads_into_the_hook_gate(tmp_path):
    state = _graded(tmp_path)
    assert p.step(state, tmp_path) is True
    assert state.stage_enum is Stage.GATE_HOOK
    assert state.hook_candidates


def test_the_gate_blocks_until_a_hook_is_picked(tmp_path):
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    assert p.step(state, tmp_path) is False


def test_the_gate_prints_a_numbered_shortlist(tmp_path, capsys):
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "CHECKPOINT 3 of 3" in out
    for i in range(1, len(state.hook_candidates) + 1):
        assert f"  {i}. " in out
    # Every option says where it came from, so nothing looks invented.
    assert out.count("from [") == len(state.hook_candidates)


def test_a_blank_topic_file_is_seeded_for_the_operator(tmp_path):
    p.step(_graded(tmp_path), tmp_path)
    assert "tools" in (tmp_path / "topic.txt").read_text(encoding="utf-8")


def test_an_existing_topic_file_is_never_overwritten(tmp_path):
    (tmp_path / "topic.txt").write_text("tools: Remotion\n", encoding="utf-8")
    p.step(_graded(tmp_path), tmp_path)
    assert (tmp_path / "topic.txt").read_text(encoding="utf-8") == "tools: Remotion\n"


def test_the_whole_shortlist_is_written_out_not_just_the_pick(tmp_path):
    """A rejected option has to be recoverable without a regeneration that
    might rank differently."""
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    text = (tmp_path / "hooks.txt").read_text(encoding="utf-8")
    for c in state.hook_candidates:
        assert c["sv"] in text


def _pick(tmp_path, number, monkeypatch):
    monkeypatch.setattr(p, "run", lambda *a, **k: 0)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "hook", str(number), "--project", str(tmp_path)])
    return p.main()


def test_picking_a_number_records_that_hook_and_moves_on(tmp_path, monkeypatch):
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    save(tmp_path, state)
    assert _pick(tmp_path, 2, monkeypatch) == 0
    after = load(tmp_path)
    assert after.hook == state.hook_candidates[1]["sv"]
    assert after.stage_enum is Stage.HOOK_CHOSEN


def test_the_pick_is_written_to_hook_txt_as_well(tmp_path, monkeypatch):
    """So it survives a rebuild from earlier, and can be edited by hand."""
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    save(tmp_path, state)
    _pick(tmp_path, 1, monkeypatch)
    assert p.load_hook(tmp_path) == state.hook_candidates[0]["sv"]


@pytest.mark.parametrize("number", [-1, 99])
def test_a_number_outside_the_shortlist_is_refused(tmp_path, number, monkeypatch):
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    save(tmp_path, state)
    assert _pick(tmp_path, number, monkeypatch) == 2
    assert load(tmp_path).stage_enum is Stage.GATE_HOOK


def test_zero_means_use_the_hook_written_by_hand(tmp_path, monkeypatch):
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    save(tmp_path, state)
    (tmp_path / "hook.txt").write_text("En helt egen hook\n", encoding="utf-8")
    assert _pick(tmp_path, 0, monkeypatch) == 0
    assert load(tmp_path).hook == "En helt egen hook"


def test_zero_with_no_hook_file_is_refused(tmp_path, monkeypatch):
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    save(tmp_path, state)
    assert _pick(tmp_path, 0, monkeypatch) == 2


def test_approve_at_the_hook_gate_asks_for_a_number(tmp_path, capsys, monkeypatch):
    """The hook checkpoint is a choice, not a yes/no -- so it must not guess."""
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    save(tmp_path, state)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "approve", "--project", str(tmp_path)])
    assert p.main() == 1
    assert "expects a number" in capsys.readouterr().out
    assert load(tmp_path).stage_enum is Stage.GATE_HOOK


def test_the_hooks_command_offers_as_many_as_asked_for(tmp_path, capsys, monkeypatch):
    _graded(tmp_path)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "hooks", "--count", "9", "--project", str(tmp_path)])
    assert p.main() == 0
    assert len(load(tmp_path).hook_candidates) == 9
    assert "  9. " in capsys.readouterr().out


def test_the_chosen_hook_reaches_the_render(tmp_path, monkeypatch):
    state = _graded(tmp_path)
    state.hook = "Den valda hooken"
    state.stage = Stage.HOOK_CHOSEN.value
    seen = {}
    monkeypatch.setattr(p, "render_captions",
                        lambda v, t, o, hook_text="", cues=None:
                        seen.update(hook=hook_text, cues=cues))
    monkeypatch.setattr(p, "probe_duration", lambda _: 20.0)
    p.step(state, tmp_path)
    assert seen["hook"] == "Den valda hooken"
    assert state.stage_enum is Stage.DONE


def test_a_topic_file_can_be_installed_from_the_command_line(tmp_path, monkeypatch):
    """`copy` means different things in cmd and PowerShell, and a failed copy
    silently reuses the old file -- same reason --edit-script exists."""
    source = tmp_path / "prepared.txt"
    source.write_text("tools: Remotion\n", encoding="utf-8")
    project = tmp_path / "proj"
    _graded(project)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "hooks", "--topic", str(source),
                         "--project", str(project)])
    assert p.main() == 0
    assert (project / "topic.txt").read_text(encoding="utf-8") == "tools: Remotion\n"


def test_a_missing_topic_file_stops_rather_than_carrying_on(tmp_path, monkeypatch):
    _graded(tmp_path)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "hooks", "--topic", str(tmp_path / "nope.txt"),
                         "--project", str(tmp_path)])
    assert p.main() == 2


def test_printed_commands_are_runnable_as_typed(tmp_path, capsys, monkeypatch):
    """Hardcoding "pipeline.py" produced instructions that failed from the
    repo root, which is where it is actually run from."""
    monkeypatch.setattr(p.sys, "argv", ["pipeline\\pipeline.py"])
    state = _graded(tmp_path)
    p.step(state, tmp_path)
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "python pipeline\\pipeline.py hook 1" in out
    assert "python pipeline.py " not in out


# --- retiming explicit ranges -----------------------------------------------

def test_an_explicit_range_is_taken_as_written_by_default(tmp_path, capsys):
    """A stated range is the operator's call. Moving it silently would defeat
    the whole reason for stating one."""
    state = _explicit_project(tmp_path, retime=False)
    p.step(state, tmp_path)
    entry = state.cutlist[0]
    assert (entry["start"], entry["end"]) == (1.0, 3.0)
    assert "taken as given" in capsys.readouterr().out


def test_retime_re_measures_around_the_words_covered(tmp_path, capsys):
    state = _explicit_project(tmp_path, retime=True)
    p.step(state, tmp_path)
    entry = state.cutlist[0]
    # Words run 1.2-1.8 and 2.0-2.6, so the range tightens onto them.
    assert entry["start"] == pytest.approx(1.2 - 0.05, abs=0.001)
    assert entry["end"] == pytest.approx(2.6 + 0.3, abs=0.001)
    assert "re-measured" in capsys.readouterr().out


def test_retime_takes_effect_on_a_finished_pipeline(tmp_path, monkeypatch, capsys):
    """Same as --max-gap: the setting only reaches the cut through a rebuild,
    and a finished project must not quietly ignore it."""
    state = _explicit_project(tmp_path, retime=False)
    state.stage = Stage.DONE.value
    save(tmp_path, state)
    monkeypatch.setattr(p, "step", lambda *a, **k: False)
    p.run(tmp_path, retime=True)
    assert load(tmp_path).retime is True
    assert "rebuilding the cut list" in capsys.readouterr().out


def _explicit_project(tmp_path, retime):
    words = [{"word": " Ett", "start": 1.2, "end": 1.8, "probability": 1.0},
             {"word": " två.", "start": 2.0, "end": 2.6, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    (tmp_path / "edit-script.json").write_text(
        json.dumps([{"beat": "ONLY", "start": 1.0, "end": 3.0}]), encoding="utf-8")
    state = PipelineState(
        source="raw.mp4", stage=Stage.THROUGHLINE_APPROVED.value,
        raw_transcript=str(transcript), retime=retime,
        edit_script=[{"beat": "ONLY", "start": 1.0, "end": 3.0}],
    )
    save(tmp_path, state)
    return state


def test_only_the_last_beat_of_several_gets_the_end_tail(tmp_path):
    """The 0.3s belongs to the end of the video, not the end of every beat."""
    words = [{"word": " Ett", "start": 1.0, "end": 1.5, "probability": 1.0},
             {"word": " två", "start": 5.0, "end": 5.5, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    script = [{"beat": "A", "start": 0.5, "end": 2.0},
              {"beat": "B", "start": 4.5, "end": 6.0}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")
    state = PipelineState(source="raw.mp4",
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)
    first, last = state.cutlist
    assert first["end"] == pytest.approx(1.5 + 0.15, abs=0.001)
    assert last["end"] == pytest.approx(5.5 + 0.3, abs=0.001)


def test_the_gate_shows_what_retiming_took_back(tmp_path, capsys):
    """A range set by ear can sit well past the tails. Replacing it silently
    would leave the loss to be discovered on playback."""
    words = [{"word": " Slut.", "start": 1.2, "end": 1.8, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    # Held a full second past the last word -- an ear judgement, not a tail.
    script = [{"beat": "ONLY", "start": 1.0, "end": 2.8}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")
    state = PipelineState(source="raw.mp4",
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "retimed from 1.00 -> 2.80" in out
    assert "(-0.85s)" in out
    assert "listen to the end of it" in out


def test_nothing_is_reported_when_the_range_barely_moved(tmp_path, capsys):
    words = [{"word": " Ett", "start": 1.05, "end": 1.85, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    script = [{"beat": "ONLY", "start": 1.0, "end": 2.15}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")
    state = PipelineState(source="raw.mp4",
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)
    p.step(state, tmp_path)
    assert "retimed from" not in capsys.readouterr().out


def test_taking_ranges_as_written_reports_no_retiming(tmp_path, capsys):
    state = _explicit_project(tmp_path, retime=False)
    p.step(state, tmp_path)
    p.step(state, tmp_path)
    assert "retimed from" not in capsys.readouterr().out


# --- retiming against the audio ---------------------------------------------

@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")
def test_retime_measures_the_audio_and_clears_the_clipped_word(tmp_path, capsys):
    """The real failure, reproduced.

    Speech runs 1.0-2.0. The transcript, drifting early the way vad_filter
    makes it, puts it at 0.6-1.6. Retiming against the transcript cuts at
    1.6 + 0.3 = 1.90 -- inside the word, which is how "video" became "vi".
    Retiming against the audio finds 2.0 and cuts past it.
    """
    source = tmp_path / "raw.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*300*t)*between(t,1,2)':d=4:s=44100", str(source)],
        check=True,
    )
    words = [{"word": " Video.", "start": 0.6, "end": 1.6, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    script = [{"beat": "ONLY", "start": 0.6, "end": 1.6}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")
    state = PipelineState(source=str(source),
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)
    entry = state.cutlist[0]
    assert entry["end"] > 2.0, "the cut still lands inside the last word"
    assert entry["end"] == pytest.approx(2.0 + 0.3, abs=0.05)
    # And the leading silence goes with it: the same drift opened the cut
    # before anyone spoke.
    assert entry["start"] == pytest.approx(1.0 - 0.05, abs=0.05)
    assert "against the audio" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")
def test_the_gate_reports_how_far_the_transcript_was_out(tmp_path, capsys):
    source = tmp_path / "raw.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*300*t)*between(t,1,2)':d=4:s=44100", str(source)],
        check=True,
    )
    words = [{"word": " Video.", "start": 0.6, "end": 1.6, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    script = [{"beat": "ONLY", "start": 0.6, "end": 1.6}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")
    state = PipelineState(source=str(source),
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "from where the transcript put it" in out
    assert "inside the last word" in out


def test_an_unreadable_source_says_so_instead_of_drifting_silently(tmp_path, capsys):
    """Falling back to the word timestamps is the behaviour that clipped the
    words, so it must never happen quietly."""
    state = _explicit_project(tmp_path, retime=True)
    p.step(state, tmp_path)
    out = capsys.readouterr().out
    assert "the clock that drifts" in out
    assert "against the transcript" in out


def test_status_shows_the_settings_a_rebuild_will_use(tmp_path, capsys, monkeypatch):
    """They live in pipeline.json and are easy to forget a week later."""
    save(tmp_path, PipelineState(source="raw.mp4", stage=Stage.DONE.value,
                                 retime=True, noise_db=-45.0,
                                 hook="Bytte ut min videoredigerare"))
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "status", "--project", str(tmp_path)])
    assert p.main() == 0
    out = capsys.readouterr().out
    assert "retime  : on" in out and "-45dB" in out
    assert "0.05s before" in out and "0.15s after" in out
    assert "Bytte ut min videoredigerare" in out


def test_status_says_when_ranges_are_taken_as_written(tmp_path, capsys, monkeypatch):
    save(tmp_path, PipelineState(source="raw.mp4", stage=Stage.DONE.value))
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "status", "--project", str(tmp_path)])
    p.main()
    assert "taken as written" in capsys.readouterr().out


# --- the overlay cue sheet ---------------------------------------------------

def _cue_project(tmp_path, sheet, transcript="klipp captions color correction"):
    words = [{"word": " " + w, "start": i * 0.5, "end": i * 0.5 + 0.4,
              "probability": 1.0}
             for i, w in enumerate(transcript.split())]
    (tmp_path / "cut.words.json").write_text(json.dumps({"words": words}),
                                             encoding="utf-8")
    (tmp_path / "overlays.json").write_text(json.dumps(sheet), encoding="utf-8")
    return PipelineState(source="raw.mp4",
                         cut_transcript=str(tmp_path / "cut.words.json"),
                         graded_video=str(tmp_path / "graded.mp4"))


def test_no_cue_sheet_means_no_overlays(tmp_path):
    """Every project before this stage existed still renders."""
    state = _cue_project(tmp_path, [])
    (tmp_path / "overlays.json").unlink()
    assert p.build_cues(state, tmp_path) == []


def test_cues_resolve_to_frames_for_the_renderer(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    state = _cue_project(tmp_path, [
        {"kind": "emojiRow", "emoji": [{"emoji": "1", "cue": "klipp"},
                                       {"emoji": "2", "cue": "captions"}]}])
    cues = p.build_cues(state, tmp_path)
    assert len(cues) == 1
    assert [e["enter"] for e in cues[0]["emoji"]] == [0, 15]
    out = capsys.readouterr().out
    assert "1 of 1 cues placed" in out


def test_a_cue_that_missed_is_named_at_the_checkpoint(tmp_path, monkeypatch, capsys):
    """Silently dropping it is how an overlay in the wrong place ships."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    state = _cue_project(tmp_path, [
        {"kind": "image", "cue": "ord som aldrig sades", "src": "x.png"}])
    assert p.build_cues(state, tmp_path) == []
    out = capsys.readouterr().out
    assert "ord som aldrig sades" in out
    assert "not said" in out
    assert "0 of 1 cues placed" in out


def test_advice_is_never_printed_as_a_bare_imperative(tmp_path, monkeypatch, capsys):
    """A line starting with a capitalised verb reads as a command in a
    terminal, and has twice been pasted back into one. Guidance gets a marker;
    only real commands are left looking runnable."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    state = _cue_project(tmp_path, [
        {"kind": "image", "cue": "ord som aldrig sades", "src": "x.png"}])
    p.build_cues(state, tmp_path)
    for line in capsys.readouterr().out.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("NOTE:", "!", "python")):
            continue
        first = stripped.split(" ")[0]
        assert not (first.istitle() and first.isalpha() and len(first) > 2 and
                    stripped.endswith(".")), f"reads as a command: {stripped!r}"


# --- cue assets --------------------------------------------------------------

def test_a_missing_image_drops_its_cue_instead_of_failing_the_render(
    tmp_path, monkeypatch, capsys
):
    """Remotion does not degrade on a 404: a missing <Img> takes the whole
    render down, thousands of lines of stack trace deep."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    state = _cue_project(tmp_path, [
        {"kind": "image", "cue": "klipp", "src": "nope.png"},
        {"kind": "emojiRow", "emoji": [{"emoji": "1", "cue": "captions"}]},
    ])
    cues = p.build_cues(state, tmp_path)
    assert [c["kind"] for c in cues] == ["emojiRow"], "the good cue survives"
    out = capsys.readouterr().out
    assert "no such file" in out
    assert "nope.png" in out


def test_an_asset_is_staged_from_the_project_into_the_renderer(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    staged = tmp_path / "public" / p.STAGED
    monkeypatch.setattr(p, "BROLL", tmp_path)
    (tmp_path / p.ASSET_DIR).mkdir()
    (tmp_path / p.ASSET_DIR / "shot.png").write_bytes(b"not really a png")
    state = _cue_project(tmp_path, [
        {"kind": "image", "cue": "klipp", "src": "shot.png"}])
    cues = p.build_cues(state, tmp_path)
    assert (staged / "shot.png").is_file()
    # The renderer gets the path it can serve, not the one on disk.
    assert cues[0]["src"] == f"{p.STAGED}/shot.png"


def test_each_icon_slot_stages_its_own_file(tmp_path, monkeypatch):
    """An iconRow names a file per slot, not one for the cue."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    staged = tmp_path / "public" / p.STAGED
    monkeypatch.setattr(p, "BROLL", tmp_path)
    (tmp_path / p.ASSET_DIR).mkdir()
    for name in ("robot.png", "claude.png"):
        (tmp_path / p.ASSET_DIR / name).write_bytes(b"not really a png")
    state = _cue_project(tmp_path, [
        {"kind": "iconRow", "cue": "klipp", "slots": [
            {"name": "A", "src": "robot.png", "cue": "klipp"},
            {"name": "B", "src": "claude.png", "cue": "captions"},
        ]}])
    cues = p.build_cues(state, tmp_path)
    assert (staged / "robot.png").is_file()
    assert (staged / "claude.png").is_file()
    assert [s["src"] for s in cues[0]["slots"]] == [
        f"{p.STAGED}/robot.png", f"{p.STAGED}/claude.png"]


def test_a_missing_icon_file_is_reported_with_its_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    monkeypatch.setattr(p, "BROLL", tmp_path)
    (tmp_path / p.ASSET_DIR).mkdir()
    state = _cue_project(tmp_path, [
        {"kind": "iconRow", "cue": "klipp", "slots": [
            {"name": "A", "src": "nope.png", "cue": "klipp"}]}])
    p.build_cues(state, tmp_path)
    out = capsys.readouterr().out
    assert "nope.png" in out


def test_the_chat_survives_without_the_video_it_sends_back(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    monkeypatch.setattr(p, "BROLL", tmp_path)
    state = _cue_project(tmp_path, [
        {"kind": "chat", "cue": "klipp", "prompt": "Redigera min video",
         "replyVideo": "nope.mp4"}])
    cues = p.build_cues(state, tmp_path)
    assert len(cues) == 1, "the chat itself is not lost"
    assert "replyVideo" not in cues[0]
    assert "rendered without it" in capsys.readouterr().out


def test_overlays_can_be_switched_off_without_losing_the_sheet(
    tmp_path, monkeypatch, capsys
):
    """Shipping the simple cut must not mean deleting the cue sheet the next
    pass wants back."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    state = _cue_project(tmp_path, [
        {"kind": "emojiRow", "emoji": [{"emoji": "1", "cue": "klipp"}]}])
    state.overlays = False
    assert p.build_cues(state, tmp_path) == []
    assert (tmp_path / "overlays.json").is_file(), "the sheet stays on disk"
    assert "off" in capsys.readouterr().out


def test_switching_overlays_rewinds_only_as_far_as_the_captions(
    tmp_path, monkeypatch, capsys
):
    """Nothing before the caption render reads the cue sheet, so a re-cut, a
    re-grade and a re-transcribe are all wasted work here."""
    save(tmp_path, PipelineState(source="raw.mp4", stage=Stage.DONE.value))
    monkeypatch.setattr(p, "step", lambda *a, **k: False)
    p.run(tmp_path, overlays=False)
    after = load(tmp_path)
    assert after.overlays is False
    assert after.stage_enum is Stage.HOOK_CHOSEN
    assert "re-rendering captions" in capsys.readouterr().out


def test_a_bare_filename_is_pointed_at_the_footage_it_meant(tmp_path, monkeypatch, capsys):
    """A bare filename is the natural thing to type and the wrong thing to
    pass, since footage lives in videos/ and the command runs from the root."""
    monkeypatch.setattr(p, "ROOT", tmp_path)
    (tmp_path / "videos").mkdir()
    (tmp_path / "videos" / "clip.mp4").write_bytes(b"x")
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "init", "clip.mp4", "--project", str(tmp_path / "proj")])
    assert p.main() == 2
    out = capsys.readouterr().out
    assert "Did you mean" in out
    assert "clip.mp4" in out


def test_a_name_that_is_nowhere_does_not_invent_a_suggestion(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p, "ROOT", tmp_path)
    monkeypatch.setattr(p.sys, "argv",
                        ["p", "init", "ghost.mp4", "--project", str(tmp_path / "proj")])
    assert p.main() == 2
    assert "Did you mean" not in capsys.readouterr().out


# --- blooper detection at the throughline gate -------------------------------

RETAKES = (
    "Jag bygger ett system som... "
    "Jag bygger ett system som sätter varenda editor i konkurs. "
    "Och jag använder det här kontot som testkanin."
)


def _raw_project(tmp_path, text=RETAKES):
    words = [{"word": " " + w, "start": round(i * 0.4, 3),
              "end": round(i * 0.4 + 0.3, 3), "probability": 1.0}
             for i, w in enumerate(text.split())]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    return PipelineState(source="raw.mp4", stage=Stage.GATE_THROUGHLINE.value,
                         raw_transcript=str(transcript))


def test_the_first_gate_names_the_bloopers(tmp_path, capsys):
    """It printed a raw transcript and said nothing, so a take full of retakes
    shipped with every one intact."""
    p.show_throughline_gate(_raw_project(tmp_path), tmp_path)
    out = capsys.readouterr().out
    assert "CUT" in out
    assert "look like bloopers" in out
    assert "truncated" in out or "said again" in out


def test_a_clean_take_says_so_rather_than_inventing_a_fault(tmp_path, capsys):
    clean = "Det finns tre skills du borde använda. Skriv i kommentarerna."
    p.show_throughline_gate(_raw_project(tmp_path, clean), tmp_path)
    assert "No bloopers found" in capsys.readouterr().out


def test_the_gate_says_who_does_the_reasoning(tmp_path, capsys):
    """It read as an instruction to the operator to work eight stages by hand.
    Choosing beats is a reasoning task and belongs with Claude; the gate has to
    say so or it reads as homework. Since `direct` exists, saying so means
    naming the command that does it rather than describing the work."""
    p.show_throughline_gate(_raw_project(tmp_path), tmp_path)
    out = capsys.readouterr().out
    assert "direct --project" in out
    assert out.index("direct --project") < out.index("draft --project"), (
        "the judgement path is the default; the mechanical one is the fallback")
    assert "DIRECTOR.md" in out


def test_the_gate_says_the_verdicts_are_not_self_applying(tmp_path, capsys):
    """The classification is useless if the edit script is written without it."""
    p.show_throughline_gate(_raw_project(tmp_path), tmp_path)
    out = capsys.readouterr().out
    assert "an edit script decides what is kept" in out
    assert "draft --project" in out


def test_draft_writes_a_script_of_the_survivors(tmp_path):
    state = _raw_project(tmp_path)
    assert p.draft_edit_script(state, tmp_path) == 0
    beats = json.loads((tmp_path / "edit-script.json").read_text(encoding="utf-8"))
    assert beats, "a draft with no beats is not a draft"
    joined = " ".join(b["line"] for b in beats)
    assert "..." not in joined, "the truncated take should not survive"
    for beat in beats:
        assert beat["end"] > beat["start"]


def test_draft_refuses_rather_than_writing_an_empty_script(tmp_path, capsys):
    state = _raw_project(tmp_path, "Halvfärdig mening som aldrig")
    assert p.draft_edit_script(state, tmp_path) == 1
    assert not (tmp_path / "edit-script.json").exists()
    assert "Not writing" in capsys.readouterr().out


# --- arbitrary markup, and b-roll placed by filename --------------------------

def test_markup_is_inlined_from_the_project_assets(tmp_path):
    """Read here rather than fetched at render time: a missing file must be
    caught with the other assets, not by Remotion cancelling mid-render."""
    (tmp_path / p.ASSET_DIR).mkdir()
    (tmp_path / p.ASSET_DIR / "beat.html").write_text(
        "<div>en ruta</div>", encoding="utf-8")
    cue = {"kind": "html", "htmlFile": "beat.html"}
    assert p.inline_html(cue, tmp_path) == []
    assert cue["html"] == "<div>en ruta</div>"
    assert "htmlFile" not in cue, "the renderer should never see a path"


def test_missing_markup_is_reported_not_rendered_empty(tmp_path):
    cue = {"kind": "html", "htmlFile": "gone.html"}
    missing = p.inline_html(cue, tmp_path)
    assert missing and missing[0].startswith("htmlFile:")
    assert "html" not in cue


def test_a_cue_without_markup_is_left_alone(tmp_path):
    cue = {"kind": "emojiRow"}
    assert p.inline_html(cue, tmp_path) == []
    assert cue == {"kind": "emojiRow"}


def test_a_clip_is_placed_by_its_filename(tmp_path):
    """Gathering the footage should be the whole job."""
    directory = tmp_path / p.ASSET_DIR / p.BROLL_DIR
    directory.mkdir(parents=True)
    (directory / "hemsidor.mp4").write_bytes(b"x")
    (directory / "motion-design.mov").write_bytes(b"x")
    found = {c["cue"]: c for c in p.discover_broll(tmp_path)}
    assert set(found) == {"hemsidor", "motion design"}
    assert found["hemsidor"]["kind"] == "clip"
    assert found["hemsidor"]["src"].endswith("hemsidor.mp4")


def test_a_file_that_is_not_footage_is_ignored(tmp_path):
    directory = tmp_path / p.ASSET_DIR / p.BROLL_DIR
    directory.mkdir(parents=True)
    (directory / "notes.txt").write_bytes(b"x")
    (directory / "poster.png").write_bytes(b"x")
    assert p.discover_broll(tmp_path) == []


def test_no_broll_directory_is_not_an_error(tmp_path):
    assert p.discover_broll(tmp_path) == []


def test_an_explicit_entry_beats_the_filename_convention(
    tmp_path, monkeypatch, capsys
):
    """The convention is a default, not a rule."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    monkeypatch.setattr(p, "BROLL", tmp_path)
    directory = tmp_path / p.ASSET_DIR / p.BROLL_DIR
    directory.mkdir(parents=True)
    (directory / "klipp.mp4").write_bytes(b"x")
    state = _cue_project(tmp_path, [
        {"kind": "image", "cue": "klipp", "src": "shot.png"}])
    (tmp_path / p.ASSET_DIR / "shot.png").write_bytes(b"x")
    cues = p.build_cues(state, tmp_path)
    assert [c["kind"] for c in cues] == ["image"], "the sheet wins on 'klipp'"


# --- a beat name with a dot in it is not a split piece -----------------------

@pytest.mark.parametrize("name,expected", [
    ("HOOK", "HOOK"),
    ("HOOK.5", "HOOK"),
    ("P.INTRO", "P.INTRO"),
    ("P.INTRO.2", "P.INTRO"),
    ("S.WHAT+S.BRIEF", "S.WHAT"),
    ("U.HOW+U.LAND.2", "U.HOW"),
])
def test_only_a_trailing_number_marks_a_split_piece(name, expected):
    """Splitting on the first dot treated "P.INTRO" and "P.LAND" as two pieces
    of a beat called "P", reassembled their text together, and reported every
    beat as differing from its own script line."""
    assert p.base_beat(name) == expected


def test_dotted_beat_names_do_not_report_false_wording_drift(tmp_path, capsys):
    state = PipelineState(source="raw.mp4", stage=Stage.GATE_CUTLIST.value,
                          cutlist=[
        {"beat": "P.ONE", "text": "Den första är planering.",
         "matched_text": "Den första är planering.",
         "actual_text": "Den första är planering.",
         "explicit": False, "start": 0.0, "end": 2.0, "duration": 2.0,
         "score": 1.0},
        {"beat": "P.TWO", "text": "Det andra är struktur.",
         "matched_text": "Det andra är struktur.",
         "actual_text": "Det andra är struktur.",
         "explicit": False, "start": 3.0, "end": 5.0, "duration": 2.0,
         "score": 1.0},
    ])
    p.show_cutlist_gate(state, tmp_path)
    assert "differs from the script line" not in capsys.readouterr().out


# --- the bank does not always hold a hook ------------------------------------

def _hook_project(tmp_path, transcript):
    words = [{"word": " " + w, "start": i * 0.4, "end": i * 0.4 + 0.3,
              "probability": 1.0} for i, w in enumerate(transcript.split())]
    (tmp_path / "cut.words.json").write_text(json.dumps({"words": words}),
                                             encoding="utf-8")
    return PipelineState(source="raw.mp4",
                         cut_transcript=str(tmp_path / "cut.words.json"),
                         graded_video=str(tmp_path / "graded.mp4"))


def test_a_video_the_bank_does_not_fit_is_told_so(tmp_path, monkeypatch, capsys):
    """Every hook is scored, so there is always a top five -- but a top five is
    not a match. Five hooks tying at 2.0 on one incidental keyword were
    presented with the same confidence as a real one scoring 28."""
    monkeypatch.setattr(p, "probe_duration", lambda _: 40.0)
    state = _hook_project(
        tmp_path,
        "Det är planering struktur och utförande och hur mycket det kostar")
    p.build_hook_shortlist(state, tmp_path, 5)
    assert state.hook_weak
    p.show_hook_gate(state, tmp_path)
    out = capsys.readouterr().out
    assert "Nothing in the scored bank fits this video" in out
    assert "your own spoken opening" in out
    assert "MATCHED from the scored bank" not in out


def test_a_video_the_bank_does_fit_is_not_hedged(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p, "probe_duration", lambda _: 40.0)
    (tmp_path / "topic.txt").write_text(
        "tools: Claude Code\nabout: automating video editing end to end\n",
        encoding="utf-8")
    state = _hook_project(
        tmp_path,
        "Jag bygger ett system som klipper video captions och b-roll åt mig "
        "helt automatiskt med Claude och content blir sjukt mycket bättre")
    p.build_hook_shortlist(state, tmp_path, 5)
    assert not state.hook_weak
    p.show_hook_gate(state, tmp_path)
    out = capsys.readouterr().out
    assert "Nothing in the scored bank" not in out
    assert "MATCHED from the scored bank" in out


# --- files the operator hand-edits on Windows --------------------------------

def test_a_byte_order_mark_does_not_reach_the_hook(tmp_path):
    """PowerShell's Set-Content -Encoding utf8 writes a BOM. Read as plain
    utf-8 it survives as an invisible leading character -- a glyph on screen in
    a hook, and a silently failing match in a cue phrase."""
    (tmp_path / "hook.txt").write_bytes(
        "﻿De tre stegen bakom varenda projekt\r\n".encode("utf-8"))
    assert p.load_hook(tmp_path) == "De tre stegen bakom varenda projekt"


def test_a_byte_order_mark_does_not_reach_the_filler_list(tmp_path):
    (tmp_path / "fillers.txt").write_bytes("﻿öh\r\nehm\r\n".encode("utf-8"))
    assert p.load_fillers(tmp_path) == {"öh", "ehm"}


def test_a_byte_order_mark_does_not_reach_a_cue_sheet(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(p, "probe_duration", lambda _: 10.0)
    monkeypatch.setattr(p, "BROLL", tmp_path)
    state = _cue_project(tmp_path, [])
    (tmp_path / "overlays.json").write_bytes(
        '﻿[{"kind": "emojiRow", "emoji": [{"emoji": "1", "cue": "klipp"}]}]'
        .encode("utf-8"))
    cues = p.build_cues(state, tmp_path)
    assert len(cues) == 1, "the sheet failed to parse at all"


# --- per-beat overrides on an explicit range ---------------------------------

def test_by_default_both_edges_are_measured_with_the_standard_tail():
    from sentences import DEFAULT_TAIL
    assert p.range_settings({"beat": "X"}, False, True) == (True, True, DEFAULT_TAIL)


def test_the_last_beat_keeps_the_longer_tail():
    from sentences import DEFAULT_END_TAIL
    assert p.range_settings({"beat": "X"}, True, True)[2] == DEFAULT_END_TAIL


def test_a_beat_can_refuse_retiming_on_both_edges():
    """Where a discarded attempt sits just before a beat, the audio search
    reaches back into it and pulls the cut open over words meant to be gone."""
    assert p.range_settings({"beat": "X", "retime": False}, False, True)[:2] == (False, False)


def test_a_beat_can_pin_its_start_and_still_measure_its_end():
    """false was too blunt: a start pinned off a smeared transcript also keeps
    whatever silence the transcript put after the last word, which plays as a
    long pause before the next beat."""
    assert p.range_settings({"beat": "X", "retime": "end"}, False, True)[:2] == (False, True)


def test_a_beat_can_pin_its_end_and_still_measure_its_start():
    assert p.range_settings({"beat": "X", "retime": "start"}, False, True)[:2] == (True, False)


def test_a_beat_can_set_its_own_tail():
    assert p.range_settings({"beat": "X", "tail": 0.0}, False, True)[2] == 0.0


def test_a_pinned_beat_still_reports_its_tail():
    """The tail is what a "retime": "end" beat is asking for."""
    assert p.range_settings({"beat": "X", "retime": "end", "tail": 0.0},
                            False, True) == (False, True, 0.0)


def test_nothing_is_measured_when_retiming_is_off():
    assert p.range_settings({"beat": "X"}, False, False)[:2] == (False, False)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")
def test_silence_inside_a_kept_range_is_removed_before_cutting(tmp_path, capsys):
    """The operator's report, reproduced: a beat that opens in silence.

    A blip at 1.0-1.3s, then the words from 2.5s. Measuring around the range
    takes the blip as the onset and reports no clamp, so nothing upstream
    catches it. The pass that looks INSIDE the chosen range does.
    """
    source = tmp_path / "raw.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*300*t)*(between(t,1,1.3)+between(t,2.5,5))"
         "':d=7:s=44100", str(source)],
        check=True,
    )
    words = [{"word": " Orden.", "start": 2.5, "end": 5.0, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    script = [{"beat": "ONLY", "start": 1.1, "end": 5.0}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")

    state = PipelineState(source=str(source),
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)

    entry = state.cutlist[0]
    assert entry["start"] > 2.0, (
        f"the cut still opens on the blip, at {entry['start']}")
    assert entry["start"] == pytest.approx(2.5 - 0.05, abs=0.15)
    assert "silence found inside the kept ranges" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")
def test_a_pinned_start_is_not_trimmed_either(tmp_path, capsys):
    """"retime": "end" pins the start, and the trim must honour that too.

    Same audio as above. The operator pinned this start because the
    measurement got it wrong; trimming it back to the blip is that same
    measurement arriving by a different door.
    """
    source = tmp_path / "raw.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "aevalsrc='0.5*sin(2*PI*300*t)*(between(t,1,1.3)+between(t,2.5,5))"
         "':d=7:s=44100", str(source)],
        check=True,
    )
    words = [{"word": " Orden.", "start": 2.5, "end": 5.0, "probability": 1.0}]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({"words": words}), encoding="utf-8")
    script = [{"beat": "ONLY", "start": 1.1, "end": 5.0, "retime": "end"}]
    (tmp_path / "edit-script.json").write_text(json.dumps(script), encoding="utf-8")

    state = PipelineState(source=str(source),
                          stage=Stage.THROUGHLINE_APPROVED.value,
                          raw_transcript=str(transcript), retime=True,
                          edit_script=script)
    p.step(state, tmp_path)

    assert state.cutlist[0]["start"] == pytest.approx(1.1), (
        "the pinned start moved")


def test_previewing_the_smeared_stretches_needs_a_project():
    """The whole convenience is that it reads the project's own source and
    take list; without one there is nothing to read."""
    import subprocess as sp
    done = sp.run([sys.executable, str(Path(p.__file__).parent / "preview.py"),
                   "--smeared"], capture_output=True, text=True)
    assert done.returncode == 2
    assert "--smeared needs --project" in done.stderr


def test_transcription_is_verbatim():
    """Whisper smooths false starts and repetitions out of the transcript while
    the audio still contains them. Every smeared stretch this project has
    fought came from that, and --verbatim has existed since transcribe.py was
    written without the pipeline ever passing it."""
    import inspect
    source = inspect.getsource(p.transcribe)
    assert '"--verbatim"' in source


def test_the_transcriber_takes_the_flag_the_pipeline_passes():
    """A flag the pipeline invents and the transcriber does not accept would
    fail at run time, on a GPU, minutes in."""
    text = (Path(p.__file__).resolve().parent.parent
            / "transcribe" / "transcribe.py").read_text(encoding="utf-8")
    assert '"--verbatim"' in text


def test_a_project_may_replace_the_shared_vocabulary(tmp_path):
    """Hotwords bias the decoder, so a term this recording never says is pure
    risk: fed in as a prompt it gets emitted over audio the model cannot read.
    A Swedish video about voice agents came back with "TypeScript React GIS"
    in it, because those are in the shared list for a different video."""
    import inspect
    source = inspect.getsource(p.transcribe)
    assert '"--vocabulary", str(vocabulary)' in source
    assert 'project / "vocabulary.txt"' in source


def test_a_project_adds_to_the_shared_corrections_rather_than_replacing(tmp_path):
    """A find/replace only acts on text already there, so it cannot misfire
    the way a hotword can -- the shared rules stay useful."""
    import inspect
    source = inspect.getsource(p.transcribe)
    assert '"--extra-corrections", str(corrections)' in source


def test_the_transcriber_accepts_what_the_pipeline_passes():
    text = (Path(p.__file__).resolve().parent.parent
            / "transcribe" / "transcribe.py").read_text(encoding="utf-8")
    for flag in ('"--vocabulary"', '"--extra-corrections"', '"--verbatim"'):
        assert flag in text, f"transcribe.py does not accept {flag}"
