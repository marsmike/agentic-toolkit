"""Terminal capability detection: unicode/emoji glyphs, OSC 8 hyperlinks, and a colour-depth
hint — detected once per call from env vars and an isatty check, never from the network, and
never blocking. `--help`, `--version`, error text and the startup banner (cli.py) go through
this instead of guessing; `ui.py`'s colour rule (NO_COLOR, FORCE_COLOR) is separate and stays
in ui.py — this module is only about glyphs and links, not colour codes.

A pipe or `--json` gets plain ASCII and no OSC 8 sequences, same spirit as NO_COLOR: an agent or
a log file should never see an escape it didn't ask for.

Override: UNISPHERE_ASCII=1 forces the plain glyphs even on a terminal this would otherwise
call capable — for the terminals this heuristic gets wrong.
"""

from __future__ import annotations

import os
import re
import sys
from typing import TextIO

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# name -> (unicode glyph, plain-ASCII fallback). Kept short and meaningful, not decorative —
# only what `unisphere --help`/`--version`/errors and the startup banner actually print.
GLYPHS: dict[str, tuple[str, str]] = {
    "node": ("◉", "(o)"),
    "ok": ("✓", "*"),
    "bad": ("✗", "x"),
    "warn": ("!", "!"),
    "info": ("·", "-"),
    "tip": ("💡", ""),
    "book": ("📖", ""),
    "start": ("🚀", ""),
    "find": ("🔎", ""),
    "setup": ("🛠", ""),
    "agents": ("🤖", ""),
}

# Glyphs that take two terminal cells, for callers doing their own column alignment.
_WIDE = {u for u, _ in GLYPHS.values() if u not in {"✓", "✗", "!", "·"}}


def is_tty(stream: TextIO | None = None) -> bool:
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def _utf8_locale() -> bool:
    """The first of LC_ALL/LC_CTYPE/LANG that is set names the locale; UTF-8 must be in it.
    None of them set is not assumed UTF-8 (a bare C/POSIX default has none)."""
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        value = os.environ.get(var)
        if value:
            return "utf-8" in value.lower() or "utf8" in value.lower()
    return False


def unicode_enabled(stream: TextIO | None = None) -> bool:
    """Emoji/unicode glyphs: a TTY, a UTF-8 locale, and TERM not dumb/linux (the Linux console
    framebuffer font has no emoji glyphs). UNISPHERE_ASCII=1 always wins."""
    if os.environ.get("UNISPHERE_ASCII"):
        return False
    if os.environ.get("TERM") in ("dumb", "linux"):
        return False
    return is_tty(stream) and _utf8_locale()


def glyph(name: str, stream: TextIO | None = None) -> str:
    unicode_glyph, ascii_glyph = GLYPHS[name]
    return unicode_glyph if unicode_enabled(stream) else ascii_glyph


def glyph_width(name: str, stream: TextIO | None = None) -> int:
    """Terminal cell width of `glyph(name)` as rendered right now — 2 for a wide glyph shown as
    unicode, 1 otherwise (including its own ASCII fallback). Not a general wcwidth: only covers
    GLYPHS."""
    return 2 if glyph(name, stream) in _WIDE else 1


def hyperlinks_enabled() -> bool:
    """OSC 8 clickable links: terminals known to render them, or FORCE_HYPERLINK=1. Off for a
    non-TTY regardless (a pipe/log/agent should never see the escape), except the forced case."""
    if os.environ.get("FORCE_HYPERLINK"):
        return True
    if not is_tty():
        return False
    if os.environ.get("TERM_PROGRAM") in ("iTerm.app", "WezTerm", "vscode", "ghostty"):
        return True
    if os.environ.get("KITTY_WINDOW_ID") or os.environ.get("WT_SESSION"):
        return True
    vte = os.environ.get("VTE_VERSION", "")
    return vte.isdigit() and int(vte) >= 5000


def link(url: str, text: str | None = None) -> str:
    """`text` (default `url`) as an OSC 8 hyperlink when the terminal supports it, else just the
    plain text — never a raw escape a non-supporting terminal or a pipe would print literally."""
    label = text or url
    return f"\033]8;;{url}\033\\{label}\033]8;;\033\\" if hyperlinks_enabled() else label


def display_width(text: str) -> int:
    """Terminal cell width of `text`: ANSI colour codes cost nothing, and a wide glyph from
    GLYPHS (an emoji) costs 2 cells, same as most terminals actually render it. Not a general
    wcwidth — covers plain ASCII/latin text plus the handful of glyphs this CLI prints, which is
    what `ui.wrap_field`'s column alignment needs."""
    plain = _ANSI_RE.sub("", text)
    return sum(2 if ch in _WIDE else 1 for ch in plain)


def rich_accent_enabled() -> bool:
    """True if the terminal claims a 256-colour or true-colour palette (COLORTERM=truecolor/24bit,
    or TERM containing "256color"). Advisory only: `ui.py` keeps every colour it actually prints
    in the basic 16-colour set regardless, so output still reads on an unknown terminal — this
    just says a caller *could* reach for a nicer accent if it chose to."""
    if os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return True
    return "256color" in os.environ.get("TERM", "")
