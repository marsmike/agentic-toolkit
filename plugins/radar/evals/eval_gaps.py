"""Eval: `radar.py gaps` and `radar.py kagi`, offline (stubbed Kagi, judgment backend and Reader).

1. no key     — without a Kagi key: SKIPPED, nothing judged, no file
2. gaps       — an interest with neither queries nor a gloss is not searched; results older than
                7 days, already seen by the radar, or held by the vault are
                dropped before judging; the interest query goes to Kagi and never to the judgment
                backend; the strong ones are listed with their sites; the week's file is written once
                (a second run is `exists`, no call)
3. promote    — with --promote the strongest are saved to Reader Later tagged radar/<interest>,
                within what is left of the day's promotion budget, and counted in promoted.jsonl
                (3b: the budget is `promote_per_day` from the profile/env, shared with scan's)
4. digest     — the week's digest has a "Found outside your feeds" section
5. kagi       — `kagi answer` returns FastGPT's output and references, recorded in the ledger;
                over the weekly budget nothing is sent
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from _sandbox import make_sandbox, teardown_sandbox

NAME = "gaps"
ENV_KEYS = ("TOOLKIT_RADAR_JUDGMENT_API_KEY", "OPENROUTER_API_KEY", "TOOLKIT_RADAR_JUDGMENT_BACKEND",
            "TOOLKIT_RADAR_INTERESTS_NOTE", "TOOLKIT_RADAR_TODOIST_PROJECT_ID", "KAGI_API_KEY",
            "TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD", "TOOLKIT_RADAR_PROMOTE_PER_DAY")
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
INTERESTS_NOTE = """---
description: Fixture interests for the radar gaps eval.
status: active
interests:
  - name: Agent Memory
    gloss: How software agents store and recall what they learned across sessions.
    queries: [SECRET-QUERY-memory]
  - name: A chore with nothing to search by
---

# Radar interests (fixture)
"""
KNOWN_NOTE = "---\ndescription: known\nstatus: distilled\nsource: https://known.example.org/post\n---\n# k\n"


def _hit(path: str, title: str, days_ago: float) -> dict:
    return {"t": 0, "url": f"https://{path}", "title": title, "snippet": f"snippet {title}",
            "published": (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")}


NEWS = [_hit("blog.example.org/strong-one", "Agent memory STRONG one", 1),
        _hit("blog.example.org/strong-two", "Agent memory STRONG two", 2),
        _hit("other.example.org/meh", "Something else", 1),
        _hit("old.example.org/post", "Agent memory STRONG but old", 12),
        _hit("seen.example.org/post", "Agent memory STRONG but seen", 1),
        _hit("known.example.org/post", "Agent memory STRONG but in the vault", 1)]


def run(vault: Path) -> dict:
    import gaps
    import judge
    import kagi
    import radar
    import reader
    import reports
    from judgments import policy

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (judge._post, reader._request, kagi._request, policy.PROMOTE_PER_DAY)
    kagi_calls, judged_state, saves = [], [], []
    sandbox = None

    def kagi_stub(url, body=None):
        if not os.environ.get("KAGI_API_KEY"):
            raise kagi.NoKey("stub")
        kagi_calls.append((url, body))
        if url.endswith("/fastgpt"):
            return {"meta": {"api_balance": 9.0}, "data": {"output": "An answer.", "references": [{"title": "r", "url": "https://r.example.org"}]}}
        return {"meta": {"api_balance": 10.0}, "data": NEWS}

    def judge_stub(url, payload, headers):
        judged_state.append(payload["state"])
        answers = {}
        for qid in payload["questions"]:
            if qid.startswith("kind_"):
                answers[qid] = {"type": "choice", "choice": "other", "probabilities": {"other": 1.0}}
                continue
            _, key, n = qid.split("_")
            about_memory = list(payload["state"]["interests"])[int(n)] == "agent-memory"
            strong = about_memory and "STRONG" in payload["state"]["items"][key]["title"]
            answers[qid] = {"type": "noul", "noul": 0.9 if strong else 0.2}
        return {"model": "stub-1", "usage": {"input_tokens": 100}, "answers": answers}

    def reader_stub(method, url, data=None):
        if method != "POST" or not url.endswith("/save/"):
            problems.append(f"reader: gaps may only save, got {method} {url}")
        saves.append(data)
        return 201, {"id": f"saved{len(saves)}"}, None

    try:
        sandbox = make_sandbox(vault)
        (sandbox / "03_Areas" / "Radar-Interests.md").write_text(INTERESTS_NOTE, encoding="utf-8")
        (sandbox / "04_Resources" / "Known.md").write_text(KNOWN_NOTE, encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "03_Areas/Radar-Interests.md"
        os.environ["TOOLKIT_RADAR_JUDGMENT_API_KEY"] = "stub-key-not-a-secret"
        judge._post, reader._request, kagi._request = judge_stub, reader_stub, kagi_stub
        out = sandbox.parent / "radar"
        out.mkdir()
        (out / "seen.jsonl").write_text(json.dumps({"canonical": "seen.example.org/post"}) + "\n", encoding="utf-8")

        # 1. no key
        r = gaps.gaps(sandbox, out, NOW)
        if r["status"] != "SKIPPED" or judged_state or list(out.glob("gaps-*.json")):
            problems.append(f"phase 1: expected SKIPPED with nothing judged or written, got {r['status']}")

        # 2 + 3. gaps with promotion, one slot left today
        os.environ["KAGI_API_KEY"] = "stub-kagi-not-a-secret"
        policy.PROMOTE_PER_DAY = 2
        (out / "promoted.jsonl").write_text(json.dumps({"canonical": "x", "date": NOW.date().isoformat()}) + "\n", encoding="utf-8")
        r = gaps.gaps(sandbox, out, NOW, promote=True)
        titles = [s["items"][k]["title"] for s in judged_state for k in s["items"]]
        if sorted(titles) != ["Agent memory STRONG one", "Agent memory STRONG two", "Something else"]:
            problems.append(f"phase 2: old, seen and vault-held results must not be judged, judged {sorted(titles)}")
        if "SECRET-QUERY" in json.dumps(judged_state) or "SECRET-QUERY" not in parse_qs(urlparse(kagi_calls[0][0]).query)["q"][0]:
            problems.append("phase 2: the query must go to Kagi and never to the judgment backend")
        if len(kagi_calls) != 1:
            problems.append(f"phase 2: an interest with neither queries nor a gloss must not be searched, got {len(kagi_calls)} searches")
        data = gaps.load_week(out, reports.week_of(NOW.date().isoformat())) or {}
        if [g["title"] for g in data.get("rows", []) if g["strong"]] != ["Agent memory STRONG one", "Agent memory STRONG two"] \
                or data.get("sites") != [["blog.example.org", 2]]:
            problems.append(f"phase 2: expected two strong rows from one site, got {data.get('sites')}")
        n = len(kagi_calls)
        if gaps.gaps(sandbox, out, NOW)["status"] != "exists" or len(kagi_calls) != n:
            problems.append("phase 2: a second run in the same week must be `exists` without a call")
        if r.get("promoted") != 1 or len(saves) != 1 or saves[0]["location"] != "later" \
                or saves[0]["tags"] != ["radar", "radar/agent-memory"] or not saves[0]["notes"].startswith("[radar gap"):
            problems.append(f"phase 3: one save (the budget's last slot), tagged, with a note; got {saves}")

        # 3b. the budget is the profile's promote_per_day (env override), not the constant: 0 saves
        # nothing; 5 saves the one strong row phase 3 could not fit (the other is already promoted)
        strong_rows = [g for g in data.get("rows", []) if g["strong"]]
        names = {i: i for g in strong_rows for i in g["strong"]}
        os.environ["TOOLKIT_RADAR_PROMOTE_PER_DAY"] = "0"
        saves.clear()
        gaps._promote(out, strong_rows, names, NOW, sandbox)
        if saves:
            problems.append(f"phase 3b: promote_per_day=0 must save nothing, got {len(saves)}")
        os.environ["TOOLKIT_RADAR_PROMOTE_PER_DAY"] = "5"
        gaps._promote(out, strong_rows, names, NOW, sandbox)
        if len(saves) != 1:
            problems.append(f"phase 3b: with the budget raised the remaining strong row is saved once, got {len(saves)}")
        os.environ.pop("TOOLKIT_RADAR_PROMOTE_PER_DAY", None)

        # 4. digest
        text = reports.render_weekly(reports.week_of(NOW.date().isoformat()), [], [], NOW, gaps=data)
        if "## Found outside your feeds" not in text or "blog.example.org (2)" not in text:
            problems.append("phase 4: the digest must list what the feeds missed and the sites")

        # 5. kagi
        r = radar.kagi_cmd(sandbox, out, "answer", "what is graphiti")
        if r.get("status") != "ok" or r["result"]["output"] != "An answer." or kagi_calls[-1][1] != {"query": "what is graphiti"}:
            problems.append(f"phase 5: kagi answer should POST the query to FastGPT, got {r}")
        os.environ["TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD"] = "0.001"
        n = len(kagi_calls)
        r = radar.kagi_cmd(sandbox, out, "search", "anything")
        if r.get("status") != "over-budget" or len(kagi_calls) != n:
            problems.append(f"phase 5: over the budget nothing may be sent, got {r.get('status')}")
    finally:
        judge._post, reader._request, kagi._request, policy.PROMOTE_PER_DAY = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"5 offline phases ok ({len(kagi_calls)} stubbed Kagi calls)"}
