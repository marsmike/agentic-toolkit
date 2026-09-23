"""Eval: pipeline_run.py, the deterministic ends of an unattended run, in a git sandbox.

1. queue    — the owner's clips come first, then radar/newsletter captures, oldest first, capped
              at the batch size; a second begin while the lock is held is `busy`
2. end      — Index.md rebuilt, one Log.md line, one git commit carrying the run's summary; the
              lock is released and never committed
3. parking  — a capture that failed twice leaves the queue and gets one DLQ note; it is not deleted
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


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
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "clips first, lock, one commit per run, parking after two failures"}
