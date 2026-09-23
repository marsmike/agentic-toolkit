"""Eval: `radar.py replay`, the acceptance run, offline (stubbed `judge._post` and `reader._request`).

1. arithmetic — AUC with ties, recall at a budget and BM25 ranking on hand-made numbers
2. no key      — SKIPPED, no request, nothing written
3. replay      — clips from every clip location are positives; feed items that were also clipped,
                 back catalogue and items after --exclude-last-days are not negatives; `category`
                 never reaches the backend (it would give the label away); a judge that tells
                 clips apart scores AUC 1.0; Reader is only read; nothing in the vault changes;
                 exactly the two report files are written to --out
"""
from __future__ import annotations

import json
import os
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "replay"
ENV_KEYS = ("TOOLKIT_RADAR_JUDGMENT_API_KEY", "OPENROUTER_API_KEY", "TOOLKIT_RADAR_JUDGMENT_BACKEND",
            "TOOLKIT_RADAR_INTERESTS_NOTE", "TOOLKIT_RADAR_TODOIST_PROJECT_ID")
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

INTERESTS_NOTE = """---
description: Fixture interests for the radar replay eval.
status: active
interests:
  - name: Agent Memory
    gloss: How software agents store and recall what they learned across sessions.
    queries: [agent memory recall]
  - name: Firmware
    gloss: Embedded firmware on microcontrollers, RTOS releases and toolchains.
---

# Radar interests (fixture)
"""


def _doc(i: int, title: str, location: str, days_ago: float, category: str = "article",
         published: str = "2026-09-10", url: str | None = None) -> dict:
    return {"id": f"d{i}", "title": title, "summary": f"summary of {title}", "category": category,
            "source_url": url or f"https://example.org/{location}/{i}", "site_name": "Example",
            "location": location, "parent_id": None, "published_date": published,
            "saved_at": (NOW - timedelta(days=days_ago)).isoformat()}


DOCS = {
    "new": [_doc(1, "Agent memory survey CLIP", "new", 10)],
    "later": [_doc(2, "Zephyr RTOS release notes CLIP", "later", 12, url="https://example.org/shared")],
    "shortlist": [],
    "archive": [_doc(3, "A thread on agent recall CLIP", "archive", 15, category="tweet"),
                _doc(4, "Too recent CLIP", "archive", 2)],
    "feed": [_doc(10, "Local weather", "feed", 11, category="rss"),
             _doc(11, "Celebrity news", "feed", 13, category="rss"),
             _doc(12, "Same page as a clip", "feed", 12, category="rss", url="https://example.org/shared"),
             _doc(13, "Back catalogue", "feed", 14, category="rss", published="2019-01-01"),
             _doc(14, "Sports results", "feed", 16, category="rss"),
             _doc(15, "Too recent feed", "feed", 1, category="rss")],
}


def run(vault: Path) -> dict:
    import judge
    import reader
    import replay

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (judge._post, reader._request, reader.PAGE_DELAY_S)
    calls: list[dict] = []
    sandbox = None

    # 1. arithmetic
    if replay.auc([3, 2], [1, 0]) != 1.0 or replay.auc([1], [1]) != 0.5 or replay.auc([0], [1]) != 0.0:
        problems.append("phase 1: AUC wrong on separable, tied or inverted scores")
    if replay.auc([2, 1], [1, 0]) != 0.875:
        problems.append(f"phase 1: AUC with a partial tie should be 0.875, got {replay.auc([2, 1], [1, 0])}")
    if replay.recall_at_budget([5, 1], [4, 3, 2, 0], 0.25) != 0.5:
        problems.append("phase 1: recall at a 25% budget of [4,3,2,0] should admit 5 and not 1")
    docs = [replay.tokens("firmware release for the rtos"), replay.tokens("a recipe for soup"), replay.tokens("soup again")]
    s = replay.bm25(docs, [replay.tokens("rtos firmware")])
    if not (s[0] > s[1] == s[2] == 0.0):
        problems.append(f"phase 1: BM25 should rank only the matching doc, got {s}")

    def reader_stub(method, url, data=None):
        if method != "GET":
            problems.append(f"reader: unexpected {method} (replay must never write to Reader)")
        loc = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["location"][0]
        return 200, {"results": DOCS[loc], "nextPageCursor": None}, None

    def judge_stub(url, payload, headers):
        calls.append(payload)
        answers = {}
        for qid in payload["questions"]:
            if qid.startswith("kind_"):
                answers[qid] = {"type": "choice", "choice": "other", "probabilities": {"other": 1.0}}
                continue
            _, key, _n = qid.split("_")
            answers[qid] = {"type": "noul", "noul": 0.9 if "CLIP" in payload["state"]["items"][key]["title"] else 0.2}
        return {"model": "stub-1", "usage": {"input_tokens": 100}, "answers": answers}

    try:
        sandbox = make_sandbox(vault)
        (sandbox / "03_Areas" / "Radar-Interests.md").write_text(INTERESTS_NOTE, encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "03_Areas/Radar-Interests.md"
        reader._request, reader.PAGE_DELAY_S, judge._post = reader_stub, 0, judge_stub
        out = sandbox.parent / "replay-out"
        since, until = NOW - timedelta(days=30), NOW - timedelta(days=7)

        # 2. no key
        before = snapshot(sandbox)
        r = replay.replay(sandbox, out, since, until, feed_sample=0)
        if r["status"] != "SKIPPED" or calls or out.exists() or snapshot(sandbox) != before:
            problems.append(f"phase 2: expected SKIPPED with no request and no write, got {r['status']}")

        # 3. replay
        os.environ["TOOLKIT_RADAR_JUDGMENT_API_KEY"] = "stub-key-not-a-secret"
        r = replay.replay(sandbox, out, since, until, feed_sample=0)
        if r.get("status") != "ok" or r.get("clips") != 3 or r.get("feed_in_window") != 3:
            problems.append(f"phase 3: expected ok, 3 clips, 3 feed items, got "
                            f"{json.dumps({k: r.get(k) for k in ('status', 'clips', 'feed_in_window', 'feed_dropped', 'detail')})}")
        if r.get("feed_dropped") != {"also clipped": 1, "backlog": 1, "outside window": 1}:
            problems.append(f"phase 3: wrong drop reasons {r.get('feed_dropped')}")
        if r.get("metrics", {}).get("jev", {}).get("auc") != 1.0 or r.get("jev_beats_bm25") is None:
            problems.append(f"phase 3: a separating judge must score AUC 1.0, got {r.get('metrics')}")
        for payload in calls:
            if any(it.get("category") for it in payload["state"]["items"].values()):
                problems.append("phase 3: category reached the backend")
                break
        if snapshot(sandbox) != before:
            problems.append("phase 3: replay wrote into the vault")
        if sorted(p.name for p in out.iterdir()) != ["replay-report.json", "replay-rows.jsonl"]:
            problems.append(f"phase 3: --out should hold exactly the two report files, got {sorted(p.name for p in out.iterdir())}")
        rows = [json.loads(ln) for ln in (out / "replay-rows.jsonl").read_text(encoding="utf-8").splitlines()]
        if sorted(r_["label"] for r_ in rows) != [0, 0, 0, 1, 1, 1] or {"tweet", "rss"} - {r_["category"] for r_ in rows}:
            problems.append("phase 3: rows should keep labels and the original category for the audit")
    finally:
        judge._post, reader._request, reader.PAGE_DELAY_S = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"3 offline phases ok ({len(calls)} stubbed judgment requests)"}
