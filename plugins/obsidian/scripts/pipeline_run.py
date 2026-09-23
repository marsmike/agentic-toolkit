#!/usr/bin/env python3
"""The deterministic ends of one pipeline run; the distilling in between is the agent's.

    uv run scripts/pipeline_run.py begin                  # take the lock (or: busy, stop)
    uv run scripts/pipeline_run.py queue [--batch N]      # after the sources ran: this run's captures
    uv run scripts/pipeline_run.py end --distilled N --retired N [--failed CAPTURE ...]

`begin` takes the run lock (`00_Memory/pipeline.lock`; a lock younger than LOCK_STALE_HOURS means
another run is still going: status `busy`, do nothing). `queue` picks this run's batch from
`01_Capture/`: the owner's clips first, then everything else, oldest first, at most `--batch`
(profile `pipeline_batch`, default 10). A capture that has failed MAX_ATTEMPTS runs is left out
and written to the DLQ once: it needs a human, and it must not block the queue.

`end` records failures, rebuilds Index.md (`index_build.py`), appends one Log.md line, commits
the vault if it is a git repository (the undo for an unattended run), and releases the lock.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from vault_utils import profile_value, read_frontmatter, require_vault, write_dlq_note

LOCK = Path("00_Memory") / "pipeline.lock"
STATE = Path("00_Memory") / "pipeline-state.json"
LOCK_STALE_HOURS = 6
MAX_ATTEMPTS = 2
DEFAULT_BATCH = 10
SCRIPTS = Path(__file__).resolve().parent


def _state(vault: Path) -> dict[str, Any]:
    path = vault / STATE
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except json.JSONDecodeError:
        return {}


def _save_state(vault: Path, state: dict[str, Any]) -> None:
    path = vault / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _order(vault: Path, path: Path) -> tuple[int, str]:
    try:
        fm, _ = read_frontmatter(path)
    except Exception:
        fm = {}
    clip = str(fm.get("via") or "clip") == "clip"
    return (0 if clip else 1, str(fm.get("saved_at") or fm.get("created") or fm.get("captured") or path.name))


def begin(vault: Path, now: datetime) -> dict[str, Any]:
    lock = vault / LOCK
    if lock.is_file():
        try:
            started = datetime.fromisoformat(lock.read_text(encoding="utf-8").strip())
        except ValueError:
            started = now - timedelta(hours=LOCK_STALE_HOURS + 1)
        if now - started < timedelta(hours=LOCK_STALE_HOURS):
            return {"status": "busy", "detail": f"another run holds the lock since {started.isoformat()}"}
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(now.isoformat() + "\n", encoding="utf-8")
    return {"status": "ok", "locked_at": now.isoformat()}


def queue(vault: Path, batch: int | None = None) -> dict[str, Any]:
    state = _state(vault)
    attempts: dict[str, int] = state.get("attempts", {})
    parked: list[str] = state.get("parked", [])
    captures = sorted((p for p in (vault / "01_Capture").glob("*.md") if p.is_file()), key=lambda p: _order(vault, p))
    newly_parked = []
    queue = []
    for p in captures:
        rel = p.relative_to(vault).as_posix()
        if attempts.get(rel, 0) >= MAX_ATTEMPTS:
            if rel not in parked:
                parked.append(rel)
                newly_parked.append(rel)
            continue
        queue.append(rel)
    for rel in newly_parked:
        write_dlq_note(vault, slug=f"pipeline-parked-{Path(rel).stem[:60]}", title=f"Pipeline could not distill {Path(rel).name}",
                       what_happened=f"{rel} failed distill_check in {MAX_ATTEMPTS} runs; the pipeline no longer picks it.",
                       why_recorded="A capture that keeps failing must not block the queue, and must not be dropped.",
                       resolution="Distill it by hand (the dossier says why it is hard), or delete it from pipeline-state.json to retry.",
                       confidence="high")
    state["parked"] = parked
    _save_state(vault, state)
    size = int(batch or profile_value(vault, "pipeline_batch", DEFAULT_BATCH))
    return {"status": "ok", "batch": queue[:size], "backlog": len(queue), "parked_now": newly_parked, "parked_total": len(parked)}


def _git(vault: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, check=False)


def end(vault: Path, now: datetime, distilled: int, retired: int, failed: list[str], note: str = "") -> dict[str, Any]:
    state = _state(vault)
    attempts: dict[str, int] = state.get("attempts", {})
    for rel in failed:
        attempts[rel] = attempts.get(rel, 0) + 1
    state["attempts"] = {k: v for k, v in attempts.items() if (vault / k).is_file()}
    state["last_run"] = {"at": now.isoformat(), "distilled": distilled, "retired": retired, "failed": len(failed)}
    _save_state(vault, state)

    summary = f"{distilled} distilled, {retired} retired, {len(failed)} failed" + (f"; {note}" if note else "")
    env = {**os.environ, "TOOLKIT_VAULT": str(vault)}
    subprocess.run([sys.executable, str(SCRIPTS / "index_build.py")], capture_output=True, check=False, env=env)
    subprocess.run([sys.executable, str(SCRIPTS / "log_vault.py"), "pipeline", summary], capture_output=True, check=False, env=env)

    (vault / LOCK).unlink(missing_ok=True)  # released before the commit, so it is never committed
    commit = None
    if _git(vault, "rev-parse", "--is-inside-work-tree").returncode == 0:
        _git(vault, "add", "-A")
        if _git(vault, "diff", "--cached", "--quiet").returncode != 0:
            msg = f"pipeline {now.strftime('%Y-%m-%d %H:%M')}: {summary}"
            if _git(vault, "commit", "-q", "-m", msg).returncode == 0:
                commit = _git(vault, "rev-parse", "--short", "HEAD").stdout.strip()
    return {"status": "ok", "summary": summary, "commit": commit}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Begin or end one pipeline run")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("begin")
    b.add_argument("--json", action="store_true")
    q = sub.add_parser("queue")
    q.add_argument("--batch", type=int, default=None)
    q.add_argument("--json", action="store_true")
    e = sub.add_parser("end")
    e.add_argument("--distilled", type=int, default=0)
    e.add_argument("--retired", type=int, default=0)
    e.add_argument("--failed", nargs="*", default=[])
    e.add_argument("--note", default="")
    e.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    vault, now = require_vault(), datetime.now(UTC)
    if args.cmd == "begin":
        result = begin(vault, now)
    elif args.cmd == "queue":
        result = queue(vault, args.batch)
    else:
        result = end(vault, now, args.distilled, args.retired, args.failed, args.note)
    print(json.dumps(result, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
