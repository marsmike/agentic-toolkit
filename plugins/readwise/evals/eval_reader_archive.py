"""Eval: `ingest.archive_settled` archives in Reader only what is settled on the remote (offline).

In a git sandbox with a bare upstream, the ledger holds: A retired to 05_Archive and pushed,
B retired but only committed locally, C still in 01_Capture, D found already in the vault (a
pushed note), E a copy of A, F archived by an earlier run.

1. no upstream — skipped, Reader untouched
2. settled     — A, D and E are archived (D answers 404 and is recorded `gone`); B, C, F are not
3. ledger      — one row each in 00_Memory/readwise-archived.jsonl
4. rerun       — a second pass archives nothing
5. next run    — once B is pushed, it is archived
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "reader_archive"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
ARCH = "05_Archive/Readwise-Captures-2026-09"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import ingest
    import readwise_api as rw

    problems: list[str] = []
    calls: list[str] = []

    def fake_archive(doc_id: str, token: str | None = None) -> dict:
        calls.append(doc_id)
        if doc_id == "D":
            raise rw.ReadwiseAPIError("not found", status=404)
        return {"id": doc_id}

    sandbox, bare = make_sandbox(vault), Path(tempfile.mkdtemp(prefix="readwise-plugin-eval-bare-"))
    saved = (rw.reader_archive, ingest.GET_DELAY_S)
    try:
        rw.reader_archive, ingest.GET_DELAY_S = fake_archive, 0
        (sandbox / ARCH).mkdir(parents=True, exist_ok=True)
        (sandbox / "01_Capture").mkdir(exist_ok=True)
        (sandbox / ARCH / "Readwise-Tweet-a-2026-09-24--FULLCAPTURE.md").write_text("a\n", encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Tweet-c-2026-09-25.md").write_text("c\n", encoding="utf-8")
        (sandbox / "04_Resources" / "Known-D.md").write_text("---\nstatus: distilled\n---\n# D\n", encoding="utf-8")
        rows = [{"doc_id": "A", "capture": "01_Capture/Readwise-Tweet-a-2026-09-24.md"},
                {"doc_id": "B", "capture": "01_Capture/Readwise-Tweet-b-2026-09-25.md"},
                {"doc_id": "C", "capture": "01_Capture/Readwise-Tweet-c-2026-09-25.md"},
                {"doc_id": "D", "found": "04_Resources/Known-D.md"},
                {"doc_id": "E", "duplicate_of": "A"},
                {"doc_id": "F", "capture": "01_Capture/Readwise-Tweet-a-2026-09-24.md"}]
        (sandbox / ingest.LEDGER).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (sandbox / ingest.ARCHIVED).write_text(json.dumps({"doc_id": "F", "archived": "2026-09-24"}) + "\n", encoding="utf-8")
        for args in (("init", "-q", "-b", "main"), ("config", "user.email", "eval@example.org"),
                     ("config", "user.name", "eval"), ("add", "-A"), ("commit", "-q", "-m", "base")):
            _git(sandbox, *args)

        r = ingest.archive_settled(sandbox, NOW)
        if r["status"] != "skipped" or calls:
            problems.append(f"no upstream: {r}, calls {calls}")

        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], capture_output=True, check=False)
        _git(sandbox, "remote", "add", "origin", str(bare))
        _git(sandbox, "push", "-q", "-u", "origin", "main")
        (sandbox / ARCH / "Readwise-Tweet-b-2026-09-25--FULLCAPTURE.md").write_text("b\n", encoding="utf-8")
        _git(sandbox, "add", "-A")
        _git(sandbox, "commit", "-q", "-m", "retire b, not pushed")

        r = ingest.archive_settled(sandbox, NOW)
        if sorted(calls) != ["A", "D", "E"] or (r["archived"], r["gone"]) != (2, 1):
            problems.append(f"settled: calls {sorted(calls)}, result {r}")
        got = [json.loads(x) for x in (sandbox / ingest.ARCHIVED).read_text(encoding="utf-8").splitlines()]
        if sorted((g["doc_id"], "gone" in g) for g in got[1:]) != [("A", False), ("D", True), ("E", False)]:
            problems.append(f"ledger: {got}")

        calls.clear()
        ingest.archive_settled(sandbox, NOW)
        if calls:
            problems.append(f"rerun archived again: {calls}")

        _git(sandbox, "push", "-q")
        ingest.archive_settled(sandbox, NOW)
        if calls != ["B"]:
            problems.append(f"next run: {calls}")
    finally:
        rw.reader_archive, ingest.GET_DELAY_S = saved
        teardown_sandbox(sandbox)
        subprocess.run(["rm", "-rf", str(bare)], check=False)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "archives only what the remote has, once"}
