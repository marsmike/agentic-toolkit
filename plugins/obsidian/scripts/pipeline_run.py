#!/usr/bin/env python3
"""The deterministic ends of one pipeline run; the distilling in between is the agent's.

    uv run scripts/pipeline_run.py begin                  # take the lock (or: busy, stop)
    uv run scripts/pipeline_run.py queue [--batch N]      # after the sources ran: this run's captures
    uv run scripts/pipeline_run.py end --distilled N --dropped N [--failed CAPTURE ...]

`begin` takes the run lock (`00_Memory/pipeline.lock`, created atomically; a lock younger than
LOCK_STALE_HOURS means another run is still going: status `busy`, do nothing). The lock is local
to one checkout, so exactly one scheduler may run the pipeline. With an upstream, `begin` then
commits any hand edits and pulls (`--rebase`), so work pushed from a cloud session arrives before
the run; a conflict aborts the rebase, writes a DLQ note, releases the lock and returns `skipped`.
Git is the sync channel and the pipeline is its one committer. [earned: 2026-09-23, R12 — cloud
sessions write to the vault through GitHub]

`queue` picks this run's batch from `01_Capture/`: the owner's clips first, then everything else,
oldest first, at most `--batch` (profile `pipeline_batch`, default 25). A capture that has failed
MAX_ATTEMPTS runs is left out and written to the DLQ once: it needs a human, and it must not
block the queue.

`end` records failures, rebuilds Index.md, the maps and Now.md (`index_build.py`, `map_build.py`,
`now_build.py`), appends one Log.md line, and releases the lock. If the vault is a git repository
it commits (the undo for an unattended run), then pulls and pushes when there is an upstream.
Before any commit the staged diff is scanned for key-shaped strings; a hit refuses the commit and
writes a DLQ note that names the file and the kind of key, never the value (status `refused`).
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from vault_utils import profile_value, read_frontmatter, require_vault, write_dlq_note

LOCK = Path("00_Memory") / "pipeline.lock"
STATE = Path("00_Memory") / "pipeline-state.json"
# What came in is counted from the sources' own ledgers (rows appended between begin and end), so
# the run's summary is a record, not a recollection. [earned: 2026-09-24 — a cloud run reported
# "3 promoted as strong" where its radar had promoted none]
LEDGERS = {"judged": Path("00_Memory/radar/state.jsonl"), "promoted": Path("00_Memory/radar/promoted.jsonl"),
           "ingested": Path("00_Memory/readwise-ingested.jsonl")}
LOCK_STALE_HOURS = 6
MAX_ATTEMPTS = 2
DEFAULT_BATCH = 25
SCRIPTS = Path(__file__).resolve().parent
GENERATORS = {  # script → the files it writes (a trailing / = every file directly in that folder)
    "index_build.py": ("Index.md",),
    "map_build.py": ("Maps/",),
    "now_build.py": ("Now.md", "Boards/Pipeline.md"),
}
SECRET_PATTERNS = {
    "OpenRouter key": r"sk-or-v1-[0-9a-f]{32,}",
    "Anthropic key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "OpenAI-style key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}",
    "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "private key": r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
    "assigned secret": r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]?(?=[A-Za-z_\-]*\d)[A-Za-z0-9_\-]{24,}",
}
_SECRETS = [(name, re.compile(rx)) for name, rx in SECRET_PATTERNS.items()]


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


def _guard(lock: Path):
    """An OS lock on a guard file outside the vault (never committed), serialising every claim and
    release: inside it, check-then-write is safe, including taking over a stale lock.
    [earned: 2026-09-23, PR #24 reviews — O_EXCL, then rename-aside takeovers each left a race]"""
    key = hashlib.sha1(str(lock.resolve()).encode()).hexdigest()[:16]
    g = open(Path(tempfile.gettempdir()) / f"agentic-toolkit-{key}.guard", "a")  # noqa: SIM115 — closed by the caller's with
    fcntl.flock(g, fcntl.LOCK_EX)
    return g


def _claim(lock: Path, now: datetime, token: str) -> datetime | None:
    """Take the lock for `token`; return the holder's start time if another run has it.

    Of two runs starting together exactly one gets past here, before the slow commit-and-pull.
    A lock older than LOCK_STALE_HOURS is a crashed run and is taken over. The lock holds the start
    time and the run's token, and appears complete through an atomic replace, never empty.
    [earned: 2026-09-23, PR #20 review — check-then-write let two runs both sync and both run]
    """
    lock.parent.mkdir(parents=True, exist_ok=True)
    with _guard(lock):
        if lock.exists():
            started = _lock_time(lock, now)
            if now - started < timedelta(hours=LOCK_STALE_HOURS):
                return started
        new = lock.with_name(f"{lock.name}.new-{os.getpid()}-{time.time_ns()}")
        new.write_text(f"{now.isoformat()}\n{token}\n", encoding="utf-8")
        os.replace(new, lock)
        return None


def _release(lock: Path, token: str | None) -> None:
    """Remove the lock, but only if it is still this run's: a run that outlived LOCK_STALE_HOURS
    must not delete the lock of the run that took over. An `end` without a token removes only a
    lock that carries none (an old one); a tokened lock waits for its run or goes stale.
    [earned: 2026-09-23, PR #24 reviews]"""
    if not lock.exists():
        return
    with _guard(lock):
        if _lock_token(lock) == (token or ""):
            lock.unlink(missing_ok=True)


def _lock_token(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return lines[1].strip() if len(lines) > 1 else ""


def _lock_time(path: Path, now: datetime) -> datetime:
    """When the run holding `path` started; unreadable or garbled counts as stale."""
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").splitlines()[0].strip())
    except (OSError, ValueError, IndexError):
        return now - timedelta(hours=LOCK_STALE_HOURS + 1)


def begin(vault: Path, now: datetime) -> dict[str, Any]:
    lock = vault / LOCK
    token = f"{os.getpid()}-{time.time_ns()}"
    holder = _claim(lock, now, token)
    if holder is not None:
        return {"status": "busy", "detail": f"another run holds the lock since {holder.isoformat()}"}
    sync = _pull(vault, now)
    if sync.get("conflict") or sync.get("secrets"):
        _release(lock, token)
        return {"status": "skipped", "detail": sync["detail"], "sync": sync}
    # A pull that merely failed (offline, a transient auth error) does not stop the run, by design:
    # distilling needs no network, the run's commit stays local, and the next run's pull and push
    # reconcile it. A real conflict is the only reason to skip. `sync.pulled` says which it was.
    # Pass `token` to `end --token` so it releases only this run's lock.
    state = _state(vault)
    state["marks"] = {k: len(_rows(vault / rel)) for k, rel in LEDGERS.items()}
    _save_state(vault, state)
    return {"status": "ok", "locked_at": now.isoformat(), "token": token, "sync": sync}


def _rows(path: Path) -> list[dict]:
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line)) if line.strip() else None
            except json.JSONDecodeError:
                rows.append({})
    return rows


def came_in(vault: Path, marks: dict[str, int]) -> str:
    """'radar 12 judged, 2 promoted; readwise 3 new (2 clip, 1 radar)' from the rows appended since begin."""
    new = {k: _rows(vault / rel)[marks.get(k, 0):] for k, rel in LEDGERS.items()}
    captures = [r for r in new["ingested"] if r.get("capture")]
    by_via: dict[str, int] = {}
    for r in captures:
        by_via[r.get("via") or "clip"] = by_via.get(r.get("via") or "clip", 0) + 1
    vias = ", ".join(f"{n} {v}" for v, n in sorted(by_via.items()))
    return (f"radar {len(new['judged'])} judged, {len(new['promoted'])} promoted; "
            f"readwise {len(captures)} new" + (f" ({vias})" if vias else ""))


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


def _dlq_once(vault: Path, slug: str, **note: Any) -> None:
    """One open DLQ note per recurring problem: a run every three hours must not stack them."""
    for p in (vault / "00_Memory" / "dlq").glob(f"*-{slug}*.md"):
        if str(read_frontmatter(p)[0].get("status", "active")) == "active":
            return
    write_dlq_note(vault, slug=slug, **note)


def _is_repo(vault: Path) -> bool:
    return _git(vault, "rev-parse", "--is-inside-work-tree").returncode == 0


def _has_upstream(vault: Path) -> bool:
    return _git(vault, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").returncode == 0


def scan_staged(vault: Path) -> list[dict[str, Any]]:
    """Key-shaped strings on the staged diff's added lines: file, line and kind, never the value."""
    diff = _git(vault, "diff", "--cached", "-U0", "--no-color", "--no-ext-diff").stdout
    hits, path, line_no = [], "", 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            line_no = int(m.group(1)) if m else 0
        elif line.startswith("+") and path:
            kind = next((name for name, rx in _SECRETS if rx.search(line)), None)
            if kind:
                hits.append({"file": path, "line": line_no, "kind": kind})
            line_no += 1
    return hits


def _commit(vault: Path, message: str, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    """Stage everything and commit, unless the diff holds a key-shaped string: then unstage and DLQ."""
    added = _git(vault, "add", "-A", "--", ".", *(f":(exclude){e}" for e in exclude))
    if added.returncode != 0:
        # An empty index after a failed add is not "nothing to commit". [earned: PR #24 review]
        return {"commit": None, "secrets": [], "error": "git add: " + (added.stderr.strip().splitlines() or ["?"])[-1][:200]}
    if _git(vault, "diff", "--cached", "--quiet").returncode == 0:
        return {"commit": None, "secrets": []}
    hits = scan_staged(vault)
    if hits:
        _git(vault, "reset", "-q")
        where = "; ".join(f"{h['file']}:{h['line']} ({h['kind']})" for h in hits[:10])
        _dlq_once(vault, slug="pipeline-secret-refused", title="Pipeline refused to commit a key-shaped string",
                       what_happened=f"The staged diff holds {len(hits)} key-shaped string(s): {where}. Nothing was committed or pushed.",
                       why_recorded="A key in git is a key on GitHub; the pipeline commits and pushes unattended.",
                       resolution="Move the key to a password manager or ~/.env and leave a placeholder in the note, "
                                  "or add the file to .gitignore. The next run commits once the diff is clean.",
                       confidence="high")
        return {"commit": None, "secrets": hits}
    done = _git(vault, "commit", "-q", "-m", message)
    if done.returncode != 0:
        # Not a no-op: something was staged and did not commit (a hook, identity, index error).
        return {"commit": None, "secrets": [], "error": (done.stderr.strip().splitlines() or ["?"])[-1][:200]}
    return {"commit": _git(vault, "rev-parse", "--short", "HEAD").stdout.strip(), "secrets": []}


def _rebase_in_progress(vault: Path) -> bool:
    return any(Path(vault, _git(vault, "rev-parse", "--git-path", d).stdout.strip()).exists()
               for d in ("rebase-merge", "rebase-apply"))


def _pull(vault: Path, now: datetime) -> dict[str, Any]:
    """Bring the upstream's commits in under the vault's own; hand edits are committed first, so
    nothing sits in a stash. A conflict is aborted and recorded, never resolved by guessing."""
    if not _is_repo(vault) or not _has_upstream(vault):
        return {"pulled": False, "detail": "no git upstream"}
    local = _commit(vault, f"vault: hand edits before pipeline {now.strftime('%Y-%m-%d %H:%M')}", exclude=(LOCK.as_posix(),))
    if local["secrets"]:
        return {"pulled": False, "secrets": local["secrets"], "detail": "hand edits hold a key-shaped string; see the DLQ"}
    before = _git(vault, "rev-parse", "HEAD").stdout.strip()
    pull = _git(vault, "pull", "--rebase", "--no-edit")
    if pull.returncode != 0:
        if _rebase_in_progress(vault):
            _git(vault, "rebase", "--abort")
            _dlq_once(vault, slug="pipeline-pull-conflict", title="Pipeline could not rebase onto the vault's upstream",
                           what_happened="git pull --rebase hit a conflict between this machine's commits and the upstream's; "
                                         "the rebase was aborted and the run skipped. Nothing was lost.",
                           why_recorded="Two writers changed the same note; picking a side is a human decision.",
                           resolution="In the vault: git pull --rebase, resolve the conflict, git rebase --continue, git push.",
                           confidence="high")
            return {"pulled": False, "conflict": True, "detail": "pull conflict; rebase aborted, run skipped"}
        return {"pulled": False, "detail": "pull failed: " + (pull.stderr.strip().splitlines() or ["?"])[-1]}
    after = _git(vault, "rev-parse", "HEAD").stdout.strip()
    count = _git(vault, "rev-list", "--count", f"{before}..{after}").stdout.strip()
    return {"pulled": True, "hand_edits": local["commit"], "new_commits": int(count) if count.isdigit() else 0}


def _push(vault: Path, now: datetime) -> dict[str, Any]:
    if not _has_upstream(vault):
        return {"pushed": False, "detail": "no git upstream"}
    sync = _pull(vault, now)
    if not sync.get("pulled"):
        return {"pushed": False, "detail": sync["detail"]}
    # Push explicitly to the upstream (the remote `begin` pulled from), never where pushRemote or
    # pushDefault would send a bare `git push`. [earned: 2026-09-23, PR #24 review]
    upstream = _git(vault, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").stdout.strip()
    remote, _, branch = upstream.partition("/")
    push = _git(vault, "push", "-q", remote, f"HEAD:{branch}")
    if push.returncode != 0:
        return {"pushed": False, "detail": "push failed: " + (push.stderr.strip().splitlines() or ["?"])[-1]}
    return {"pushed": True}


def end(vault: Path, now: datetime, distilled: int, dropped: int, failed: list[str], note: str = "",
        token: str | None = None) -> dict[str, Any]:
    state = _state(vault)
    attempts: dict[str, int] = state.get("attempts", {})
    for rel in failed:
        attempts[rel] = attempts.get(rel, 0) + 1
    state["attempts"] = {k: v for k, v in attempts.items() if (vault / k).is_file()}
    state["last_run"] = {"at": now.isoformat(), "distilled": distilled, "dropped": dropped, "failed": len(failed)}
    marks = state.pop("marks", None)
    _save_state(vault, state)

    summary = f"{distilled} distilled, {dropped} dropped, {len(failed)} failed"
    if marks is not None:
        summary += f"; in: {came_in(vault, marks)}"
    left = sum(1 for p in (vault / "01_Capture").glob("*.md") if p.is_file())
    summary += f"; {left} in the inbox" + (f"; {note}" if note else "")
    env = {**os.environ, "TOOLKIT_VAULT": str(vault)}
    # A generator that fails may have replaced some of its files and not others, so its files go
    # back to how they were before it ran: navigation is this run's or the last one's, never a mix.
    # The run is still committed (it is the undo for the notes it wrote); the failure is reported
    # and gets a DLQ note. [earned: 2026-09-23, PR #20 and #24 reviews]
    failed_builds = []
    for script in GENERATORS:
        before = _snapshot(vault, GENERATORS[script])
        run = subprocess.run([sys.executable, str(SCRIPTS / script)], capture_output=True, text=True, check=False, env=env)
        if run.returncode != 0:
            failed_builds.append({"script": script, "error": (run.stderr.strip().splitlines() or ["?"])[-1][:200]})
            _restore(vault, GENERATORS[script], before)
    if failed_builds:
        _dlq_once(vault, slug="pipeline-build-failed", title="A navigation build failed at the end of a pipeline run",
                  what_happened="; ".join(f"{f['script']}: {f['error']}" for f in failed_builds),
                  why_recorded="Index.md, the maps or Now.md kept their previous version and are out of date until it builds again.",
                  resolution="Run the script by hand with TOOLKIT_VAULT set, fix what it names (often a note or "
                             "Config/toolkit/maps.md), then mark this note resolved.",
                  confidence="high")
        summary += f"; build failed: {', '.join(f['script'] for f in failed_builds)}"
    subprocess.run([sys.executable, str(SCRIPTS / "log_vault.py"), "pipeline", summary], capture_output=True, check=False, env=env)

    result: dict[str, Any] = {"status": "ok", "summary": summary, "commit": None}
    if failed_builds:
        result["build_failed"] = failed_builds
    # The lock is held through commit and push (and never staged), so no other run starts its
    # pull while this one is still writing to git. [earned: 2026-09-23, PR #24 review]
    try:
        if _is_repo(vault):
            committed = _commit(vault, f"pipeline {now.strftime('%Y-%m-%d %H:%M')}: {summary}", exclude=(LOCK.as_posix(),))
            result["commit"] = committed["commit"]
            if committed["secrets"]:
                result.update(status="refused", secrets=committed["secrets"])
            elif committed.get("error"):
                result.update(status="commit_failed", detail=committed["error"])
            else:
                result["sync"] = _push(vault, now)
    finally:
        _release(vault / LOCK, token)
    return result


def _owned(vault: Path, paths: tuple[str, ...]) -> list[Path]:
    """The files a generator may touch: a named file, or every file directly in a named folder."""
    out = []
    for rel in paths:
        target = vault / rel
        out += sorted(p for p in target.iterdir() if p.is_file()) if rel.endswith("/") and target.is_dir() else [target]
    return out


def _snapshot(vault: Path, paths: tuple[str, ...]) -> dict[Path, bytes | None]:
    """Exact bytes of every file a generator may touch, taken just before it runs."""
    return {p: (p.read_bytes() if p.is_file() else None) for p in _owned(vault, paths)}


def _restore(vault: Path, paths: tuple[str, ...], before: dict[Path, bytes | None]) -> None:
    """Put a failed generator's files back exactly as they were before it ran: changed or deleted
    ones get their bytes back, ones it created are removed, anything else it never saw stays.
    Needs no git and no ownership guess. [earned: 2026-09-23, PR #24 reviews — restoring from
    HEAD missed first-run files and deleted maps, and could hit a hand-made canvas]"""
    for path, data in before.items():
        if data is None:
            path.unlink(missing_ok=True)
        elif not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for path in _owned(vault, paths):
        if path not in before:
            path.unlink(missing_ok=True)


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
    e.add_argument("--dropped", type=int, default=0, help="captures that left WITHOUT a note (a radar or newsletter discard); never a clip")
    e.add_argument("--failed", nargs="*", default=[])
    e.add_argument("--note", default="")
    e.add_argument("--token", default=None, help="the token `begin` returned; the lock is released only if it is still this run's")
    e.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    vault, now = require_vault(), datetime.now(UTC)
    if args.cmd == "begin":
        result = begin(vault, now)
    elif args.cmd == "queue":
        result = queue(vault, args.batch)
    else:
        result = end(vault, now, args.distilled, args.dropped, args.failed, args.note, args.token)
    print(json.dumps(result, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
