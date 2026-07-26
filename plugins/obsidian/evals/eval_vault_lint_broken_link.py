"""Eval: checks.links.audit() flags the vault's planted broken wikilink.

Fixture: `04_Resources/Guides/Vault-Maintenance-and-Linting.md` links to
`[[Nonexistent-Note-For-Linting-Demo]]` on purpose — see `Test-Corpus-Map.md`'s "Planted
edge cases" table. Read-only: audit() never writes, so this runs directly against the
resolved vault, no sandbox needed.
"""
from __future__ import annotations

from pathlib import Path

FIXTURE_REL = "04_Resources/Guides/Vault-Maintenance-and-Linting.md"
EXPECTED_TARGET = "Nonexistent-Note-For-Linting-Demo"


def run(vault: Path) -> dict:
    fixture = vault / FIXTURE_REL
    if not fixture.is_file():
        return {"eval": "vault_lint_broken_link", "pass": False, "detail": f"fixture not present: {FIXTURE_REL}"}

    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from checks import links as links_check
    from vault_utils import read_frontmatter

    fm, body = read_frontmatter(fixture)
    issues = links_check.audit(fixture, fm, body, vault)
    hit = next((i for i in issues if EXPECTED_TARGET in i.description), None)

    if hit is None:
        return {
            "eval": "vault_lint_broken_link", "pass": False,
            "detail": f"audit() did not flag [[{EXPECTED_TARGET}]]; issues found: {[i.description for i in issues]}",
        }
    return {"eval": "vault_lint_broken_link", "pass": True, "detail": f"flagged: {hit.description}"}
