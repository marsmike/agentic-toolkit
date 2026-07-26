"""Mechanically-checkable conformance of ./vault against contract/VAULT_SCHEMA.md.

Only rules that are checkable by a script without judgment calls: folder presence, every
note's frontmatter parsing, and required-for-status fields being present where the schema
says they must be. This is the "example vault as executable contract" check from docs/PLAN.md
— it is not a full schema validator and doesn't try to be.
"""

from __future__ import annotations

from conftest import EXAMPLE_VAULT, skip_if_example_vault_empty
from toolkit_core.vault import PARA_FOLDERS, FrontmatterError, parse_frontmatter


def test_para_folders_exist():
    skip_if_example_vault_empty()
    for folder in PARA_FOLDERS:
        assert (EXAMPLE_VAULT / folder).is_dir(), f"./vault is missing {folder}/"


def test_every_note_frontmatter_parses():
    skip_if_example_vault_empty()
    failures = []
    for note_path in EXAMPLE_VAULT.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        try:
            parse_frontmatter(text)
        except FrontmatterError as exc:
            failures.append(f"{note_path.relative_to(EXAMPLE_VAULT)}: {exc}")
    assert not failures, "malformed frontmatter:\n" + "\n".join(failures)


def test_distilled_notes_carry_source_and_processed_date():
    skip_if_example_vault_empty()
    failures = []
    for note_path in EXAMPLE_VAULT.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, _, had_frontmatter = parse_frontmatter(text)
        if not had_frontmatter or frontmatter.get("status") != "distilled":
            continue
        missing = [f for f in ("source", "processed_date") if f not in frontmatter]
        if missing:
            rel = note_path.relative_to(EXAMPLE_VAULT)
            failures.append(f"{rel}: status=distilled but missing {missing}")
    assert not failures, "\n".join(failures)


def test_resources_carry_description_and_kind():
    skip_if_example_vault_empty()
    resources_dir = EXAMPLE_VAULT / "04_Resources"
    if not resources_dir.is_dir():
        return
    failures = []
    for note_path in resources_dir.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, _, had_frontmatter = parse_frontmatter(text)
        if not had_frontmatter:
            continue
        missing = [f for f in ("description", "kind") if f not in frontmatter]
        if missing:
            rel = note_path.relative_to(EXAMPLE_VAULT)
            failures.append(f"{rel}: in 04_Resources but missing {missing}")
    assert not failures, "\n".join(failures)


def test_areas_carry_description():
    skip_if_example_vault_empty()
    areas_dir = EXAMPLE_VAULT / "03_Areas"
    if not areas_dir.is_dir():
        return
    failures = []
    for note_path in areas_dir.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, _, had_frontmatter = parse_frontmatter(text)
        if not had_frontmatter or "description" in frontmatter:
            continue
        failures.append(str(note_path.relative_to(EXAMPLE_VAULT)))
    assert not failures, "03_Areas notes missing description:\n" + "\n".join(failures)


def test_capture_is_flat_no_subfolders():
    skip_if_example_vault_empty()
    capture_dir = EXAMPLE_VAULT / "01_Capture"
    if not capture_dir.is_dir():
        return
    subdirs = [p for p in capture_dir.iterdir() if p.is_dir()]
    assert not subdirs, f"01_Capture/ must be flat, found subfolders: {subdirs}"


def test_core_and_plugin_frontmatter_implementations_agree(tmp_path):
    """The obsidian plugin's standalone vault_utils must apply the same floor rule as
    toolkit_core — two implementations of the contract may never drift apart
    [earned: adversarial R0 review 2026-07-26 — duplicated logic with no shared test]."""
    import sys

    scripts_dir = EXAMPLE_VAULT.parent / "plugins" / "obsidian" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import vault_utils
    finally:
        sys.path.remove(str(scripts_dir))

    note = tmp_path / "note.md"
    note.write_text(
        "---\ndescription: parity check\nstatus: draft\nunknown_field: keep-me\n"
        "nested:\n  a: 1\n---\n\nBody text.\n",
        encoding="utf-8",
    )

    core_fm, core_body, _ = parse_frontmatter(note.read_text(encoding="utf-8"))
    plugin_fm, plugin_body = vault_utils.read_frontmatter(note)

    assert plugin_fm == core_fm
    assert plugin_body.strip() == core_body.strip()
    assert plugin_fm["unknown_field"] == "keep-me"
