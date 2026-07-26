"""Eval: distill-memory's write primitive is idempotent — distilling the same lesson
from the same source twice produces exactly one note, byte-identical after both calls
— and a genuinely new source for the same lesson still updates in place rather than
duplicating. Fixture-driven, no network, no real session data. Writes, so runs against
a sandbox copy of ./vault.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox


def run(vault: Path) -> dict:
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import distill_memory as dm

    sandbox_vault = make_sandbox(vault)
    try:
        base_args = dict(
            vault=sandbox_vault,
            kind="warning",
            slug="uv-run-project-flag-required",
            title="uv run without --project silently uses the wrong venv",
            body_text=(
                "Running `uv run python3 script.py` from a plugin's scripts/ directory without "
                "`--project scripts` can pick up an unrelated venv on PATH. Always pass "
                "`--project scripts` explicitly.\n"
            ),
            source="00_Memory/sessions/2026-07-26-fixture-session.md",
            today="2026-07-26",
        )

        dest1, created1 = dm.write_memory_note(**base_args)
        content1 = dest1.read_text(encoding="utf-8")
        dest2, created2 = dm.write_memory_note(**base_args)
        content2 = dest2.read_text(encoding="utf-8")

        problems = []
        if not created1:
            problems.append("first call should report a fresh creation")
        if created2:
            problems.append("second identical call reported a fresh creation")
        if dest1 != dest2:
            problems.append(f"second call wrote a different path: {dest1} vs {dest2}")
        if content1 != content2:
            problems.append("note content changed between two identical calls (not idempotent)")

        # A genuinely new source for the same lesson should update in place, not duplicate.
        update_args = {**base_args, "source": "00_Memory/sessions/2026-07-27-fixture-session-2.md", "today": "2026-07-27"}
        dest3, created3 = dm.write_memory_note(**update_args)
        if created3:
            problems.append("a new source on an existing slug should update, not report a fresh creation")
        if dest3 != dest1:
            problems.append(f"update wrote a different path than the original note: {dest3} vs {dest1}")

        matches = list((sandbox_vault / "00_Memory" / "notes").glob(f"{base_args['slug']}*.md"))
        if len(matches) != 1:
            problems.append(f"expected exactly one note for slug {base_args['slug']!r}, found {len(matches)}")

        import memory_vault as mv
        fm, _ = mv.read_note(dest1)
        if fm.get("sources") != [base_args["source"], update_args["source"]]:
            problems.append(f"expected both sources recorded in order, got {fm.get('sources')!r}")
        if fm.get("updated") != "2026-07-27":
            problems.append(f"expected updated=2026-07-27 after the update call, got {fm.get('updated')!r}")

        if problems:
            return {"eval": "distill_idempotent", "pass": False, "detail": "; ".join(problems)}
        return {
            "eval": "distill_idempotent",
            "pass": True,
            "detail": f"idempotent create+no-op+update confirmed: {dest1.relative_to(sandbox_vault)}",
        }
    finally:
        teardown_sandbox(sandbox_vault)
