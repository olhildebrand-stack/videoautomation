"""Tests for hook matching.

The rule under test throughout: hooks are MATCHED from the winning-hooks bank,
never written, and a swap costs words against a hard limit of three.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from hookgen import (  # noqa: E402
    BANK, MAX_WORDS_CHANGED, Topic, apply_slots, generate, load_bank,
    parse_topic, real_change, render_file, substitutions,
)

# The recording this pipeline was built on. Note what it never says: not
# "Claude Code", not "Remotion", not the name of a single tool. That absence is
# the whole reason topic.txt exists.
TRANSCRIPT = (
    "Jag håller på att bygga ett system som kommer sätta varenda short form "
    "content editor i konkurs. Och jag kommer använda det här kontot som "
    "testkanin. Det jag ska försöka åstadkomma med det här systemet är att jag "
    "ska bara filma en video och sen ska jag skicka in den. Och så kommer det "
    "ut en fullbordad video. Den ska ha klipp, den ska ha captions, color "
    "correction, den ska ha b-roll, den ska ha allting. Och ingenting ska jag "
    "behöva göra själv. Så inte bara kommer kvaliteten på min content höjas. "
    "Utan jag kommer också behöva göra mycket mindre för att få ut min content."
)

TOPIC = parse_topic(
    "tools    : Claude Code, Remotion\n"
    "subject  : videoredigering | video editing\n"
    "makes    : klipp | Videos\n"
    "replaces : videoredigerare | Video Editor\n"
    "about    : automating short form video editing end to end\n"
)


# --- the bank ---------------------------------------------------------------

def test_all_38_hooks_are_present_and_numbered():
    assert [h["n"] for h in load_bank()] == list(range(1, 39))


@pytest.mark.parametrize("hook", load_bank(), ids=lambda h: str(h["n"]))
def test_every_hook_has_both_renderings_and_tags(hook):
    assert hook["en"].strip()
    assert hook["sv"].strip()
    assert hook["tags"]


@pytest.mark.parametrize("hook", load_bank(), ids=lambda h: str(h["n"]))
def test_slot_text_appears_in_both_renderings(hook):
    """A slot that cannot be found is a slot that silently never fires."""
    for slot in hook.get("slots", []):
        assert slot["en"] in hook["en"]
        assert slot["sv"] in hook["sv"]
        assert slot["words"] <= MAX_WORDS_CHANGED


def test_bank_carries_its_own_documentation():
    assert "_readme" in json.loads(Path(BANK).read_text(encoding="utf-8"))


# --- topic.txt --------------------------------------------------------------

def test_topic_reads_every_field():
    assert TOPIC.tools == ["Claude Code", "Remotion"]
    assert TOPIC.replaces == ("videoredigerare", "Video Editor")
    assert TOPIC.makes == ("klipp", "Videos")
    assert "short form" in TOPIC.about


def test_comments_and_blank_values_are_ignored():
    topic = parse_topic("# tools: Nope\ntools:\nabout : real\n")
    assert topic.tools == []
    assert topic.about == "real"


def test_the_english_half_is_optional():
    """Without a '|' the Swedish stands for both -- right for a proper noun,
    harmless for anything else."""
    assert parse_topic("replaces: Remotion\n").replaces == ("Remotion", "Remotion")


# --- substitution -----------------------------------------------------------

@pytest.mark.parametrize("slot,fill,expected", [
    # Spending two of the three words to turn "Viral Videos" into "Videos"
    # buys nothing but a weaker hook.
    ("Viral Videos", "Videos", False),
    ("Ads", "Meta Ads", False),
    ("Marketing Agency", "Video Editor", True),
    ("Obsidian", "Remotion", True),
])
def test_a_containing_term_is_not_a_real_change(slot, fill, expected):
    assert real_change(slot, fill) is expected


def test_leaving_every_slot_alone_is_always_an_option():
    hook = next(h for h in load_bank() if h["n"] == 37)
    assert [] in substitutions(hook, TOPIC)


def test_applying_a_slot_changes_both_renderings():
    hook = next(h for h in load_bank() if h["n"] == 37)
    sv, en, changed = apply_slots(
        hook, [(hook["slots"][0], ("videoredigerare", "Video Editor"))]
    )
    assert sv == "Bytte ut min videoredigerare mot Claude Code"
    assert en == "Replaced My Video Editor with Claude Code"
    assert changed == 2


# --- ranking ----------------------------------------------------------------

def test_the_three_word_limit_is_never_exceeded():
    for c in generate(TRANSCRIPT, TOPIC, count=38):
        assert c.changed <= MAX_WORDS_CHANGED, c.sv


def test_every_candidate_traces_back_to_a_bank_hook():
    numbers = {h["n"] for h in load_bank()}
    assert all(c.source_n in numbers for c in generate(TRANSCRIPT, TOPIC, count=38))


def test_one_candidate_per_bank_hook_at_most():
    """Variants of a single hook must not crowd out the rest of the bank."""
    sources = [c.source_n for c in generate(TRANSCRIPT, TOPIC, count=38)]
    assert len(sources) == len(set(sources))


def test_count_is_respected():
    assert len(generate(TRANSCRIPT, TOPIC, count=3)) == 3


def test_the_top_match_is_the_one_that_changed_nothing():
    top = generate(TRANSCRIPT, TOPIC)[0]
    assert (top.source_n, top.changed) == (36, 0)
    assert top.sv == "Gör hur många virala klipp som helst med Claude Code"


def test_a_wrong_product_is_swapped_for_the_right_one():
    """[5] is 'Obsidian + Claude Code'. This video is not about Obsidian."""
    c = next(c for c in generate(TRANSCRIPT, TOPIC, count=38) if c.source_n == 5)
    assert c.sv == "Remotion + Claude Code är sjukt"
    assert c.changed == 1


def test_a_generic_noun_is_redirected_onto_this_video():
    c = next(c for c in generate(TRANSCRIPT, TOPIC, count=38) if c.source_n == 37)
    assert c.sv == "Bytte ut min videoredigerare mot Claude Code"
    assert c.changed == 2


def test_hooks_about_something_else_rank_below_hooks_about_this():
    ranked = [c.source_n for c in generate(TRANSCRIPT, TOPIC, count=38)]
    clawbot = next(n for n in (1, 4, 6, 7, 10) if n in ranked)
    assert ranked.index(clawbot) > ranked.index(36)


def test_without_a_topic_everything_offered_is_verbatim():
    """No topic.txt means nothing to swap in -- and zero words changed is the
    preferred outcome anyway, so the shortlist is still usable."""
    for c in generate(TRANSCRIPT, Topic()):
        assert c.changed == 0
        assert c.en == c.source_en


def test_an_empty_transcript_still_ranks_from_the_topic():
    candidates = generate("", TOPIC)
    assert candidates
    assert "Claude Code" in candidates[0].en


# --- hooks.txt --------------------------------------------------------------

def test_first_non_comment_line_is_the_top_match():
    candidates = generate(TRANSCRIPT, TOPIC)
    lines = [line for line in render_file(candidates).splitlines()
             if line.strip() and not line.startswith("#")]
    assert lines[0] == candidates[0].sv


def test_every_other_option_survives_as_a_comment():
    candidates = generate(TRANSCRIPT, TOPIC)
    text = render_file(candidates)
    assert all(f"# {c.sv}" in text for c in candidates[1:])
    assert all(f"[{c.source_n}]" in text for c in candidates)
