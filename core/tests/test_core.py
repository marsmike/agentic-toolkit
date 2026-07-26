"""Essential core tests: the floor rule, resolution precedence, init safety, doctor.

Deliberately lean — one test per unique failure mode, nothing else.
"""

from __future__ import annotations

import json

import pytest
from conftest import skip_if_example_vault_empty
from toolkit_core import cli, knowledge, profile, vault

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
