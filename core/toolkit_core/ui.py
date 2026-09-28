"""Terminal rendering for the human side of the `unisphere` CLI. The agent side is `--json`.

Colour only on a TTY, never with NO_COLOR set or TERM=dumb (https://no-color.org), so piped or
logged text output stays plain. No dependency: a handful of ANSI codes is all the CLI needs.
"""

from __future__ import annotations

import os
import shutil
import sys
import textwrap
from typing import TextIO

_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "cyan": "36"}

# Status levels shared by every renderer: what a row means, and how it is marked.
MARKS = {"ok": ("✓", "green"), "warn": ("!", "yellow"), "bad": ("✗", "red"), "info": ("·", "dim")}


def color_enabled(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
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
        symbol, color = MARKS[level]
        return self._wrap(symbol, color)

    def level(self, text: str, level: str) -> str:
        return self._wrap(text, MARKS[level][1])


def width() -> int:
    return max(60, min(shutil.get_terminal_size((100, 24)).columns, 120))


def wrap(text: str, indent: int) -> list[str]:
    """`text` wrapped to the terminal, every line indented by `indent` spaces."""
    pad = " " * indent
    return textwrap.wrap(text, width=width(), initial_indent=pad, subsequent_indent=pad) or [pad]


def section(style: Style, label: str, rows: list[str]) -> list[str]:
    """A labelled block: the label in a fixed-width column, its rows aligned beside it."""
    out = []
    for i, row in enumerate(rows or [style.dim("—")]):
        head = style.bold(f"{label:<10}") if i == 0 else " " * 10
        out.append(f"  {head} {row}")
    return out
