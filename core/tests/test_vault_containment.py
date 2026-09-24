"""A `.md` symlink that resolves outside the vault is not a vault note (Copilot review of #26).

The unattended pipeline indexes, reads and sends on vault notes. A symlink planted in an active
folder or at the vault root must not pull a file from elsewhere into `Index.md`, discovery, search
or the judgment service. Each test fails on main after #26 and passes with the containment check.
"""

from __future__ import annotations

import sys

import pytest
from conftest import REPO_ROOT

SECRET = "---\nstatus: active\ndescription: private text outside the vault\n---\n\nnot for the vault\n"


def _module(plugin: str, name: str):
    scripts = str(REPO_ROOT / "plugins" / plugin / "scripts")
    sys.path.insert(0, scripts)
    for mod in ("vault_utils", name):
        sys.modules.pop(mod, None)
    try:
        return __import__(name)
    finally:
        sys.path.remove(scripts)


@pytest.fixture()
def vault(tmp_path):
    outside = tmp_path / "outside" / "private.md"
    outside.parent.mkdir()
    outside.write_text(SECRET, encoding="utf-8")
    v = tmp_path / "vault"
    for folder in ("02_Projects", "03_Areas", "04_Resources"):
        (v / folder).mkdir(parents=True)
    (v / "03_Areas" / "Real-Note.md").write_text("---\nstatus: active\n---\n\nreal\n", encoding="utf-8")
    (v / "03_Areas" / "Planted.md").symlink_to(outside)
    (v / "Persona.md").write_text("---\nstatus: active\n---\n\nroot note\n", encoding="utf-8")
    (v / "Root-Planted.md").symlink_to(outside)
    return v


def test_index_build_skips_symlinks_out_of_the_vault(vault):
    notes = _module("obsidian", "index_build").collect(vault)
    assert "03_Areas/Real-Note" in notes and "Persona" in notes
    assert "03_Areas/Planted" not in notes and "Root-Planted" not in notes, sorted(notes)


def test_obsidian_discovery_skips_symlinks_out_of_the_vault(vault):
    vu = _module("obsidian", "vault_utils")
    roots = {p.name for p in vu.root_active_notes(vault)}
    assert roots == {"Persona.md"}, roots
    found = {p.name for p in vu.discover_notes(vault)}
    assert "Real-Note.md" in found and "Persona.md" in found
    assert not found & {"Planted.md", "Root-Planted.md"}, found


def test_core_listing_skips_symlinks_out_of_the_vault(vault):
    from toolkit_core.vault import list_active_notes
    names = {p.name for p in list_active_notes(vault)}
    assert {"Real-Note.md", "Persona.md"} <= names
    assert not names & {"Planted.md", "Root-Planted.md"}, names


def test_a_symlink_loop_is_skipped_not_fatal(vault):
    # Codex cross-review of the fix: resolve() can raise on a loop and abort the whole run.
    loop = vault / "03_Areas" / "Loop.md"
    loop.symlink_to(loop)
    found = {p.name for p in _module("obsidian", "vault_utils").discover_notes(vault)}
    assert "Real-Note.md" in found and "Loop.md" not in found
    from toolkit_core.vault import list_active_notes
    assert "Loop.md" not in {p.name for p in list_active_notes(vault)}


def test_a_symlink_inside_the_vault_still_counts(vault):
    # Containment, not a blanket symlink ban: an alias to another vault note stays a note.
    (vault / "04_Resources" / "Alias.md").symlink_to(vault / "03_Areas" / "Real-Note.md")
    found = {p.name for p in _module("obsidian", "vault_utils").discover_notes(vault)}
    assert "Alias.md" in found


def test_a_malformed_pdf_url_is_refused_not_raised():
    pdf = _module("readwise", "pdf_extract")
    bad = "http://[::1"  # urlsplit raises ValueError on a broken IPv6 literal
    assert pdf._is_web_url(bad) is False
    assert pdf._download(bad) is None
