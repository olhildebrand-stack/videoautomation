#!/usr/bin/env python3
"""Read a JSON file a person edits, and say where it broke.

Every file this pipeline reads by hand -- the edit script, the overlay sheet, a
decision -- is edited in a text editor, and the most common damage is a missing
comma. Python's own message for that is a stack trace ending in

    json.decoder.JSONDecodeError: Expecting ',' delimiter: line 7 column 1

which does not say WHICH file, does not show the line, and buries the one
useful fact under six frames of interpreter internals. The operator hit it
twice on the same edit.
"""

from __future__ import annotations

import json
from pathlib import Path


class BadJSON(RuntimeError):
    pass


# What the parser complains about, and what actually causes it. The parser
# points at where it noticed, which is usually the line AFTER the mistake.
HINTS = {
    "Expecting ',' delimiter":
        "a missing comma at the end of the line before this one",
    "Expecting property name enclosed in double quotes":
        "a trailing comma after the last entry, or a single quote",
    # An edit script is an array of beats, so a trailing comma after the last
    # one lands here rather than on the property-name message.
    "Expecting value":
        "a trailing comma after the last entry, or a value left out",
    "Extra data":
        "something after the closing bracket -- a duplicated block, usually",
}


def read(path: Path, what: str = "file"):
    """Parse it, or raise BadJSON naming the file, the line and the fix."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise BadJSON(f"no {what} at {path}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        lines = text.splitlines()
        report = [f"{path} is not valid JSON.", ""]
        # The line before is shown because that is usually where the mistake
        # is, even though the parser points here.
        for number in range(max(1, exc.lineno - 1), min(len(lines), exc.lineno) + 1):
            marker = ">" if number == exc.lineno else " "
            report.append(f"  {marker} {number:>3} | {lines[number - 1]}")
        report.append(f"        {' ' * (exc.colno + 2)}^")
        report.append("")
        report.append(f"  {exc.msg}, at line {exc.lineno} column {exc.colno}.")
        hint = next((h for k, h in HINTS.items() if exc.msg.startswith(k)), None)
        if hint:
            report.append(f"  Usually {hint}.")
        raise BadJSON("\n".join(report)) from exc
