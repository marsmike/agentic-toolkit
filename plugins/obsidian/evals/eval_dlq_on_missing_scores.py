"""Eval: the dead-letter acceptance criterion — a script that can't confidently finish
writes a DLQ note under 00_Memory/dlq/ instead of silently proceeding.

Triggers retrieval_verification.build_report() with one sampled note missing from the
scores map (simulating an interrupted predict/score pass) and asserts a DLQ note lands
with the frontmatter fields 00_Memory/dlq/*.md notes are expected to carry. Writes, so
this runs against a sandbox copy.
"""
from __future__ import annotations

from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

REQUIRED_FRONTMATTER_FIELDS = ("description", "status", "created", "confidence")


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import retrieval_verification as rv
    from vault_utils import read_frontmatter

    sandbox_vault = make_sandbox(vault)
    try:
        dlq_dir = sandbox_vault / "00_Memory" / "dlq"
        before = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()

        samples = [
            {"path": "04_Resources/Guides/Vault-Maintenance-and-Linting.md", "title": "Vault-Maintenance-and-Linting", "description": "x", "has_description": True},
            {"path": "04_Resources/Guides/Test-Corpus-Map.md", "title": "Test-Corpus-Map", "description": "y", "has_description": True},
        ]
        # Deliberately incomplete: only one of the two sampled notes has a score.
        scores = {samples[0]["path"]: {"score": 4, "predicted": "p", "note": "n"}}

        report = rv.build_report(samples, scores, sandbox_vault)

        after = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()
        new_entries = after - before

        problems = []
        if samples[1]["path"] not in report["missing_scores"]:
            problems.append(f"expected missing_scores to include {samples[1]['path']!r}, got {report['missing_scores']}")
        if not new_entries:
            problems.append("no new DLQ note was written under 00_Memory/dlq/")
        else:
            dlq_note = max(new_entries)
            fm, body = read_frontmatter(dlq_note)
            missing_fields = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in fm]
            if missing_fields:
                problems.append(f"{dlq_note.name} missing frontmatter fields: {missing_fields}")
            if not body.strip():
                problems.append(f"{dlq_note.name} has an empty body")

        if problems:
            return {"eval": "dlq_on_missing_scores", "pass": False, "detail": "; ".join(problems)}
        return {"eval": "dlq_on_missing_scores", "pass": True, "detail": f"DLQ note written: {max(new_entries).name}"}
    finally:
        teardown_sandbox(sandbox_vault)
