"""Tests for reading a JSON file a person edited.

Why this exists: the operator put "retime": "end" on its own line without a
comma, twice, and got a six-frame traceback ending in a message that named
neither the file nor the line's contents.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from jsonfile import BadJSON, read  # noqa: E402

BROKEN = '''[
  {
    "beat": "HOOK",
    "start": 0.32,
    "end": 4.1,
    "retime": "end"
    "line": "Min Claude redigerar mina videos."
  }
]
'''


def written(tmp_path, text, name="edit-script.json"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_good_json_is_returned(tmp_path):
    assert read(written(tmp_path, '[{"beat": "HOOK"}]')) == [{"beat": "HOOK"}]


def test_a_bom_is_tolerated(tmp_path):
    """PowerShell's Set-Content writes one."""
    path = tmp_path / "x.json"
    path.write_text('{"a": 1}', encoding="utf-8-sig")
    assert read(path) == {"a": 1}


def test_a_missing_comma_names_the_file(tmp_path):
    path = written(tmp_path, BROKEN)
    with pytest.raises(BadJSON) as raised:
        read(path, "edit script")
    assert str(path) in str(raised.value)


def test_it_shows_the_line_before_because_that_is_where_the_mistake_is(tmp_path):
    with pytest.raises(BadJSON) as raised:
        read(written(tmp_path, BROKEN))
    message = str(raised.value)
    assert '"retime": "end"' in message, "the offending line is not shown"
    assert '"line": "Min Claude' in message, "the line it complained at is not shown"


def test_it_says_what_to_fix(tmp_path):
    with pytest.raises(BadJSON) as raised:
        read(written(tmp_path, BROKEN))
    assert "missing comma" in str(raised.value)


def test_a_trailing_comma_is_named_too(tmp_path):
    with pytest.raises(BadJSON) as raised:
        read(written(tmp_path, '[{"a": 1},]'))
    assert "trailing comma" in str(raised.value)


def test_a_missing_file_says_which(tmp_path):
    with pytest.raises(BadJSON) as raised:
        read(tmp_path / "nope.json", "overlay sheet")
    assert "no overlay sheet at" in str(raised.value)


def test_every_hand_edited_file_is_read_through_this():
    """An edit script, an overlay sheet and a decision are all typed by hand.
    A second reader would report a missing comma the old way."""
    here = Path(__file__).resolve().parent
    for module, name in (("pipeline.py", "edit script"),
                         ("cues.py", "overlay sheet"),
                         ("director.py", "decision")):
        text = (here / module).read_text(encoding="utf-8")
        assert "read_json" in text, f"{module} does not use the shared reader"
