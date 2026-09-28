"""Terminal rendering for the human side of the `unisphere` CLI. The agent side is `--json`.

Colour only on a TTY, never with NO_COLOR set or TERM=dumb (https://no-color.org), so piped or
logged text output stays plain. FORCE_COLOR / CLICOLOR_FORCE (the de-facto convention several
CLIs share — https://force-color.org) force it back on even off a TTY, e.g. for a colour sample
in a report or a `script(1)` capture; NO_COLOR still wins if both are set. No dependency: a
handful of basic ANSI codes (the 16-colour set, so it reads on light and dark terminals alike)
is all the CLI needs.
"""

from __future__ import annotations

import os
import shutil
import sys
import textwrap
from typing import TextIO

_CODES = {"bold": "1", "dim": "2", "underline": "4", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}

# Status levels shared by every renderer: what a row means, and how it is marked.
MARKS = {"ok": ("✓", "green"), "warn": ("!", "yellow"), "bad": ("✗", "red"), "info": ("·", "dim")}


def color_enabled(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


class Style:
    def __init__(self, color: bool | None = None):
        self.color = color_enabled() if color is None else color

    def _wrap(self, text: str, *names: str) -> str:
        if not self.color or not names:
            return text
        return f"\033[{';'.join(_CODES[n] for n in names)}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self._wrap(text, "bold")

    def dim(self, text: str) -> str:
        return self._wrap(text, "dim")

    def accent(self, text: str) -> str:
        return self._wrap(text, "cyan")

    def mark(self, level: str) -> str:
        from toolkit_core import term  # local import: term.py doesn't import ui, keep the edge one-directional

        _, color = MARKS[level]
        return self._wrap(term.glyph(level), color)

    def level(self, text: str, level: str) -> str:
        return self._wrap(text, MARKS[level][1])

    # --- help/usage rendering (gh/kubectl-style: a heading colour, a command colour, a flag
    # colour, dim for metadata) — same 16-colour palette `status`/`doctor` already use, just
    # named for what `--help` and error text reach for.

    def heading(self, text: str) -> str:
        """A `--help` section heading (USAGE, COMMANDS, EXAMPLES, …): bold and accented."""
        return self._wrap(text, "bold", "cyan")

    def command(self, text: str) -> str:
        """A command or subcommand name in a listing, e.g. `search` in the COMMANDS table."""
        return self._wrap(text, "cyan")

    def flag(self, text: str) -> str:
        """A flag, e.g. `--limit`, in USAGE/FLAGS text."""
        return self._wrap(text, "yellow")

    def metavar(self, text: str) -> str:
        """A placeholder a flag or positional takes, e.g. `PATH` or `N`."""
        return self._wrap(text, "underline")

    def good(self, text: str) -> str:
        return self._wrap(text, "green")

    def err(self, text: str) -> str:
        return self._wrap(text, "bold", "red")


def width() -> int:
    return max(60, min(shutil.get_terminal_size((100, 24)).columns, 100))


def wrap(text: str, indent: int) -> list[str]:
    """`text` wrapped to the terminal, every line indented by `indent` spaces."""
    pad = " " * indent
    return textwrap.wrap(text, width=width(), initial_indent=pad, subsequent_indent=pad, break_on_hyphens=False) or [pad]


def wrap_field(prefix: str, text: str, extra_indent: int = 0) -> list[str]:
    """A `--help` table row: `prefix` (already coloured — a padded name/flag column plus its
    trailing gap) starts the first line, and `text` wraps to the terminal width with
    continuation lines aligned under where `text` begins. The indent is `prefix`'s on-screen
    width (`term.display_width`: ANSI codes don't count, a wide glyph counts twice), not
    `len(prefix)`, so a coloured or emoji-bearing prefix still lines up."""
    from toolkit_core import term  # local import: term.py doesn't import ui, but keep the edge one-directional

    indent = term.display_width(prefix) + extra_indent
    body_width = max(20, width() - indent)
    lines = textwrap.wrap(text, width=body_width, break_on_hyphens=False) or [""]
    return [prefix + lines[0]] + [(" " * indent) + line for line in lines[1:]]


def section(style: Style, label: str, rows: list[str]) -> list[str]:
    """A labelled block: the label in a fixed-width column, its rows aligned beside it."""
    out = []
    for i, row in enumerate(rows or [style.dim("—")]):
        head = style.bold(f"{label:<10}") if i == 0 else " " * 10
        out.append(f"  {head} {row}")
    return out
