"""Tests for the GPU->CPU fallback. No model download required."""

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import transcribe as t


# --- stubs -----------------------------------------------------------------

class StubWord:
    def __init__(self, word, start, end, prob):
        self.word, self.start, self.end, self.probability = word, start, end, prob


class StubSegment:
    def __init__(self):
        self.id, self.start, self.end = 0, 0.0, 1.5
        self.text = " Hej och välkommen."
        self.words = [
            StubWord(" Hej", 0.0, 0.4, 0.98),
            StubWord(" och", 0.4, 0.7, 0.95),
            StubWord(" välkommen.", 0.7, 1.5, 0.91),
        ]


class StubInfo:
    language = "sv"
    language_probability = 0.99
    duration = 1.5
    duration_after_vad = 1.4


class StubModel:
    def transcribe(self, *args, **kwargs):
        self.kwargs = kwargs
        return iter([StubSegment()]), StubInfo()


# --- is_gpu_failure ---------------------------------------------------------

@pytest.mark.parametrize("msg", [
    "CUDA failed with error CUDA driver version is insufficient for CUDA runtime version",
    "Library cudnn_ops64_9.dll is not found",
    "cuBLAS failed with status CUBLAS_STATUS_NOT_INITIALIZED",
    "CUDA out of memory",
    "no kernel image is available for execution on the device",
])
def test_gpu_failures_are_recognised(msg):
    assert t.is_gpu_failure(RuntimeError(msg))


@pytest.mark.parametrize("exc", [
    FileNotFoundError("no such file: clip.mp4"),
    ValueError("Invalid beam_size"),
])
def test_unrelated_failures_are_not_gpu_failures(exc):
    assert not t.is_gpu_failure(exc)


# --- fallback flow ----------------------------------------------------------

def test_falls_back_to_cpu_when_cuda_load_fails(monkeypatch, tmp_path, capsys):
    attempts = []

    def fake_load(model_size, device, compute_type, download_root):
        attempts.append((device, compute_type))
        if device == "cuda":
            raise RuntimeError("CUDA failed with error CUDA driver version is insufficient")
        return StubModel()

    monkeypatch.setattr(t, "load_model", fake_load)
    result, backend = t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)

    assert attempts == [("cuda", "float16"), ("cpu", "int8")]
    assert backend.is_fallback
    assert result["device"] == "cpu" and result["compute_type"] == "int8"
    assert result["used_fallback"] is True
    assert "Falling back to CPU/int8" in capsys.readouterr().err


def test_falls_back_when_cuda_fails_at_first_decode(monkeypatch, tmp_path):
    """A missing cuDNN loads fine and only fails once a kernel runs."""

    class ExplodingModel:
        def transcribe(self, *args, **kwargs):
            def gen():
                raise RuntimeError("Library cudnn_ops64_9.dll is not found")
                yield  # pragma: no cover
            return gen(), StubInfo()

    def fake_load(model_size, device, compute_type, download_root):
        return ExplodingModel() if device == "cuda" else StubModel()

    monkeypatch.setattr(t, "load_model", fake_load)
    result, backend = t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)
    assert backend.is_fallback and result["used_fallback"] is True


def test_non_gpu_error_is_raised_not_downgraded(monkeypatch, tmp_path):
    def fake_load(model_size, device, compute_type, download_root):
        raise ValueError("something unrelated broke")

    monkeypatch.setattr(t, "load_model", fake_load)
    with pytest.raises(ValueError):
        t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)


def test_gpu_path_used_when_it_works(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "load_model", lambda *a, **k: StubModel())
    result, backend = t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)
    assert not backend.is_fallback
    assert result["device"] == "cuda" and result["compute_type"] == "float16"


def test_cpu_flag_skips_cuda_entirely(monkeypatch, tmp_path):
    attempts = []

    def fake_load(model_size, device, compute_type, download_root):
        attempts.append(device)
        return StubModel()

    monkeypatch.setattr(t, "load_model", fake_load)
    t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=True)
    assert attempts == ["cpu"]


# --- required options actually reach faster-whisper -------------------------

def test_required_transcribe_options_are_passed(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)
    assert model.kwargs["language"] == "sv"
    assert model.kwargs["vad_filter"] is True
    assert model.kwargs["word_timestamps"] is True


# --- output shape -----------------------------------------------------------

def test_output_has_flat_and_nested_word_timestamps(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "load_model", lambda *a, **k: StubModel())
    result, _ = t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)

    assert result["word_count"] == 3
    assert [w["word"] for w in result["words"]] == [" Hej", " och", " välkommen."]
    assert result["words"][2]["start"] == 0.7
    assert result["segments"][0]["words"] == result["words"]
    # Swedish characters must survive the JSON round-trip unescaped.
    dumped = json.dumps(result, ensure_ascii=False)
    assert "välkommen" in dumped


# --- CUDA DLL discovery (Windows) ------------------------------------------

def test_find_cuda_dll_dirs_picks_up_wheel_layout(tmp_path):
    """The nvidia-*-cu12 wheels drop DLLs in site-packages/nvidia/<pkg>/bin."""
    for pkg in ("cublas", "cudnn"):
        d = tmp_path / "nvidia" / pkg / "bin"
        d.mkdir(parents=True)
        (d / f"{pkg}64_12.dll").write_bytes(b"")

    found = t.find_cuda_dll_dirs(str(tmp_path))
    assert [p.parent.name for p in found] == ["cublas", "cudnn"]


def test_find_cuda_dll_dirs_skips_dirs_without_dlls(tmp_path):
    (tmp_path / "nvidia" / "empty" / "bin").mkdir(parents=True)
    assert t.find_cuda_dll_dirs(str(tmp_path)) == []


def test_find_cuda_dll_dirs_handles_missing_nvidia_tree(tmp_path):
    assert t.find_cuda_dll_dirs(str(tmp_path)) == []


def test_register_is_a_noop_off_windows(monkeypatch):
    monkeypatch.setattr(t.sys, "platform", "linux")
    assert t.register_cuda_dll_dirs() == []


# --- language selection -----------------------------------------------------

def test_language_defaults_to_swedish(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "clip.mp4", "large-v3", 5, None, force_cpu=False)
    assert model.kwargs["language"] == "sv"


def test_language_can_be_overridden(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "clip.mp4", "large-v3", 5, None, False, language="en")
    assert model.kwargs["language"] == "en"


def test_language_none_means_autodetect(monkeypatch, tmp_path):
    """faster-whisper detects the language when language=None."""
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "clip.mp4", "large-v3", 5, None, False, language=None)
    assert model.kwargs["language"] is None


# --- PATH prepending (the lazy-LoadLibrary fix) -----------------------------

def test_prepend_to_path_puts_dirs_first(tmp_path):
    # Entries avoid ':' so the test is valid on either platform's os.pathsep.
    env = {"PATH": f"existing{t.os.pathsep}other"}
    t.prepend_to_path([tmp_path / "cublas" / "bin", tmp_path / "cudnn" / "bin"], env)
    parts = env["PATH"].split(t.os.pathsep)
    assert parts[0].endswith("bin") and parts[1].endswith("bin")
    assert parts[-2:] == ["existing", "other"]


def test_prepend_to_path_handles_empty_path(tmp_path):
    env = {}
    t.prepend_to_path([tmp_path / "cublas" / "bin"], env)
    assert env["PATH"] == str(tmp_path / "cublas" / "bin")
    assert not env["PATH"].startswith(t.os.pathsep)


def test_prepend_to_path_is_a_noop_with_no_dirs():
    env = {"PATH": "existing"}
    t.prepend_to_path([], env)
    assert env["PATH"] == "existing"


# --- vocabulary / hotwords --------------------------------------------------

def test_load_vocabulary_ignores_comments_and_blanks(tmp_path):
    f = tmp_path / "vocab.txt"
    f.write_text(
        "# a comment\n\nClaude\n  jättelätt  \n\n# another\nRemotion\n",
        encoding="utf-8",
    )
    assert t.load_vocabulary(f) == ["Claude", "jättelätt", "Remotion"]


def test_load_vocabulary_missing_file_is_empty(tmp_path):
    assert t.load_vocabulary(tmp_path / "nope.txt") == []


def test_vocabulary_is_passed_as_hotwords(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "c.mp4", "large-v3", 5, None, False, vocabulary=["Claude", "Remotion"])
    assert model.kwargs["hotwords"] == "Claude Remotion"


def test_no_vocabulary_means_hotwords_none(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "c.mp4", "large-v3", 5, None, False, vocabulary=[])
    assert model.kwargs["hotwords"] is None


def test_vocabulary_count_recorded_in_output(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "load_model", lambda *a, **k: StubModel())
    result, _ = t.run(tmp_path / "c.mp4", "large-v3", 5, None, False, vocabulary=["Claude"])
    assert result["vocabulary_terms"] == 1


def test_shipped_vocabulary_parses_and_covers_known_misses():
    terms = t.load_vocabulary(t.VOCABULARY_FILE)
    assert "Claude" in terms and "jättelätt" in terms
    assert all(not term.startswith("#") for term in terms)


# --- corrections ------------------------------------------------------------

def test_load_corrections_parses_rules(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text("# note\n\nCloud => Claude\njätterätt => jättelätt\nnoarrow\n", encoding="utf-8")
    assert t.load_corrections(f) == [("Cloud", "Claude"), ("jätterätt", "jättelätt")]


def test_corrections_are_case_sensitive_and_word_bounded():
    rules = [("Cloud", "Claude")]
    assert t.apply_corrections("Vi kör Cloud idag", rules)[0] == "Vi kör Claude idag"
    # A legitimate lowercase 'cloud' must survive.
    assert t.apply_corrections("det är cloud computing", rules)[0] == "det är cloud computing"
    # Must not corrupt a longer word.
    assert t.apply_corrections("Cloudflare", rules)[0] == "Cloudflare"


def test_corrections_handle_swedish_characters():
    rules = [("jätterätt", "jättelätt")]
    out, counts = t.apply_corrections("det är jätterätt bra", rules)
    assert out == "det är jättelätt bra"
    assert counts == {"jätterätt => jättelätt": 1}


class SwedishStubSegment(StubSegment):
    def __init__(self):
        super().__init__()
        self.text = " Vi bygger med Cloud och det är jätterätt."
        self.words = [
            StubWord(" Vi", 0.0, 0.2, 0.99),
            StubWord(" Cloud", 0.2, 0.6, 0.90),
            StubWord(" jätterätt.", 0.6, 1.2, 0.88),
        ]


def test_corrections_fix_words_and_segment_text_consistently(monkeypatch, tmp_path):
    class M:
        def transcribe(self, *a, **k):
            return iter([SwedishStubSegment()]), StubInfo()

    monkeypatch.setattr(t, "load_model", lambda *a, **k: M())
    result, _ = t.run(
        tmp_path / "c.mp4", "large-v3", 5, None, False,
        corrections=[("Cloud", "Claude"), ("jätterätt", "jättelätt")],
    )

    assert [w["word"] for w in result["words"]] == [" Vi", " Claude", " jättelätt."]
    assert "Claude" in result["segments"][0]["text"]
    assert "Cloud" not in result["segments"][0]["text"]
    # Timings must survive the rewrite untouched.
    assert result["words"][1]["start"] == 0.2 and result["words"][1]["end"] == 0.6


def test_corrections_are_tallied_in_output(monkeypatch, tmp_path):
    class M:
        def transcribe(self, *a, **k):
            return iter([SwedishStubSegment()]), StubInfo()

    monkeypatch.setattr(t, "load_model", lambda *a, **k: M())
    result, _ = t.run(
        tmp_path / "c.mp4", "large-v3", 5, None, False,
        corrections=[("Cloud", "Claude")],
    )
    # Counted once per actual correction: segment text is rebuilt from the
    # corrected words rather than corrected separately, so no double-count.
    assert result["corrections_applied"] == {"Cloud => Claude": 1}


def test_no_corrections_leaves_text_alone(monkeypatch, tmp_path):
    class M:
        def transcribe(self, *a, **k):
            return iter([SwedishStubSegment()]), StubInfo()

    monkeypatch.setattr(t, "load_model", lambda *a, **k: M())
    result, _ = t.run(tmp_path / "c.mp4", "large-v3", 5, None, False, corrections=[])
    assert " Cloud" in [w["word"] for w in result["words"]]
    assert result["corrections_applied"] == {}


def test_shipped_corrections_cover_reported_errors():
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    assert ("Cloud", "Claude") in rules
    assert ("jätterätt", "jättelätt") in rules


# --- multi-token corrections (split Swedish compounds) ----------------------

def _w(word, start, end, prob=0.9):
    return {"word": word, "start": start, "end": end, "probability": prob}


def test_sequence_correction_merges_split_compound():
    words = [_w(" det", 0.0, 0.2), _w(" jätte", 0.2, 0.6, 0.8), _w(" rätt", 0.6, 1.0, 0.7)]
    out, counts = t.apply_sequence_corrections(words, [("jätte rätt", "jättelätt")])

    assert [e["word"] for e in out] == [" det", " jättelätt"]
    assert counts == {"jätte rätt => jättelätt": 1}
    # Timing spans the whole merged run; probability is the weakest link.
    assert out[1]["start"] == 0.2 and out[1]["end"] == 1.0
    assert out[1]["probability"] == 0.7


def test_sequence_correction_leaves_non_matches_alone():
    words = [_w(" jätte", 0.0, 0.4), _w(" bra", 0.4, 0.8)]
    out, counts = t.apply_sequence_corrections(words, [("jätte rätt", "jättelätt")])
    assert [e["word"] for e in out] == [" jätte", " bra"]
    assert counts == {}


def test_sequence_correction_ignores_single_token_rules():
    words = [_w(" Cloud", 0.0, 0.4)]
    out, counts = t.apply_sequence_corrections(words, [("Cloud", "Claude")])
    assert out == words and counts == {}


def test_sequence_correction_handles_repeats():
    words = [_w(" jätte", 0, 0.2), _w(" rätt", 0.2, 0.4), _w(" och", 0.4, 0.6),
             _w(" jätte", 0.6, 0.8), _w(" rätt", 0.8, 1.0)]
    out, counts = t.apply_sequence_corrections(words, [("jätte rätt", "jättelätt")])
    assert [e["word"] for e in out] == [" jättelätt", " och", " jättelätt"]
    assert counts == {"jätte rätt => jättelätt": 2}


def test_segment_text_rebuilt_after_merge(monkeypatch, tmp_path):
    class Seg:
        id, start, end = 0, 0.0, 1.0
        text = " det är jätte rätt."
        words = [StubWord(" det", 0.0, 0.2, 0.9), StubWord(" är", 0.2, 0.4, 0.9),
                 StubWord(" jätte", 0.4, 0.7, 0.8), StubWord(" rätt.", 0.7, 1.0, 0.8)]

    class M:
        def transcribe(self, *a, **k):
            return iter([Seg()]), StubInfo()

    monkeypatch.setattr(t, "load_model", lambda *a, **k: M())
    result, _ = t.run(
        tmp_path / "c.mp4", "large-v3", 5, None, False,
        corrections=[("rätt.", "rätt"), ("jätte rätt", "jättelätt")],
    )
    # Word list and segment text must agree after the merge.
    joined = "".join(w["word"] for w in result["words"])
    assert joined == result["segments"][0]["text"]
    assert "jättelätt" in joined


def test_correction_matches_term_ending_in_punctuation():
    """A trailing \\b after '.' never matches at end of sentence."""
    out, counts = t.apply_corrections("det är rätt.", [("rätt.", "rätt")])
    assert out == "det är rätt"
    assert counts == {"rätt. => rätt": 1}


def test_correction_with_punctuation_still_respects_left_boundary():
    out, _ = t.apply_corrections("bortrated.", [("rated.", "X")])
    assert out == "bortrated."


# --- show.py path resolution ------------------------------------------------

import show  # noqa: E402


def test_show_resolves_media_path_to_sibling_transcript(tmp_path, capsys):
    (tmp_path / "clip.mp4").write_bytes(b"\x00\x8a\xff")
    transcript = tmp_path / "clip.words.json"
    transcript.write_text("{}", encoding="utf-8")
    assert show.resolve_json_path(tmp_path / "clip.mp4") == transcript


def test_show_accepts_the_json_directly(tmp_path):
    transcript = tmp_path / "clip.words.json"
    transcript.write_text("{}", encoding="utf-8")
    assert show.resolve_json_path(transcript) == transcript


def test_show_explains_a_media_file_with_no_transcript(tmp_path, capsys):
    (tmp_path / "clip.mp4").write_bytes(b"\x00\x8a\xff")
    assert show.resolve_json_path(tmp_path / "clip.mp4") is None
    err = capsys.readouterr().err
    assert "is not a transcript" in err and "clip.words.json" in err


def test_show_reports_missing_file(tmp_path, capsys):
    assert show.resolve_json_path(tmp_path / "nope.json") is None
    assert "no such file" in capsys.readouterr().err


# --- regression: the actual observed transcript -----------------------------

REAL_LINES = [
    ("Min cloud kan nu göra custom formulär med designen av min brand consistently.",
     "Min Claude kan nu göra custom formulär med designen av min brand consistently."),
    ("ta transcripten och bara skicka den till cloud direkt.",
     "ta transcripten och bara skicka den till Claude direkt."),
    ("du behöver få svar av till cloud och han skapar ett formulär till dig.",
     "du behöver få svar av till Claude och han skapar ett formulär till dig."),
]


@pytest.mark.parametrize("given,expected", REAL_LINES)
def test_shipped_rules_fix_the_observed_transcript(given, expected):
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    assert t.apply_corrections(given, rules)[0] == expected


@pytest.mark.parametrize("line", [
    "Cloudflare skyddar sajten",
    "vi kör allt i molnet",
])
def test_shipped_rules_leave_unrelated_text_alone(line):
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    assert t.apply_corrections(line, rules)[0] == line


def test_shipped_rules_cover_lowercase_cloud():
    """The observed text is lowercase; a capital-only rule silently does nothing."""
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    assert ("cloud", "Claude") in rules


# --- punctuation-tolerant and in-place sequence rules -----------------------

def test_sequence_rule_matches_across_trailing_punctuation():
    words = [_w(" den", 0.0, 0.2), _w(" en", 0.3, 0.5), _w(" formulär.", 0.6, 0.9)]
    out, counts = t.apply_sequence_corrections(words, [("en formulär", "ett formulär")])
    assert [e["word"] for e in out] == [" den", " ett", " formulär."]
    assert counts == {"en formulär => ett formulär": 1}


def test_same_length_replacement_preserves_each_timestamp():
    words = [_w(" en", 0.3, 0.5, 0.91), _w(" formulär", 0.6, 0.9, 0.77)]
    out, _ = t.apply_sequence_corrections(words, [("en formulär", "ett formulär")])
    assert out[0]["start"] == 0.3 and out[0]["end"] == 0.5 and out[0]["probability"] == 0.91
    assert out[1]["start"] == 0.6 and out[1]["end"] == 0.9 and out[1]["probability"] == 0.77


def test_shrinking_replacement_still_merges():
    words = [_w(" jätte", 0.3, 0.5), _w(" rätt.", 0.6, 0.9)]
    out, _ = t.apply_sequence_corrections(words, [("jätte rätt", "jättelätt")])
    assert [e["word"] for e in out] == [" jättelätt."]
    assert out[0]["start"] == 0.3 and out[0]["end"] == 0.9


def test_mid_phrase_punctuation_prevents_a_match():
    """'en, formulär' is two clauses, not the phrase being corrected."""
    words = [_w(" en,", 0.3, 0.5), _w(" formulär", 0.6, 0.9)]
    out, counts = t.apply_sequence_corrections(words, [("en formulär", "ett formulär")])
    assert [e["word"] for e in out] == [" en,", " formulär"]
    assert counts == {}


def test_shipped_rules_fix_the_gender_error():
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    words = [_w(" skapa", 0.0, 0.2), _w(" den", 0.3, 0.5),
             _w(" en", 0.6, 0.8), _w(" formulär.", 0.9, 1.2)]
    out, counts = t.apply_sequence_corrections(words, rules)
    assert "".join(e["word"] for e in out) == " skapa den ett formulär."
    assert counts == {"en formulär => ett formulär": 1}


def test_correct_ett_formular_is_left_alone():
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    words = [_w(" skapar", 0.0, 0.2), _w(" ett", 0.3, 0.5), _w(" formulär", 0.6, 0.9)]
    out, counts = t.apply_sequence_corrections(words, rules)
    assert [e["word"] for e in out] == [" skapar", " ett", " formulär"]
    assert counts == {}


# --- verbatim mode ----------------------------------------------------------

def test_default_transcription_uses_vad_and_conditioning(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "c.mp4", "large-v3", 5, None, False)
    assert model.kwargs["vad_filter"] is True
    assert model.kwargs["condition_on_previous_text"] is True


def test_verbatim_disables_both(monkeypatch, tmp_path):
    """Both are what smooth false starts out of an otherwise honest transcript."""
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "c.mp4", "large-v3", 5, None, False, verbatim=True)
    assert model.kwargs["vad_filter"] is False
    assert model.kwargs["condition_on_previous_text"] is False


def test_verbatim_keeps_word_timestamps_on(monkeypatch, tmp_path):
    model = StubModel()
    monkeypatch.setattr(t, "load_model", lambda *a, **k: model)
    t.run(tmp_path / "c.mp4", "large-v3", 5, None, False, verbatim=True)
    assert model.kwargs["word_timestamps"] is True


# --- deletion-only corrections (a mistranscription, not a stumble) ----------

def _pw(word, start, end):
    return {"word": word, "start": start, "end": end, "probability": 0.99}


PHANTOM = [
    _pw(" behöva", 78.92, 79.32), _pw(" göra", 79.32, 79.48),
    _pw(" mer.", 79.48, 79.62), _pw(" Och", 79.62, 79.82),
    _pw(" mycket", 79.82, 80.10), _pw(" mindre", 80.10, 80.48),
]
PHANTOM_RULE = [("göra mer. Och mycket mindre", "göra mycket mindre")]


def test_invented_words_are_removed_keeping_the_real_ones():
    out, counts = t.apply_sequence_corrections(PHANTOM, PHANTOM_RULE)
    assert "".join(e["word"] for e in out).strip() == "behöva göra mycket mindre"
    assert counts


def test_surviving_words_keep_individual_timing():
    """Merging into one token would destroy word-level caption timing."""
    out, _ = t.apply_sequence_corrections(PHANTOM, PHANTOM_RULE)
    assert len(out) == 4
    assert [e["word"].strip() for e in out] == ["behöva", "göra", "mycket", "mindre"]
    assert out[2]["start"] == 79.82 and out[2]["end"] == 80.10


def test_dropped_time_is_given_to_the_previous_word():
    """Otherwise the caption blanks out over audio that is still playing."""
    out, _ = t.apply_sequence_corrections(PHANTOM, PHANTOM_RULE)
    gora = next(e for e in out if e["word"].strip() == "göra")
    assert gora["end"] == 79.82, "spans the removed words"
    assert all(
        out[i]["end"] == out[i + 1]["start"] for i in range(len(out) - 1)
    ), "no gap left behind"


def test_a_rule_may_contain_punctuation_mid_phrase():
    """'mer.' is part of what identifies the invented run."""
    out, counts = t.apply_sequence_corrections(PHANTOM, PHANTOM_RULE)
    assert counts, "a full stop inside the pattern must not block the match"


def test_a_genuine_compound_still_merges_into_one_token():
    """Shrinking is not always deletion; jätte rätt is one word."""
    words = [_pw(" det", 0.0, 0.2), _pw(" jätte", 0.3, 0.6), _pw(" rätt", 0.6, 1.0)]
    out, _ = t.apply_sequence_corrections(words, [("jätte rätt", "jättelätt")])
    assert [e["word"].strip() for e in out] == ["det", "jättelätt"]
    assert out[1]["start"] == 0.3 and out[1]["end"] == 1.0


def test_shipped_rule_covers_the_reported_mishearing():
    rules = t.load_corrections(t.CORRECTIONS_FILE)
    assert ("göra mer. Och mycket mindre", "göra mycket mindre") in rules


def test_a_recordings_own_rules_run_after_the_shared_ones(tmp_path):
    """Order matters: rules apply in sequence to text the earlier ones have
    already changed, so a recording's own rule can correct something a general
    rule got wrong."""
    import argparse
    shared = tmp_path / "corrections.txt"
    shared.write_text("cloud => Claude\n", encoding="utf-8")
    mine = tmp_path / "project.txt"
    mine.write_text("Claude Skills => Claude-färdigheter\n", encoding="utf-8")

    args = argparse.Namespace(corrections=shared, extra_corrections=mine)
    rules = t.corrections_for(args)
    assert rules == [("cloud", "Claude"), ("Claude Skills", "Claude-färdigheter")]

    out, _ = t.apply_corrections("jag gillar cloud Skills", rules)
    assert out == "jag gillar Claude-färdigheter"


def test_no_extra_rules_is_just_the_shared_ones(tmp_path):
    import argparse
    shared = tmp_path / "corrections.txt"
    shared.write_text("a => b\n", encoding="utf-8")
    args = argparse.Namespace(corrections=shared, extra_corrections=None)
    assert t.corrections_for(args) == [("a", "b")]


# --- deletion: a rule with nothing on the right -----------------------------

HALLUCINATION = [
    _w(" Okej", 0.5, 0.9),
    _w(" TypeScript", 1.0, 1.3),
    _w(" React", 1.3, 1.5),
    _w(" GIS", 1.5, 1.9),
    _w(" nu", 2.0, 2.2),
]


def _corrected(words, rules):
    """Both correction passes, in the order build_output runs them."""
    out = [{**e, "word": t.apply_corrections(e["word"], rules)[0]} for e in words]
    out, _ = t.apply_sequence_corrections(out, rules)
    return t.drop_deleted(out)


def test_an_empty_rule_loads_as_a_deletion(tmp_path):
    path = tmp_path / "corrections.txt"
    path.write_text("Textning.nu =>\n", encoding="utf-8")
    assert t.load_corrections(path) == [("Textning.nu", "")]


def test_a_deleted_phrase_leaves_no_word_behind():
    out = _corrected(HALLUCINATION, [("TypeScript React GIS", "")])
    assert [e["word"] for e in out] == [" Okej", " nu"]


def test_a_deleted_phrase_hands_its_time_to_the_previous_word():
    # The audio under the phantom still plays, so the caption must not blank.
    out = _corrected(HALLUCINATION, [("TypeScript React GIS", "")])
    assert out[0]["end"] == 1.9


def test_a_single_deleted_word_goes_too():
    words = [_w(" Datamaskin", 1.0, 1.4), _w(" Nästa", 1.4, 1.8)]
    out = _corrected(words, [("Datamaskin", "")])
    assert [e["word"] for e in out] == [" Nästa"]


def test_a_deletion_at_the_very_start_is_simply_gone():
    # Nothing precedes it, so there is no earlier word to hand the time to.
    out = _corrected(HALLUCINATION[1:], [("TypeScript React GIS", "")])
    assert [e["word"] for e in out] == [" nu"]
    assert out[0]["start"] == 2.0


class PhantomSegment(StubSegment):
    def __init__(self):
        super().__init__()
        self.text = " Okej Datamaskin"
        self.words = [
            StubWord(" Okej", 0.5, 0.9, 0.95),
            StubWord(" Datamaskin", 1.0, 1.4, 0.31),
        ]


def test_deletion_rebuilds_the_segment_text(tmp_path):
    out = t.build_output(
        tmp_path / "clip.wav", "large-v3", t.Backend("cpu", "int8"), StubInfo(),
        [PhantomSegment()], 1.0, corrections=[("Datamaskin", "")],
    )
    assert [e["word"] for e in out["words"]] == [" Okej"]
    assert "Datamaskin" not in out["segments"][0]["text"]
    assert out["corrections_applied"] == {"Datamaskin => ": 1}
