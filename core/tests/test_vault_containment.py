"""A `.md` symlink that resolves outside the vault is not a vault note (Copilot review of #26).

The unattended pipeline indexes, reads and sends on vault notes. A symlink planted in an active
folder or at the vault root must not pull a file from elsewhere into `Index.md`, discovery, search
or the judgment service. Each test fails on main after #26 and passes with the containment check.
"""

from __future__ import annotations

import json
import subprocess
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


def test_the_capture_queue_skips_symlinks_out_of_the_vault(vault, tmp_path):
    # Copilot re-review of #28: pipeline_run.queue read 01_Capture/*.md before any containment check.
    cap = vault / "01_Capture"
    cap.mkdir()
    (cap / "Real-Capture.md").write_text("---\nstatus: capture\n---\n\nclip\n", encoding="utf-8")
    (cap / "Planted-Capture.md").symlink_to(tmp_path / "outside" / "private.md")
    (vault / "00_Memory").mkdir()
    result = repr(_module("obsidian", "pipeline_run").queue(vault))
    assert "Real-Capture" in result and "Planted-Capture" not in result, result


def test_radar_and_readwise_indexes_skip_symlinks_out_of_the_vault(vault, tmp_path):
    # Copilot re-review of #28: both scripts run in the unattended pipeline with their own walkers.
    (tmp_path / "outside" / "sourced.md").write_text(
        "---\nsource: https://example.com/private\nreadwise_doc_id: 999\n---\n\nx\n", encoding="utf-8")
    (vault / "03_Areas" / "Planted-Source.md").symlink_to(tmp_path / "outside" / "sourced.md")
    (vault / "03_Areas" / "Real-Source.md").write_text(
        "---\nsource: https://example.com/real\nreadwise_doc_id: 111\n---\n\nx\n", encoding="utf-8")
    # Each in its own interpreter: plugins may ship same-named modules (e.g. `judgments`), and an
    # import left over from another test would shadow them.
    def run(plugin: str, code: str):
        out = subprocess.run([sys.executable, "-c", code, str(vault)], cwd=REPO_ROOT / "plugins" / plugin / "scripts",
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)

    radar = run("radar", "import json, sys; from pathlib import Path; import radar\n"
                         "print(json.dumps(radar.vault_sources(Path(sys.argv[1]))))")
    assert any("Real-Source" in v for v in radar.values()) and not any("Planted" in v for v in radar.values()), radar
    ids, sources = run("readwise", "import json, sys; from pathlib import Path; import ingest\n"
                                   "print(json.dumps(ingest.vault_index(Path(sys.argv[1]))))")
    assert "111" in ids and "999" not in ids, ids
    assert not any("Planted" in v for v in sources.values()), sources


def test_a_malformed_pdf_url_is_refused_not_raised():
    pdf = _module("readwise", "pdf_extract")
    bad = "http://[::1"  # urlsplit raises ValueError on a broken IPv6 literal
    assert pdf._is_web_url(bad) is False
    assert pdf._download(bad) is None
