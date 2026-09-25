#!/usr/bin/env python3
"""Watchdog: is the pipeline alive and well? Reads the vault, prints a verdict, changes nothing.

    uv run scripts/watchdog.py [--json] [--max-age-hours 4] [--now ISO]

The pipeline routine can only report what goes wrong inside a run. This says what it cannot: that
no run has committed for too long, that a run died holding the lock, that the last run's summary
carries a failure, that captures are parked or piling up, that a DLQ note appeared. A second
routine runs it between pipeline runs and sends one notification only when `ok` is false.
[earned: 2026-09-25, owner's request — "alert me if something is not working"]

Exit 1 when there is a problem, so a shell can branch on it. Every check is deterministic: no
model, no network, only git and files.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vault_utils import contained, read_frontmatter, require_vault

LOCK = Path("00_Memory") / "pipeline.lock"
STATE = Path("00_Memory") / "pipeline-state.json"
DLQ = Path("00_Memory") / "dlq"
MAX_AGE_HOURS = 4.0        # the routine runs every 3 h; one missed run is a problem
LOCK_STALE_HOURS = 6.0     # pipeline_run's own stale-lock horizon; the lock is never committed, so in a fresh
                           # clone (the cloud routine) a hung run shows up as `stale`, not `hung`
NEW_DLQ_HOURS = 24.0       # a DLQ note this recent is news; older open ones are listed, not alerted
INBOX_LIMIT = 25           # pipeline_run.DEFAULT_BATCH: more than one batch waiting means runs are not keeping up
FAIL_WORDS = ("failed", "build failed", "git-ignored", "missing", "not attempted", "refused")


def _git(vault: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, errors="replace", check=False)
    return run.stdout if run.returncode == 0 else ""


def last_pipeline_commit(vault: Path) -> tuple[datetime | None, str]:
    """(commit time, subject) of the newest `pipeline …` commit, or (None, "")."""
    out = _git(vault, "log", "-1", "--grep=^pipeline", "--format=%cI%x09%s").strip()
    if not out:
        return None, ""
    when, _, subject = out.partition("\t")
    try:
        return datetime.fromisoformat(when), subject
    except ValueError:
        return None, subject


def _counts(summary: str) -> dict[str, int]:
    m = re.search(r"(\d+) distilled, (\d+) dropped, (\d+) failed", summary)
    return {"distilled": int(m.group(1)), "dropped": int(m.group(2)), "failed": int(m.group(3))} if m else {}


def check(vault: Path, now: datetime, max_age_hours: float = MAX_AGE_HOURS) -> dict:
    problems: list[dict[str, str]] = []
    facts: dict[str, object] = {}

    when, subject = last_pipeline_commit(vault)
    facts["last_run"] = when.isoformat() if when else None
    facts["last_summary"] = subject.split(": ", 1)[-1] if subject else ""
    if when is None:
        problems.append({"kind": "no-run", "detail": "no `pipeline …` commit in this checkout's history"})
    else:
        age = (now - when.astimezone(timezone.utc)).total_seconds() / 3600
        facts["age_hours"] = round(age, 1)
        if age > max_age_hours:
            problems.append({"kind": "stale", "detail": f"no pipeline run committed for {age:.1f} h (last: {when.strftime('%Y-%m-%d %H:%M')} UTC)"})
        summary = facts["last_summary"]
        counts = _counts(summary)
        flagged = [w for w in FAIL_WORDS if w in summary and not (w == "failed" and counts.get("failed", 1) == 0)]
        if flagged:
            problems.append({"kind": "failed", "detail": f"last run reported: {summary}"})

    lock = vault / LOCK
    if lock.is_file():
        held = (now - datetime.fromtimestamp(lock.stat().st_mtime, tz=timezone.utc)).total_seconds() / 3600
        facts["lock_hours"] = round(held, 1)
        if held > LOCK_STALE_HOURS:
            problems.append({"kind": "hung", "detail": f"pipeline.lock has been held for {held:.1f} h: a run died or hangs"})

    try:
        state = json.loads((vault / STATE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    parked = state.get("parked") or []
    facts["parked"] = len(parked)
    if parked:
        problems.append({"kind": "parked", "detail": f"{len(parked)} capture(s) parked after repeated failures: {', '.join(str(p) for p in parked[:5])}"})

    inbox = [p for p in contained((vault / "01_Capture").glob("*.md"), vault) if p.is_file()]
    facts["inbox"] = len(inbox)
    if len(inbox) > INBOX_LIMIT:
        problems.append({"kind": "backlog", "detail": f"{len(inbox)} captures waiting, more than one batch ({INBOX_LIMIT}): runs are not keeping up"})

    open_notes, new_notes = [], []
    for p in sorted(contained((vault / DLQ).glob("*.md"), vault)):
        fm, _ = read_frontmatter(p)
        if str(fm.get("status") or "") != "active":
            continue
        open_notes.append(p.name)
        created = str(fm.get("created") or "")[:10]
        try:
            fresh = now - datetime.fromisoformat(created).replace(tzinfo=timezone.utc) <= timedelta(hours=NEW_DLQ_HOURS)
        except ValueError:
            fresh = False
        if fresh:
            new_notes.append(f"{p.stem}: {str(fm.get('description') or '')[:120]}")
    facts["dlq_open"] = open_notes
    if new_notes:
        problems.append({"kind": "dlq", "detail": f"{len(new_notes)} new DLQ note(s): " + "; ".join(new_notes[:5])})

    return {"ok": not problems, "checked_at": now.isoformat(timespec="minutes"), "problems": problems, "facts": facts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-age-hours", type=float, default=MAX_AGE_HOURS)
    ap.add_argument("--now", help="ISO time to check against (default: now, UTC)")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now).astimezone(timezone.utc) if args.now else datetime.now(timezone.utc)
    result = check(require_vault(), now, args.max_age_hours)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["ok"]:
        print(f"OK  last run {result['facts'].get('last_run')}: {result['facts'].get('last_summary')}")
    else:
        print("PROBLEM\n" + "\n".join(f"- [{p['kind']}] {p['detail']}" for p in result["problems"]))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
