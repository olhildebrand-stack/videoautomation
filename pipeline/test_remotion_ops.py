"""Tests for finding the Remotion CLI.

Why this exists: verify.py shelled out to `npx remotion`. On Windows npx is
npx.cmd, which subprocess cannot resolve without a shell, so the first real run
died with a bare WinError 2 -- a lesson pipeline.py had already learned and
written down in a copy of the code that verify.py did not use.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from remotion_ops import RemotionMissing, binary, command  # noqa: E402


def install(tmp_path: Path, *names: str) -> Path:
    """A fake broll/ with the named CLI shims in node_modules/.bin."""
    binaries = tmp_path / "node_modules" / ".bin"
    binaries.mkdir(parents=True)
    for name in names:
        (binaries / name).write_text("#!/bin/sh\n", encoding="utf-8")
    return tmp_path


def test_the_windows_shim_wins_when_both_exist(tmp_path):
    """npm writes both; only the .cmd can be executed on Windows."""
    broll = install(tmp_path, "remotion", "remotion.cmd")
    assert binary(broll).name == "remotion.cmd"


def test_the_plain_binary_is_used_where_there_is_no_cmd(tmp_path):
    broll = install(tmp_path, "remotion")
    assert binary(broll).name == "remotion"


def test_a_missing_install_says_how_to_fix_it(tmp_path):
    with pytest.raises(RemotionMissing) as raised:
        binary(tmp_path)
    assert "setup.ps1" in str(raised.value)


def test_the_command_never_goes_through_npx(tmp_path):
    """The whole bug in one assertion."""
    broll = install(tmp_path, "remotion")
    args = command("still", "CaptionedVideo", broll=broll)
    assert Path(args[0]).is_absolute()
    assert "npx" not in args
    assert args[1:] == ["still", "CaptionedVideo"]


def test_the_browser_override_is_appended_when_set(tmp_path, monkeypatch):
    broll = install(tmp_path, "remotion")
    monkeypatch.setenv("REMOTION_BROWSER_EXECUTABLE", "/opt/chrome")
    assert command("render", broll=broll)[-1] == "--browser-executable=/opt/chrome"


def test_the_browser_override_is_absent_when_unset(tmp_path, monkeypatch):
    broll = install(tmp_path, "remotion")
    monkeypatch.delenv("REMOTION_BROWSER_EXECUTABLE", raising=False)
    assert not any("browser-executable" in a for a in command("render", broll=broll))


def test_no_module_shells_out_to_npx():
    """Guard the whole pipeline, not just the two callers fixed today."""
    for module in sorted(Path(__file__).parent.glob("*.py")):
        if module.name == Path(__file__).name:
            continue
        text = module.read_text(encoding="utf-8")
        assert '"npx"' not in text and "'npx'" not in text, (
            f"{module.name} runs npx; use remotion_ops.command instead")


def test_an_absent_binary_is_reported_before_subprocess_is_reached(tmp_path):
    """A RemotionMissing, not the FileNotFoundError the operator actually saw."""
    with pytest.raises(RemotionMissing):
        subprocess.run(command("still", broll=tmp_path))
