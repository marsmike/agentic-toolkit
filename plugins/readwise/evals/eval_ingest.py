"""Eval: `ingest.py`, the scripted ingest, offline (stubbed `readwise_api._request`).

1. no token    — SKIPPED, nothing written
2. ingest      — a clip, a newsletter and a radar-promoted feed item become captures with
                 `via: clip | newsletter | radar` (and `radar_interests`); a feed item, a feed item
                 the radar archived without promoting, and a highlight child are not ingested; a
                 clip whose address a vault note already has is recorded, not captured; only
                 01_Capture/ and 00_Memory/ change; nothing in Reader is written
3. gap         — an item whose full text fails: status failed, one DLQ note, the watermark stays
4. rerun       — the next run captures the missing item and nothing twice; the watermark moves
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "ingest"
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
KNOWN_NOTE = """---
description: A note distilled earlier from a post the owner clipped again.
status: distilled
source: https://www.example.org/known-post/?utm_source=x
---

# Known post
"""


def _doc(i: str, title: str, location: str, category: str = "article", tags: dict | None = None, **kw) -> dict:
    return {"id": i, "title": title, "category": category, "location": location, "parent_id": None,
            "source_url": kw.pop("url", f"https://example.org/{i}"), "author": "Someone", "summary": f"summary {i}",
            "saved_at": "2026-09-20T10:00:00+00:00", "tags": tags or {}, "notes": kw.pop("notes", ""), **kw}


DOCS = [
    _doc("clip1", "A clipped article", "new"),
    _doc("news1", "Weekly newsletter", "new", category="email"),
    _doc("radar1", "Claude Code v2", "later", category="rss",
         tags={"radar": {}, "radar/claude-code": {}, "radar/dev-tooling": {}}, notes="[radar 2026-09-23] Claude Code p=0.95"),
    _doc("feed1", "Still in the feed", "feed", category="rss"),
    _doc("arch1", "Judged and archived by the radar", "archive", category="rss"),
    _doc("hl1", "a highlight", "new", category="highlight", parent_id="clip1"),
    _doc("known1", "Clipped again", "archive", url="https://example.org/known-post"),
    _doc("flaky1", "Full text fails once", "later"),
]


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import ingest
    import readwise_api as rw
    from vault_utils import read_frontmatter

    problems: list[str] = []
    real = (rw._request, ingest.GET_DELAY_S)
    saved_tok = os.environ.pop("READWISE_TOKEN", None)
    calls: list[tuple[str, str]] = []
    mode = {"flaky": True}
    sandbox = None

    def stub(method, url, token, data=None, timeout=30):
        calls.append((method, url))
        if method != "GET":
            problems.append(f"reader: ingest must not write to Reader, got {method} {url}")
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        if "id" in q:
            if q["id"] == "flaky1" and mode["flaky"]:
                return 500, {"detail": "stub"}
            d = next(d for d in DOCS if d["id"] == q["id"])
            return 200, {"results": [{**d, "html_content": f"<p>full text of {d['id']}</p>"}]}
        docs = [d for d in DOCS if "location" not in q or d["location"] == q["location"]]
        return 200, {"results": docs, "nextPageCursor": None}

    def snap(root: Path) -> dict[str, int]:
        return {p.relative_to(root).as_posix(): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}

    try:
        sandbox = make_sandbox(vault)
        (sandbox / "04_Resources" / "Known-Post.md").write_text(KNOWN_NOTE, encoding="utf-8")
        rw._request, ingest.GET_DELAY_S = stub, 0

        # 1. no token
        before = snap(sandbox)
        r = ingest.ingest(sandbox, NOW)
        if r["status"] != "SKIPPED" or snap(sandbox) != before:
            problems.append(f"phase 1: expected SKIPPED and no write, got {r['status']}")

        # 2 + 3. ingest with one failing full-text fetch
        os.environ["READWISE_TOKEN"] = "stub-token-not-a-secret"
        r = ingest.ingest(sandbox, NOW)
        caps = {}
        for p in (sandbox / "01_Capture").glob("Readwise-*.md"):
            fm, _ = read_frontmatter(p)
            if fm.get("readwise_doc_id") in {d["id"] for d in DOCS}:
                caps[str(fm["readwise_doc_id"])] = fm
        if sorted(caps) != ["clip1", "news1", "radar1"]:
            problems.append(f"phase 2: expected captures for clip1, news1, radar1, got {sorted(caps)}")
        if caps.get("clip1", {}).get("via") != "clip" or caps.get("news1", {}).get("via") != "newsletter":
            problems.append("phase 2: a clip and a newsletter must say so in `via`")
        if caps.get("radar1", {}).get("via") != "radar" or caps.get("radar1", {}).get("radar_interests") != ["claude-code", "dev-tooling"]:
            problems.append(f"phase 2: the radar item needs via: radar and its interests, got {caps.get('radar1')}")
        if r.get("already_in_vault") != 1:
            problems.append(f"phase 2: the clip whose address a note has should be recorded as known, got {r.get('already_in_vault')}")
        changed = {p for p, m in snap(sandbox).items() if before.get(p) != m} - {"04_Resources/Known-Post.md"}
        if any(not (p.startswith("01_Capture/") or p.startswith("00_Memory/")) for p in changed):
            problems.append(f"phase 2: ingest wrote outside 01_Capture/ and 00_Memory/: {sorted(changed)}")
        if r.get("status") != "failed" or r.get("missing") != ["flaky1"] or not list((sandbox / "00_Memory" / "dlq").glob("*readwise-ingest-gap-*.md")):
            problems.append(f"phase 3: a failed full-text fetch must fail the run with one DLQ note, got {r.get('status')}, {r.get('missing')}")
        if (sandbox / ingest.STATE_NOTE).is_file() and "2026-09-23" in (sandbox / ingest.STATE_NOTE).read_text(encoding="utf-8"):
            problems.append("phase 3: the watermark moved after an incomplete run")

        # 4. rerun
        mode["flaky"] = False
        n_caps = len(list((sandbox / "01_Capture").glob("Readwise-*.md")))
        r = ingest.ingest(sandbox, NOW)
        after = len(list((sandbox / "01_Capture").glob("Readwise-*.md")))
        if r.get("status") != "ok" or r.get("written") != 1 or after != n_caps + 1:
            problems.append(f"phase 4: the rerun should capture only flaky1, got {r.get('status')}, written={r.get('written')}, {after - n_caps} new files")
        fm, _ = read_frontmatter(sandbox / ingest.STATE_NOTE)
        if not str(fm.get("lastSyncedAt", "")).startswith("2026-09-23"):
            problems.append(f"phase 4: the watermark should move on a clean run, got {fm.get('lastSyncedAt')}")
        r = ingest.ingest(sandbox, NOW)
        if r.get("written") != 0 or r.get("new") != 0:
            problems.append(f"phase 4: a third run must find nothing new, got new={r.get('new')}")
    finally:
        rw._request, ingest.GET_DELAY_S = real
        os.environ.pop("READWISE_TOKEN", None)
        if saved_tok is not None:
            os.environ["READWISE_TOKEN"] = saved_tok
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"4 offline phases ok ({len(calls)} stubbed Reader calls, all GET)"}
