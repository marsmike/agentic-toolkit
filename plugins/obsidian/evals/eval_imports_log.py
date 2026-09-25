"""Eval: imports_log.py records what each run imported and says what became of every item.

1. record  — a run's ledger rows land in 00_Memory/imports.jsonl with the capture's title and source
2. fates   — distilled (manifest line names the note), dropped, duplicate, waiting (in the inbox),
             known (found in the vault), archived (whole in the archive, no manifest line) and
             missing (nowhere) are each told apart
3. page    — Imports.md is one file, runs as `## YYYY-MM-DD HH:MM` sections newest first, and a
             missing clipping is called out at the top
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "imports_log"
ARCH = "05_Archive/Readwise-Captures-2026-09"
CAP = "---\nsource: https://example.org/{n}\ncategory: article\nvia: clip\n---\n\n# Title {n}\n"


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import imports_log

    problems: list[str] = []
    sandbox, saved = make_sandbox(vault), os.environ.get("TOOLKIT_VAULT")
    try:
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        (sandbox / ARCH).mkdir(parents=True, exist_ok=True)
        (sandbox / "01_Capture").mkdir(exist_ok=True)
        for n in ("dist", "drop", "dup", "hand"):
            (sandbox / ARCH / f"Readwise-Article-{n}--FULLCAPTURE.md").write_text(CAP.format(n=n), encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Article-wait.md").write_text(CAP.format(n="wait"), encoding="utf-8")
        (sandbox / ARCH / "README.md").write_text(
            "# Manifest\n\n- `Readwise-Article-dist--FULLCAPTURE.md` — new note [[04_Resources/Eval-Imports-Note|Note]]. Distilled 2026-09-25.\n"
            "- `Readwise-Article-drop--FULLCAPTURE.md` — **dropped** (never distilled): radar noise. Retired 2026-09-25.\n"
            "- `Readwise-Article-dup--FULLCAPTURE.md` — **duplicate** of `04_Resources/Eval-Imports-Note.md`, kept whole here. Retired 2026-09-25.\n",
            encoding="utf-8")
        (sandbox / "04_Resources" / "Eval-Imports-Note.md").write_text("---\nstatus: distilled\n---\n# N\n", encoding="utf-8")
        c = lambda n: {"doc_id": n, "capture": f"01_Capture/Readwise-Article-{n}.md", "via": "clip"}  # noqa: E731
        imports_log.record(sandbox, "2026-09-24 10:00", [c("dist"), c("drop"), c("gone")])
        imports_log.record(sandbox, "2026-09-25 10:00", [c("dup"), c("wait"), c("hand"),
                                                         {"doc_id": "k", "found": "04_Resources/Eval-Imports-Note.md"}])
        imports_log.record(sandbox, "2026-09-25 13:00", [])

        rows = [json.loads(x) for x in (sandbox / imports_log.LOG).read_text(encoding="utf-8").splitlines()]
        first = rows[0]["items"][0]
        if first.get("title") != "Title dist" or first.get("source") != "https://example.org/dist":
            problems.append(f"record: {first}")

        fates = {it.get("doc_id"): it["fate"] for r in imports_log.resolved(sandbox) for it in r["items"]}
        want = {"dist": "distilled", "drop": "dropped", "gone": "missing", "dup": "duplicate", "wait": "waiting",
                "hand": "archived", "k": "known"}
        got = {k: fates.get(k, {}).get("status") for k in want}
        if got != want:
            problems.append(f"fates: {got}")
        if fates.get("dist", {}).get("notes") != ["04_Resources/Eval-Imports-Note"]:
            problems.append(f"fates: distilled notes {fates.get('dist')}")

        page = imports_log.render(sandbox)
        heads = re.findall(r"^## (\S+ \S+)$", page, re.M)
        if heads != ["2026-09-25 10:00", "2026-09-24 10:00"]:
            problems.append(f"page: sections {heads}")
        top = page.split("\n## ", 1)[0]
        if "Missing clippings" not in top or "gone" not in top:
            problems.append("page: missing clipping not called out first")
        if "Nothing new in 1 run(s)" not in page:
            problems.append("page: the quiet run is not mentioned")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "record, seven fates, one sorted page"}
