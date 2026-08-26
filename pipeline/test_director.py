"""Tests for the brief and the retry loop.

The model call itself is faked. What is worth testing is everything around it:
that the brief carries what a decision needs, that a failed check is handed
back rather than swallowed, and that the loop stops instead of paying for a
fourth identical answer.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import brief as brief_module  # noqa: E402
import director  # noqa: E402
from test_decision import RAW, TAKES  # noqa: E402


@pytest.fixture
def project(tmp_path):
    # The shape the transcriber actually writes: an object carrying the run's
    # settings, with the word list under "words". A fixture that wrote a bare
    # array let brief.py ship with its own reader that could not open a real
    # transcript, and the director stage died on the first one it was given.
    words = [{"word": w.word, "start": w.start, "end": w.end,
              "probability": w.probability} for w in RAW]
    transcript = tmp_path / "raw.words.json"
    transcript.write_text(json.dumps({
        "source": str(tmp_path / "raw.mp4"),
        "model": "large-v3",
        "language": "sv",
        "duration": RAW[-1].end,
        "word_count": len(words),
        "segments": [],
        "words": words,
    }), encoding="utf-8")
    (tmp_path / "pipeline.json").write_text(
        json.dumps({"source": str(tmp_path / "raw.mp4"),
                    "raw_transcript": str(transcript)}), encoding="utf-8")
    return tmp_path


def state_of(project: Path) -> dict:
    return json.loads((project / "pipeline.json").read_text(encoding="utf-8"))


RULES = (Path(__file__).resolve().parent / "DIRECTOR.md").read_text(encoding="utf-8")


# --- the brief ---------------------------------------------------------------

def test_the_brief_numbers_every_take(project):
    text = brief_module.build(project, state_of(project), RULES)
    for take in TAKES:
        assert take.text in text
        assert f"| {take.index} |" in text


def test_the_brief_carries_the_machine_verdict_to_disagree_with(project):
    text = brief_module.build(project, state_of(project), RULES)
    assert "machine says" in text and "keeper" in text


def test_the_brief_lists_the_overlay_kinds_from_the_renderers_own_types(project):
    """Restating them here would drift, and a director working from a stale
    list writes cues that resolve and render as nothing."""
    text = brief_module.build(project, state_of(project), RULES)
    assert "OverlayKind" in text and "dualGraph" in text


def test_the_brief_says_when_there_is_no_footage_to_cut_to(project):
    text = brief_module.build(project, state_of(project), RULES)
    assert "assets/` is empty" in text


def test_the_brief_lists_the_footage_there_is(project):
    (project / "assets" / "broll").mkdir(parents=True)
    (project / "assets" / "broll" / "hemsidor.mp4").write_bytes(b"x")
    text = brief_module.build(project, state_of(project), RULES)
    assert "broll/hemsidor.mp4" in text


def test_the_brief_carries_the_rules_so_they_can_be_edited_in_one_place(project):
    text = brief_module.build(project, state_of(project), RULES)
    assert "Every take gets a decision" in text


# --- the loop ----------------------------------------------------------------

def complete():
    return {"throughline": "t",
            "keep": [{"beat": "HOOK", "takes": [0, 1, 2], "why": "w"}],
            "drop": [], "overlays": [], "hook": {"pick": 1, "why": "w"}}


def incomplete():
    return {"throughline": "t",
            "keep": [{"beat": "HOOK", "takes": [0], "why": "w"}],
            "drop": [], "overlays": [], "hook": {"pick": 1, "why": "w"}}


def test_a_passing_answer_is_taken_on_the_first_call(project):
    calls = []

    def asker(prompt, model):
        calls.append(prompt)
        return complete()

    decision, problems, how = director.direct(
        project, state_of(project), asker=asker)
    assert problems == [] and len(calls) == 1
    assert "attempt 1" in how


def test_a_failed_check_is_handed_back_in_the_next_prompt(project):
    calls = []

    def asker(prompt, model):
        calls.append(prompt)
        return incomplete() if len(calls) == 1 else complete()

    decision, problems, _ = director.direct(
        project, state_of(project), asker=asker)
    assert problems == []
    assert len(calls) == 2
    assert "did not pass these checks" in calls[1]
    assert "neither `keep` nor `drop`" in calls[1]


def test_the_loop_gives_up_rather_than_paying_for_a_fourth_try(project):
    calls = []

    def asker(prompt, model):
        calls.append(prompt)
        return incomplete()

    decision, problems, how = director.direct(
        project, state_of(project), asker=asker, attempts=3)
    assert len(calls) == 3
    assert problems and "still failing" in how


def test_the_last_answer_is_kept_even_when_it_fails(project):
    """The reasoning is the part worth reading when the cut looks wrong, so a
    failing decision is shown rather than thrown away."""
    decision, problems, _ = director.direct(
        project, state_of(project), asker=lambda p, m: incomplete(), attempts=1)
    assert decision["keep"] and problems


def test_writing_produces_the_two_files_the_pipeline_reads(project):
    decision = complete()
    decision["overlays"] = [{"kind": "wordStack", "cue": "planering",
                             "why": "shows the word"}]
    summary = director.write(project, decision, state_of(project))
    beats = json.loads((project / "edit-script.json").read_text(encoding="utf-8"))
    sheet = json.loads((project / "overlays.json").read_text(encoding="utf-8"))
    assert len(beats) == summary["beats"] == 3
    assert sheet == [{"kind": "wordStack", "cue": "planering"}]


def test_no_overlay_sheet_is_written_when_there_are_no_overlays(project):
    """Three of the ten reference reels have no overlays at all; an empty sheet
    left behind would be read as one that failed to resolve."""
    director.write(project, complete(), state_of(project))
    assert not (project / "overlays.json").exists()


# --- the call itself ---------------------------------------------------------

def test_the_prompt_goes_in_on_stdin_not_on_the_command_line():
    """cmd.exe refuses a command line over 8191 characters, and a brief for a
    one-minute recording is 12k. This failed only on Windows."""
    import inspect
    source = inspect.getsource(director.ask)
    assert "input=prompt" in source
    assert '"-p", prompt' not in source


def test_what_stays_on_the_command_line_fits_in_cmd_exes_limit():
    """The schema still has to be an argument -- the CLI rejects a file path
    for it -- so it is the one thing worth measuring."""
    import json
    from decision import SCHEMA
    assert len(json.dumps(SCHEMA)) < 6000, (
        "the schema is approaching cmd.exe's 8191-character command line")


def test_the_director_is_given_no_tools():
    """An answer that depends on what the model happened to open is not
    reproducible, and every input it needs is already in the brief."""
    import inspect
    source = inspect.getsource(director.ask)
    assert "--disallowedTools" in source
    assert "--json-schema" in source
    # Also the cheapest line in the call: the MCP tool definitions were 10k
    # tokens of a 38k call that uses no tools.
    assert "--strict-mcp-config" in source


def test_a_missing_cli_says_both_ways_out(monkeypatch):
    monkeypatch.setattr(director.shutil, "which", lambda name: None)
    with pytest.raises(director.DirectorUnavailable) as raised:
        director.claude_cli()
    assert "--brief-only" in str(raised.value)
    assert "npm install" in str(raised.value)


def test_writing_turns_on_measuring_against_the_audio(project):
    """The ranges come from word timestamps, and that clock drifts. Leaving
    retime off ships a cut that clips the last word of every late beat."""
    from state import load as load_state
    director.write(project, complete(), state_of(project))
    assert load_state(project).retime is True


def test_a_new_edit_script_rewinds_a_finished_pipeline(project, capsys):
    """Directing a project that had already rendered left the stage at `done`,
    so the next `run` said "already finished" and the old video stood."""
    import json as _json
    from state import Stage, load as load_state

    state_file = project / "pipeline.json"
    stored = _json.loads(state_file.read_text(encoding="utf-8"))
    stored["stage"] = Stage.DONE.value
    state_file.write_text(_json.dumps(stored), encoding="utf-8")

    director.write(project, complete(), state_of(project))
    assert load_state(project).stage_enum is Stage.THROUGHLINE_APPROVED
    assert "Rewound to the cut list" in capsys.readouterr().out


def test_a_project_already_at_the_cut_list_is_not_told_it_was_rewound(project, capsys):
    director.write(project, complete(), state_of(project))
    capsys.readouterr()
    director.write(project, complete(), state_of(project))
    assert "Rewound" not in capsys.readouterr().out


# --- reading a hand edit back ------------------------------------------------

def test_a_hand_edit_is_reported_as_what_changed():
    """A director that keeps being overruled the same way is a rule nobody has
    written down yet. Overruling it in an editor leaves no trace unless this
    goes looking."""
    decision = {"keep": [{"beat": "HOOK", "takes": [0, 1], "why": "w"}]}
    shipped = [{"beat": "HOOK.T0"}, {"beat": "LANDING.T5"}]
    notes = director.drift(decision, shipped)
    assert any("cut 1 take" in n and "1" in n for n in notes)
    assert any("put back 1 take" in n and "5" in n for n in notes)


def test_an_unchanged_edit_says_so():
    decision = {"keep": [{"beat": "HOOK", "takes": [0]}]}
    assert director.drift(decision, [{"beat": "HOOK.T0"}]) == [
        "Nothing changed -- the decision shipped as it was."]


def test_a_script_with_no_take_numbers_cannot_be_read_back():
    decision = {"keep": [{"beat": "HOOK", "takes": [0]}]}
    notes = director.drift(decision, [{"beat": "HOOK", "start": 1, "end": 2}])
    assert any("cannot be read back" in n for n in notes)


def test_the_reader_is_the_one_the_rest_of_the_pipeline_uses(project):
    """Not a second copy that assumes a different file shape."""
    import cutlist
    assert brief_module.read_words is cutlist.read_words

    from pipeline import read_words as pipeline_read_words
    assert pipeline_read_words is cutlist.read_words


def test_the_call_says_it_is_working_before_it_blocks(project, capsys):
    """It printed nothing for several minutes, which is indistinguishable from
    a hang -- and an operator kills a hang."""
    director.direct(project, state_of(project), asker=lambda p, m: complete())
    out = capsys.readouterr().out
    assert "takes with Claude" in out and "a few minutes" in out


def test_a_timeout_is_reported_rather_than_raised_as_a_traceback(monkeypatch):
    import subprocess as sp

    def explode(*a, **k):
        raise sp.TimeoutExpired(cmd="claude", timeout=600)

    monkeypatch.setattr(director.shutil, "which", lambda name: "claude")
    monkeypatch.setattr(director.subprocess, "run", explode)
    with pytest.raises(director.DirectorUnavailable) as raised:
        director.ask("brief", "sonnet")
    assert "did not answer within 600s" in str(raised.value)
    assert "--brief-only" in str(raised.value)


def test_the_brief_says_what_each_overlay_is_for_not_only_its_fields(project):
    """types.ts lists fields. Given only that, a flash was cued to emphasise a
    word -- but a flash is white and exists to cover a cut."""
    text = brief_module.build(project, state_of(project), RULES)
    assert "What each one is for" in text
    assert "covers the cut underneath it" in text


def test_every_drawing_component_contributes_its_purpose():
    blocks = brief_module.purposes()
    for name in ("Flash", "ChipRow", "DualGraph", "Terminal", "WordStack"):
        assert f"**{name}**" in blocks
    assert "**Overlays**" not in blocks, "the dispatcher is not a kind"


def test_a_cut_longer_than_any_reference_reel_says_so(capsys):
    """The number was printed with nothing beside it, so 82s read the same as
    30s. The comparison is the measured reels, not an invented band."""
    director.report({}, {"beats": 21, "seconds": 82.3, "overlays": 3}, [])
    assert "longer than the longest" in capsys.readouterr().out


def test_a_cut_inside_the_measured_range_says_nothing_extra(capsys):
    """69s looked over-long against the invented 25-60 band. The longest
    reference reel is 70s, so it is not."""
    director.report({}, {"beats": 18, "seconds": 69.2, "overlays": 1}, [])
    assert "longer than" not in capsys.readouterr().out


def test_the_target_band_is_the_measured_one():
    assert brief_module.TARGET_SECONDS == (23.0, 70.0)


# --- where the transcript is not to be trusted -------------------------------

def swallowed_project(tmp_path):
    """A recording with one impossibly long word: three discarded attempts that
    Whisper smoothed away without writing them down."""
    words = [{"word": " Det", "start": 0.0, "end": 0.3, "probability": 0.9},
             {"word": " har", "start": 0.3, "end": 0.6, "probability": 0.9},
             {"word": " ar", "start": 0.6, "end": 0.9, "probability": 0.9},
             # 5.5s for one word. There are takes inside this.
             {"word": " det", "start": 0.9, "end": 6.4, "probability": 0.9},
             {"word": " tre", "start": 6.4, "end": 6.7, "probability": 0.9},
             {"word": " stegen.", "start": 6.7, "end": 7.1, "probability": 0.9}]
    (tmp_path / "raw.words.json").write_text(json.dumps({
        "source": str(tmp_path / "raw.mp4"), "duration": 7.1,
        "word_count": len(words), "segments": [], "words": words,
    }), encoding="utf-8")
    (tmp_path / "pipeline.json").write_text(json.dumps({
        "source": str(tmp_path / "raw.mp4"),
        "raw_transcript": str(tmp_path / "raw.words.json")}), encoding="utf-8")
    return tmp_path


def test_the_brief_marks_where_speech_was_never_transcribed(tmp_path):
    """Unclamped, vas3's hook read as four takes -- one of them a single word
    over 5.7 seconds -- and the director chained all four."""
    project = swallowed_project(tmp_path)
    text = brief_module.build(project, state_of(project), RULES)
    assert "SPEECH NOT TRANSCRIBED HERE" in text
    assert "Whisper never wrote down" in text


def test_the_brief_splits_takes_where_the_cutter_will_split_them(tmp_path):
    """The brief has to describe the takes that will actually be produced, so
    it clamps exactly as the cutter clamps."""
    project = swallowed_project(tmp_path)
    words = brief_module.read_words(project / "raw.words.json")
    from sentences import analyse
    unclamped = brief_module.takes(words, analyse(words))
    from cutlist import clamp_slack
    clamped_words, _ = clamp_slack(words)
    clamped = brief_module.takes(clamped_words, analyse(clamped_words))
    assert len(clamped) > len(unclamped), (
        "clamping should expose the swallowed audio as a break")


# --- the saved animations ----------------------------------------------------

def test_the_brief_offers_the_animations_that_already_work(project):
    """A director given only a vocabulary invents a new combination every
    video, and the fifth video stops looking like the first."""
    text = brief_module.build(project, state_of(project), RULES)
    assert "Animations that already work" in text
    assert "Upcoming steps, blurred" in text
    assert "Files, named one at a time" in text


def test_every_saved_animation_is_a_cue_the_renderer_knows():
    """A catalogue entry naming a kind that does not exist is worse than no
    catalogue: it reads as permission."""
    import json as _json
    from decision import KINDS
    for path in sorted(brief_module.CATALOGUE.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        for field in ("title", "what", "when", "seen_in", "cue", "preview"):
            assert field in entry, f"{path.name} has no {field}"
        assert entry["cue"]["kind"] in KINDS, path.name


def test_every_saved_animation_has_a_preview_rendered_from_it():
    """The picture is the point: an animation you cannot see is a paragraph.

    The one exemption is an animation drawn from a project's own files -- a
    row of logos, say. Those do not live here, so there is nothing to render
    it over, and the catalogue says as much in place of the picture.
    """
    import animate

    for path in sorted(brief_module.CATALOGUE.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        gif = path.with_suffix(".gif")
        if animate.unrendered(entry):
            assert not gif.is_file(), f"{path.stem} has a preview after all"
            continue
        assert gif.is_file(), f"{path.stem} has no preview -- run animate.py"
        assert gif.stat().st_size > 1024


def test_the_brief_and_the_validator_count_the_same_takes(project):
    """The one cross-check between the two halves.

    build() clamped the words before splitting takes and director.py did not,
    so the table a director read had rows the validator would reject. It came
    back as "take 27 does not exist" three attempts running, while row 27 sat
    in the brief it had just been handed.
    """
    import re
    words = brief_module.read_words(project / "raw.words.json")
    counted = brief_module.take_list(words)

    text = brief_module.build(project, state_of(project), RULES)
    rows = [int(m) for m in re.findall(r"^\| (\d+) \|", text, re.M)]
    assert rows, "no take rows in the brief"
    assert rows == list(range(len(counted))), (
        "the brief numbers takes differently from the list validate() checks")
    assert f"{len(counted)} takes" in text


def test_every_take_the_brief_shows_can_be_kept(project):
    """A decision naming every row of the table has to pass."""
    from decision import validate
    words = brief_module.read_words(project / "raw.words.json")
    counted = brief_module.take_list(words)
    decision = {
        "throughline": "t",
        "keep": [{"beat": "ALL", "takes": [t.index for t in counted], "why": "w"}],
        "drop": [], "overlays": [], "hook": {"pick": 0, "why": "w"},
    }
    assert validate(decision, counted) == []


def test_words_in_no_take_are_still_shown(tmp_path):
    """sentence_ranges drops a piece under a quarter second, and the words go
    with it -- so a sentence that reads as unfinished in the table may simply
    have continued somewhere the table never showed."""
    words = [{"word": " Jag", "start": 0.0, "end": 0.3, "probability": 0.9},
             {"word": " borjade", "start": 0.3, "end": 0.7, "probability": 0.9},
             {"word": " nu.", "start": 0.7, "end": 1.0, "probability": 0.9},
             # A 0.1s island between two long silences: too short to cut from.
             {"word": " ah", "start": 4.0, "end": 4.1, "probability": 0.9},
             {"word": " Sen", "start": 8.0, "end": 8.4, "probability": 0.9},
             {"word": " kom", "start": 8.4, "end": 8.8, "probability": 0.9},
             {"word": " det.", "start": 8.8, "end": 9.2, "probability": 0.9}]
    (tmp_path / "raw.words.json").write_text(json.dumps({
        "source": str(tmp_path / "raw.mp4"), "duration": 9.2,
        "word_count": len(words), "segments": [], "words": words,
    }), encoding="utf-8")
    (tmp_path / "pipeline.json").write_text(json.dumps({
        "source": str(tmp_path / "raw.mp4"),
        "raw_transcript": str(tmp_path / "raw.words.json")}), encoding="utf-8")

    text = brief_module.build(tmp_path, state_of(tmp_path), RULES)
    covered = brief_module.take_list(
        brief_module.read_words(tmp_path / "raw.words.json"))
    assert all("ah" not in take.text for take in covered), (
        "this fixture is meant to orphan a word")
    assert "Said, but in no take" in text
    assert "`ah`" in text


def test_nothing_is_said_when_every_word_is_in_a_take(project):
    text = brief_module.build(project, state_of(project), RULES)
    assert "Said, but in no take" not in text


def test_the_smeared_windows_stop_at_the_end_of_the_recording():
    """With no silence after the last word, a window reaching past the end
    reports a run carrying on into nothing."""
    from brief import Take, smeared_windows
    take = Take(index=0, sentence=0, start=8.0, end=9.0, text="x", words=[],
                part=(1, 1), swallowed=True)
    assert smeared_windows([take], ends=9.0) == [(2.0, 9.0)]


def test_a_clean_recording_gets_no_audio_section():
    from brief import Take, smeared_windows
    take = Take(index=0, sentence=0, start=0.0, end=1.0, text="x", words=[],
                part=(1, 1), swallowed=False)
    assert smeared_windows([take]) == []
