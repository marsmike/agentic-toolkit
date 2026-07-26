"""Essential core tests: the floor rule, resolution precedence, init safety, doctor.

Deliberately lean — one test per unique failure mode, nothing else.
"""

from __future__ import annotations

import json
import shutil

import pytest
from conftest import skip_if_example_vault_empty
from toolkit_core import cli, engines, knowledge, profile, vault

NOTE_TEXT = """---
description: A test note.
status: draft
totally_unknown_field: keep-me
nested_unknown:
  a: 1
  b: 2
tags:
  - alpha
  - domain/beta
---

# Body

Some body text with a [[Wikilink]].
"""


def test_frontmatter_floor_rule_round_trip(tmp_path):
    """Unknown keys survive parse -> render and targeted updates (contract/VAULT_SCHEMA.md)."""
    frontmatter, body, had = vault.parse_frontmatter(NOTE_TEXT)
    assert had and frontmatter["totally_unknown_field"] == "keep-me"
    reparsed, reparsed_body, _ = vault.parse_frontmatter(vault.render_frontmatter(frontmatter, body, had))
    assert reparsed == frontmatter and reparsed_body == body

    note_path = tmp_path / "note.md"
    note_path.write_text(NOTE_TEXT, encoding="utf-8")
    updated = vault.update_note_frontmatter(note_path, {"status": "distilled"})
    assert updated["status"] == "distilled"
    assert updated["totally_unknown_field"] == "keep-me"
    assert updated["nested_unknown"] == {"a": 1, "b": 2}


def test_malformed_yaml_raises():
    with pytest.raises(vault.FrontmatterError):
        vault.parse_frontmatter("---\nkey: [unclosed\n---\nbody\n")


def test_vault_resolution_precedence(monkeypatch, tmp_path, repo_root):
    custom = tmp_path / "my-vault"
    custom.mkdir()
    monkeypatch.setenv("TOOLKIT_VAULT", str(custom))
    resolution = vault.resolve_vault()
    assert resolution.source == "env:TOOLKIT_VAULT" and resolution.path == custom.resolve()

    monkeypatch.delenv("TOOLKIT_VAULT", raising=False)
    monkeypatch.chdir(repo_root)
    resolution = vault.resolve_vault()
    assert resolution.source == "default:./vault" and resolution.path == repo_root / "vault"


def test_vault_init_scaffolds_and_refuses_nonempty(tmp_path, claude_md_template):
    target = tmp_path / "new-vault"
    vault.scaffold_vault(target, claude_md_template)
    for folder in vault.PARA_FOLDERS:
        assert (target / folder).is_dir(), f"missing {folder}"
    assert (target / "Config" / "toolkit").is_dir()
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == claude_md_template.read_text(encoding="utf-8")

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(vault.VaultInitError):
        vault.scaffold_vault(occupied, claude_md_template)
    assert (occupied / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_profile_resolution_precedence(tmp_path, monkeypatch):
    config_dir = tmp_path / "Config" / "toolkit"
    config_dir.mkdir(parents=True)
    (config_dir / "obsidian.md").write_text("---\nsearch_score_gate: 0.7\n---\nnote\n", encoding="utf-8")

    monkeypatch.delenv("TOOLKIT_OBSIDIAN_SEARCH_SCORE_GATE", raising=False)
    assert profile.get(tmp_path, "obsidian", "search_score_gate", default=0.5) == 0.7
    monkeypatch.setenv("TOOLKIT_OBSIDIAN_SEARCH_SCORE_GATE", "0.9")
    assert profile.get(tmp_path, "obsidian", "search_score_gate", default=0.5) == "0.9"
    assert profile.get(tmp_path, "obsidian", "missing_key", default="the-default") == "the-default"
    assert profile.read_profile_note(tmp_path, "no-such-plugin") == {}


def test_doctor_green_on_example_vault(monkeypatch, repo_root, capsys):
    skip_if_example_vault_empty()
    monkeypatch.delenv("TOOLKIT_VAULT", raising=False)
    monkeypatch.delenv("TOOLKIT_GAIAFIELD_BIN", raising=False)
    monkeypatch.setattr(knowledge, "gaiafield_binary", lambda: None)
    monkeypatch.chdir(repo_root)

    exit_code = cli.main(["doctor", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert exit_code == 0 and out["ok"] is True
    assert out["vault_source"] == "default:./vault"
    assert set(out["para_folders"]) == set(vault.PARA_FOLDERS)
    assert out["frontmatter_parse_errors"] == []
    assert "obsidian" in out["profiles"]
    assert out["graph"] == {"present": False, "note": "gaiafield not present"}

    # contract/VAULT_SCHEMA.md's root-note clause: a root-level *.md with its own
    # frontmatter status: active (the example vault's Alex-Vega.md persona note) counts as
    # active content; Index.md/CLAUDE.md (no frontmatter) and Config/ never do.
    active_rels = {
        p.relative_to(repo_root / "vault").as_posix() for p in vault.list_active_notes(repo_root / "vault")
    }
    assert "Alex-Vega.md" in active_rels
    assert "Index.md" not in active_rels
    assert "CLAUDE.md" not in active_rels
    assert not any(rel.startswith("Config/") for rel in active_rels)


def test_doctor_graph_section_reports_present_binary(monkeypatch, repo_root, tmp_path, capsys):
    """With a gaiafield binary configured, doctor's graph section reports counts and
    freshness from `gaiafield stats --json` rather than "not present" — exercised with a
    stub script and a tmp_path db (never the real vault's) so this doesn't depend on the
    Rust crate being built for pytest to pass, and never touches ./vault/.gaiafield."""
    skip_if_example_vault_empty()
    monkeypatch.delenv("TOOLKIT_VAULT", raising=False)
    monkeypatch.chdir(repo_root)

    fake_db = tmp_path / "graph.db"
    fake_db.write_bytes(b"")
    monkeypatch.setattr(knowledge, "default_db_path", lambda vault_path: fake_db)

    stub = tmp_path / "gaiafield"
    stub.write_text(
        "#!/bin/sh\n"
        'echo \'{"nodes": 73, "edges": 627, "dangling_edges": 1, "boundary_violations": 0, "top_linked": []}\'\n'
    )
    stub.chmod(0o755)
    monkeypatch.setenv("TOOLKIT_GAIAFIELD_BIN", str(stub))

    exit_code = cli.main(["doctor", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert out["graph"]["present"] is True
    assert out["graph"]["nodes"] == 73
    assert out["graph"]["dangling_edges"] == 1
    assert out["graph"]["stale"] is False  # db just written now postdates every existing note's mtime
    # This stub's stats JSON carries no model/inferred/ambiguous fields at all — the v1
    # engine shape, predating gaiafield v2's inference layer (contract/KNOWLEDGE_API.md).
    assert out["graph"]["inference"] == {
        "available": False,
        "note": "engine lacks inference (v1 binary — no inference fields in stats)",
    }


def test_doctor_graph_section_reports_inference_when_present(monkeypatch, repo_root, tmp_path, capsys):
    """A v2 `gaiafield stats --json` payload carrying model/gates/inferred/ambiguous
    fields surfaces them under `graph.inference` instead of the v1 "engine lacks
    inference" fallback."""
    skip_if_example_vault_empty()
    monkeypatch.delenv("TOOLKIT_VAULT", raising=False)
    monkeypatch.chdir(repo_root)

    fake_db = tmp_path / "graph.db"
    fake_db.write_bytes(b"")
    monkeypatch.setattr(knowledge, "default_db_path", lambda vault_path: fake_db)

    stub = tmp_path / "gaiafield"
    stub.write_text(
        "#!/bin/sh\n"
        'echo \'{"nodes": 73, "edges": 627, "dangling_edges": 1, "boundary_violations": 0, '
        '"top_linked": [], "model": "stub-embed-v1", "high_gate": 0.82, "low_gate": 0.68, '
        '"inferred_edges": 12, "ambiguous_edges": 3}\'\n'
    )
    stub.chmod(0o755)
    monkeypatch.setenv("TOOLKIT_GAIAFIELD_BIN", str(stub))

    exit_code = cli.main(["doctor", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert out["graph"]["inference"] == {
        "available": True,
        "model": "stub-embed-v1",
        "high_gate": 0.82,
        "low_gate": 0.68,
        "inferred_edges": 12,
        "ambiguous_edges": 3,
        "note": "12 inferred, 3 ambiguous (model=stub-embed-v1)",
    }

    # The untested middle state: a v2 binary whose index exists but `gaiafield infer`
    # hasn't run yet reports `model: ""` (key present, value empty) rather than omitting
    # the key entirely (the v1 case, covered above) or populating it (the case just
    # asserted). knowledge._inference_status() is exercised directly here rather than
    # through another doctor/stub round trip — same three-state function, no new stub
    # needed.
    assert knowledge._inference_status({"model": ""}) == {
        "available": False,
        "note": "not inferred — run `gaiafield infer` to compute inferred edges",
    }


# --- engines: platform-triple mapping, manifest round-trip, discovery-dir probe order ---
# No network in any of these — the fetch itself (engines._fetch_releases /
# install_engine's download) is never exercised here, only the pure-logic and
# filesystem-only pieces around it.


def test_engine_target_triple_mapping():
    """Mirrors the exact matrix in .github/workflows/release-binaries.yml (plus the
    real, well-formed Darwin/x86_64 and Windows/x86_64 triples this repo doesn't build
    for on every leg — see engines.py's `_TARGET_TRIPLES` docstring)."""
    assert engines.target_triple("Darwin", "arm64") == "aarch64-apple-darwin"
    assert engines.target_triple("Darwin", "x86_64") == "x86_64-apple-darwin"
    assert engines.target_triple("Linux", "aarch64") == "aarch64-unknown-linux-musl"
    assert engines.target_triple("Linux", "x86_64") == "x86_64-unknown-linux-musl"
    assert engines.target_triple("Windows", "AMD64") == "x86_64-pc-windows-msvc"
    # An OS/arch combo not in the release matrix reads as "unsupported", not a guess.
    assert engines.target_triple("Linux", "i686") is None
    assert engines.target_triple("FreeBSD", "x86_64") is None


def test_engines_latest_for_engine_picks_newest_matching_tag():
    """`_latest_for_engine` trusts the GitHub API's own newest-first ordering and just
    filters by tag prefix — each engine's own release cadence never leaks into the
    other's "latest"."""
    releases = [
        {"tag_name": "gaiafield-v0.2.0", "draft": False, "prerelease": False, "assets": []},
        {"tag_name": "gaiafield-v0.1.1", "draft": False, "prerelease": False, "assets": []},
        {"tag_name": "farsight-v0.1.1", "draft": False, "prerelease": False, "assets": []},
        {"tag_name": "gaiafield-v0.3.0-rc1", "draft": False, "prerelease": True, "assets": []},
    ]
    assert engines._latest_for_engine("gaiafield", releases)["tag_name"] == "gaiafield-v0.2.0"
    assert engines._latest_for_engine("farsight", releases)["tag_name"] == "farsight-v0.1.1"
    assert engines._latest_for_engine("no-such-engine", releases) is None


def test_engine_manifest_round_trip_and_install_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert engines.install_dir() == tmp_path / ".local" / "share" / "agentic-toolkit" / "bin"
    assert engines.read_manifest() == {}  # no manifest yet is a normal state, not an error

    payload = {"farsight": {"tag": "farsight-v0.1.1", "sha256": "deadbeef"}}
    engines.write_manifest(payload)
    assert engines.read_manifest() == payload


def test_engine_manifest_corruption_degrades_to_not_installed(tmp_path, monkeypatch):
    """A corrupted manifest.json (unparseable JSON) must never raise: `read_manifest()`
    degrades to `{}` — the same "no manifest yet" state a fresh install sees — and
    `status_all()` reports every engine as a not-installed row rather than crashing on
    the bad file. No network: `_fetch_releases` is stubbed to an empty list."""
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(engines, "_fetch_releases", lambda: [])

    manifest_file = engines.manifest_path()
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text("{not valid json!!", encoding="utf-8")

    assert engines.read_manifest() == {}

    rows = engines.status_all()
    assert len(rows) == len(engines.ENGINES)
    for row in rows:
        assert row["installed_tag"] is None
        assert row["installed_path"] is None
        assert row["up_to_date"] is False


def test_engine_install_dir_honors_xdg_data_home(tmp_path, monkeypatch):
    xdg = tmp_path / "xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    assert engines.install_dir() == xdg / "agentic-toolkit" / "bin"


def test_discovery_chain_probe_order_env_beats_install_dir_beats_absent(tmp_path, monkeypatch):
    """`knowledge.gaiafield_binary()`'s three-step chain: env var, then PATH, then the
    well-known engines install dir, then absent. PATH is stubbed out entirely so this
    doesn't depend on whether the real dev machine happens to have gaiafield on PATH."""
    monkeypatch.delenv("TOOLKIT_GAIAFIELD_BIN", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda name: None)

    assert knowledge.gaiafield_binary() is None  # absent: no env, no PATH, no install-dir file

    install_bin = engines.binary_path("gaiafield")
    install_bin.parent.mkdir(parents=True, exist_ok=True)
    install_bin.write_text("#!/bin/sh\necho stub\n", encoding="utf-8")
    install_bin.chmod(0o755)
    assert knowledge.gaiafield_binary() == str(install_bin)  # install-dir beats absent

    monkeypatch.setenv("TOOLKIT_GAIAFIELD_BIN", "/explicit/path/gaiafield")
    assert knowledge.gaiafield_binary() == "/explicit/path/gaiafield"  # env beats install-dir
