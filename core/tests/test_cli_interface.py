"""The `unisphere` CLI as an interface: the catalogue agents start from, `status`, `search`/`graph`,
`link`, and the plain-vs-coloured text people read. [earned: 2026-09-28]"""

from __future__ import annotations

import json
import shutil

import pytest
from conftest import EXAMPLE_VAULT, REPO_ROOT
from toolkit_core import cli, knowledge, status, ui, vault
from toolkit_core import link as linker


def run(capsys, *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


def run_json(capsys, *argv: str) -> tuple[int, dict]:
    code, out = run(capsys, *argv, "--json")
    return code, json.loads(out)


# --- the catalogue ----------------------------------------------------------------------


def test_every_command_is_in_the_catalogue(capsys):
    """A command added to the parser without a CATALOG entry would be invisible to agents."""
    names = [name for name, _ in cli._leaf_commands(cli._build_parser())]
    assert set(names) == set(cli.CATALOG), "CATALOG and the parser disagree"
    code, data = run_json(capsys, "commands")
    assert code == 0 and data["ok"]
    assert [c["name"] for c in data["commands"]] == names
    for c in data["commands"]:
        assert c["summary"] and c["json"] and c["example"].startswith("unisphere ")
        assert all(a["name"] != "json" for a in c["arguments"])
    assert {c["cli"] for c in data["companions"]} == {"tvly", "obsidian", "td"}
    assert set(data["conventions"]["exit_codes"]) == {"0", "1", "2"}


def test_catalogue_lists_positional_arguments_first(capsys):
    _, data = run_json(capsys, "commands")
    neighbors = next(c for c in data["commands"] if c["name"] == "graph neighbors")
    assert neighbors["arguments"][0] == {"name": "note", "positional": True, "help": "a vault-relative path or a bare note name"}
    direction = next(a for a in neighbors["arguments"] if a["name"] == "--direction")
    assert direction["choices"] == ["in", "out", "both"] and direction["default"] == "both"


# --- text for people ----------------------------------------------------------------------


def test_text_is_plain_when_piped_or_no_color(monkeypatch):
    assert not ui.Style().color  # pytest's stdout is not a TTY
    assert ui.Style(color=False).mark("ok") == "✓"
    monkeypatch.setenv("NO_COLOR", "1")

    class Tty:
        def isatty(self):
            return True

    assert not ui.color_enabled(Tty())
    monkeypatch.delenv("NO_COLOR")
    assert ui.color_enabled(Tty())
    assert "\033[" in ui.Style(color=True).mark("bad")


# --- DLQ: only open entries need a person --------------------------------------------------


def test_dlq_counts_open_entries_only(tmp_path):
    dlq = tmp_path / "00_Memory" / "dlq"
    dlq.mkdir(parents=True)
    (dlq / "a.md").write_text("---\nstatus: resolved\n---\n# a\n", encoding="utf-8")
    assert vault.dlq_status(tmp_path)["note"] == "no open DLQ entries (1 resolved)"
    (dlq / "b.md").write_text("---\nstatus: active\n---\n# b\n", encoding="utf-8")
    (dlq / "c.md").write_text("no frontmatter at all\n", encoding="utf-8")
    result = vault.dlq_status(tmp_path)
    assert (result["count"], result["open"]) == (3, 2)
    assert result["open_notes"] == ["00_Memory/dlq/b.md", "00_Memory/dlq/c.md"]


# --- status ---------------------------------------------------------------------------


def _registry(tmp_path, monkeypatch, plugins: dict) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": plugins}), encoding="utf-8")


def test_plugins_current_outdated_orphaned_and_missing(tmp_path, monkeypatch):
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    latest = {p["name"]: p["version"] for p in market["plugins"]}
    _registry(tmp_path, monkeypatch, {
        "obsidian@agentic-toolkit": [{"scope": "user", "version": latest["obsidian"]},
                                     {"scope": "project", "projectPath": "/x", "version": "0.0.1"}],
        "readwise@agentic-toolkit": [{"scope": "user", "version": latest["readwise"]}],
        "imagine@agentic-toolkit": [{"scope": "user", "version": "c5779c36f870"}],
        "other@elsewhere": [{"scope": "user", "version": "9"}],
    })
    rows = {r["plugin"]: r for r in status.plugins_section(REPO_ROOT)["plugins"]}
    assert rows["obsidian"]["state"] == "outdated"
    assert rows["readwise"]["state"] == "current"
    assert rows["imagine"]["state"] == "orphaned"
    assert rows["radar"]["state"] == "not-installed"
    assert "other" not in rows


def test_plugins_without_a_checkout_are_not_judged(tmp_path, monkeypatch):
    """`uv tool install` has no marketplace.json beside it: report nothing, never "orphaned"."""
    _registry(tmp_path, monkeypatch, {"obsidian@agentic-toolkit": [{"scope": "user", "version": "3.0.2"}]})
    section = status.plugins_section(None)
    assert section["marketplace_found"] is False and section["plugins"] == []


def test_status_json_on_the_example_vault(tmp_path, monkeypatch, capsys):
    _registry(tmp_path, monkeypatch, {"imagine@agentic-toolkit": [{"scope": "user", "version": "abc"}]})
    monkeypatch.setenv("TOOLKIT_VAULT", str(EXAMPLE_VAULT))
    code, data = run_json(capsys, "status", "--offline")
    assert set(data) >= {"ok", "problems", "toolkit", "engines", "plugins", "vault", "pipeline", "companions"}
    assert data["pipeline"] == {"present": False, "note": "this vault runs no pipeline"}
    assert data["engines"]["checked_latest"] is False
    assert data["engines"]["cloud_pin"].startswith("gaiafield-v")
    assert any(p["section"] == "plugins" and "imagine" in p["detail"] for p in data["problems"])
    assert code == 1 and data["ok"] is False
    for companion in data["companions"]:
        assert set(companion) <= {"cli", "path", "on_path", "ready", "version", "auth_mode", "note"}


def test_status_text_names_every_section(tmp_path, monkeypatch, capsys):
    _registry(tmp_path, monkeypatch, {})
    monkeypatch.setenv("TOOLKIT_VAULT", str(EXAMPLE_VAULT))
    _, out = run(capsys, "status", "--offline")
    for label in ("ENGINES", "PLUGINS", "VAULT", "COMPANIONS"):
        assert label in out
    assert "\033[" not in out


# --- search and graph ---------------------------------------------------------------------

needs_engines = pytest.mark.skipif(
    knowledge.farsight_binary() is None or knowledge.gaiafield_binary() is None,
    reason="engines not installed (unisphere engines install)",
)


@pytest.fixture
def example_vault_copy(tmp_path, monkeypatch):
    """The graph commands index into <vault>/.gaiafield; never write into the repo's own vault."""
    copy = tmp_path / "vault"
    shutil.copytree(EXAMPLE_VAULT, copy, ignore=shutil.ignore_patterns(".gaiafield"))
    monkeypatch.setenv("TOOLKIT_VAULT", str(copy))
    return copy


@needs_engines
def test_search_json(example_vault_copy, capsys):
    code, data = run_json(capsys, "search", "dead", "letter", "queue", "--limit", "3")
    assert code == 0 and data["query"] == "dead letter queue"
    assert 0 < len(data["results"]) <= 3
    assert set(data["results"][0]) >= {"path", "score", "title"}


@needs_engines
def test_graph_neighbors_path_and_suggestions(example_vault_copy, capsys):
    code, data = run_json(capsys, "graph", "neighbors", "Alex-Vega")
    assert code == 0 and data["op"] == "neighbors" and data["result"]
    code, data = run_json(capsys, "graph", "path", "Alex-Vega", "Gaiafield")
    assert code == 0 and data["result"]["connected"]
    code, data = run_json(capsys, "graph", "neighbors", "Gaiafeld-Typo")
    assert code == 1 and not data["ok"] and "Gaiafeld-Typo" in data["error"]
    assert isinstance(data["suggestions"], list)
    _, out = run(capsys, "graph", "path", "Alex-Vega", "Gaiafield")
    assert "hop(s)" in out and "Gaiafield" in out


# --- link ------------------------------------------------------------------------------


def test_link_writes_a_shim_and_never_clobbers_foreign_files(tmp_path, monkeypatch):
    monkeypatch.setattr(linker, "OBSIDIAN_APP_CLI", tmp_path / "no-obsidian")
    bin_dir = tmp_path / "bin"
    result = linker.link(REPO_ROOT, bin_dir, tmp_path / "MyVault")
    shim = (bin_dir / "unisphere").read_text(encoding="utf-8")
    assert result["links"][0] == {"name": "unisphere", "path": str(bin_dir / "unisphere"), "action": "created"}
    assert f"--project {REPO_ROOT}" in shim and f"TOOLKIT_VAULT={tmp_path / 'MyVault'}" in shim
    assert (bin_dir / "unisphere").stat().st_mode & 0o111
    assert all(r["name"] != "toolkit" for r in result["links"]) and not (bin_dir / "toolkit").exists()

    again = linker.link(REPO_ROOT, bin_dir, None)
    assert again["links"][0]["action"] == "updated"
    assert "TOOLKIT_VAULT" not in (bin_dir / "unisphere").read_text(encoding="utf-8")

    (bin_dir / "unisphere").write_text("#!/bin/sh\necho someone else's\n", encoding="utf-8")
    refused = linker.link(REPO_ROOT, bin_dir, None)
    assert refused["links"][0]["action"] == "skipped" and not refused["ok"]
    assert "someone else's" in (bin_dir / "unisphere").read_text(encoding="utf-8")
    assert linker.link(REPO_ROOT, bin_dir, None, force=True)["links"][0]["action"] == "updated"

    for row in again["links"][1:]:
        if row["action"] != "skipped":
            assert (bin_dir / row["name"]).is_symlink()


def test_link_removes_its_old_toolkit_entry_but_not_foreign_files(tmp_path, monkeypatch):
    monkeypatch.setattr(linker, "OBSIDIAN_APP_CLI", tmp_path / "no-obsidian")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "toolkit").write_text("#!/bin/sh\n# Written by `toolkit link` — old\n", encoding="utf-8")
    elsewhere = tmp_path / "someone-elses-gaiafield"
    elsewhere.write_text("", encoding="utf-8")
    (bin_dir / "gaiafield").symlink_to(elsewhere)

    rows = {r["name"]: r for r in linker.link(REPO_ROOT, bin_dir, None)["links"]}
    assert rows["toolkit"]["action"] == "removed" and not (bin_dir / "toolkit").exists()

    (bin_dir / "toolkit").symlink_to(bin_dir / "unisphere")  # the alias an earlier link wrote
    assert {r["name"]: r for r in linker.link(REPO_ROOT, bin_dir, None)["links"]}["toolkit"]["action"] == "removed"

    (bin_dir / "toolkit").write_text("#!/bin/sh\necho another tool\n", encoding="utf-8")
    assert "toolkit" not in {r["name"] for r in linker.link(REPO_ROOT, bin_dir, None)["links"]}
    assert (bin_dir / "toolkit").read_text(encoding="utf-8") == "#!/bin/sh\necho another tool\n"
    assert rows["gaiafield"]["action"] == "skipped"
    assert (bin_dir / "gaiafield").resolve() == elsewhere.resolve(), "a foreign symlink was replaced"


def test_shim_quotes_paths(tmp_path):
    """A vault path is data: $(…), quotes and spaces must not run or break the shim."""
    marker = tmp_path / "ran"
    odd = tmp_path / f"My Vault $(touch {marker}) 'x'"
    shim = linker.shim_text(REPO_ROOT, odd)
    probe = tmp_path / "probe.sh"
    probe.write_text(shim.replace('exec uv run', 'printf %s "$TOOLKIT_VAULT" #'), encoding="utf-8")
    import subprocess

    out = subprocess.run(["sh", str(probe)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}).stdout
    assert out == str(odd) and not marker.exists()


# --- review regressions (PR #71) ----------------------------------------------------------------


def test_path_render_accepts_inferred_hops():
    text = cli._render_graph({"op": "path", "result": {"connected": True, "path": [
        "A.md", {"path": "B.md", "kind": "inferred"}, "C.md"]}})
    assert "2 hop(s)" in text and "B.md" in text


def test_unknown_latest_release_is_a_problem_unless_offline(monkeypatch):
    rows = [{"engine": "gaiafield", "installed_tag": "gaiafield-v0.2.4", "latest_tag": None, "up_to_date": False,
             "note": "could not check latest release: offline"}]
    base = {"plugins": {"plugins": []}, "vault": {"found": True, "dlq": {}, "checkout": {}}, "pipeline": {}}
    online = status._problems({**base, "engines": {"engines": rows, "checked_latest": True}})
    assert online and "latest release unknown" in online[0]["detail"]
    assert not status._problems({**base, "engines": {"engines": rows, "checked_latest": False}})


def test_unreadable_dlq_entry_counts_as_open(tmp_path):
    dlq = tmp_path / "00_Memory" / "dlq"
    dlq.mkdir(parents=True)
    (dlq / "bad.md").write_bytes(b"---\nstatus: resolved\n---\n\xff\xfe broken")
    assert vault.dlq_status(tmp_path)["open"] == 1


def test_the_cli_is_unisphere_only(capsys):
    """Renamed from `toolkit` on 2026-09-28, with no alias left behind."""
    import tomllib

    scripts = tomllib.loads((REPO_ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert scripts == {"unisphere": "toolkit_core.cli:main"}
    assert cli._build_parser().prog == "unisphere"
    _, data = run_json(capsys, "commands")
    assert all(c["example"].startswith("unisphere ") for c in data["commands"])
