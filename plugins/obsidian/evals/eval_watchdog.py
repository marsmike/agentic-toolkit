"""Eval: watchdog.py tells a healthy pipeline from each way it can be unwell, from the vault alone.

In a git sandbox with a `pipeline …` commit an hour old:
1. ok        — nothing to report; the run's age and summary are in the facts
2. stale     — no pipeline commit for longer than --max-age-hours
3. failed    — the last run's summary carries a failure ("1 failed", "build failed", …); "0 failed" alone does not
4. hung      — pipeline.lock held longer than the stale horizon
5. parked    — pipeline-state.json lists parked captures
6. backlog   — more captures waiting than one batch
7. dlq       — an open DLQ note created today is a problem; an older open one is listed in the facts only
8. exit      — the CLI exits 1 on a problem and 0 when ok
9. notify    — `notification` names every kind and is cut to 600 characters however many problems there are
10. stats    — `facts.week` counts the window's runs and what they distilled; the Sunday-evening check carries a
              `weekly_digest` (≤ 600 chars) and any other time it is empty
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "watchdog"
DLQ = "---\ndescription: {d}\nstatus: active\ncreated: '{c}'\ntags:\n- domain/toolkit-meta\n---\n\n# DLQ\n"


def _git(root: Path, *args: str, when: datetime | None = None) -> str:
    env = dict(os.environ)
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when.isoformat()
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False, env=env).stdout


def _commit(root: Path, subject: str, when: datetime) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--allow-empty", "-m", subject, when=when)


def run(vault: Path) -> dict:
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import watchdog

    problems: list[str] = []
    now = datetime.now(UTC)
    kinds = lambda r: sorted(p["kind"] for p in r["problems"])  # noqa: E731
    sandbox, saved = make_sandbox(vault), os.environ.get("TOOLKIT_VAULT")
    try:
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        # An older open DLQ note the sandbox corpus may carry must not count as news.
        dlq = sandbox / "00_Memory" / "dlq"
        dlq.mkdir(parents=True, exist_ok=True)
        for p in dlq.glob("*.md"):
            p.unlink()
        (sandbox / "01_Capture").mkdir(exist_ok=True)
        for p in (sandbox / "01_Capture").glob("*.md"):
            p.unlink()
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"attempts": {}, "parked": []}), encoding="utf-8")
        for args in (("init", "-q", "-b", "main"), ("config", "user.email", "e@x.org"), ("config", "user.name", "e")):
            _git(sandbox, *args)
        _commit(sandbox, "base", now - timedelta(hours=2))
        _commit(sandbox, "pipeline 2026-09-25 13:06: 7 distilled, 0 dropped, 0 failed; in: radar 3 judged, 0 promoted; 0 in the inbox",
                now - timedelta(hours=1))

        r = watchdog.check(sandbox, now)
        if not r["ok"] or not (0.9 <= r["facts"].get("age_hours", 0) <= 1.2) or "7 distilled" not in r["facts"]["last_summary"]:
            problems.append(f"ok: {r}")

        r = watchdog.check(sandbox, now + timedelta(hours=4))
        if kinds(r) != ["stale"]:
            problems.append(f"stale: {kinds(r)}")

        _commit(sandbox, "pipeline 2026-09-25 16:06: 3 distilled, 0 dropped, 1 failed; 1 in the inbox", now - timedelta(minutes=30))
        r = watchdog.check(sandbox, now)
        if kinds(r) != ["failed"]:
            problems.append(f"failed: {kinds(r)}")
        _commit(sandbox, "pipeline 2026-09-25 16:36: 2 distilled, 0 dropped, 0 failed; build failed: map_build.py", now - timedelta(minutes=20))
        if kinds(watchdog.check(sandbox, now)) != ["failed"]:
            problems.append("failed: a build failure in the summary is not flagged")
        _commit(sandbox, "pipeline 2026-09-25 17:06: 1 distilled, 0 dropped, 0 failed; 0 in the inbox", now - timedelta(minutes=10))
        if not watchdog.check(sandbox, now)["ok"]:
            problems.append("failed: a clean summary after a bad one must clear")

        lock = sandbox / "00_Memory" / "pipeline.lock"
        lock.write_text("x", encoding="utf-8")
        old = (now - timedelta(hours=7)).timestamp()
        os.utime(lock, (old, old))
        if kinds(watchdog.check(sandbox, now)) != ["hung"]:
            problems.append("hung: a stale lock is not flagged")
        lock.unlink()

        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"attempts": {}, "parked": ["01_Capture/x.md"]}), encoding="utf-8")
        if kinds(watchdog.check(sandbox, now)) != ["parked"]:
            problems.append("parked: not flagged")
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"attempts": {}, "parked": []}), encoding="utf-8")

        for i in range(watchdog.INBOX_LIMIT + 1):
            (sandbox / "01_Capture" / f"Readwise-Eval-{i}.md").write_text("---\nvia: clip\n---\n# c\n", encoding="utf-8")
        if kinds(watchdog.check(sandbox, now)) != ["backlog"]:
            problems.append("backlog: not flagged")
        for p in (sandbox / "01_Capture").glob("Readwise-Eval-*.md"):
            p.unlink()

        (dlq / "old-note.md").write_text(DLQ.format(d="an old one", c=(now - timedelta(days=3)).date().isoformat()), encoding="utf-8")
        r = watchdog.check(sandbox, now)
        if not r["ok"] or r["facts"]["dlq_open"] != ["old-note.md"]:
            problems.append(f"dlq: an old open note must be listed, not alerted: {r['problems']}, {r['facts'].get('dlq_open')}")
        (dlq / "new-note.md").write_text(DLQ.format(d="Radar scan got no judgments", c=now.date().isoformat()), encoding="utf-8")
        r = watchdog.check(sandbox, now)
        if kinds(r) != ["dlq"] or "Radar scan got no judgments" not in r["problems"][0]["detail"]:
            problems.append(f"dlq: {r['problems']}")

        for i in range(6):
            (dlq / f"long-{i}.md").write_text(DLQ.format(d=("a very long description of a failure " * 5)[:120], c=now.date().isoformat()), encoding="utf-8")
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"attempts": {}, "parked": [f"01_Capture/{'x' * 60}-{i}.md" for i in range(5)]}), encoding="utf-8")
        r = watchdog.check(sandbox, now)
        n = r["notification"]
        if not n.startswith("TheVoid pipeline:") or len(n) > watchdog.NOTIFY_CHARS or not n.endswith("…") or "[dlq]" not in n:
            problems.append(f"notify: {len(n)} chars, starts {n[:30]!r}")
        for i in range(6):
            (dlq / f"long-{i}.md").unlink()
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"attempts": {}, "parked": []}), encoding="utf-8")
        r = watchdog.check(sandbox, now)
        wk = r["facts"].get("week") or {}
        if wk.get("runs") != 4 or wk.get("distilled") != 13 or wk.get("failed") != 1 or wk.get("runs_expected") != 56:
            problems.append(f"stats: week {wk}")
        sunday = (now + timedelta(days=(6 - now.weekday()) % 7)).replace(hour=20, minute=58)
        d = watchdog.check(sandbox, sunday)["weekly_digest"]
        if not d.startswith("TheVoid, week to") or "runs" not in d or len(d) > watchdog.NOTIFY_CHARS:
            problems.append(f"stats: digest {d[:60]!r}")
        if watchdog.check(sandbox, sunday + timedelta(days=1))["weekly_digest"] != "":
            problems.append("stats: a Monday check must carry no digest")
        if watchdog.check(sandbox, sunday.replace(hour=23))["weekly_digest"] != "":
            problems.append("stats: the Sunday 23:58 check must not send the digest a second time")
        cli = subprocess.run([sys.executable, str(scripts_dir / "watchdog.py"), "--json"], capture_output=True, text=True, check=False,
                             env={**os.environ, "TOOLKIT_VAULT": str(sandbox)})
        if cli.returncode != 1 or not json.loads(cli.stdout)["problems"]:
            problems.append(f"exit: expected 1 with a problem, got {cli.returncode}")
        (dlq / "new-note.md").unlink()
        cli = subprocess.run([sys.executable, str(scripts_dir / "watchdog.py")], capture_output=True, text=True, check=False,
                             env={**os.environ, "TOOLKIT_VAULT": str(sandbox)})
        if cli.returncode != 0 or not cli.stdout.startswith("OK"):
            problems.append(f"exit: expected 0 and OK, got {cli.returncode}: {cli.stdout[:80]}")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "ok, stale, failed, hung, parked, backlog, dlq, exit codes"}
