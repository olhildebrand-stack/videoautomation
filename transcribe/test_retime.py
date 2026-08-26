"""retime.py: moving one word the transcript placed wrong."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "retime.py"


def _doc(words):
    return {
        "words": words,
        "word_count": len(words),
        "segments": [{"id": 0, "start": words[0]["start"], "end": words[-1]["end"],
                      "text": "".join(w["word"] for w in words), "words": list(words)}],
    }


def _w(word, start, end):
    return {"word": word, "start": start, "end": end, "probability": 0.9}


def _run(path, *rest):
    return subprocess.run([sys.executable, str(SCRIPT), str(path), *rest],
                          capture_output=True, text=True, encoding="utf-8")


def _written(tmp_path, words):
    path = tmp_path / "clip.words.json"
    path.write_text(json.dumps(_doc(words)), encoding="utf-8")
    return path


WORDS = [_w(" AI", 0.0, 0.72), _w("-röstagenter", 0.72, 1.4), _w(" kan", 1.4, 1.6)]


def test_the_word_moves_and_the_file_is_written(tmp_path):
    path = _written(tmp_path, WORDS)
    done = _run(path, "--at", "0.0", "--start", "0.65", "--end", "0.72")
    assert done.returncode == 0, done.stderr
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["words"][0]["start"] == 0.65
    assert data["words"][0]["end"] == 0.72


def test_the_end_is_left_alone_unless_given(tmp_path):
    path = _written(tmp_path, WORDS)
    _run(path, "--at", "0.0", "--start", "0.65")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["words"][0]["end"] == 0.72


def test_the_segments_are_rebuilt_so_the_two_views_agree(tmp_path):
    path = _written(tmp_path, WORDS)
    _run(path, "--at", "0.0", "--start", "0.65")
    data = json.loads(path.read_text(encoding="utf-8"))
    in_segments = [w for s in data["segments"] for w in s["words"]]
    assert [w["start"] for w in in_segments] == [w["start"] for w in data["words"]]


def test_a_dry_run_writes_nothing(tmp_path):
    path = _written(tmp_path, WORDS)
    before = path.read_text(encoding="utf-8")
    done = _run(path, "--at", "0.0", "--start", "0.65", "--dry-run")
    assert done.returncode == 0
    assert path.read_text(encoding="utf-8") == before


def test_an_ambiguous_time_is_refused(tmp_path):
    """Two words cannot both be the one meant."""
    path = _written(tmp_path, [_w(" AI", 0.0, 0.3), _w(" AI", 0.0, 0.3)])
    done = _run(path, "--at", "0.0", "--start", "0.65")
    assert done.returncode == 2
    assert "2 words start at" in done.stderr


def test_a_time_no_word_has_is_refused(tmp_path):
    path = _written(tmp_path, WORDS)
    done = _run(path, "--at", "9.9", "--start", "0.65")
    assert done.returncode == 2
    assert "0 words start at" in done.stderr


def test_a_start_after_the_end_is_refused(tmp_path):
    path = _written(tmp_path, WORDS)
    done = _run(path, "--at", "0.0", "--start", "0.9")
    assert done.returncode == 2
    assert "not before" in done.stderr


def test_the_previous_transcript_is_kept(tmp_path):
    path = _written(tmp_path, WORDS)
    _run(path, "--at", "0.0", "--start", "0.65")
    assert (tmp_path / "clip.words.json.bak").is_file()
