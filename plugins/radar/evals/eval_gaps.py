"""Eval: `radar.py gaps` and `radar.py kagi`, offline (stubbed Kagi, judgment backend and Reader).

1. no key     — without a Kagi key: SKIPPED, nothing judged, no file
2. gaps       — an interest with neither queries nor a gloss is not searched; results older than
                7 days, already seen by the radar, or held by the vault are
                dropped before judging; the interest query goes to Kagi and never to the judgment
                backend; the strong ones are listed with their sites; the week's file is written once
                (a second run is `exists`, no call)
3. promote    — with --promote the strongest are saved to Reader Later tagged radar/<interest>,
                within one run's promotion budget (an earlier promotion that day does not count),
                and counted in promoted.jsonl (3b: the budget is `promote_per_run` from the profile/env)
4. digest     — the week's digest has a "Found outside your feeds" section
5. kagi       — `kagi answer` returns FastGPT's output and references, recorded in the ledger;
                over the weekly budget nothing is sent (5b: a non-numeric kagi_weekly_budget_usd
                falls back to the default instead of crashing); a truncated ledger line (5c) or a
                bare urlopen timeout (5d, the genuine `kagi._request`) must not crash reading or
                calling Kagi; a truncated gaps-<week>.json (5e) is recomputed, not read as done
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
            "TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD", "TOOLKIT_RADAR_PROMOTE_PER_RUN")
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
    real = (judge._post, reader._request, kagi._request, policy.PROMOTE_PER_RUN)
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

        # 2 + 3. gaps with promotion, a budget of one; the row promoted earlier today does not count
        os.environ["KAGI_API_KEY"] = "stub-kagi-not-a-secret"
        policy.PROMOTE_PER_RUN = 1
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
            problems.append(f"phase 3: one save (the run's one slot), tagged, with a note; got {saves}")

        # 3b. the budget is the profile's promote_per_run (env override), not the constant: 0 saves
        # nothing; 5 saves the one strong row phase 3 could not fit (the other is already promoted)
        strong_rows = [g for g in data.get("rows", []) if g["strong"]]
        names = {i: i for g in strong_rows for i in g["strong"]}
        os.environ["TOOLKIT_RADAR_PROMOTE_PER_RUN"] = "0"
        saves.clear()
        gaps._promote(out, strong_rows, names, NOW, sandbox)
        if saves:
            problems.append(f"phase 3b: promote_per_run=0 must save nothing, got {len(saves)}")
        os.environ["TOOLKIT_RADAR_PROMOTE_PER_RUN"] = "5"
        gaps._promote(out, strong_rows, names, NOW, sandbox)
        if len(saves) != 1:
            problems.append(f"phase 3b: with the budget raised the remaining strong row is saved once, got {len(saves)}")
        os.environ.pop("TOOLKIT_RADAR_PROMOTE_PER_RUN", None)

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

        # 5b. a non-numeric kagi_weekly_budget_usd (profile or env) falls back to the default
        # instead of crashing the kagi skill
        os.environ["TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD"] = "not-a-number"
        r = radar.kagi_cmd(sandbox, out, "search", "anything")
        if r.get("status") != "ok":
            problems.append(f"phase 5b: a non-numeric kagi_weekly_budget_usd must fall back to the default, got {r}")
        os.environ.pop("TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD", None)

        # 5c. a truncated line in the kagi ledger (killed mid-append) must not crash reading it —
        # both Tavily ledgers reuse this class, so this covers them too
        (out / "kagi-ledger.jsonl").write_text(
            json.dumps({"at": NOW.isoformat(), "kind": "search", "query": "x", "usd": 0.025, "balance": 9.9}) + "\n"
            + '{"at": "2026-09-2', encoding="utf-8")  # no closing brace: unparseable
        rows = kagi.ledger(out, 1.0).rows()
        if len(rows) != 1 or rows[0]["query"] != "x":
            problems.append(f"phase 5c: a truncated kagi ledger line must be skipped, not crash reading it, got {rows}")

        # 5d. a bare timeout from the stdlib client becomes kagi.KagiError, not a crash (the
        # genuine `_request`, captured in `real` before it was replaced by `kagi_stub` above)
        import urllib.request as _urllib_request
        real_kagi_request = real[2]
        real_urlopen = _urllib_request.urlopen

        def _timeout_urlopen(*a, **k):
            raise TimeoutError("timed out")
        _urllib_request.urlopen = _timeout_urlopen
        try:
            try:
                real_kagi_request(f"{kagi.BASE}/search?q=x")
                problems.append("phase 5d: a bare TimeoutError from urlopen must not pass through silently")
            except kagi.KagiError:
                pass
            except TimeoutError:
                problems.append("phase 5d: a bare TimeoutError must be converted to kagi.KagiError")
        finally:
            _urllib_request.urlopen = real_urlopen

        # 5e. an unparseable gaps-<week>.json (truncated write) is treated as absent — this week
        # is recomputed rather than left permanently missing its "Found outside your feeds" section
        week = reports.week_of(NOW.date().isoformat())
        (out / f"gaps-{week}.json").write_text('{"week": "2026-W', encoding="utf-8")  # truncated
        n = len(kagi_calls)
        r = gaps.gaps(sandbox, out, NOW)
        if r.get("status") != "ok" or len(kagi_calls) == n:
            problems.append(f"phase 5e: a truncated gaps-{week}.json must be recomputed, not read as done, got {r}")
        if not json.loads((out / f"gaps-{week}.json").read_text(encoding="utf-8")).get("rows"):
            problems.append("phase 5e: the recomputed gaps file must actually be rewritten")
    finally:
        judge._post, reader._request, kagi._request, policy.PROMOTE_PER_RUN = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"5 offline phases ok ({len(kagi_calls)} stubbed Kagi calls)"}
