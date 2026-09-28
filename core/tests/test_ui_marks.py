"""`ui.Style.mark()`'s ASCII fallback — kept in its own file (not test_cli_interface.py) so this
battle-test fix lands as an isolated, easily reviewable change. [earned: 2026-09-28]"""

from __future__ import annotations

from toolkit_core import term, ui


def test_mark_is_ascii_off_a_tty_even_with_color_forced_on():
    """Not a TTY (pytest's stdout), so `term.glyph()`'s ASCII fallback applies regardless of
    `color` — `color` only ever governs the ANSI wrapping, never which symbol is chosen."""
    assert ui.Style(color=True).mark("ok") == "\033[32m*\033[0m"
    assert ui.Style(color=False).mark("ok") == "*"


def test_mark_falls_back_to_ascii_with_color_on(monkeypatch):
    """`status`/`doctor`/`link` marks (✓ ✗ ! ·) must honour the same ASCII fallback as
    `--help`/the startup banner — `UNISPHERE_ASCII=1`, `TERM=dumb`/`linux`, or a non-UTF-8 locale
    with no known-UTF-8 `LC_ALL`/`LC_CTYPE`/`LANG` — even on a real TTY with colour on.
    `ui.Style.mark()` used to read its symbol straight out of its own `MARKS` dict instead of
    `term.glyph()`, so none of this ever reached it. [battle-test 2026-09-28: `unisphere status`
    on a pty with `UNISPHERE_ASCII=1`, and `unisphere status | cat`, both still printed ✓/✗/!/·]
    """
    monkeypatch.setattr(term, "is_tty", lambda stream=None: True)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("UNISPHERE_ASCII", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    style = ui.Style(color=True)
    assert style.mark("ok") == "\033[32m✓\033[0m"  # sanity: unicode on a real UTF-8 TTY

    monkeypatch.setenv("UNISPHERE_ASCII", "1")
    assert style.mark("ok") == "\033[32m*\033[0m"

    monkeypatch.delenv("UNISPHERE_ASCII")
    monkeypatch.setenv("LANG", "C")
    assert style.mark("ok") == "\033[32m*\033[0m"

    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("TERM", "linux")
    assert style.mark("ok") == "\033[32m*\033[0m"
