"""Eval: pipeline_run.py, the deterministic ends of an unattended run, in a git sandbox.

1. queue    — the owner's clips come first, then radar/newsletter captures, oldest first, capped
              at the batch size; a second begin while the lock is held is `busy`
2. end      — Index.md rebuilt, one Log.md line, one git commit carrying the run's summary; the
              lock is released and never committed
3. parking  — a capture that failed twice leaves the queue and gets one DLQ note; it is not deleted
4. secrets  — a staged note holding a key-shaped string makes `end` refuse the commit and write one DLQ
              note that names the file, never the key; the next clean run commits
5. sync     — with a bare upstream: a second clone's commit arrives with `begin`, `end` pushes, and a
              conflicting hand edit skips the run (no lock, one DLQ note, the edit kept)
"""
from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "pipeline_run"
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
CAPTURES = {
    "Readwise-Article-radar-older.md": "---\nvia: radar\nsaved_at: 2026-09-01\n---\n# r\n",
    "Readwise-Article-clip-newer.md": "---\nvia: clip\nsaved_at: 2026-09-20\n---\n# c2\n",
    "Readwise-Article-clip-older.md": "---\nvia: clip\nsaved_at: 2026-09-10\n---\n# c1\n",
    "Readwise-Newsletter-news.md": "---\nvia: newsletter\nsaved_at: 2026-09-05\n---\n# n\n",
}


FAKE_KEY = "sk-or-v1-" + "0123456789abcdef" * 4


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def _sync_phase(pr, sandbox: Path) -> list[str]:
    """A bare upstream and a second clone (the cloud session): its commit arrives with `begin`, the
    run's commit reaches the upstream with `end`, and a conflicting hand edit skips the run."""
    problems = []
    remote, other = sandbox.parent / "remote.git", sandbox.parent / "other"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=False)
    _git(sandbox, "remote", "add", "origin", str(remote))
    _git(sandbox, "push", "-q", "-u", "origin", "HEAD")
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=False)
    for args in (("config", "user.email", "cloud@example.org"), ("config", "user.name", "cloud")):
        _git(other, *args)
    (other / "04_Resources" / "Eval-From-Cloud.md").write_text("---\ndescription: from the cloud\n---\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "cloud: one note")
    _git(other, "push", "-q")

    r = pr.begin(sandbox, NOW + timedelta(hours=18))
    if r.get("status") != "ok" or not (sandbox / "04_Resources" / "Eval-From-Cloud.md").is_file():
        problems.append(f"phase 5: begin must pull the cloud's commit, got {r}")
    r = pr.end(sandbox, NOW + timedelta(hours=18), 1, 0, [])
    if not r.get("sync", {}).get("pushed") or _git(sandbox, "rev-parse", "HEAD") != _git(remote, "rev-parse", "HEAD"):
        problems.append(f"phase 5: end must push the run's commit, got {r.get('sync')}")

    _git(other, "pull", "-q")
    for root, text in ((other, "cloud version\n"), (sandbox, "mac version\n")):
        (root / "04_Resources" / "Eval-From-Cloud.md").write_text(text, encoding="utf-8")
    _git(other, "commit", "-q", "-am", "cloud: edit")
    _git(other, "push", "-q")
    r = pr.begin(sandbox, NOW + timedelta(hours=21))
    conflicts = list((sandbox / "00_Memory" / "dlq").glob("*pull-conflict*.md"))
    if r.get("status") != "skipped" or (sandbox / pr.LOCK).exists() or len(conflicts) != 1:
        problems.append(f"phase 5: a conflict skips the run without the lock and writes one DLQ note, got {r.get('status')}")
    if pr._rebase_in_progress(sandbox) or "mac version" not in (sandbox / "04_Resources" / "Eval-From-Cloud.md").read_text(encoding="utf-8"):
        problems.append("phase 5: the aborted rebase must leave the Mac's own edit in place")
    return problems


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import pipeline_run as pr

    problems: list[str] = []
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        for name, text in CAPTURES.items():
            (sandbox / "01_Capture" / name).write_text(text, encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval"),
                     ("add", "-A"), ("commit", "-q", "-m", "base")):
            _git(sandbox, *args)
        head0 = _git(sandbox, "rev-parse", "HEAD").strip()

        # 1. begin
        pr.begin(sandbox, NOW)
        r = pr.queue(sandbox, batch=3)
        names = [Path(p).name for p in r.get("batch", [])]
        if names[:2] != ["Readwise-Article-clip-older.md", "Readwise-Article-clip-newer.md"] or len(names) != 3:
            problems.append(f"phase 1: clips first, oldest first, three in all; got {names}")
        if pr.begin(sandbox, NOW + timedelta(minutes=5))["status"] != "busy":
            problems.append("phase 1: a second begin while the lock is held must be busy")

        # 2. end
        failed = "01_Capture/Readwise-Newsletter-news.md"
        r = pr.end(sandbox, NOW, distilled=2, dropped=1, failed=[failed])
        log = _git(sandbox, "log", "--format=%s", f"{head0}..HEAD").splitlines()
        if len(log) != 1 or "2 distilled, 1 dropped, 1 failed" not in log[0]:
            problems.append(f"phase 2: expected one commit with the summary, got {log}")
        committed = _git(sandbox, "show", "--name-only", "--format=", "HEAD").split()
        if "00_Memory/pipeline.lock" in committed or (sandbox / pr.LOCK).exists():
            problems.append("phase 2: the lock must be released and never committed")
        if "Log.md" not in committed or "pipeline |" not in (sandbox / "Log.md").read_text(encoding="utf-8"):
            problems.append("phase 2: one Log.md line for the run")

        # 3. parking
        pr.begin(sandbox, NOW + timedelta(hours=3))
        pr.end(sandbox, NOW + timedelta(hours=3), distilled=0, dropped=0, failed=[failed])
        pr.begin(sandbox, NOW + timedelta(hours=6))
        r = pr.queue(sandbox)
        if failed in r.get("batch", []) or r.get("parked_now") != [failed]:
            problems.append(f"phase 3: a capture failing twice must be parked, got {r}")
        dlq = list((sandbox / "00_Memory" / "dlq").glob("*pipeline-parked-*.md"))
        if len(dlq) != 1 or not (sandbox / failed).is_file():
            problems.append(f"phase 3: parking writes one DLQ note and keeps the capture, got {len(dlq)} notes")
        pr.end(sandbox, NOW + timedelta(hours=6), 0, 0, [])
        pr.begin(sandbox, NOW + timedelta(hours=9))
        if pr.queue(sandbox).get("parked_now"):
            problems.append("phase 3: a parked capture gets its DLQ note once")
        pr.end(sandbox, NOW + timedelta(hours=9), 0, 0, [])

        # 4. secret scan
        leak = sandbox / "04_Resources" / "Eval-Leaky-Note.md"
        leak.write_text(f"---\ndescription: leaky\n---\n\nkey: {FAKE_KEY}\n", encoding="utf-8")
        head = _git(sandbox, "rev-parse", "HEAD").strip()
        pr.begin(sandbox, NOW + timedelta(hours=12))
        r = pr.end(sandbox, NOW + timedelta(hours=12), 0, 0, [])
        dlq = list((sandbox / "00_Memory" / "dlq").glob("*secret-refused*.md"))
        if r.get("status") != "refused" or _git(sandbox, "rev-parse", "HEAD").strip() != head:
            problems.append(f"phase 4: a key-shaped string must refuse the commit, got {r.get('status')}")
        if len(dlq) != 1 or FAKE_KEY in dlq[0].read_text(encoding="utf-8") or "Eval-Leaky-Note.md" not in dlq[0].read_text(encoding="utf-8"):
            problems.append(f"phase 4: one DLQ note naming the file, never the key; got {len(dlq)}")
        if _git(sandbox, "diff", "--cached", "--name-only").strip():
            problems.append("phase 4: a refused commit must leave nothing staged")
        leak.unlink()
        pr.begin(sandbox, NOW + timedelta(hours=15))
        if pr.end(sandbox, NOW + timedelta(hours=15), 0, 0, []).get("status") != "ok":
            problems.append("phase 4: once the key is gone the next run commits")

        # 5. git sync through an upstream
        problems += _sync_phase(pr, sandbox)
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "clips first, lock, one commit per run, parking after two failures"}
