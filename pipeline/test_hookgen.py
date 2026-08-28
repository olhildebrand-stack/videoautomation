"""Tests for on-screen hook matching.

The rule under test throughout: a card is MATCHED from the on-screen bank,
never written. The bank is prose, so the match itself is a judgement and is
not tested here -- what is tested is the boundary around it, and every one of
these exists because that boundary is the only thing standing between "only
these" as a paragraph and "only these" as a fact.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import hookgen  # noqa: E402
from hookgen import (  # noqa: E402
    BANK, BankUnavailable, Candidate, as_dicts, generate, in_bank, load_topic,
    prompt, render_file,
)

BANKLET = """\
Replaced My Marketing Agency with Claude Code
the clawbot setup nobody is talking about...
"I'M NOT GETTING ENOUGH CUSTOMERS IN MY STORE"
"""


def answer(monkeypatch, payload):
    """Stand in for the Claude call, recording the prompt it was given."""
    seen = {}

    def fake(prompt_text, model, schema=None, system="", timeout=600.0):
        seen["prompt"] = prompt_text
        return payload

    monkeypatch.setattr(hookgen, "ask", fake)
    return seen


ONE = {"nothing_fits": False, "candidates": [
    {"text": "Ersatte min videoredigerare med Claude",
     "source": "Replaced My Marketing Agency with Claude Code",
     "changed": "Bytte 'Marketing Agency' mot 'videoredigerare'"}]}


# --- topic.txt --------------------------------------------------------------

def test_a_missing_topic_file_is_blank_not_an_error(tmp_path):
    assert load_topic(tmp_path) == ""


def test_the_comments_in_the_seed_are_not_the_topic(tmp_path):
    """The seed is all comments. Read naively it becomes the topic, and the
    match is then against instructions for the operator."""
    (tmp_path / "topic.txt").write_text(hookgen.SEED_TOPIC, encoding="utf-8")
    assert load_topic(tmp_path) == ""


def test_the_prose_survives_the_comments(tmp_path):
    (tmp_path / "topic.txt").write_text(
        "# what is it about\nEtt system som klipper video.\n", encoding="utf-8")
    assert load_topic(tmp_path) == "Ett system som klipper video."


# --- only these -------------------------------------------------------------

def test_a_source_in_the_bank_is_recognised():
    assert in_bank("Replaced My Marketing Agency with Claude Code", BANKLET)


def test_quotes_and_spacing_are_not_the_difference_worth_rejecting_over():
    """A quoted-caps source comes back sometimes with its quotes and sometimes
    without. That is not an invented hook."""
    assert in_bank("I'M NOT GETTING ENOUGH CUSTOMERS IN MY STORE", BANKLET)
    assert in_bank('"replaced   my marketing agency with claude code"', BANKLET)


def test_a_source_that_is_not_in_the_bank_is_not_recognised():
    assert not in_bank("Replaced My Video Editor With A Prompt", BANKLET)


def test_an_invented_hook_is_refused(monkeypatch):
    """The one failure this stage exists to prevent: a hook that was written
    and then presented as matched."""
    answer(monkeypatch, {"nothing_fits": False, "candidates": [
        {"text": "Nåt nytt", "source": "A hook nobody has ever run",
         "changed": "everything"}]})
    with pytest.raises(BankUnavailable, match="not in the bank"):
        generate("", "", bank=BANKLET)


# --- the shortlist ----------------------------------------------------------

def test_a_match_comes_back_carrying_what_it_came_from(monkeypatch):
    answer(monkeypatch, ONE)
    got = generate("", "", bank=BANKLET)
    assert got == [Candidate("Ersatte min videoredigerare med Claude",
                             "Replaced My Marketing Agency with Claude Code",
                             "Bytte 'Marketing Agency' mot 'videoredigerare'")]


def test_nothing_fitting_is_an_empty_shortlist_not_a_bent_hook(monkeypatch):
    answer(monkeypatch, {"nothing_fits": True, "candidates": [
        {"text": "whatever", "source": "Replaced My Marketing Agency with "
                                       "Claude Code", "changed": "x"}]})
    assert generate("", "", bank=BANKLET) == []


def test_more_offered_than_asked_for_is_trimmed(monkeypatch):
    answer(monkeypatch, {"nothing_fits": False, "candidates":
                         ONE["candidates"] * 4})
    assert len(generate("", "", count=2, bank=BANKLET)) == 2


# --- what the matcher is given ----------------------------------------------

def test_the_bank_is_in_the_prompt(monkeypatch):
    seen = answer(monkeypatch, ONE)
    generate("", "", bank=BANKLET)
    assert BANKLET in seen["prompt"]


def test_the_cut_and_the_topic_are_both_in_the_prompt(monkeypatch):
    """A recording can spend ninety seconds on a system without naming one
    tool it is built from, which is why the transcript alone is not enough."""
    seen = answer(monkeypatch, ONE)
    generate("Jag byggde nåt.", "Ett system som klipper video.", bank=BANKLET)
    assert "Jag byggde nåt." in seen["prompt"]
    assert "Ett system som klipper video." in seen["prompt"]


def test_the_count_asked_for_reaches_the_prompt(monkeypatch):
    seen = answer(monkeypatch, ONE)
    generate("", "", count=9, bank=BANKLET)
    assert "9" in seen["prompt"]


# --- hooks.txt --------------------------------------------------------------

def test_only_the_first_line_renders():
    text = render_file([Candidate("Först", "S1", "c1"),
                        Candidate("Andra", "S2", "c2")])
    live = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    assert live == ["Först"]


def test_every_option_is_recoverable_with_its_source():
    text = render_file([Candidate("Först", "S1", "c1"),
                        Candidate("Andra", "S2", "c2")])
    for bit in ("Först", "Andra", "S1", "S2", "c1", "c2"):
        assert bit in text


def test_the_shortlist_survives_being_put_in_state():
    assert as_dicts([Candidate("a", "b", "c")]) == [
        {"sv": "a", "source": "b", "changed": "c"}]


# --- the bank itself --------------------------------------------------------

def test_every_worked_example_quotes_a_source_the_bank_lists():
    """The bank's own examples are the reference for the method, so an example
    citing a source that is not in the source list is the bank drifting."""
    text = BANK.read_text(encoding="utf-8")
    sources, examples = text.split("== The 45 ==")
    for line in examples.splitlines():
        if line.strip().startswith("from:"):
            assert in_bank(line.split("from:", 1)[1].strip(), sources)
