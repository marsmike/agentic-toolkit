"""`unisphere help`'s bare (no-argument) LEARN MORE footer wraps to COLUMNS.

Kept in its own file rather than added to test_cli_help.py's `test_help_and_commands_wrap_to_columns`
parametrization: that test's per-line skip (any line starting with "unisphere " and containing no
"  # " comment marker is treated as a bare copy-pasteable example, exempt from the width check) would
also skip these two LEARN MORE lines even after the fix, since they happen to start with "unisphere "
too despite being prose, not example commands — so it wouldn't actually catch a regression here.
[battle-test 2026-09-28]
"""

from __future__ import annotations

import re

import pytest
from toolkit_core import cli

ANSI = re.compile(r"\033\[[0-9;]*m")


def run(capsys, *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


@pytest.mark.parametrize("columns", [60, 80])
def test_learn_more_footer_wraps_to_columns(capsys, monkeypatch, columns):
    """The bare `unisphere help` LEARN MORE section's two command-reference lines were raw
    f-strings that never consulted `ui.width()` — at COLUMNS=60 the `commands --json` line was 98
    characters. They now route through `ui.wrap_field`, the same as every other help field."""
    monkeypatch.setenv("COLUMNS", str(columns))
    code, out = run(capsys, "help")
    assert code == 0
    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "LEARN MORE")
    tail = lines[start + 1 :]  # LEARN MORE is the help page's last section
    assert tail, "LEARN MORE printed no rows"
    for line in tail:
        plain = ANSI.sub("", line)
        if not plain.strip() or plain.strip().startswith("https://"):
            continue  # a blank separator or a bare URL can't be word-wrapped
        assert len(plain) <= columns, f"LEARN MORE line exceeds COLUMNS={columns} ({len(plain)} chars): {plain!r}"
