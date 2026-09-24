"""Eval: distill-memory's write primitive refuses a slug that is a path (review-01 SEC-5). The
slug is proposed by a model; `/x`, `../x` or `a/b` must never write outside
`00_Memory/notes/`, while an ordinary slug still writes there. Writes, so runs against a
sandbox copy of ./vault.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

BAD_SLUGS = ("../escaped", "../../escaped", "/tmp/escaped", "sub/escaped", "..", ".", "", "a\\b", "C:escaped", "C:\\escaped")


def run(vault: Path) -> dict:
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import distill_memory as dm

    sandbox_vault = make_sandbox(vault)
    problems = []
    try:
        args = dict(vault=sandbox_vault, kind="warning", title="t", body_text="b\n",
                    source="00_Memory/sessions/2026-09-24-fixture.md", today="2026-09-24")
        notes_dir = (sandbox_vault / "00_Memory" / "notes").resolve()
        for slug in BAD_SLUGS:
            try:
                dest, _ = dm.write_memory_note(slug=slug, **args)
            except ValueError:
                continue
            problems.append(f"slug {slug!r} was accepted and wrote {dest}")
            if dest.resolve().parent != notes_dir:
                dest.unlink(missing_ok=True)
        dest, created = dm.write_memory_note(slug="plain-slug", **args)
        if not created or dest.resolve().parent != notes_dir:
            problems.append(f"an ordinary slug did not write into 00_Memory/notes/: {dest}")
    finally:
        teardown_sandbox(sandbox_vault)

    return {"eval": "slug_containment", "pass": not problems,
            "detail": "; ".join(problems) if problems else f"{len(BAD_SLUGS)} path-like slugs refused, a plain slug writes"}
