"""Every wikilink reader in the obsidian plugin reads a link written inside a Markdown table.

In a table the separator is `\\|` (Obsidian's documented escape): `[[target\\|alias]]`. Each
reader used to take `target\\` with the backslash, so the link never matched its note — the
vault linter called the note an orphan, distill_check called the link dangling, the maps lost
the edge. checks/links.py alone had been fixed, on 2026-09-22. [earned: 2026-09-28, 106 table
links in the owner's vault, 13 in the generated Maps/Overview; gaiafield had the same bug,
covered in crates/gaiafield/tests/graph_test.rs]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "plugins" / "obsidian" / "scripts"
BODY = "| [[02_Projects/x/b\\|b]] | 1 |\nplain [[c|see c]] and [[d]]"


def _module(name: str):
    sys.path.insert(0, str(SCRIPTS))
    for mod in ("vault_utils", name.split(".")[0], name):
        sys.modules.pop(mod, None)
    try:
        return __import__(name, fromlist=["_"])
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.mark.parametrize("module, attr", [
    ("vault_lint", "WIKILINK_RE"), ("map_build", "WIKILINK"),
    ("distill_check", "WIKILINK_RE"), ("judgments.capture", "WIKILINK_RE"), ("imports_log", "WIKILINK"),
])
def test_table_escaped_link_targets(module, attr):
    rx = getattr(_module(module), attr)
    assert [m.group(1).strip() for m in rx.finditer(BODY)] == ["02_Projects/x/b", "c", "d"]


def test_link_checker_names_the_note_of_a_table_escaped_link():
    """checks/links.py fixed this first (2026-09-22) in its normaliser; it keeps the raw target so
    a repair can preserve the escaped alias."""
    note_part = _module("checks.links")._note_part
    assert [note_part(t) for t in ("02_Projects/x/b\\", "Note#Heading", "Note^block")] == ["02_Projects/x/b", "Note", "Note"]


def test_display_text_of_a_table_escaped_link():
    """index_build and imports_log show a link's alias: `b`, never `02_Projects/x/b\\|b`."""
    source = (SCRIPTS / "index_build.py").read_text(encoding="utf-8")
    pattern = re.search(r're\.sub\(r"(\\\[\\\[.*?)", r"\\2"', source).group(1)
    assert re.sub(pattern, r"\2", BODY).startswith("| b | 1 |")
