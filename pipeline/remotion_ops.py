#!/usr/bin/env python3
"""Finding and invoking the Remotion CLI.

Stated once, because stating it twice is exactly what broke. pipeline.py had
already learned that the CLI has to be the project-local binary -- and that on
Windows that binary is `remotion.cmd`, which subprocess cannot resolve without
a shell. verify.py, written later, shelled out to `npx remotion` and died with
a bare WinError 2 the first time it was run on the machine that matters.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROLL = ROOT / "broll"


class RemotionMissing(RuntimeError):
    pass


def binary(broll: Path = BROLL) -> Path:
    """The project-local Remotion CLI, so no global install is assumed.

    The `.cmd` shim comes first: on Windows it is the only one of the two that
    can actually be executed, and npm writes both.
    """
    for candidate in (
        broll / "node_modules" / ".bin" / "remotion.cmd",
        broll / "node_modules" / ".bin" / "remotion",
    ):
        if candidate.is_file():
            return candidate
    raise RemotionMissing(
        f"Remotion CLI not found under {broll / 'node_modules'}. Run setup.ps1."
    )


def command(*rest: str, broll: Path = BROLL) -> list[str]:
    """An argv for the Remotion CLI, with the browser override applied.

    REMOTION_BROWSER_EXECUTABLE is set when the platform's Remotion cannot
    fetch its own Chrome -- the session container, where remotion.media is
    blocked by the egress policy, is the case this exists for.
    """
    args = [str(binary(broll)), *rest]
    browser = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    if browser:
        args.append(f"--browser-executable={browser}")
    return args
