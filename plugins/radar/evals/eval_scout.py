"""Eval: `radar.py scout`, offline (stubbed Kagi, judgment backend, Reader and discover.discover).

1. shapes    — a GitHub repo collapses to one key from any URL under it (root, `.git`, a deep
               release/tag link); a well-known content host (x.com, youtube.com, a bare
               github.com path with no repo) is never a candidate; a bare domain is; markdown
               links and bare URLs are both found in a body of text
2. novelty   — `_novel` drops a candidate whose exact source URL the vault already has, whose
               domain a Reader feed already carries, and whose name is already in `Index.md`; a
               genuinely new one survives all three checks
3. no key    — without a judgment backend key: SKIPPED, nothing searched or judged, no capture
4. scout     — end to end: candidates from state.jsonl's worth items (a repo mentioned from two
               feeds, an item outside the four-week window dropped), the owner's clips (the
               source and a link inside the body; a clip outside the window dropped), and one
               Kagi query per interest with queries or a gloss (an interest with neither is not
               searched); the known/subscribed/indexed candidates from phase 2's fixtures do not
               reach the capture; a low-value candidate is judged but not proposed; a feed-kind
               pick is handed to `discover.discover` as a seed and nothing else is; `--dry-run`
               changes nothing in the vault; a second run without `--force` is `exists` and calls
               neither the judge nor discover again; `--force` runs it all again
5. budget    — over the Kagi budget: no interest is searched, it is recorded in `notes`, and the
               run still succeeds on feed and clip candidates alone (a soft degrade, not SKIPPED)
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "scout"
ENV_KEYS = ("TOOLKIT_RADAR_JUDGMENT_API_KEY", "OPENROUTER_API_KEY", "TOOLKIT_RADAR_JUDGMENT_BACKEND",
            "TOOLKIT_RADAR_INTERESTS_NOTE", "TOOLKIT_RADAR_TODOIST_PROJECT_ID", "KAGI_API_KEY",
            "TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD")
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)  # ISO week 39: LAUNCH_ANGLES[39 % 4] == "new dataset"
SINCE = (NOW - timedelta(days=28)).date().isoformat()

INTERESTS_NOTE = """---
description: Fixture interests for the radar scout eval.
status: active
interests:
  - name: Agent Memory
    gloss: How software agents store and recall what they learned across sessions.
    queries: [SECRET-QUERY-memory]
  - name: A chore with nothing to search by
---

# Radar interests (fixture)
"""
KNOWN_NOTE = "---\ndescription: known\nstatus: distilled\nsource: https://known.example.org/repo\n---\n# k\n"
CLIP_IN_WINDOW = """---
via: clip
saved_at: '2026-09-19'
source: https://coolblog.example.org/post
---
# Clip About Cool Repo

See [this repo](https://github.com/clipfound/coolrepo) for details, or just visit
https://coolblog.example.org/post directly.
"""
CLIP_OUT_OF_WINDOW = """---
via: clip
saved_at: '2026-07-01'
source: https://tooold.example.org/post
---
# An old clip

Nothing here should count: https://tooold.example.org/post is outside the four-week window.
"""


def _rows() -> list[dict]:
    def row(url: str, title: str, feed: str, saved_at: str, worth: bool = True) -> dict:
        return {"run": saved_at, "saved_at": saved_at, "url": url, "title": title, "feed": feed,
                "backend": "jev", "p": {"agent-memory": 0.9 if worth else 0.1}}

    return [
        row("https://github.com/newco/newtool", "NewTool ships fast", "FeedA", "2026-09-20"),
        row("https://github.com/newco/newtool/blob/main/README.md", "NewTool v1 release", "FeedB", "2026-09-21"),
        row("https://known.example.org/repo", "Known thing again", "FeedA", "2026-09-20"),
        row("https://x.com/someone/status/1", "tweet about stuff", "FeedA", "2026-09-20"),
        row("https://subscribed.example.org/post", "Subscribed blog post", "FeedA", "2026-09-20"),
        row("https://github.com/someorg/handytool", "HandyTool released", "FeedA", "2026-09-20"),
        row("https://github.com/oldco/zzzscoutfixtureold", "Zzzscoutfixtureold old thing", "FeedA", "2026-07-01"),  # outside window
        row("https://feedsite.example.org/about", "FEEDSITE blog launches", "FeedA", "2026-09-20"),
        row("https://github.com/ignored/notworth", "Not worth reading", "FeedA", "2026-09-20", worth=False),
    ]


NEWS = [{"t": 0, "url": "https://newsvc.example.org/announcement", "title": "NEWSVC dataset launch",
        "snippet": "a new dataset", "published": NOW.isoformat()}]
READER_DOCS = [{"id": "r1", "title": "t", "category": "rss", "location": "archive", "parent_id": None,
               "site_name": "Subscribed Blog", "source_url": "https://subscribed.example.org/feed",
               "saved_at": (NOW - timedelta(days=3)).isoformat()}]


def _value(url: str) -> float:
    return 0.4 if "coolblog" in url else 0.85


def _kind(url: str) -> str:
    if "feedsite" in url or "coolblog" in url:
        return "feed"
    if "newsvc" in url:
        return "dataset"
    return "tool"


def run(vault: Path) -> dict:
    import discover
    import judge
    import kagi
    import reader
    import scout

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (judge._post, reader._request, kagi._request, discover.discover)
    judge_calls: list[dict] = []
    kagi_calls: list[tuple] = []
    discover_calls: list[dict] = []
    sandbox = None

    # 1. shapes
    root, deep, dotgit = ("https://github.com/acme/proj", "https://github.com/acme/proj/releases/tag/v1",
                          "https://github.com/acme/proj.git")
    if len({scout.candidate_key(root), scout.candidate_key(deep), scout.candidate_key(dotgit)}) != 1:
        problems.append("phase 1: every URL under one repo must collapse to the same candidate key")
    if scout.candidate_key("https://x.com/user/status/1") is not None:
        problems.append("phase 1: a content host (x.com) must never be a candidate")
    if scout.candidate_key("https://www.youtube.com/watch?v=abc123") is not None:
        problems.append("phase 1: a content host (youtube.com) must never be a candidate")
    if scout.candidate_key("https://github.com/topics/ai") is not None:
        problems.append("phase 1: a non-repo GitHub path must not be treated as a repo")
    if scout.candidate_key("https://newtool.example.org/page") != "newtool.example.org":
        problems.append("phase 1: a bare domain should be its own candidate key")
    if scout.candidate_key("http://localhost:3000/dashboard") is not None:
        problems.append("phase 1: a local dev address must never be a candidate")
    if scout.candidate_key("https://192.168.1.5/setup") is not None:
        problems.append("phase 1: a bare IP address must never be a candidate")
    if scout.candidate_key("https://discord.gg/abc123") != "discord.gg/abc123":
        problems.append(f"phase 1: a Discord invite should key on its code, got {scout.candidate_key('https://discord.gg/abc123')}")
    if scout.candidate_key("https://discord.gg/") is not None:
        problems.append("phase 1: a bare invite shortener with no code names nothing on its own")
    links = scout._links_in("See [this](https://x.example.org/1) and also https://y.example.org/2 for more.")
    if links != {"https://x.example.org/1", "https://y.example.org/2"}:
        problems.append(f"phase 1: markdown and bare links should both be found, got {links}")

    # 2. novelty
    cands = {k: scout.Candidate(key=k, urls={f"https://{k}"}) for k in
             ("known.example.org", "subscribed.example.org", "github.com/co/handytool", "novel.example.org")}
    cands["known.example.org"].urls = {"https://known.example.org/repo"}
    known_urls = {"known.example.org/repo": "some/note.md"}
    survivors = scout._novel(cands, known_urls, "we already know about handytool, it's great",
                             {"subscribed.example.org"})
    if set(survivors) != {"novel.example.org"}:
        problems.append(f"phase 2: expected only the untouched candidate to survive, got {sorted(survivors)}")
    if "novel.example.org" in scout._novel(cands, known_urls, "", set(), visited={"novel.example.org"}):
        problems.append("phase 2: a site the owner clipped from himself is not new to him")
    homes = scout.feed_homes([{"feed": "SDK releases", "url": f"https://github.com/acme/sdk/releases/tag/v{i}"} for i in range(3)]
                             + [{"feed": "HN", "url": "https://github.com/acme/sdk"}, {"feed": "HN", "url": "https://other.example.org/x"}])
    homes |= scout.feed_homes([{"feed": "Mixed releases", "url": "https://github.com/acme/cli/releases/tag/v1"},
                               {"feed": "Mixed releases", "url": "https://github.com/other/lib/releases/tag/v2"}])
    if homes != {"github.com/acme/sdk", "github.com/acme/cli", "github.com/other/lib"}:
        problems.append(f"phase 2: a feed whose items all live on one site is a subscription; an aggregator is not, got {homes}")
    # half the judged slots go to what only the web search found, even against many-mention mined ones
    from judgments import policy as scout_policy
    mined = [scout.Candidate(key=f"mined{i}.example.org", clip_hits=3) for i in range(30)]
    web = [scout.Candidate(key=f"web{i}.example.org", kagi_hits=1) for i in range(30)]
    picked = scout.rank_for_judging(mined + web)
    n_web = sum(1 for c in picked if c.key.startswith("web"))
    want = int(scout_policy.SCOUT_MAX_JUDGED * scout_policy.SCOUT_EXTERNAL_SHARE)
    if len(picked) != scout_policy.SCOUT_MAX_JUDGED or n_web != want:
        problems.append(f"phase 2: {want} of {scout_policy.SCOUT_MAX_JUDGED} judged slots go to web-only finds, got {n_web} of {len(picked)}")
    if len(scout.rank_for_judging(mined[:5] + web)) != scout_policy.SCOUT_MAX_JUDGED:
        problems.append("phase 2: slots the mined candidates cannot fill go to web finds")

    # 3. no key (judgment backend unavailable — Kagi may still have a key, it must not matter)
    try:
        sandbox = make_sandbox(vault)
        (sandbox / "03_Areas" / "Radar-Interests.md").write_text(INTERESTS_NOTE, encoding="utf-8")
        (sandbox / "04_Resources" / "Known.md").write_text(KNOWN_NOTE, encoding="utf-8")
        index_path = sandbox / "Index.md"
        index_path.write_text(index_path.read_text(encoding="utf-8") + "\n\nHandyTool is a nice utility.\n",
                              encoding="utf-8")
        (sandbox / "01_Capture" / "Radar-Scout-clip-in.md").write_text(CLIP_IN_WINDOW, encoding="utf-8")
        (sandbox / "01_Capture" / "Radar-Scout-clip-old.md").write_text(CLIP_OUT_OF_WINDOW, encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "03_Areas/Radar-Interests.md"
        out = sandbox.parent / "scout-out"
        out.mkdir()
        (out / "state.jsonl").write_text("\n".join(json.dumps(r) for r in _rows()) + "\n", encoding="utf-8")

        r = scout.scout(sandbox, out, NOW)
        if r["status"] != "SKIPPED" or judge_calls or kagi_calls or list((sandbox / "01_Capture").glob("Radar-Scout-2026-W*.md")):
            problems.append(f"phase 3: no judgment key should SKIP with nothing sent or written, got {r}")

        # 4. scout, end to end
        os.environ["TOOLKIT_RADAR_JUDGMENT_API_KEY"] = "stub-key-not-a-secret"
        os.environ["KAGI_API_KEY"] = "stub-kagi-not-a-secret"

        def judge_stub(url, payload, headers):
            judge_calls.append(payload)
            answers = {}
            state = payload["state"]
            for qid in payload["questions"]:
                prefix, key = qid.split("_", 1)
                curl = state["candidates"][key]["url"]
                if prefix == "kind":
                    kind = _kind(curl)
                    answers[qid] = {"type": "choice", "choice": kind, "probabilities": {kind: 1.0}}
                elif prefix == "value":
                    answers[qid] = {"type": "noul", "noul": _value(curl)}
                elif prefix == "action":
                    answers[qid] = {"type": "noul", "noul": 0.7}
            return {"model": "stub-1", "usage": {"input_tokens": 100}, "answers": answers}

        def kagi_stub(url, body=None):
            if not os.environ.get("KAGI_API_KEY"):
                raise kagi.NoKey("stub")
            kagi_calls.append((url, body))
            if "dataset" not in url:
                problems.append(f"phase 4: expected the 'new dataset' launch angle for week 39, got {url}")
            return {"meta": {"api_balance": 10.0 - 0.002 * len(kagi_calls)}, "data": NEWS}

        def reader_stub(method, url, data=None):
            if method != "GET":
                problems.append(f"reader: scout may only read Reader, got {method} {url}")
            docs = READER_DOCS if "location=archive" in url else []
            return 200, {"results": docs, "nextPageCursor": None}, None

        def discover_stub(vault_, out_, now_, only, seeds, queries_per_interest=0):
            discover_calls.append({"seeds": list(seeds or []), "queries_per_interest": queries_per_interest})
            return {"status": "ok", "proposed": len(seeds or []), "opml": str(out_ / "fake.opml")}

        judge._post, reader._request, kagi._request, discover.discover = judge_stub, reader_stub, kagi_stub, discover_stub

        # dry-run first: nothing in the vault may change
        before = snapshot(sandbox)
        r = scout.scout(sandbox, out, NOW, dry_run=True)
        if r["status"] != "ok" or "dry_run_capture" not in r or snapshot(sandbox) != before:
            problems.append(f"phase 4: --dry-run must change nothing in the vault, got status={r.get('status')}")
        if list((sandbox / "01_Capture").glob("Radar-Scout-2026-W39.md")):
            problems.append("phase 4: --dry-run must not write the capture")

        n_judge, n_discover = len(judge_calls), len(discover_calls)
        r = scout.scout(sandbox, out, NOW)
        if r["status"] != "ok":
            problems.append(f"phase 4: expected ok, got {r}")
        dropped = {"known.example.org", "x.com", "subscribed.example.org", "github.com/someorg/handytool",
                  "github.com/oldco/zzzscoutfixtureold", "github.com/ignored/notworth"}
        capture_path = sandbox / "01_Capture" / "Radar-Scout-2026-W39.md"
        text = capture_path.read_text(encoding="utf-8") if capture_path.is_file() else ""
        if not text:
            problems.append("phase 4: the scout capture was not written")
        if any(d in text for d in dropped):
            problems.append(f"phase 4: a known/subscribed/indexed/old/not-worth candidate reached the capture: {text}")
        for want in ("github.com/newco/newtool", "github.com/clipfound/coolrepo", "newsvc.example.org",
                    "feedsite.example.org"):
            if want not in text:
                problems.append(f"phase 4: expected {want} in the capture, got:\n{text}")
        if "coolblog.example.org" in text:
            problems.append("phase 4: a candidate below the value threshold must not be proposed")
        fm_end = text.find("---", 3)
        frontmatter = text[3:fm_end]
        if "via: radar" not in frontmatter or "kind: radar-scout" not in frontmatter:
            problems.append(f"phase 4: frontmatter should be via: radar, kind: radar-scout, got {frontmatter}")
        if len(discover_calls) != n_discover + 1 or discover_calls[-1]["seeds"] != ["https://feedsite.example.org"]:
            problems.append(f"phase 4: exactly the feed-kind pick should seed discover, got {discover_calls[n_discover:]}")
        if len(judge_calls) <= n_judge:
            problems.append("phase 4: the real run must have judged candidates")

        # a second run without --force must not judge or discover again
        n_judge, n_discover = len(judge_calls), len(discover_calls)
        r = scout.scout(sandbox, out, NOW)
        if r["status"] != "exists" or len(judge_calls) != n_judge or len(discover_calls) != n_discover:
            problems.append(f"phase 4: a second run without --force must be `exists` and call nothing again, got {r}")

        # --force runs it all again
        r = scout.scout(sandbox, out, NOW, force=True)
        if r["status"] != "ok" or len(judge_calls) <= n_judge:
            problems.append("phase 4: --force must rewrite the capture and judge again")

        # 5. budget
        out2 = sandbox.parent / "scout-out2"
        out2.mkdir()
        (out2 / "state.jsonl").write_text((out / "state.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        kagi.Ledger(out2 / "kagi-ledger.jsonl", 1.0).record(
            {"at": NOW.isoformat(), "kind": "news", "query": "earlier", "usd": 0.999, "balance": 9.0})
        os.environ["TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD"] = "1.0"
        n = len(kagi_calls)
        r = scout.scout(sandbox, out2, NOW + timedelta(days=7), week="2026-W40")
        if not any("budget" in note for note in r.get("notes", [])) or len(kagi_calls) != n:
            problems.append(f"phase 5: over budget must search nothing new and say so, got {r.get('notes')}")
        if r["status"] != "ok":
            problems.append(f"phase 5: over budget must still succeed on feed/clip candidates alone, got {r}")
    finally:
        judge._post, reader._request, kagi._request, discover.discover = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"5 offline phases ok ({len(judge_calls)} stubbed judgment requests, {len(kagi_calls)} stubbed Kagi calls)"}
