"""`unisphere`'s built-in guidance: bare invocation, `help`, per-command `--help`, `--version`,
typo suggestions, and the colour/ASCII rules behind all of it. [earned: 2026-09-28 — the owner
asked for help like gh/kubectl/brew: rich, structured, discoverable without reading the source]"""

from __future__ import annotations

import json
import re

import pytest
from toolkit_core import cli, term, ui

ANSI = re.compile(r"\033\[")


def run(capsys, *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


def run_err(capsys, *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().err


def run_json(capsys, *argv: str) -> tuple[int, dict]:
    code, out = run(capsys, *argv, "--json")
    return code, json.loads(out)


# --- bare invocation, help, and per-command help agree ------------------------------------


def test_bare_invocation_shows_help_and_exits_0(capsys):
    code, out = run(capsys)
    assert code == 0
    assert "COMMANDS" in out and "EXAMPLES" in out and "USAGE" in out
    assert "unknown command" not in out


def test_top_level_flag_and_bare_help_agree(capsys):
    _, bare = run(capsys)
    code, flagged = run(capsys, "--help")
    assert code == 0 and flagged == bare
    code, via_help = run(capsys, "help")
    assert code == 0 and via_help == bare


def test_help_command_matches_flag_help_for_a_leaf_and_a_parent(capsys):
    _, from_help = run(capsys, "help", "search")
    _, from_flag = run(capsys, "search", "--help")
    assert from_help == from_flag and "USAGE" in from_help and "EXAMPLES" in from_help

    _, from_help = run(capsys, "help", "graph", "neighbors")
    _, from_flag = run(capsys, "graph", "neighbors", "--help")
    assert from_help == from_flag

    _, parent_help = run(capsys, "graph", "--help")
    assert "COMMANDS" in parent_help and "neighbors" in parent_help


def test_every_command_and_subcommand_has_real_help():
    """The declarative table (item 7) is the only place this can be authored, so a command added
    without a description/example here can't ship — the catalogue test already enforces every
    leaf is present; this enforces what's *in* each entry."""
    for name, entry in cli.CATALOG.items():
        assert len(entry["description"]) >= 40, f"{name}: description too thin"
        assert entry["examples"], f"{name}: no examples"
        for cmd, note in entry["examples"]:
            assert cmd.startswith("unisphere ") and note
    for name, entry in cli.GROUP_HELP.items():
        assert len(entry["description"]) >= 40, f"{name}: description too thin"
        assert entry["examples"]


# --- typo suggestions ----------------------------------------------------------------------


def test_typo_suggestion_top_level(capsys):
    code, err = run_err(capsys, "serch")
    assert code == 2
    assert 'unknown command "serch" for "unisphere"' in err
    assert "Did you mean this?" in err and "search" in err
    assert "Run 'unisphere --help' for usage." in err


def test_typo_suggestion_subcommand(capsys):
    code, err = run_err(capsys, "graph", "neighbour")
    assert code == 2
    assert 'unknown command "neighbour" for "unisphere graph"' in err
    assert "neighbors" in err
    assert "Run 'unisphere graph --help' for usage." in err


def test_missing_required_argument_is_short_not_a_full_dump(capsys):
    code, err = run_err(capsys, "search")
    assert code == 2
    assert err.startswith("error:")
    assert "unisphere search" in err
    assert "Run 'unisphere search --help' for more." in err
    assert err.count("\n") <= 3  # one-liner + usage + hint, not argparse's own multi-block dump


@pytest.mark.parametrize(
    ("group", "choices"),
    [
        ("vault", "{init}"),
        ("graph", "{stats,neighbors,path,candidates}"),
        ("engines", "{install,update,status}"),
    ],
)
def test_missing_subcommand_names_no_internal_dest(capsys, group, choices):
    """A parent command with no subcommand (`unisphere vault`/`graph`/`engines`) used to leak
    argparse's internal `add_subparsers(dest=...)` variable name ("vault_command",
    "graph_command", "engines_command") straight into the error line — an implementation detail,
    not anything the user typed or would recognise. The USAGE line right below it already lists
    the real choices, so the one-liner just needs to say a subcommand is missing.
    [battle-test 2026-09-28]"""
    code, err = run_err(capsys, group)
    assert code == 2
    assert err.startswith("error: a subcommand is required\n")
    assert "_command" not in err
    assert choices in err  # the real choices still show, in the USAGE line


@pytest.mark.parametrize(
    ("argv", "flag"),
    [
        (["search", "foo", "--limit", "-5"], "--limit"),
        (["graph", "neighbors", "X", "--depth", "-1"], "--depth"),
        (["graph", "candidates", "X", "--limit", "-3"], "--limit"),
    ],
)
def test_negative_limit_or_depth_is_a_clean_one_liner(capsys, argv, flag):
    """`--limit`/`--depth` are forwarded straight into an engine's (farsight's/gaiafield's) own
    argv; a negative value used to sail through unisphere's own int() parsing and only get
    rejected downstream by the Rust engine's clap parser, whose own error text/usage then leaked
    through verbatim — e.g. "farsight: error: unexpected argument '-5' found" plus clap's usage
    line, nothing like this CLI's own one-line errors. [battle-test 2026-09-28]"""
    code, err = run_err(capsys, *argv)
    assert code == 2
    assert err.startswith(f"error: argument {flag}: must not be negative")
    assert "clap" not in err.lower()
    assert "unexpected argument" not in err


def test_unrecognized_flag_blames_the_subcommand_not_the_top_level(capsys):
    """`argparse.ArgumentParser.parse_args()` only checks for leftover ("unrecognized
    arguments") tokens on the OUTERMOST parser it was called on — so a bad flag on a subcommand
    used to render `unisphere`'s own top-level USAGE (every command listed) instead of that
    subcommand's. [battle-test 2026-09-28]"""
    code, err = run_err(capsys, "search", "--unknown-flag", "foo")
    assert code == 2
    assert err.startswith("error: unrecognized arguments: --unknown-flag\n")
    assert "unisphere search " in err
    assert "{vault,doctor,profile" not in err  # not the top-level USAGE line

    code, err = run_err(capsys, "graph", "neighbors", "X", "--bogus")
    assert code == 2
    assert err.startswith("error: unrecognized arguments: --bogus\n")
    assert "unisphere graph neighbors " in err


# --- version --------------------------------------------------------------------------------


def test_version_flag_and_command_agree(capsys):
    code, out = run(capsys, "--version")
    assert code == 0 and "unisphere" in out
    code, data = run_json(capsys, "version")
    assert code == 0 and data["ok"] and data["unisphere"]
    assert {"farsight", "gaiafield"} == {r["engine"] for r in data["engines"]}


# --- colour: NO_COLOR/non-TTY plain, FORCE_COLOR rich -----------------------------------------


def test_help_has_no_escapes_by_default(capsys):
    """capsys's stdout is not a TTY, so this is already the NO_COLOR-equivalent path."""
    _, out = run(capsys)
    assert not ANSI.search(out)
    _, out = run(capsys, "search", "--help")
    assert not ANSI.search(out)


def test_no_color_env_var_forces_plain_even_with_force_color(capsys, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    _, out = run(capsys, "search", "--help")
    assert not ANSI.search(out)


def test_force_color_puts_ansi_in_headings_commands_and_flags(capsys, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    _, out = run(capsys)
    assert ANSI.search(out), "FORCE_COLOR should colour bare help even off a TTY"
    heading = next(line for line in out.splitlines() if "COMMANDS" in line)
    assert "\033[" in heading
    _, out = run(capsys, "search", "--help")
    flag_line = next(line for line in out.splitlines() if "--limit" in line)
    assert "\033[" in flag_line


def test_typo_error_colours_under_force_color(capsys, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    _, err = run_err(capsys, "serch")
    assert "\033[" in err


# --- commands --json stays additive ----------------------------------------------------------


def test_commands_json_gained_examples_and_group_additively(capsys):
    _, data = run_json(capsys, "commands")
    old_keys = {"name", "summary", "arguments", "json", "example"}
    for c in data["commands"]:
        assert old_keys <= set(c)  # every key the old catalogue promised is still there
        assert c["examples"] and all(isinstance(e, str) for e in c["examples"])
        assert c["description"]
    grouped = {c["name"] for c in data["commands"] if "group" in c}
    assert grouped == {"status", "search", "doctor", "profile", "demo", "link", "commands", "vault init", "version"}


# --- ui.Style: the new help/error colours ------------------------------------------------


def test_style_new_methods_are_plain_without_color():
    st = ui.Style(color=False)
    assert st.heading("X") == "X" and st.flag("--x") == "--x" and st.metavar("Y") == "Y"
    assert st.good("ok") == "ok" and st.err("bad") == "bad"


def test_style_new_methods_wrap_with_color():
    st = ui.Style(color=True)
    assert "\033[" in st.heading("X") and "\033[" in st.flag("--x")
    assert "\033[" in st.metavar("Y") and "\033[" in st.good("ok") and "\033[" in st.err("bad")


def test_force_color_env_enables_color_off_a_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert ui.color_enabled() is True  # pytest's stdout is not a TTY


def test_no_color_wins_over_force_color(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    assert ui.color_enabled() is False


# --- term.py: terminal capability detection ----------------------------------------------


class _Tty:
    def isatty(self):
        return True


class _NotTty:
    def isatty(self):
        return False


def test_unicode_disabled_off_a_tty(monkeypatch):
    monkeypatch.delenv("UNISPHERE_ASCII", raising=False)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert term.unicode_enabled(_NotTty()) is False


def test_unicode_disabled_without_utf8_locale(monkeypatch):
    monkeypatch.delenv("UNISPHERE_ASCII", raising=False)
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        monkeypatch.delenv(var, raising=False)
    assert term.unicode_enabled(_Tty()) is False


def test_unicode_enabled_on_a_utf8_tty(monkeypatch):
    monkeypatch.delenv("UNISPHERE_ASCII", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert term.unicode_enabled(_Tty()) is True


def test_unicode_disabled_on_dumb_or_linux_term(monkeypatch):
    monkeypatch.delenv("UNISPHERE_ASCII", raising=False)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    for value in ("dumb", "linux"):
        monkeypatch.setenv("TERM", value)
        assert term.unicode_enabled(_Tty()) is False


def test_unisphere_ascii_override_forces_plain(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.setenv("UNISPHERE_ASCII", "1")
    assert term.unicode_enabled(_Tty()) is False
    assert term.glyph("node", _Tty()) == "(o)"


def test_glyph_falls_back_to_ascii(monkeypatch):
    monkeypatch.delenv("UNISPHERE_ASCII", raising=False)
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        monkeypatch.delenv(var, raising=False)
    assert term.glyph("node", _NotTty()) == "(o)"
    assert term.glyph("ok", _NotTty()) == "*"
    assert term.glyph("bad", _NotTty()) == "x"


@pytest.mark.parametrize("var,value", [("TERM_PROGRAM", "iTerm.app"), ("KITTY_WINDOW_ID", "1"), ("WT_SESSION", "1")])
def test_hyperlinks_enabled_for_known_terminals(monkeypatch, var, value):
    monkeypatch.delenv("FORCE_HYPERLINK", raising=False)
    monkeypatch.setattr(term, "is_tty", lambda stream=None: True)
    monkeypatch.setenv(var, value)
    assert term.hyperlinks_enabled() is True


def test_hyperlinks_disabled_off_a_tty_even_for_a_known_terminal(monkeypatch):
    monkeypatch.delenv("FORCE_HYPERLINK", raising=False)
    monkeypatch.setattr(term, "is_tty", lambda stream=None: False)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    assert term.hyperlinks_enabled() is False


def test_force_hyperlink_wins_even_off_a_tty(monkeypatch):
    monkeypatch.setattr(term, "is_tty", lambda stream=None: False)
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.setenv("FORCE_HYPERLINK", "1")
    assert term.hyperlinks_enabled() is True
    assert term.link("https://example.com", "docs").startswith("\033]8;;")


def test_link_is_plain_text_without_hyperlink_support(monkeypatch):
    monkeypatch.delenv("FORCE_HYPERLINK", raising=False)
    monkeypatch.setattr(term, "is_tty", lambda stream=None: False)
    assert term.link("https://example.com", "docs") == "docs"
