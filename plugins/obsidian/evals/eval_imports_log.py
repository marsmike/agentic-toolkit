"""Eval: imports_log.py records what each run imported and says what became of every item.

1. record  — a run's ledger rows land in 00_Memory/imports.jsonl with the capture's title and source
2. fates   — distilled (manifest line names the note), dropped, duplicate, waiting (in the inbox),
             known (found in the vault), archived (whole in the archive, no manifest line) and
             missing (nowhere) are each told apart
3. page    — Imports.md is one file, days as `## YYYY-MM-DD` sections headed by how many runs the
             day had (quiet ones too), runs as `### YYYY-MM-DD HH:MM` sections newest first, and a
             missing clipping is called out at the top; an item with no `retired` row renders from
             its manifest line exactly as before
4. retired — an item's `retired` row wins over its manifest prose: the notes it names (though the
             `--line` has no wikilink), `kind`, and a drop's `reason` as a field
5. counts  — a run row's own counts make the day's totals; a legacy row without counts (and no
             commit to read them from) still counts as a run, its numbers as "not recorded"
6. prune   — rows older than 84 days go (a run row by its label, a retired row by its `at`), this
             run and undated rows stay, the file stays valid JSONL, a second prune changes nothing
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "imports_log"
ARCH = "05_Archive/Readwise-Captures-2026-09"
CAP = ("---\nsource: https://example.org/{n}\ncategory: article\nvia: clip\n"
       'ingested_at: "2026-09-24T08:00:00Z"\n---\n\n# Title {n}\n')


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
        (sandbox / "04_Resources" / "Eval-Imports-Note.md").write_text(
            '---\nstatus: distilled\ndistilled_at: "2026-09-25T12:00:00Z"\n---\n# N\n', encoding="utf-8")
        c = lambda n: {"doc_id": n, "capture": f"01_Capture/Readwise-Article-{n}.md", "via": "clip"}  # noqa: E731
        imports_log.record(sandbox, "2026-09-24 10:00", [c("dist"), c("drop"), c("gone")])
        imports_log.record(sandbox, "2026-09-25 10:00", [c("dup"), c("wait"), c("hand"),
                                                         {"doc_id": "k", "found": "04_Resources/Eval-Imports-Note.md"}])
        imports_log.record(sandbox, "2026-09-25 13:00", [])
        imports_log.record(sandbox, "2026-09-25 16:00", [c("new"), c("why")], at="2026-09-25T16:00:05Z", distilled=3,
                           dropped=1, failed=0, shallow=False, summary="3 distilled, 1 dropped, 0 failed")
        for n in ("new", "why"):
            (sandbox / ARCH / f"Readwise-Article-{n}--FULLCAPTURE.md").write_text(CAP.format(n=n), encoding="utf-8")
        with (sandbox / ARCH / "README.md").open("a", encoding="utf-8") as fh:
            fh.write("- `Readwise-Article-new--FULLCAPTURE.md` — new note on things, no link here Distilled 2026-09-25.\n"
                     "- `Readwise-Article-why--FULLCAPTURE.md` — **dropped** (never distilled): prose reason Retired 2026-09-25.\n")
        with (sandbox / imports_log.LOG).open("a", encoding="utf-8") as fh:
            for row in ({"retired": "01_Capture/Readwise-Article-new.md", "at": "2026-09-25T15:50:00Z", "kind": "new",
                         "notes": ["04_Resources/Eval-Imports-Note.md"], "reason": None, "what": "new note on things, no link here"},
                        {"retired": "01_Capture/Readwise-Article-why.md", "at": "2026-09-25T15:51:00Z", "kind": "dropped",
                         "notes": [], "reason": "a Windows-only plugin", "what": None}):
                fh.write(json.dumps(row) + "\n")

        rows = [json.loads(x) for x in (sandbox / imports_log.LOG).read_text(encoding="utf-8").splitlines()]
        first = rows[0]["items"][0]
        if first.get("title") != "Title dist" or first.get("source") != "https://example.org/dist":
            problems.append(f"record: {first}")
        if first.get("ingested_at") != "2026-09-24T08:00:00Z":
            problems.append(f"record: ingested_at not carried from the capture: {first.get('ingested_at')!r}")

        items = {it.get("doc_id"): it for r in imports_log.resolved(sandbox) for it in r["items"]}
        fates = {k: it["fate"] for k, it in items.items()}
        want = {"dist": "distilled", "drop": "dropped", "gone": "missing", "dup": "duplicate", "wait": "waiting",
                "hand": "archived", "k": "known", "new": "distilled", "why": "dropped"}
        got = {k: fates.get(k, {}).get("status") for k in want}
        if got != want:
            problems.append(f"fates: {got}")
        if fates.get("dist", {}).get("notes") != ["04_Resources/Eval-Imports-Note"]:
            problems.append(f"fates: distilled notes {fates.get('dist')}")
        if fates.get("dist", {}).get("distilled_at") != "2026-09-25T12:00:00Z":
            problems.append(f"fates: distilled_at not read from the note, got {fates.get('dist')}")

        if (fates.get("new", {}).get("notes"), fates.get("new", {}).get("kind")) != (["04_Resources/Eval-Imports-Note"], "new"):
            problems.append(f"retired: the row's notes and kind must win over the manifest prose, got {fates.get('new')}")
        if (fates.get("why", {}).get("reason"), fates.get("why", {}).get("detail")) != ("a Windows-only plugin",) * 2:
            problems.append(f"retired: a drop's reason must come from its row, got {fates.get('why')}")
        if "reason" in fates.get("drop", {}):
            problems.append("retired: a legacy manifest-only drop has no structured reason")
        if (fates.get("new", {}).get("retired_at"), fates.get("why", {}).get("retired_at")) != ("2026-09-25T15:50:00Z", "2026-09-25T15:51:00Z"):
            problems.append(f"retired: a fate carries when its capture was retired, got {fates.get('new')}")
        # an enrichment shows when it enriched, never the note's own first distilled_at [earned: 2026-10-01]
        enriched = {"title": "E", "category": "article", "fate": {"status": "distilled", "kind": "enriched", "notes": [],
                    "detail": "L1", "distilled_at": "2026-09-01T00:00:00Z", "retired_at": "2026-09-25T15:50:00Z"}}
        line = imports_log._bullet(sandbox, enriched)
        if "(enriched 2026-09-25 15:50" not in line or "distilled 2026-09-01" in line:
            problems.append(f"page: an enrichment must show when it enriched, not the note's first distillation: {line}")

        page = imports_log.render(sandbox)
        if ("- **Article** [Title drop](https://example.org/drop) — clip, ingested 2026-09-24 08:00 UTC → dropped: "
                "**dropped** (never distilled): radar noise. Retired 2026-09-25.") not in page:
            problems.append("page: a legacy item (no retired row) no longer renders from its manifest line as before")
        if "→ dropped: a Windows-only plugin" not in page or "[[04_Resources/Eval-Imports-Note|" not in page.split("Title new", 1)[-1]:
            problems.append("page: a retired row's reason or note is not shown")
        if not re.search(r"\*Generated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\.\*", page):
            problems.append("page: missing its own 'Generated ... UTC' header line")
        if "ingested 2026-09-24 08:00 UTC" not in page:
            problems.append("page: a capture's own ingested timestamp is not shown per item")
        if "distilled 2026-09-25 12:00 UTC" not in page:
            problems.append("page: a distilled note's own distilled timestamp is not shown per item")
        heads = re.findall(r"^### (\S+ \S+)$", page, re.M)
        if heads != ["2026-09-25 16:00", "2026-09-25 10:00", "2026-09-24 10:00"]:
            problems.append(f"page: run sections {heads}")
        days = re.findall(r"^## (\S+)\n\n(.+)$", page, re.M)
        if days != [("2026-09-25", "3 runs: 3 distilled, 1 dropped, 0 failed (2 run(s) without recorded counts)."),
                    ("2026-09-24", "1 run: 0 distilled, 0 dropped, 0 failed (1 run(s) without recorded counts).")]:
            problems.append(f"page/counts: day sections {days}")
        t = imports_log.day_totals(imports_log.runs(sandbox), "2026-09-25")
        if t != {"runs": 3, "distilled": 3, "dropped": 1, "failed": 0, "uncounted": 2}:
            problems.append(f"counts: {t}")
        top = page.split("\n## ", 1)[0]
        if "Missing clippings" not in top or "gone" not in top:
            problems.append("page: missing clipping not called out first")
        if "Nothing new in 1 run(s)" not in page:
            problems.append("page: the quiet run is not mentioned")

        # prune: a fresh ledger, dated around today; a line that is not JSON goes with the rewrite
        today, log = date.today(), sandbox / imports_log.LOG
        old, edge = (today - timedelta(days=85)).isoformat(), (today - timedelta(days=84)).isoformat()
        rows = [{"kind": "run", "run": f"{old} 10:00", "items": []}, {"retired": "01_Capture/x.md", "at": f"{old}T10:00:00Z"},
                {"kind": "run", "run": f"{old} 13:00", "items": []}, {"kind": "run", "run": f"{edge} 10:00", "items": []},
                {"retired": "01_Capture/y.md", "at": f"{today.isoformat()}T10:00:00Z"}, {"note": "undated"}]
        log.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n", encoding="utf-8")
        gone = imports_log.prune(sandbox, f"{old} 13:00", today)  # the old 13:00 run is this one: kept
        kept = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
        if gone != 2 or kept != rows[2:]:
            problems.append(f"prune: removed {gone}, kept {kept}")
        second = imports_log.prune(sandbox, f"{today.isoformat()} 10:00", today)
        before = log.read_bytes()
        if second != 1 or imports_log.prune(sandbox, f"{today.isoformat()} 10:00", today) != 0 or log.read_bytes() != before:
            problems.append(f"prune: the old run goes once it is not this run ({second}), and a second prune changes nothing")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "record, seven fates, retired rows win, day counts, one sorted page, prune"}
