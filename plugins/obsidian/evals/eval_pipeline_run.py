"""Eval: pipeline_run.py, the deterministic ends of an unattended run, in a git sandbox.

1. queue    — the owner's clips come first, then radar/newsletter captures, oldest first, capped
              at the batch size; a second begin while the lock is held is `busy`
2. end      — Index.md and the day's 00_Daily/ note rebuilt, one Log.md line, one git commit carrying the run's summary; the
              lock is released and never committed; what came in is counted from the rows the
              radar and Readwise ledgers gained since begin, never from rows that were there; batch
              captures left in the inbox and not reported failed are named as not attempted
3. parking  — a capture that failed twice leaves the queue and gets one DLQ note; it is not deleted;
              `--failed ""` or a path no longer in 01_Capture/ counts no failure
4. secrets  — (4b: password assignments — quoted, bare, underscore/camelCase-prefixed, unquoted —
               and a URL carrying a login are found; stand-ins, env lookups, empty values and
               prose are not; 4c: an image a capture names that git ignores or that is gone gets a DLQ
               note and a summary count) a staged note holding a key-shaped string makes `end`
              refuse the commit and write one DLQ note that names the file, never the key; the
              next clean run commits
5. sync     — with a bare upstream: a second clone's commit arrives with `begin`, `end` pushes, and a
              conflicting hand edit skips the run (no lock, one DLQ note, the edit kept)
7. commit   — `commit --path 00_Memory/radar` (a routine's own files) commits only that path, keeps
              an unrelated untracked note out of it, rebases over a commit another clone pushed in
              between and pushes; a key-shaped string commits only its DLQ note (never the value); a path
              outside the vault, "nothing changed" and something staged beforehand commit nothing
              (the staged file stays staged); a named file not written yet is skipped; a second
              refusal the same day stages and records nothing new (the first refusal's note
              already covers it) rather than failing on an empty commit
6. build    — a generator that fails is reported in `build_failed` and gets one DLQ note across
              runs; its files go back exactly as before it ran (changed, added, deleted; a hand-made
              canvas beside a map untouched); the run still commits
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


_TOKEN: dict[str, str | None] = {"last": None}


def _begin(pr, vault: Path, now: datetime) -> dict:
    """`begin`, keeping the token it hands out for the next `_end`, as the pipeline skill does."""
    r = pr.begin(vault, now)
    if r.get("token"):
        _TOKEN["last"] = r["token"]
    return r


def _end(pr, vault: Path, now: datetime, *args, **kwargs) -> dict:
    return pr.end(vault, now, *args, token=_TOKEN["last"], **kwargs)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def _commit_phase(pr, sandbox: Path) -> list[str]:
    """A fresh clone of phase 5's upstream stands in for the Signal Radar routine's checkout."""
    problems = []
    remote, other, mine = sandbox.parent / "remote.git", sandbox.parent / "other", sandbox.parent / "signal"
    subprocess.run(["git", "clone", "-q", str(remote), str(mine)], check=False)
    for root in (mine, other):
        for args in (("config", "user.email", "cloud@example.org"), ("config", "user.name", "cloud")):
            _git(root, *args)
    radar = mine / "00_Memory" / "radar"
    radar.mkdir(parents=True, exist_ok=True)
    (radar / "signal.json").write_text('{"blips": []}\n', encoding="utf-8")
    (mine / "04_Resources" / "Eval-Untracked.md").write_text("# not the routine's\n", encoding="utf-8")
    _git(other, "pull", "-q")
    (other / "04_Resources" / "Eval-Meanwhile.md").write_text("# pushed meanwhile\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "pipeline: meanwhile")
    _git(other, "push", "-q")

    r = pr.commit_paths(mine, NOW, ["00_Memory/radar"], "signal radar: eval")
    files = _git(mine, "show", "--name-only", "--format=", "HEAD").split()
    if r.get("status") != "ok" or not r.get("sync", {}).get("pushed") or files != ["00_Memory/radar/signal.json"]:
        problems.append(f"phase 7: commit must push only the named path, got {r} with {files}")
    if _git(mine, "rev-parse", "HEAD") != _git(remote, "rev-parse", "HEAD") or not (mine / "04_Resources" / "Eval-Meanwhile.md").is_file():
        problems.append("phase 7: commit must rebase over the other clone's push and reach the upstream")
    if not (mine / "04_Resources" / "Eval-Untracked.md").is_file() or "Eval-Untracked" in _git(remote, "log", "--name-only", "--format="):
        problems.append("phase 7: an unnamed file must stay untouched and uncommitted")
    (radar / "signal.json").write_text(f'{{"title": "{FAKE_KEY}"}}\n', encoding="utf-8")
    r = pr.commit_paths(mine, NOW, ["00_Memory/radar"], "signal radar: eval key")
    files = _git(mine, "show", "--name-only", "--format=", "HEAD").split()
    if r.get("status") != "refused" or not r.get("dlq_commit") or len(files) != 1 or "commit-secret-refused" not in files[0] \
            or FAKE_KEY in _git(mine, "log", "-p", "-1") or _git(mine, "diff", "--cached", "--name-only") \
            or _git(mine, "rev-parse", "HEAD") != _git(remote, "rev-parse", "HEAD"):
        problems.append(f"phase 7: a key-shaped string must be refused, only its DLQ note committed and pushed, got {r} {files}")
    # A second refusal the same day: `_dlq_once` finds today's still-active note and skips writing
    # (there is nothing new to say), and this must not re-find "the" note by globbing the slug —
    # that glob also matches the first refusal's note, already committed, and re-adding/committing
    # it either no-ops or recommits stale content. Nothing new to stage or commit is fine; the
    # first refusal's commit and push must stand untouched. [earned: 2026-09-28]
    after_first_refusal = _git(mine, "rev-parse", "HEAD")
    (radar / "signal.json").write_text(f'{{"title": "{FAKE_KEY}", "n": 2}}\n', encoding="utf-8")
    r = pr.commit_paths(mine, NOW, ["00_Memory/radar"], "signal radar: eval key again")
    if r.get("status") != "refused" or "dlq_commit" in r or _git(mine, "rev-parse", "HEAD") != after_first_refusal \
            or _git(mine, "diff", "--cached", "--name-only").strip():
        problems.append(f"phase 7: a second same-day refusal must stage and record nothing new, got {r}")
    (radar / "signal.json").write_text('{"blips": []}\n', encoding="utf-8")
    if pr.commit_paths(mine, NOW, ["../elsewhere"], "x").get("status") != "refused":
        problems.append("phase 7: a path outside the vault must be refused")
    if pr.commit_paths(mine, NOW, ["00_Memory/radar"], "x").get("commit") is not None:
        problems.append("phase 7: nothing changed must commit nothing")
    r = pr.commit_paths(mine, NOW, ["00_Memory/radar/signal.json", "00_Memory/radar/not-written-yet.jsonl"], "x")
    if r.get("status") != "ok":
        problems.append(f"phase 7: a named file not written yet must be skipped, not fail the commit, got {r}")
    _git(mine, "add", "04_Resources/Eval-Untracked.md")
    (radar / "signal.json").write_text('{"blips": [1]}\n', encoding="utf-8")
    r = pr.commit_paths(mine, NOW, ["00_Memory/radar"], "x")
    if r.get("status") != "refused" or _git(mine, "diff", "--cached", "--name-only").split() != ["04_Resources/Eval-Untracked.md"]:
        problems.append(f"phase 7: something staged beforehand must refuse the commit and stay staged, got {r}")
    return problems


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

    r = _begin(pr, sandbox, NOW + timedelta(hours=18))
    if r.get("status") != "ok" or not (sandbox / "04_Resources" / "Eval-From-Cloud.md").is_file():
        problems.append(f"phase 5: begin must pull the cloud's commit, got {r}")
    r = _end(pr, sandbox, NOW + timedelta(hours=18), 1, 0, [])
    if not r.get("sync", {}).get("pushed") or _git(sandbox, "rev-parse", "HEAD") != _git(remote, "rev-parse", "HEAD"):
        problems.append(f"phase 5: end must push the run's commit, got {r.get('sync')}")

    _git(other, "pull", "-q")
    for root, text in ((other, "cloud version\n"), (sandbox, "mac version\n")):
        (root / "04_Resources" / "Eval-From-Cloud.md").write_text(text, encoding="utf-8")
    _git(other, "commit", "-q", "-am", "cloud: edit")
    _git(other, "push", "-q")
    r = _begin(pr, sandbox, NOW + timedelta(hours=21))
    conflicts = list((sandbox / "00_Memory" / "dlq").glob("*pull-conflict*.md"))
    if r.get("status") != "skipped" or (sandbox / pr.LOCK).exists() or len(conflicts) != 1:
        problems.append(f"phase 5: a conflict skips the run without the lock and writes one DLQ note, got {r.get('status')}")
    if pr._rebase_in_progress(sandbox) or "mac version" not in (sandbox / "04_Resources" / "Eval-From-Cloud.md").read_text(encoding="utf-8"):
        problems.append("phase 5: the aborted rebase must leave the Mac's own edit in place")
    return problems


def _build_failure_phase(pr, sandbox: Path) -> list[str]:
    """map_build.py replaced by a script that fails: `end` still commits, reports `build_failed`,
    and writes one DLQ note across two failing runs."""
    import shutil
    import tempfile
    problems = []
    stubs = Path(tempfile.mkdtemp(prefix="obsidian-plugin-eval-stubs-"))
    saved = pr.SCRIPTS
    try:
        for name in ("index_build.py", "now_build.py", "daily_build.py", "dashboard_build.py", "dashboard_template.html", "imports_log.py", "report_build.py", "radar_ledger.py",
                     "log_vault.py", "vault_utils.py"):
            shutil.copy(saved / name, stubs / name)
        for name in ("map_build.py", "pipeline_run.py"):
            shutil.copy(saved / name, stubs / name)
        # Still importable (now_build uses its helpers). Run as the build script it does damage a
        # half-finished build could do (overwrite one map, add one, delete one), then fails.
        damage = ("import os\nfrom pathlib import Path\nm = Path(os.environ['TOOLKIT_VAULT']) / 'Maps'\n"
                  "(m / 'Overview.md').write_text('half-written by a build that then failed')\n"
                  "(m / 'stray.md').write_text('added by the failed build')\n"
                  "(m / 'toolkit-meta.md').unlink()\n"
                  "sys.exit('map_build: boom')")
        real = (saved / "map_build.py").read_text(encoding="utf-8")
        (stubs / "map_build.py").write_text(real.replace("sys.exit(main())", damage.replace("\n", "\n    ")), encoding="utf-8")
        pr.SCRIPTS = stubs
        _git(sandbox, "remote", "remove", "origin")
        maps = sandbox / "Maps"
        mine = maps / "toolkit-meta-sketch.canvas"  # hand-made, beside a generated map
        mine.write_text('{"nodes": [], "edges": []}\n', encoding="utf-8")
        for hours in (24, 27):
            before = {p.name: p.read_bytes() for p in maps.iterdir() if p.is_file()}
            token = pr.begin(sandbox, NOW + timedelta(hours=hours)).get("token")
            (sandbox / "04_Resources" / f"Eval-Build-Fail-{hours}.md").write_text("---\ndescription: x\n---\n", encoding="utf-8")
            r = pr.end(sandbox, NOW + timedelta(hours=hours), 1, 0, [], token=token)
            if [f["script"] for f in r.get("build_failed", [])] != ["map_build.py"] or not r.get("commit"):
                problems.append(f"phase 6: a failing map_build is reported and the run still commits, got {r}")
            after = {p.name: p.read_bytes() for p in maps.iterdir() if p.is_file()}
            if after != before:
                problems.append(f"phase 6: a failed build's files go back exactly as before it ran; differs: "
                                f"{sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))}")
            if (sandbox / pr.LOCK).exists():
                problems.append("phase 6: end with the run's own token releases the lock")
        dlq = list((sandbox / "00_Memory" / "dlq").glob("*pipeline-build-failed*.md"))
        if len(dlq) != 1:
            problems.append(f"phase 6: a failing build gets one DLQ note, got {len(dlq)}")
    finally:
        pr.SCRIPTS = saved
        shutil.rmtree(stubs, ignore_errors=True)
    return problems


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import pipeline_run as pr
    from vault_utils import read_frontmatter

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
        old = sandbox / pr.LEDGERS["ingested"]  # an earlier run's capture: not this run's
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text('{"doc_id": "0", "capture": "01_Capture/old.md", "via": "clip"}\n', encoding="utf-8")

        # 1. begin
        _begin(pr, sandbox, NOW)
        r = pr.queue(sandbox, batch=3)
        names = [Path(p).name for p in r.get("batch", [])]
        if names[:2] != ["Readwise-Article-clip-older.md", "Readwise-Article-clip-newer.md"] or len(names) != 3:
            problems.append(f"phase 1: clips first, oldest first, three in all; got {names}")
        if _begin(pr, sandbox, NOW + timedelta(minutes=5))["status"] != "busy":
            problems.append("phase 1: a second begin while the lock is held must be busy")
        later = NOW + timedelta(hours=pr.LOCK_STALE_HOURS + 1)
        lock = sandbox / pr.LOCK
        if pr._claim(lock, later, "taker") is not None or pr._lock_time(lock, later) != later or \
                pr._lock_token(lock) != "taker" or list(lock.parent.glob("pipeline.lock.*-*")):
            problems.append("phase 1: a stale lock must be taken over atomically, leaving no temporary copy")
        if pr._claim(lock, later + timedelta(minutes=1), "third") != later:
            problems.append("phase 1: right after a takeover the lock is fresh again: busy")
        pr._release(lock, "the-run-that-was-taken-over")
        if not lock.exists():
            problems.append("phase 1: a run must not release a lock another run took over")
        lock.write_text(f"{NOW.isoformat()}\n{_TOKEN['last']}\n", encoding="utf-8")  # back to the phase-1 run

        # 2. end — the sources ran between begin and end: two judged, one promoted, two captures
        def add(rel: Path, *rows: str) -> None:
            path = sandbox / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write("".join(r + "\n" for r in rows))
        add(pr.LEDGERS["judged"], '{"canonical": "a"}', '{"canonical": "b"}')
        add(pr.LEDGERS["promoted"], '{"canonical": "a", "date": "2026-09-23"}')
        add(pr.LEDGERS["ingested"], '{"doc_id": "1", "capture": "01_Capture/x.md", "via": "clip"}',
            '{"doc_id": "2", "capture": "01_Capture/y.md", "via": "radar"}', '{"doc_id": "3", "found": "04_Resources/z.md"}')
        failed = "01_Capture/Readwise-Newsletter-news.md"
        r = _end(pr, sandbox, NOW, distilled=2, dropped=1, failed=[failed])
        log = _git(sandbox, "log", "--format=%s", f"{head0}..HEAD").splitlines()
        if len(log) != 1 or "2 distilled, 1 dropped, 1 failed" not in log[0]:
            problems.append(f"phase 2: expected one commit with the summary, got {log}")
        # the batch was three (the failed newsletter is not among them), all still in the inbox
        if "; 3 of the batch not attempted" not in r.get("summary", "") or len(r.get("not_attempted", [])) != 3:
            problems.append(f"phase 2: batch captures left in the inbox and not failed must be reported, got {r.get('summary')}")
        if "in: radar 2 judged, 1 promoted; readwise 2 new (1 clip, 1 radar)" not in r.get("summary", ""):
            problems.append(f"phase 2: what came in must be counted from the ledgers' new rows, got {r.get('summary')}")
        committed = _git(sandbox, "show", "--name-only", "--format=", "HEAD").split()
        if "00_Memory/pipeline.lock" in committed or (sandbox / pr.LOCK).exists():
            problems.append("phase 2: the lock must be released and never committed")
        if "Log.md" not in committed or "pipeline |" not in (sandbox / "Log.md").read_text(encoding="utf-8"):
            problems.append("phase 2: one Log.md line for the run")
        daily = [p for p in committed if p.startswith("00_Daily/")]
        if not daily or any("%% daily:start %%" not in (sandbox / p).read_text(encoding="utf-8") for p in daily):
            problems.append(f"phase 2: end builds and commits the day's daily note (daily_build.py), got {committed}")

        # 3. parking
        _begin(pr, sandbox, NOW + timedelta(hours=3))
        _end(pr, sandbox, NOW + timedelta(hours=3), distilled=0, dropped=0, failed=[failed])
        _begin(pr, sandbox, NOW + timedelta(hours=6))
        r = pr.queue(sandbox)
        if failed in r.get("batch", []) or r.get("parked_now") != [failed]:
            problems.append(f"phase 3: a capture failing twice must be parked, got {r}")
        dlq = list((sandbox / "00_Memory" / "dlq").glob("*pipeline-parked-*.md"))
        if len(dlq) != 1 or not (sandbox / failed).is_file():
            problems.append(f"phase 3: parking writes one DLQ note and keeps the capture, got {len(dlq)} notes")
        r = _end(pr, sandbox, NOW + timedelta(hours=6), 0, 0, ["", "01_Capture/Gone-Already.md"])
        if "0 failed" not in r.get("summary", "") or r.get("failed_not_found") != ["01_Capture/Gone-Already.md"]:
            problems.append(f"phase 3: a blank --failed or a capture not in 01_Capture is no failure, got {r.get('summary')}")
        _begin(pr, sandbox, NOW + timedelta(hours=9))
        if pr.queue(sandbox).get("parked_now"):
            problems.append("phase 3: a parked capture gets its DLQ note once")
        _end(pr, sandbox, NOW + timedelta(hours=9), 0, 0, [])

        # 4. secret scan
        leak = sandbox / "04_Resources" / "Eval-Leaky-Note.md"
        leak.write_text(f"---\ndescription: leaky\n---\n\nkey: {FAKE_KEY}\n", encoding="utf-8")
        head = _git(sandbox, "rev-parse", "HEAD").strip()
        _begin(pr, sandbox, NOW + timedelta(hours=12))
        r = _end(pr, sandbox, NOW + timedelta(hours=12), 0, 0, [])
        dlq = list((sandbox / "00_Memory" / "dlq").glob("*secret-refused*.md"))
        if r.get("status") != "refused" or _git(sandbox, "rev-parse", "HEAD").strip() != head:
            problems.append(f"phase 4: a key-shaped string must refuse the commit, got {r.get('status')}")
        if len(dlq) != 1 or FAKE_KEY in dlq[0].read_text(encoding="utf-8") or "Eval-Leaky-Note.md" not in dlq[0].read_text(encoding="utf-8"):
            problems.append(f"phase 4: one DLQ note naming the file, never the key; got {len(dlq)}")
        if _git(sandbox, "diff", "--cached", "--name-only").strip():
            problems.append("phase 4: a refused commit must leave nothing staged")
        leak.unlink()

        # 4b. password assignments: quoted, bare, underscore- or camelCase-prefixed, unquoted, and
        # a credential embedded in a URL are each found in the staged diff by kind; a placeholder
        # (angle brackets, an env-var reference, all-asterisks, "changeme"), an environment lookup,
        # an empty value and prose are not
        password_lines = ['password="my pass"', "PASSWORD: 'abcdef12'", '{"password": "s3cr3tpw"}',
                           'DB_PASSWORD="hunter2xyz"', 'POSTGRES_PASSWORD=hunter2xyz', 'userPassword: "hunter2xyz"',
                           'password: hunter2xyz', 'export PASSWORD=hunter2xyz']
        url_lines = ['https://user:secret@host.example.com/path']
        clean_lines = ['password="<redacted: demo>"', 'password = os.environ["PW"]', "passwords are hard to remember",
                       'password: <redacted>', 'password: ${VAR}', 'password=', 'the password is required',
                       'password: <password>', 'password: ***', 'password: changeme']
        hits_file = sandbox / "04_Resources" / "Eval-Password-Note.md"
        hits_file.write_text("\n".join(password_lines + url_lines + clean_lines) + "\n", encoding="utf-8")
        _git(sandbox, "add", "--", str(hits_file.relative_to(sandbox)))
        hits = pr.scan_staged(sandbox)
        found = sorted(h.get("line") for h in hits if h.get("kind") == "password assignment")
        want = list(range(1, len(password_lines) + 1))
        if found != want:
            problems.append(f"phase 4b: password assignments found on lines {found}, want {want}")
        url_found = sorted(h.get("line") for h in hits if h.get("kind") == "credential in URL")
        url_want = list(range(len(password_lines) + 1, len(password_lines) + len(url_lines) + 1))
        if url_found != url_want:
            problems.append(f"phase 4b: credentials in a URL found on lines {url_found}, want {url_want}")
        clean_start = len(password_lines) + len(url_lines) + 1
        stray = [h for h in hits if h.get("line", 0) >= clean_start]
        if stray:
            problems.append(f"phase 4b: a placeholder, env lookup, empty value or prose must not be flagged, got {stray}")
        _git(sandbox, "reset", "-q", "--", str(hits_file.relative_to(sandbox)))
        hits_file.unlink()
        _begin(pr, sandbox, NOW + timedelta(hours=15))
        if _end(pr, sandbox, NOW + timedelta(hours=15), 0, 0, []).get("status") != "ok":
            problems.append("phase 4: once the key is gone the next run commits")

        # 4c. an image a capture names that git ignores (or that is gone) gets a DLQ note and a
        # summary count, so the loss is never silent
        gi = sandbox / ".gitignore"
        gi_before = gi.read_text(encoding="utf-8") if gi.is_file() else None
        gi.write_text("*.JPG\n", encoding="utf-8")
        _git(sandbox, "config", "core.ignorecase", "true")  # a Mac checkout: *.JPG also matches .jpg
        att = sandbox / "04_Resources" / "Attachments" / "Tweets"
        att.mkdir(parents=True, exist_ok=True)
        (att / "eval-1.jpg").write_bytes(b"\xff\xd8\xff")  # no NUL: git diffs it as text, and it is not UTF-8
        (att / "eval-2.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        capm = sandbox / "01_Capture" / "Readwise-Tweet-Media.md"
        capm.write_text("---\nsource: https://x.com/a/status/1\nmedia:\n- 04_Resources/Attachments/Tweets/eval-1.jpg\n"
                        "- 04_Resources/Attachments/Tweets/eval-2.png\n- 04_Resources/Attachments/Tweets/eval-gone.jpg\n---\n# M\n",
                        encoding="utf-8")
        _begin(pr, sandbox, NOW + timedelta(hours=16))
        with (sandbox / pr.LEDGERS["ingested"]).open("a", encoding="utf-8") as fh:
            fh.write('{"doc_id": "m1", "capture": "01_Capture/Readwise-Tweet-Media.md", "via": "clip"}\n')
        r = _end(pr, sandbox, NOW + timedelta(hours=16), 0, 0, [])
        want = {"ignored": ["04_Resources/Attachments/Tweets/eval-1.jpg"], "missing": ["04_Resources/Attachments/Tweets/eval-gone.jpg"]}
        dlq = list((sandbox / "00_Memory" / "dlq").glob("*media-not-in-git*.md"))
        if r.get("lost_media") != want or "1 image(s) git-ignored, 1 image(s) missing" not in r.get("summary", ""):
            problems.append(f"phase 4c: expected {want} in the result and summary, got {r.get('lost_media')} / {r.get('summary')}")
        if len(dlq) != 1 or "eval-1.jpg" not in dlq[0].read_text(encoding="utf-8") or "eval-gone.jpg" not in dlq[0].read_text(encoding="utf-8"):
            problems.append(f"phase 4c: one DLQ note naming the ignored and the missing image, got {len(dlq)}")
        capm.unlink()
        for f in att.iterdir():
            f.unlink()
        if gi_before is None:
            gi.unlink()
        else:
            gi.write_text(gi_before, encoding="utf-8")

        # 5. git sync through an upstream
        problems += _sync_phase(pr, sandbox)

        # 6. a failing generator: reported, one DLQ note however often it fails, the run committed
        problems += _build_failure_phase(pr, sandbox)

        # 7. a routine's own files: commit only the named paths
        problems += _commit_phase(pr, sandbox)

        # 8. stamp_distilled_notes: the `end` safety net beside retire_capture.py's own stamping —
        # a distilled note missing distilled_at/ingested_at, changed but not yet committed, gets
        # both: distilled_at to now, ingested_at carried from its own already-archived capture
        # (matched by source); a note with its own value is left alone
        arch_dir = sandbox / "05_Archive" / "Readwise-Captures-2026-09"
        arch_dir.mkdir(parents=True, exist_ok=True)
        (arch_dir / "Stamp-Safety-Net--FULLCAPTURE.md").write_text(
            '---\nsource: https://example.org/stamp-safety-net\ningested_at: "2026-09-01T09:00:00Z"\n---\n\nbody\n',
            encoding="utf-8")
        untouched_note = sandbox / "04_Resources" / "Eval-Stamp-Untracked.md"
        untouched_note.write_text(
            "---\ndescription: not part of this run's diff\nstatus: distilled\n"
            "source: https://example.org/stamp-safety-net-other\nprocessed_date: 2026-09-24\n---\n\nBody.\n",
            encoding="utf-8")
        _git(sandbox, "add", "-A")
        _git(sandbox, "commit", "-q", "-m", "eval fixture: pre-existing note")
        target = sandbox / "04_Resources" / "Eval-Stamp-Safety-Net.md"
        target.write_text(
            "---\ndescription: safety-net stamped note\nstatus: distilled\n"
            "source: https://example.org/stamp-safety-net\nprocessed_date: 2026-09-24\n---\n\nBody.\n", encoding="utf-8")
        rows_in = [{"doc_id": "safety1", "capture": "01_Capture/Stamp-Safety-Net.md"}]
        stamped = pr.stamp_distilled_notes(sandbox, rows_in)
        if stamped != ["04_Resources/Eval-Stamp-Safety-Net.md"]:
            problems.append(f"phase 8: stamp_distilled_notes should stamp only the changed note, got {stamped}")
        fm, _ = read_frontmatter(target)
        import re as _re
        if not _re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", str(fm.get("distilled_at") or "")):
            problems.append(f"phase 8: distilled_at not stamped in the right format: {fm.get('distilled_at')!r}")
        if fm.get("ingested_at") != "2026-09-01T09:00:00Z":
            problems.append(f"phase 8: ingested_at not carried from the matching archived capture: {fm.get('ingested_at')!r}")
        if pr.stamp_distilled_notes(sandbox, rows_in):
            problems.append("phase 8: not idempotent — a second call re-stamped an already-stamped note")
        untouched_fm, _ = read_frontmatter(untouched_note)
        if untouched_fm.get("distilled_at") or untouched_fm.get("ingested_at"):
            problems.append("phase 8: a note outside this run's working-tree diff must not be touched")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "clips first, lock, one commit per run, parking after two failures"}
