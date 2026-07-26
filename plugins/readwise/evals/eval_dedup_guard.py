"""Eval: the dedup-before-distill acceptance criterion — running ingest's capture-write
step twice over the same clipping never produces a second file. This is readwise's own
share of the rule in contract/templates/VAULT_CLAUDE.md ("check for prior distillation
before writing... overlapping capture sources collide more often than expected"), earned
by the 2026-07-26 X-Bookmark/Readwise double-distill collision: cross-origin dedup is
distill's job, but readwise re-emitting a duplicate raw capture on every re-ingest would
make that job harder for no reason. Writes, so this runs against a sandbox copy.
"""
from __future__ import annotations

import json
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox


def run(vault: Path) -> dict:
    import sys

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_captures as bc
    from vault_utils import iter_captures

    fixture = json.loads((Path(__file__).parent / "fixtures" / "reader_item.json").read_text())

    sandbox_vault = make_sandbox(vault)
    try:
        path1, status1 = bc.write_capture(sandbox_vault, fixture)
        path2, status2 = bc.write_capture(sandbox_vault, fixture)

        problems = []
        if status1 != "written":
            problems.append(f"first write: expected 'written', got {status1!r}")
        if status2 != "skipped-duplicate":
            problems.append(f"second write: expected 'skipped-duplicate', got {status2!r}")
        if path2 is not None:
            problems.append(f"second write returned a path when it should have returned None: {path2}")

        matching = [
            p for p in iter_captures(sandbox_vault)
            if fixture["id"] in p.read_text(encoding="utf-8", errors="replace")
        ]
        if len(matching) != 1:
            problems.append(f"expected exactly 1 capture file for doc_id {fixture['id']!r}, found {len(matching)}: {[p.name for p in matching]}")

        if problems:
            return {"eval": "dedup_guard", "pass": False, "detail": "; ".join(problems)}
        return {"eval": "dedup_guard", "pass": True, "detail": f"second write correctly skipped; 1 capture file present ({path1.name})"}
    finally:
        teardown_sandbox(sandbox_vault)
