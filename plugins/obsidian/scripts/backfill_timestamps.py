#!/usr/bin/env python3
"""Propose `ingested_at`/`distilled_at` for existing captures and notes from what the vault
already recorded — never a guessed time.

    uv run scripts/backfill_timestamps.py            # dry run: print what would change, write nothing
    uv run scripts/backfill_timestamps.py --json      # dry run, machine-readable
    uv run scripts/backfill_timestamps.py --apply     # write the proposed fields

Covers a capture still in `01_Capture/` (or kept whole under `05_Archive/*/*--FULLCAPTURE.md`)
missing `ingested_at`, and a `status: distilled` note missing either field. Each field takes the
best evidence there is, in this order:

- `ingested_at`: the run time `00_Memory/imports.jsonl` recorded for the item (matched by capture
  path or source URL — a real minute, written without the estimated flag); the date
  `00_Memory/readwise-ingested.jsonl` recorded for the capture; the file's own `created` date;
  the oldest commit that added the file.
- `distilled_at`: the note's `processed_date`; the oldest commit that added it; its `created`.

A date alone is written as the date (`2026-07-12`), never padded with an invented time. Anything
but the imports ledger's run time goes in with `<field>_estimated: true`. A commit counts only
when it is not the vault repo's first commit: everything that existed when the repo started shows
that day, which says when the history began, not when the note was made. No evidence, no value.

Idempotent: a field already present is never touched, so a second run proposes nothing new.
[earned: 2026-09-28 — the owner asked for the ingest and distill date and time on every report
and note; the owner's vault repo begins 2026-09-26, so a git-only backfill would have dated
1,210 notes distilled since 2024 to that day]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from vault_utils import contained, discover_notes, read_frontmatter, read_jsonl, require_vault, write_frontmatter

CAPTURE_GLOBS = ("01_Capture/*.md", "05_Archive/*/*--FULLCAPTURE.md")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date(raw: object) -> str | None:
    """A frontmatter date (`processed_date`, `created`) as `YYYY-MM-DD`, or None when it is not
    one (`unknown`, empty, a malformed value)."""
    s = str(raw or "").strip().strip("'\"")[:10]
    return s if DATE_RE.match(s) else None


def _norm_url(url: object) -> str:
    return str(url or "").strip().split("#")[0].rstrip("/").removeprefix("https://").removeprefix("http://")


def _root_commit(vault: Path) -> str | None:
    run = subprocess.run(["git", "-C", str(vault), "rev-list", "--max-parents=0", "HEAD"],
                         capture_output=True, text=True, check=False)
    return run.stdout.split()[0] if run.stdout.split() else None


def _first_add(vault: Path, rel: str, root: str | None) -> str | None:
    """The oldest commit that added `rel`, as the `Z` format — None with no history for the file,
    or when that commit is the repo's first (it dates the history, not the file)."""
    run = subprocess.run(
        ["git", "-C", str(vault), "log", "--follow", "--diff-filter=A", "--format=%H %aI", "--", rel],
        capture_output=True, text=True, check=False,
    )
    lines = [ln.split() for ln in run.stdout.splitlines() if len(ln.split()) == 2]
    if not lines or lines[-1][0] == root:
        return None
    try:
        when = datetime.fromisoformat(lines[-1][1])
    except ValueError:
        return None
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ledgers(vault: Path) -> tuple[dict[str, str], dict[str, str]]:
    """What the ingest ledgers recorded: key (capture path or normalised source URL) -> the run
    time in the `Z` format (imports.jsonl, a real minute), and capture path -> date
    (readwise-ingested.jsonl)."""
    timed: dict[str, str] = {}
    for run in read_jsonl(vault / "00_Memory" / "imports.jsonl"):
        try:
            when = datetime.strptime(str(run.get("run", "")), "%Y-%m-%d %H:%M").strftime("%Y-%m-%dT%H:%M:00Z")
        except ValueError:
            continue
        for it in run.get("items") or []:
            for key in (it.get("capture"), _norm_url(it.get("source"))):
                if key:
                    timed.setdefault(key, when)  # runs are appended in order: the first is the ingest
    dated = {str(r["capture"]): d for r in read_jsonl(vault / "00_Memory" / "readwise-ingested.jsonl")
             if r.get("capture") and (d := _date(r.get("date")))}
    return timed, dated


def propose(vault: Path) -> list[dict]:
    """One row per (file, field) that would change: `{"path", "field", "value", "estimated"}`."""
    rows: list[dict] = []
    root = _root_commit(vault)
    timed, dated = _ledgers(vault)

    def ingested(rel: str, fm: dict) -> tuple[str | None, bool]:
        if when := timed.get(rel) or timed.get(_norm_url(fm.get("source"))):
            return when, False
        return dated.get(rel) or _date(fm.get("created")) or _first_add(vault, rel, root), True

    captures = [p for g in CAPTURE_GLOBS for p in contained(sorted(vault.glob(g)), vault) if p.is_file()]
    for p in captures:
        fm, _ = read_frontmatter(p)
        if fm.get("ingested_at"):
            continue
        rel = p.relative_to(vault).as_posix()
        when, est = ingested(rel, fm)
        if when:
            rows.append({"path": rel, "field": "ingested_at", "value": when, "estimated": est})

    for p in discover_notes(vault):
        fm, _ = read_frontmatter(p)
        if fm.get("status") != "distilled":
            continue
        rel = p.relative_to(vault).as_posix()
        if not fm.get("distilled_at"):
            when = _date(fm.get("processed_date")) or _first_add(vault, rel, root) or _date(fm.get("created"))
            if when:
                rows.append({"path": rel, "field": "distilled_at", "value": when, "estimated": True})
        if not fm.get("ingested_at"):
            when, est = ingested(rel, fm)
            if when:
                rows.append({"path": rel, "field": "ingested_at", "value": when, "estimated": est})
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
                if r.get("estimated", True):
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
