"""Eval: `radar.py scan` end to end, offline (stubbed `judge._post`, `reader._request`, `interests._run_td`).

1. no key      — SKIPPED, no request, no DLQ note, nothing written
2. scan        — Reader pagination, children and items older than --since dropped, arXiv abs/pdf
                 spellings deduped to one item; every question names only state that exists; state
                 carries no search queries and no reading signals; an item strong for two interests
                 is strong for both; an item whose source a vault note already has is marked; only
                 00_Memory/radar/ changes; a repost (same feed, same title, new URL) is not judged
                 again; a new feed's back catalogue is marked seen as backlog, never judged
3. rerun       — the same items are seen: no request, status empty
4. split       — a backend refusing the state for size gets smaller chunks; every item is still judged
5. failure     — a backend answering nothing: one DLQ note, status failed, nothing but backlog marked seen
6. epics       — Portfolio epics via `td`: wanted sections only, no subtasks, no completed tasks,
                 the `What:` sentence as gloss
8. promote     — with --promote the strong item and its twin move to Later tagged radar and
                 radar/<interest> with a note naming each interest and p, the rest are archived;
                 a failed promotion leaves the item in the feed (not archived) and the next scan
                 promotes it from state without a judgment request
7. archive     — every recorded item (judged, repost, backlog) is archived in Reader in one
                 bulk_update and nothing else is: not with no key, not an item a failed or
                 --limit-ed run did not judge, not with --keep-in-feed; a Reader error while
                 archiving leaves the scan ok; the only write to Reader is location=archive
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "scan"
ENV_KEYS = ("TOOLKIT_RADAR_JUDGMENT_API_KEY", "OPENROUTER_API_KEY", "TOOLKIT_RADAR_JUDGMENT_BACKEND",
            "TOOLKIT_RADAR_INTERESTS_NOTE", "TOOLKIT_RADAR_TODOIST_PROJECT_ID", "TOOLKIT_RADAR_TODOIST_SECTIONS")
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

INTERESTS_NOTE = """---
description: Fixture interests for the radar evals.
status: active
interests:
  - name: Agent Memory
    gloss: How software agents store and recall what they learned across sessions.
    queries: [SECRET-QUERY-agent-memory]
  - name: Firmware
    gloss: Embedded firmware on microcontrollers, RTOS releases and toolchains.
    queries: [SECRET-QUERY-firmware]
  - name: Birding
    gloss: Field identification of birds and field guides.
---

# Radar interests (fixture)
"""

KNOWN_NOTE = """---
description: A note distilled from a post the radar will meet again in the feed.
status: distilled
source: https://example.org/posts/known
---

# Known post
"""


def _doc(i: int, title: str, url: str, hours_ago: float = 1, parent: str | None = None, site: str = "Example Feed",
         published: str = "2026-09-22") -> dict:
    return {"id": f"doc{i}", "title": title, "summary": f"summary of {title}", "source_url": url,
            "url": f"https://read.readwise.io/read/doc{i}", "site_name": site, "category": "rss",
            "location": "feed", "parent_id": parent, "published_date": published,
            "saved_at": (NOW - timedelta(hours=hours_ago)).isoformat(), "reading_progress": 0.5}


PAGE_1 = [
    _doc(1, "Paper on agent memory [strong:agent-memory,firmware]", "https://arxiv.org/abs/2609.00001v1", site="arXiv"),
    _doc(2, "Same paper as pdf [strong:birding]", "https://arxiv.org/pdf/2609.00001v2.pdf", site="arXiv"),
    _doc(3, "Zephyr 4.3 released [worth:firmware]", "https://github.com/zephyrproject-rtos/zephyr.git"),
]
PAGE_2 = [
    _doc(4, "Local news", "https://example.org/news/1?utm_source=feed"),
    _doc(5, "a highlight", "https://example.org/h", parent="doc4"),
    _doc(6, "Old item [strong:birding]", "https://example.org/old", hours_ago=48),
    _doc(7, "Known post again [worth:agent-memory]", "https://example.org/posts/known?utm_medium=rss"),
    _doc(8, "Zephyr 4.3 Released! [worth:firmware]", "https://example.org/mirror/zephyr-4-3"),
    _doc(9, "From the new feed's archive [strong:birding]", "https://example.org/archive/2019", published="2019-03-01"),
]

TD_SECTIONS = [{"id": "s-doing", "name": "Doing"}, {"id": "s-ideas", "name": "Ideas"}]
TD_TASKS = [
    {"id": "t1", "content": "radar — feed judgments", "sectionId": "s-doing", "parentId": None, "checked": False,
     "description": "What: A plugin that judges feed items. It runs daily.\nWhy: less noise"},
    {"id": "t2", "content": "an idea", "sectionId": "s-ideas", "parentId": None, "checked": False, "description": ""},
    {"id": "t3", "content": "a subtask", "sectionId": "s-doing", "parentId": "t1", "checked": False, "description": ""},
    {"id": "t4", "content": "finished epic", "sectionId": "s-doing", "parentId": None, "checked": True, "description": ""},
]


def run(vault: Path) -> dict:
    import interests as interests_mod
    import judge
    import radar
    import reader
    from judgments import policy

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (judge._post, reader._request, reader.PAGE_DELAY_S, interests_mod._run_td, policy.ITEMS_PER_REQUEST)
    calls: list[dict] = []
    reader_calls: list[str] = []
    archived: list[list[str]] = []
    promoted: list[dict] = []
    mode = {"too_large_above": None, "fail": False, "archive_status": 200, "promote_status": 200}
    sandbox = None

    def reader_stub(method, url, data=None):
        if method == "PATCH" and url.endswith("/bulk_update/"):
            updates = data["updates"]
            if any(set(u) - {"id", "location", "tags", "notes"} or u["location"] not in ("archive", "later")
                   or (u["location"] == "archive" and set(u) != {"id", "location"}) for u in updates) or len(updates) > 50:
                problems.append(f"reader: a write other than archive or a tagged promotion, or over 50: {updates[:2]}")
            to_later = [u for u in updates if u["location"] == "later"]
            status = mode["promote_status"] if to_later else mode["archive_status"]
            if status != 200:
                return status, {"detail": "stub"}, None
            if to_later:
                promoted.extend(to_later)
            else:
                archived.append([u["id"] for u in updates])
            return 200, {"results": [{"id": u["id"], "success": True} for u in updates]}, None
        reader_calls.append(url)
        if method != "GET":
            problems.append(f"reader: unexpected {method} {url}")
        if "pageCursor=p2" in url:
            return 200, {"results": PAGE_2, "nextPageCursor": None}, None
        return 200, {"results": PAGE_1, "nextPageCursor": "p2"}, None

    def judge_stub(url, payload, headers):
        calls.append(payload)
        state, questions = payload["state"], payload["questions"]
        if mode["fail"]:
            raise judge._CallError("HTTP 401: stub", retryable_by_split=False)
        if mode["too_large_above"] and len(state["items"]) > mode["too_large_above"]:
            raise judge.StateTooLarge("stub: max_tokens_exceeded")
        ids = list(state["interests"])
        answers = {}
        for qid in questions:
            if qid.startswith("kind_"):
                answers[qid] = {"type": "choice", "choice": "news",
                                "probabilities": {"news": 0.7, "paper": 0.2, "other": 0.1}}
                continue
            _, key, n = qid.split("_")
            title = state["items"][key]["title"]
            iid = ids[int(n)]
            p = 0.1
            if "strong:" in title and iid in title.split("strong:")[1].split("]")[0].split(","):
                p = 0.9
            elif "worth:" in title and iid in title.split("worth:")[1].split("]")[0].split(","):
                p = 0.75
            answers[qid] = {"type": "noul", "noul": p}
        return {"model": "stub-1", "usage": {"input_tokens": 100}, "answers": answers}

    try:
        sandbox = make_sandbox(vault)
        (sandbox / "03_Areas" / "Radar-Interests.md").write_text(INTERESTS_NOTE, encoding="utf-8")
        (sandbox / "04_Resources" / "Known-Post.md").write_text(KNOWN_NOTE, encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "03_Areas/Radar-Interests.md"
        reader._request, reader.PAGE_DELAY_S, judge._post = reader_stub, 0, judge_stub
        out = sandbox / "00_Memory" / "radar"
        since = NOW - timedelta(days=1)

        # 1. no key
        before = snapshot(sandbox)
        r = radar.scan(sandbox, out, since, NOW)
        if r["status"] != "SKIPPED" or calls or archived or snapshot(sandbox) != before:
            problems.append(f"phase 1: expected SKIPPED with no request and no write, got {r['status']}, {len(calls)} calls")

        # 2. scan
        os.environ["TOOLKIT_RADAR_JUDGMENT_API_KEY"] = "stub-key-not-a-secret"
        before = snapshot(sandbox)
        r = radar.scan(sandbox, out, since, NOW)
        if r.get("status") != "ok" or r.get("judged") != 4 or r.get("fetched") != 7 or r.get("backlog") != 1:
            problems.append(f"phase 2: expected ok, fetched 7, judged 4, backlog 1, got {json.dumps({k: r.get(k) for k in ('status', 'fetched', 'judged', 'backlog', 'detail')})}")
        if len(reader_calls) != 2:
            problems.append(f"phase 2: expected two Reader pages, got {len(reader_calls)}")
        want = ["doc1", "doc2", "doc3", "doc4", "doc7", "doc8", "doc9"]
        if len(archived) != 1 or sorted(archived[0]) != want or r.get("archived") != 7:
            problems.append(f"phase 2: expected one bulk_update archiving {want}, got {archived}")
        for payload in calls:
            wire = json.dumps(payload["state"])
            if "SECRET-QUERY" in wire or "reading_progress" in wire or "doc1" in wire:
                problems.append("phase 2: state carries queries, reading signals or Reader ids")
            for qid, q in payload["questions"].items():
                for ref in q["instructions"].split("`")[1::2]:
                    top, _, key = ref.partition(".")
                    if top not in payload["state"] or key not in payload["state"][top]:
                        problems.append(f"phase 2: {qid} names `{ref}`, not in state")
        rows = {row["id"]: row for row in radar.read_jsonl(out / "state.jsonl")}
        if rows.get("doc1", {}).get("strong") != ["agent-memory", "firmware"]:
            problems.append(f"phase 2: doc1 should be strong for both interests, got {rows.get('doc1', {}).get('strong')}")
        if "doc2" in rows:
            problems.append("phase 2: the pdf spelling of doc1's paper was judged again")
        if "doc8" in rows or "doc9" in rows:
            problems.append("phase 2: a repost or a back-catalogue item was judged")
        if not any(r_.get("backlog") and "archive/2019" in r_["canonical"] for r_ in radar.read_jsonl(out / "seen.jsonl")):
            problems.append("phase 2: the back-catalogue item was not recorded as seen")
        if rows.get("doc3", {}).get("worth") != ["firmware"] or rows.get("doc3", {}).get("strong"):
            problems.append(f"phase 2: doc3 should be worth (not strong) for firmware, got {rows.get('doc3')}")
        if rows.get("doc7", {}).get("in_vault") != "04_Resources/Known-Post.md":
            problems.append(f"phase 2: doc7 should be marked in vault, got {rows.get('doc7', {}).get('in_vault')}")
        if any(r_.get("questions_version") is None or r_.get("model") != "stub-1" for r_ in rows.values()):
            problems.append("phase 2: rows must carry model and questions_version")
        after = snapshot(sandbox)
        changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
        if not changed or any(not p.startswith("00_Memory/radar/") for p in changed):
            problems.append(f"phase 2: writes outside 00_Memory/radar/: {sorted(changed)}")
        note = (out / f"{NOW.date().isoformat()}.md").read_text(encoding="utf-8") if (out / f"{NOW.date().isoformat()}.md").is_file() else ""
        if "## Agent Memory" not in note or "## Firmware" not in note or "Nothing worth reading for: Birding" not in note:
            problems.append("phase 2: daily note is missing an interest section or the quiet line")

        # 3. rerun
        n = len(calls)
        r = radar.scan(sandbox, out, since, NOW)
        if r.get("status") != "empty" or len(calls) != n:
            problems.append(f"phase 3: expected empty with no request, got {r.get('status')}, {len(calls) - n} calls")

        # 4. split
        out4 = sandbox.parent / "split"
        mode["too_large_above"] = 1
        n = len(calls)
        r = radar.scan(sandbox, out4, since, NOW)
        mode["too_large_above"] = None
        if r.get("judged") != 4:
            problems.append(f"phase 4: expected all 4 judged after splitting, got {r.get('judged')} ({r.get('status')})")
        if not any(len(c["state"]["items"]) == 1 for c in calls[n:]):
            problems.append("phase 4: no single-item request after StateTooLarge")

        # 5. failure
        out5 = sandbox.parent / "fail"
        dlq_before = set((sandbox / "00_Memory" / "dlq").glob("*.md"))
        mode["fail"] = True
        archived.clear()
        r = radar.scan(sandbox, out5, since, NOW)
        mode["fail"] = False
        if [sorted(a) for a in archived] != [["doc9"]]:
            problems.append(f"phase 5: only the back catalogue may be archived when nothing was judged, got {archived}")
        dlq_new = set((sandbox / "00_Memory" / "dlq").glob("*.md")) - dlq_before
        if r.get("status") != "failed" or len(dlq_new) != 1 or any(not x.get("backlog") for x in radar.read_jsonl(out5 / "seen.jsonl")):
            problems.append(f"phase 5: expected failed + one DLQ note + nothing seen, got {r.get('status')}, {len(dlq_new)} DLQ")

        # 7. archive: --limit, --keep-in-feed, a Reader error
        archived.clear()
        r = radar.scan(sandbox, sandbox.parent / "limit", since, NOW, limit=1)
        if [sorted(a) for a in archived] != [["doc1", "doc2", "doc9"]]:
            problems.append(f"phase 7: --limit 1 must archive only doc1, its pdf twin and the backlog, got {archived}")
        archived.clear()
        r = radar.scan(sandbox, sandbox.parent / "keep", since, NOW, archive=False)
        if archived or "archived" in r:
            problems.append("phase 7: --keep-in-feed still archived")
        mode["archive_status"] = 500
        r = radar.scan(sandbox, sandbox.parent / "archive-error", since, NOW)
        mode["archive_status"] = 200
        if r.get("status") != "ok" or "archive_error" not in r:
            problems.append(f"phase 7: a Reader error while archiving must leave the scan ok and say so, got {r.get('status')}")

        # 8. promote
        archived.clear()
        out8 = sandbox.parent / "promote"
        mode["promote_status"] = 500
        r = radar.scan(sandbox, out8, since, NOW, promote=True)
        mode["promote_status"] = 200
        if "promote_error" not in r or any(i in ("doc1", "doc2") for a in archived for i in a):
            problems.append(f"phase 8: a failed promotion must be reported and never archived instead, got {r}, {archived}")
        n = len(calls)
        promoted.clear()
        r = radar.scan(sandbox, out8, since, NOW, promote=True)
        by_id = {u["id"]: u for u in promoted}
        if sorted(by_id) != ["doc1", "doc2"] or len(calls) != n or r.get("promoted") != 2:
            problems.append(f"phase 8: the next scan should promote doc1 and its twin from state, no request; got {sorted(by_id)}, {len(calls) - n} calls")
        u = by_id.get("doc1", {})
        if u.get("tags") != ["radar", "radar/agent-memory", "radar/firmware"] or \
                u.get("notes") != f"[radar {NOW.date().isoformat()}] Agent Memory p=0.90; Firmware p=0.90":
            problems.append(f"phase 8: wrong tags or note on the promoted item: {u}")

        # 6. epics
        os.environ["TOOLKIT_RADAR_TODOIST_PROJECT_ID"] = "p1"
        interests_mod._run_td = lambda args: TD_SECTIONS if args[0] == "section" else TD_TASKS
        epics = [i for i in interests_mod.load(sandbox) if i.todoist_task_id]
        if [(e.todoist_task_id, e.gloss) for e in epics] != [("t1", "A plugin that judges feed items.")]:
            problems.append(f"phase 6: expected only epic t1 with its What: sentence, got {[(e.todoist_task_id, e.gloss) for e in epics]}")
    finally:
        judge._post, reader._request, reader.PAGE_DELAY_S, interests_mod._run_td, policy.ITEMS_PER_REQUEST = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"8 offline phases ok ({len(calls)} stubbed judgment requests)"}
