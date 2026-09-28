#!/usr/bin/env python3
"""Propose `ingested_at`/`distilled_at` for existing captures and notes, from git history —
never a guessed time, only the date the file's own first commit recorded.

    uv run scripts/backfill_timestamps.py            # dry run: print what would change, write nothing
    uv run scripts/backfill_timestamps.py --json      # dry run, machine-readable
    uv run scripts/backfill_timestamps.py --apply     # write the proposed fields

For a capture still in `01_Capture/` (or kept whole under `05_Archive/*/*--FULLCAPTURE.md`)
missing `ingested_at`, and for a `status: distilled` note missing `ingested_at` and/or
`distilled_at`, the proposal is the author date of the oldest commit that added the file
(`git log --follow --diff-filter=A --format=%aI`), converted to UTC and written `ingested_at`'s
own `Z` format — with `ingested_at_estimated: true` / `distilled_at_estimated: true` alongside it,
so nothing downstream mistakes an inferred value for one recorded live. A file with no commit
history (new since the last commit, or a dry-run sandbox with no git) proposes nothing for it.

Idempotent: a field already present is never touched, so a second dry run (or `--apply` run)
proposes and writes nothing new for a file the first pass already covered.

This script is *not* run automatically by this change — backfilling every existing note in a
real vault is a separate decision from writing the two fields going forward, and the coordinator
asks the owner before any `--apply` there. Tests and evals run it against `./vault` only.
[earned: 2026-09-28 — the owner asked for the ingest and distill date and time on every report
and note; the backfill itself stayed a proposal, not part of this change]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from vault_utils import contained, discover_notes, read_frontmatter, require_vault, write_frontmatter

CAPTURE_GLOBS = ("01_Capture/*.md", "05_Archive/*/*--FULLCAPTURE.md")


def _first_add(vault: Path, rel: str) -> str | None:
    """The oldest commit that added `rel`, as `ingested_at`'s own UTC `Z` format — None with no
    git history for the file (git log lists newest first; the file's first add is the last line
    that survives `--diff-filter=A`, since a later rename/re-add would already be filtered by
    `--follow` continuing the same history)."""
    run = subprocess.run(
        ["git", "-C", str(vault), "log", "--follow", "--diff-filter=A", "--format=%aI", "--", rel],
        capture_output=True, text=True, check=False,
    )
    lines = [ln.strip() for ln in run.stdout.splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        when = datetime.fromisoformat(lines[-1])
    except ValueError:
        return None
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def propose(vault: Path) -> list[dict]:
    """One row per (file, field) that would change: `{"path", "field", "value"}`."""
    rows: list[dict] = []
    captures = [p for g in CAPTURE_GLOBS for p in contained(sorted(vault.glob(g)), vault) if p.is_file()]
    for p in captures:
        fm, _ = read_frontmatter(p)
        if fm.get("ingested_at"):
            continue
        rel = p.relative_to(vault).as_posix()
        when = _first_add(vault, rel)
        if when:
            rows.append({"path": rel, "field": "ingested_at", "value": when})

    for p in discover_notes(vault):
        fm, _ = read_frontmatter(p)
        if fm.get("status") != "distilled":
            continue
        missing = [f for f in ("ingested_at", "distilled_at") if not fm.get(f)]
        if not missing:
            continue
        rel = p.relative_to(vault).as_posix()
        when = _first_add(vault, rel)
        if not when:
            continue
        rows += [{"path": rel, "field": field, "value": when} for field in missing]
    return rows


def apply(vault: Path, rows: list[dict]) -> list[str]:
    """Write every proposed field, grouped by file so one file is read and written once. Returns
    the files actually changed. Never overwrites a field the file already has by the time this
    runs (idempotent even against a concurrent write)."""
    by_path: dict[str, list[dict]] = {}
    for r in rows:
        by_path.setdefault(r["path"], []).append(r)
    written: list[str] = []
    for rel, fields in by_path.items():
        path = vault / rel
        fm, body = read_frontmatter(path)
        changed = False
        for r in fields:
            if not fm.get(r["field"]):
                fm[r["field"]] = r["value"]
                fm[f"{r['field']}_estimated"] = True
                changed = True
        if changed:
            write_frontmatter(path, fm, body)
            written.append(rel)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the proposed fields (default: dry run, write nothing)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    vault = require_vault()
    rows = propose(vault)
    files = sorted({r["path"] for r in rows})
    if args.apply:
        written = apply(vault, rows)
        summary = {"proposed": len(rows), "files_proposed": len(files), "files_written": len(written), "applied": True}
    else:
        summary = {"proposed": len(rows), "files_proposed": len(files), "files_written": 0, "applied": False, "rows": rows}
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{summary['proposed']} field(s) proposed across {summary['files_proposed']} file(s)"
              + (f"; wrote {summary['files_written']}" if args.apply else " (dry run — pass --apply to write)"))
        for r in rows[:20]:
            print(f"  {r['path']}: {r['field']} = {r['value']}")
        if len(rows) > 20:
            print(f"  … and {len(rows) - 20} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
