"""Eval: `sensors.collect`, offline (stubbed `sensors._request`, no network).

 0. enabled     — profile `sensors` (comma list) intersected with `only`, in ALL_SOURCES order
 1. hn          — dedupe across front_page + search_by_date, url falls back to the HN item page,
                  "Show HN" origin, score = points, key `hn:<objectID>`; day file has
                  {day, updated, status, items}; disabled sources report "skipped"
 2. hf          — models + spaces merged, trendingScore falling back to likes, entities =
                  [hf_family(id)] (imported from entities.py, not redefined here)
 3. github      — new-repo + topic queries merged, entities = [repo name]; a token GitHub refuses
                 falls back to anonymous once and keeps GitHub's reason; the cloud proxy's refusal
                 switches to GitHub Trending (ranked, plain-text summaries); a 403/429 stops
                  further queries this run, status "partial"
 4. reddit ok   — stickied posts skipped, score = ups, origin f"r/{sub}"
 5. reddit blk  — blocked on both hosts for one sub -> status "blocked", no further subs tried
                  (Tavily unavailable); with Tavily (stubbed `tavily._run`) the subreddits come through
                  `tvly` as "partial", without scores, its own ledger (tavily-ledger-signal.jsonl,
                  never tavily-ledger.jsonl — sensors run only from the Signal Radar routine), and
                  not again within 12 h; a subreddit empty for several runs running is named in the
                  detail (5d), read back from the ledger's own per-call `results` count
 6. rss+atom    — RSS 2.0 and Atom both parsed, items published outside the 7-day window dropped,
                  a non-feed response is a per-feed failure (status "partial") that doesn't stop
                  the others
 7. merge       — a key seen again the same day: score becomes the max, first_seen is kept,
                  last_seen moves, a [HH:MM, score] pair is appended
 8. carry       — a key already judged in an older (but retained) day file carries its p/kind
                  forward instead of being handed to judge_fn
 9. cap         — only unjudged rows go to judge_fn, highest score first, capped (9b: judge_fn
                  raising must not lose that day's already-fetched items — they are still written)
10. prune       — day files older than 45 days are removed, the boundary file is kept
11. contained   — nothing is ever written outside out/sensors/, and the vault itself is untouched
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "sensors"
NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)
NOW2 = NOW + timedelta(hours=3)


def _json(body: dict | list) -> bytes:
    return json.dumps(body).encode("utf-8")


def hn_hit(oid: str, title: str, points: float, url: str | None = "https://example.org/a", comments: int = 5) -> dict:
    return {"objectID": oid, "title": title, "url": url, "points": points, "num_comments": comments,
            "created_at": "2026-09-26T09:00:00Z"}


RSS_GOOD = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Synth Feed</title>
<item><title>New plugin released</title><link>https://synthsite.example.org/new-plugin</link>
<pubDate>Thu, 24 Sep 2026 10:00:00 +0000</pubDate><description>A shiny new plugin</description></item>
<item><title>Ancient post</title><link>https://synthsite.example.org/ancient</link>
<pubDate>Mon, 01 Jun 2026 10:00:00 +0000</pubDate><description>old</description></item>
</channel></rss>"""

GNEWS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Google News</title>
<item><title>Maschine 3.7 adds a new sequencer - Gearnews.com</title><link>https://news.google.com/rss/articles/abc</link>
<pubDate>Thu, 24 Sep 2026 10:00:00 +0000</pubDate><description>x</description></item>
</channel></rss>"""

ATOM_GOOD = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Feed</title>
<entry><title>Atom entry</title><link href="https://atomsite.example.org/item1" rel="alternate"/>
<updated>2026-09-25T10:00:00Z</updated><summary>an atom summary</summary></entry>
</feed>"""

RSS_BAD = b"not a feed at all"

TRENDING_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>GitHub Daily Trending</title>
<item><title>acme/first-place</title><link>https://github.com/acme/first-place</link>
<description>&lt;p&gt;The top repo &amp;amp; more&lt;/p&gt;&lt;p&gt;&lt;img src="x.png"&gt;README&lt;/p&gt;</description></item>
<item><title>acme/second-place</title><link>https://github.com/acme/second-place</link>
<description>&lt;p&gt;The runner-up&lt;/p&gt;</description></item>
</channel></rss>"""


def run(vault: Path) -> dict:
    import sensors

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in (
        "TOOLKIT_RADAR_SENSORS", "TOOLKIT_RADAR_SENSOR_FEEDS", "TOOLKIT_RADAR_SENSOR_GITHUB_TOPICS",
        "TOOLKIT_RADAR_SENSOR_SUBREDDITS", "TOOLKIT_RADAR_SENSOR_KAGI_NEWS", "GITHUB_TOKEN", "GH_TOKEN")}
    import tavily
    real_request, real_max_judge, real_tavily = sensors._request, sensors.MAX_JUDGE_PER_RUN, tavily._run
    tavily_calls: list[list[str]] = []
    tavily_state = {"available": False}

    def tavily_stub(args):
        if not tavily_state["available"]:
            raise tavily.NoKey("TAVILY_API_KEY is not set")
        tavily_calls.append(args)
        sub = args[1].removeprefix("r/")
        if sub in tavily_state.get("empty", ()):
            return {"results": []}
        return {"results": [
            {"url": f"https://www.reddit.com/r/{sub}/comments/tv{len(tavily_calls)}/a_thread/", "title": f"A thread : r/{sub}"},
            {"url": "https://www.reddit.com/r/SomewhereElse/comments/zz9/off_topic/", "title": "Elsewhere"},
            {"url": f"https://evilreddit.com/r/{sub}/comments/ev1/lookalike/", "title": "Lookalike host"},
            {"url": "https://example.com/not-reddit", "title": "Not reddit"}]}
    tavily._run = tavily_stub
    state: dict = {"calls": [], "github_calls": 0, "github_block_topic": False, "reddit_block": False,
                   "reddit": {}, "hn_front": {"hits": []}, "hn_bydate": {"hits": []},
                   "hf_models": [], "hf_spaces": [], "github_new": {"items": []}, "github_topic": {"items": []},
                   "feeds": {}}
    sandbox = None

    def stub(url: str, headers: dict | None = None) -> tuple[int, dict, bytes]:
        state["calls"].append(url)
        if "hn.algolia.com" in url:
            return 200, {}, _json(state["hn_front"] if "front_page" in url else state["hn_bydate"])
        if "huggingface.co/api/models" in url:
            return 200, {}, _json(state["hf_models"])
        if "huggingface.co/api/spaces" in url:
            return 200, {}, _json(state["hf_spaces"])
        if "api.github.com/search/repositories" in url:
            state["github_calls"] += 1
            if state.get("github_proxy"):
                return 403, {}, b'{"message": "This GitHub API path is not available: sessions are bound to their configured repositories"}'
            if state.get("github_refuse_token") and "Authorization" in (headers or {}):
                return 403, {}, b'{"message": "Resource not accessible by integration"}'
            if "topic:" in url:
                if state["github_block_topic"]:
                    return 403, {}, b'{"message": "rate limited"}'
                return 200, {}, _json(state["github_topic"])
            return 200, {}, _json(state["github_new"])
        if url == "https://news.kagi.com/kite.json":
            return 200, {}, _json({"categories": [{"name": "AI", "file": "ai.json"}, {"name": "Technology", "file": "tech.json"}]})
        if url.startswith("https://news.kagi.com/"):
            story = {"title": "Jev 2 ships", "unique_domains": 12, "short_summary": "A decision model.",
                     "articles": [{"title": "Jev 2", "link": "https://example.org/jev-2", "date": "2026-09-25T06:00:00+00:00"}]}
            other = {"title": "A small AI story", "unique_domains": "3", "short_summary": "",
                     "articles": [{"title": "s", "link": "https://example.org/small", "date": "2026-09-26T06:00:00+00:00"}]}
            return 200, {}, _json({"clusters": [story, other] if url.endswith("ai.json") else [story]})
        if "GitHubTrendingRSS" in url:
            return 200, {"content-type": "application/xml"}, TRENDING_RSS
        if "reddit.com/r/" in url:
            if state["reddit_block"]:
                return 403, {"content-type": "text/html"}, b"blocked"
            sub = url.split("/r/", 1)[1].split("/", 1)[0]
            return 200, {"content-type": "application/json"}, _json(state["reddit"].get(sub, {"data": {"children": []}}))
        for feed_url, (code, ctype, body) in state["feeds"].items():
            if url == feed_url:
                return code, {"content-type": ctype}, body
        return 404, {}, b""

    try:
        sandbox = make_sandbox(vault)
        sensors._request = stub

        # 0. enabled sources
        default = sensors._enabled_sources(sandbox, None)
        if default != list(sensors.ALL_SOURCES):
            problems.append(f"phase 0: default must be every source in order, got {default}")
        os.environ["TOOLKIT_RADAR_SENSORS"] = "hn, github"
        if sensors._enabled_sources(sandbox, None) != ["hn", "github"]:
            problems.append("phase 0: profile `sensors` must restrict and preserve ALL_SOURCES order")
        if sensors._enabled_sources(sandbox, ["github"]) != ["github"]:
            problems.append("phase 0: `only` must further intersect the profile's list")
        os.environ.pop("TOOLKIT_RADAR_SENSORS")

        # 1. hn: dedupe, url fallback, Show HN, day-file shape, skipped sources
        state["hn_front"] = {"hits": [hn_hit("1001", "Cool new agent framework", 500, "https://example.org/agent-fw"),
                                       hn_hit("1002", "Show HN: my synth plugin", 80, url=None)]}
        state["hn_bydate"] = {"hits": [hn_hit("1003", "Ask HN: best local setup", 45, url=None),
                                        hn_hit("1001", "Cool new agent framework", 500, "https://example.org/agent-fw")]}
        out1 = sandbox.parent / "radar-hn"
        r = sensors.collect(sandbox, out1, NOW, only=["hn"])
        items = json.loads(Path(r["file"]).read_text())["items"]
        if sorted(items) != ["hn:1001", "hn:1002", "hn:1003"]:
            problems.append(f"phase 1: expected 3 deduped HN keys, got {sorted(items)}")
        elif (items["hn:1001"]["url"] != "https://example.org/agent-fw" or items["hn:1001"]["score"] != 500.0
              or items["hn:1002"]["url"] != "https://news.ycombinator.com/item?id=1002"
              or items["hn:1002"]["origin"] != "Show HN" or items["hn:1003"]["origin"] != "Hacker News"):
            problems.append(f"phase 1: url fallback / Show HN / score wrong: {items}")
        data = json.loads(Path(r["file"]).read_text())
        if set(data) != {"day", "updated", "status", "items"} or data["day"] != "2026-09-26":
            problems.append(f"phase 1: day file must be {{day, updated, status, items}}, got {sorted(data)}")
        elif data["status"]["hn"]["status"] != "ok" or data["status"]["hf"]["status"] != "skipped":
            problems.append(f"phase 1: hn ok, others skipped when only=['hn'], got {data['status']}")

        # 2. hf: trendingScore fallback to likes, entities via hf_family
        state["hf_models"] = [
            {"id": "unsloth/Qwen3.8-27B-Instruct-GGUF", "trendingScore": 900, "likes": 50,
             "pipeline_tag": "text-generation", "library_name": "transformers", "downloads": 1200,
             "createdAt": "2026-09-20T00:00:00.000Z"},
            {"id": "acme/Mica-v0.1-4B", "likes": 30, "createdAt": "2026-09-21T00:00:00.000Z"},
        ]
        state["hf_spaces"] = [{"id": "someone/cool-space", "trendingScore": 200, "likes": 20,
                               "createdAt": "2026-09-22T00:00:00.000Z"}]
        out2 = sandbox.parent / "radar-hf"
        r = sensors.collect(sandbox, out2, NOW, only=["hf"])
        items = json.loads(Path(r["file"]).read_text())["items"]
        m1, m2, sp = (items.get("hf:unsloth/Qwen3.8-27B-Instruct-GGUF"), items.get("hf:acme/Mica-v0.1-4B"),
                     items.get("hf:someone/cool-space"))
        if not m1 or not m2 or not sp:
            problems.append(f"phase 2: expected 3 HF keys, got {sorted(items)}")
        elif (m1["entities"] != ["Qwen3.8"] or m2["entities"] != ["Mica-v0.1"] or m2["score"] != 30.0
              or sp["origin"] != "HF Spaces" or m1["url"] != "https://huggingface.co/unsloth/Qwen3.8-27B-Instruct-GGUF"):
            problems.append(f"phase 2: hf_family / fallback score / url wrong: {m1}, {m2}, {sp}")
        if sensors.hf_family("unsloth/Qwen3.8-27B-Instruct-GGUF") != "Qwen3.8" or sensors.hf_family("x/Mica-v0.1-4B") != "Mica-v0.1":
            problems.append("phase 2: hf_family must be entities.py's (imported, not redefined)")

        # 3. github: entities = [repo name], 403 on a topic query stops further queries, partial
        state["github_new"] = {"items": [{"full_name": "acme/agent-tool", "html_url": "https://github.com/acme/agent-tool",
                                          "description": "An agent tool", "language": "Python",
                                          "stargazers_count": 300, "created_at": "2026-09-20T00:00:00Z"}]}
        state["github_block_topic"] = True
        out3 = sandbox.parent / "radar-github"
        state["github_calls"] = 0
        r = sensors.collect(sandbox, out3, NOW, only=["github"])
        items = json.loads(Path(r["file"]).read_text())["items"]
        if r["sources"]["github"]["status"] != "partial" or state["github_calls"] != 2:
            problems.append(f"phase 3: a 403 on a topic query must stop github at 2 calls with status partial, "
                            f"got {state['github_calls']} calls, status {r['sources']['github']['status']}")
        if items.get("github:acme/agent-tool", {}).get("entities") != ["agent-tool"]:
            problems.append(f"phase 3: entities must be [repo name], got {items.get('github:acme/agent-tool')}")
        state["github_block_topic"] = False

        # 3b. a token GitHub refuses (a git-only credential): one anonymous retry, reason kept
        os.environ["GH_TOKEN"] = "stub-git-only-not-a-secret"
        state["github_refuse_token"], state["github_calls"] = True, 0
        r = sensors.collect(sandbox, sandbox.parent / "radar-github-token", NOW, only=["github"])
        gh = r["sources"]["github"]
        if gh["status"] != "partial" or "token refused" not in gh["detail"] or "not accessible" not in gh["detail"] \
                or not gh["items"]:
            problems.append(f"phase 3b: a refused token must fall back to anonymous and say why, got {gh}")
        state["github_refuse_token"] = False
        os.environ.pop("GH_TOKEN", None)

        # 3c. the cloud proxy refuses api.github.com: no anonymous retry, GitHub Trending instead
        state["github_proxy"], state["github_calls"] = True, 0
        r = sensors.collect(sandbox, sandbox.parent / "radar-github-proxy", NOW, only=["github"])
        gh = r["sources"]["github"]
        rows3c = json.loads(Path(r["file"]).read_text())["items"]
        first, second = rows3c.get("github:acme/first-place", {}), rows3c.get("github:acme/second-place", {})
        if state["github_calls"] != 1 or gh["status"] != "partial" or "session proxy" not in gh["detail"] \
                or first.get("origin") != "GitHub Trending" or not (first.get("score") or 0) > (second.get("score") or 0) \
                or first.get("summary") != "The top repo & more" or first.get("entities") != ["first-place"]:
            problems.append(f"phase 3c: a proxy refusal must switch to GitHub Trending once, ranked, plain text; "
                            f"got {state['github_calls']} API calls, {gh}, {first}")
        state["github_proxy"] = False

        # 3d. kagi news: one row per story across categories, score = domains; a category absent from
        #     today's index is a quiet day (named, status still ok)
        os.environ["TOOLKIT_RADAR_SENSOR_KAGI_NEWS"] = "AI, Technology, Knitting"
        r = sensors.collect(sandbox, sandbox.parent / "radar-kagi-news", NOW, only=["kagi_news"])
        kn = r["sources"]["kagi_news"]
        rows3d = json.loads(Path(r["file"]).read_text())["items"]
        jev = [v for v in rows3d.values() if v["title"] == "Jev 2 ships"]
        if kn["status"] != "ok" or "no stories today: Knitting" not in kn["detail"] or len(rows3d) != 2 or len(jev) != 1 \
                or jev[0]["score"] != 12.0 or jev[0]["origin"] != "Kagi News · AI" or jev[0]["published"] != "2026-09-25":
            problems.append(f"phase 3d: kagi news rows wrong: {kn}, {rows3d}")
        os.environ.pop("TOOLKIT_RADAR_SENSOR_KAGI_NEWS")

        # 4. reddit ok: stickied skipped, score = ups
        state["reddit"] = {"LocalLLaMA": {"data": {"children": [
            {"data": {"id": "r1", "title": "A local model release", "ups": 210, "num_comments": 40,
                      "permalink": "/r/LocalLLaMA/r1", "created_utc": 1790000000}},
            {"data": {"id": "r2", "title": "pinned rules", "ups": 1, "stickied": True, "permalink": "/r/LocalLLaMA/r2"}},
        ]}}}
        out4 = sandbox.parent / "radar-reddit-ok"
        r = sensors.collect(sandbox, out4, NOW, only=["reddit"])
        items = json.loads(Path(r["file"]).read_text())["items"]
        if sorted(items) != ["reddit:r1"] or items["reddit:r1"]["score"] != 210.0 or items["reddit:r1"]["origin"] != "r/LocalLLaMA":
            problems.append(f"phase 4: expected only r1 (stickied r2 skipped) with score=ups, got {items}")

        # 5. reddit blocked: 403 on both hosts for the first sub stops the rest
        state["reddit_block"] = True
        out5 = sandbox.parent / "radar-reddit-blocked"
        before = len(state["calls"])
        r = sensors.collect(sandbox, out5, NOW, only=["reddit"])
        reddit_calls = len(state["calls"]) - before
        if r["sources"]["reddit"]["status"] != "blocked" or reddit_calls != 2:
            problems.append(f"phase 5: blocked on both hosts must stop after 2 calls (www + old) for one sub, "
                            f"got {reddit_calls} calls, status {r['sources']['reddit']['status']}")
        if "Tavily skipped" not in r["sources"]["reddit"]["detail"]:
            problems.append(f"phase 5: without Tavily the detail must say it was skipped, got {r['sources']['reddit']['detail']!r}")

        # 5b. blocked, Tavily available: every subreddit through tvly, their own threads only, no scores
        tavily_state["available"] = True
        subs = sensors._profile_list(sandbox, "sensor_subreddits", sensors.DEFAULT_SUBREDDITS)
        out5b = sandbox.parent / "radar-reddit-tavily"
        r = sensors.collect(sandbox, out5b, NOW, only=["reddit"])
        src = r["sources"]["reddit"]
        day = json.loads((out5b / "sensors" / f"{NOW.date().isoformat()}.json").read_text(encoding="utf-8"))["items"]
        reddit_items = {k: v for k, v in day.items() if k.startswith("reddit:")}
        if src["status"] != "partial" or len(tavily_calls) != len(subs) or len(reddit_items) != len(subs):
            problems.append(f"phase 5b: expected partial with one tvly call and one thread per subreddit "
                            f"({len(subs)}), got {src['status']}, {len(tavily_calls)} calls, {len(reddit_items)} items")
        if any(v["score"] is not None or not v["origin"].startswith("r/") or v["title"].endswith(v["origin"])
               for v in reddit_items.values()):
            problems.append(f"phase 5b: Tavily threads carry no score, origin r/<sub> and a clean title, got {reddit_items}")
        if tavily_calls and not {"--include-domains", "reddit.com", "--time-range", "day", "--depth", "basic"} <= set(tavily_calls[0]):
            problems.append(f"phase 5b: the fallback is a basic reddit.com search over the day, got {tavily_calls[0]}")
        # Sensors run only from the Signal Radar routine, so its Tavily calls belong in the signal
        # ledger, never the pipeline's own. [earned: 2026-09-28 week review]
        if not (out5b / "tavily-ledger-signal.jsonl").is_file() or (out5b / "tavily-ledger.jsonl").is_file():
            problems.append("phase 5b: the sensors must write tavily-ledger-signal.jsonl, never tavily-ledger.jsonl")

        # 5c. three hours later: no subreddit is asked again within 12 h
        calls = len(tavily_calls)
        r = sensors.collect(sandbox, out5b, NOW + timedelta(hours=3), only=["reddit"])
        if len(tavily_calls) != calls or r["sources"]["reddit"]["status"] != "partial":
            problems.append(f"phase 5c: no tvly call within 12 h, got {len(tavily_calls) - calls}")

        # 5d. a subreddit with zero yield several runs running is called out in the source detail
        # (read back from the ledger's own `results` field, no separate state file)
        tavily_state["empty"] = {subs[0]}
        r = None
        for h in range(sensors.REDDIT_TAVILY_LOW_YIELD_RUNS):
            r = sensors.collect(sandbox, out5b, NOW + timedelta(hours=24 * (h + 1)), only=["reddit"])
        detail = r["sources"]["reddit"]["detail"]
        if subs[0] not in detail or "0 threads" not in detail:
            problems.append(f"phase 5d: a subreddit empty for {sensors.REDDIT_TAVILY_LOW_YIELD_RUNS}+ runs "
                            f"running should be called out, got {detail!r}")
        tavily_state.pop("empty", None)
        tavily_state["available"] = False
        state["reddit_block"] = False

        # 6. rss + atom, 7-day window, a non-feed is a per-feed failure
        os.environ["TOOLKIT_RADAR_SENSOR_FEEDS"] = ("https://synthsite.example.org/feed,"
                                                     "https://atomsite.example.org/atom,https://badsite.example.org/feed,"
                                                     "https://news.google.com/rss/search?q=maschine")
        state["feeds"] = {"https://synthsite.example.org/feed": (200, "application/rss+xml", RSS_GOOD),
                          "https://atomsite.example.org/atom": (200, "application/atom+xml", ATOM_GOOD),
                          "https://badsite.example.org/feed": (200, "text/html", RSS_BAD),
                          "https://news.google.com/rss/search?q=maschine": (200, "application/rss+xml", GNEWS)}
        out6 = sandbox.parent / "radar-rss"
        r = sensors.collect(sandbox, out6, NOW, only=["rss"])
        items = json.loads(Path(r["file"]).read_text())["items"]
        titles = sorted(v["title"] for v in items.values())
        if titles != ["Atom entry", "Maschine 3.7 adds a new sequencer", "New plugin released"]:
            problems.append(f"phase 6: expected the in-window RSS+Atom items (ancient post dropped, Google News "
                            f"title without its '- Outlet'), got {titles}")
        if r["sources"]["rss"]["status"] != "partial" or "badsite" not in r["sources"]["rss"]["detail"]:
            problems.append(f"phase 6: one bad feed among good ones must be status partial, got {r['sources']['rss']}")
        os.environ.pop("TOOLKIT_RADAR_SENSOR_FEEDS")

        # 7. merge across two runs: max score, first_seen kept, last_seen moves, scores appended
        out7 = sandbox.parent / "radar-merge"
        state["hn_front"], state["hn_bydate"] = {"hits": [hn_hit("9001", "Rising thing", 100)]}, {"hits": []}
        sensors.collect(sandbox, out7, NOW, only=["hn"])
        state["hn_front"] = {"hits": [hn_hit("9001", "Rising thing", 300)]}
        r = sensors.collect(sandbox, out7, NOW2, only=["hn"])
        row = json.loads(Path(r["file"]).read_text())["items"]["hn:9001"]
        if (row["score"] != 300.0 or row["first_seen"] != NOW.isoformat() or row["last_seen"] != NOW2.isoformat()
                or row["scores"] != [["12:00", 100.0], ["15:00", 300.0]]):
            problems.append(f"phase 7: merge must keep first_seen, max the score, move last_seen, append scores: {row}")

        # 8. carry-forward p from an older day file, never re-judged
        out8 = sandbox.parent / "radar-carry"
        (out8 / "sensors").mkdir(parents=True)
        old_day = (NOW.date() - timedelta(days=10)).isoformat()
        (out8 / "sensors" / f"{old_day}.json").write_text(json.dumps({"day": old_day, "updated": "x", "status": {},
            "items": {"hn:9001": {"source": "hn", "origin": "Hacker News", "id": "9001", "title": "Rising thing",
                                  "url": "https://example.org/a", "summary": "", "published": "2026-09-16",
                                  "score": 50.0, "first_seen": "x", "last_seen": "x", "scores": [],
                                  "p": {"local-ai": 0.77}, "kind": "model", "entities": []}}}), encoding="utf-8")
        state["hn_front"], state["hn_bydate"] = {"hits": [hn_hit("9001", "Rising thing", 60)]}, {"hits": []}
        judged: list = []

        def judge_fn(rows: list[dict]) -> dict[int, dict]:
            judged.append(rows)
            return {i: {"p": {"x": 0.5}, "kind": "other"} for i in range(len(rows))}

        r = sensors.collect(sandbox, out8, NOW, judge_fn=judge_fn, only=["hn"])
        row = json.loads(Path(r["file"]).read_text())["items"]["hn:9001"]
        if row["p"] != {"local-ai": 0.77} or row["kind"] != "model" or judged:
            problems.append(f"phase 8: an already-judged key must carry p/kind forward and skip judge_fn, got p={row['p']}, judged={judged}")

        # 9. cap: only unjudged rows go to judge_fn, highest score first, capped
        out9 = sandbox.parent / "radar-cap"
        state["hn_front"] = {"hits": [hn_hit(str(6000 + n), f"Item {n}", float(n * 10)) for n in range(6)]}
        state["hn_bydate"] = {"hits": []}
        judged.clear()
        sensors.MAX_JUDGE_PER_RUN = 3
        r = sensors.collect(sandbox, out9, NOW, judge_fn=judge_fn, only=["hn"])
        if len(judged) != 1 or len(judged[0]) != 3 or [row["score"] for row in judged[0]] != [50.0, 40.0, 30.0]:
            problems.append(f"phase 9: judge_fn must get exactly the 3 highest-scoring unjudged rows, got {judged}")
        if r["judged"] != 3:
            problems.append(f"phase 9: collect() must report 3 judged, got {r['judged']}")
        sensors.MAX_JUDGE_PER_RUN = real_max_judge

        # 9b. judge_fn raising must not lose the day's already-fetched items: they are still
        # written (unjudged), and the run stays "ok" with a short judge_error
        out9b = sandbox.parent / "radar-judge-fails"
        state["hn_front"] = {"hits": [hn_hit("7001", "Survives a judge crash", 10.0)]}
        state["hn_bydate"] = {"hits": []}

        def failing_judge_fn(rows: list[dict]) -> dict[int, dict]:
            raise RuntimeError("judgment backend exploded")
        r = sensors.collect(sandbox, out9b, NOW, judge_fn=failing_judge_fn, only=["hn"])
        items = json.loads(Path(r["file"]).read_text())["items"]
        if r.get("status") != "ok" or "hn:7001" not in items or "judge_error" not in r:
            problems.append(f"phase 9b: a judge_fn exception must not lose the fetched items, got {r}")

        # 10. pruning: older than 45 days removed, the boundary day kept
        out10 = sandbox.parent / "radar-prune"
        (out10 / "sensors").mkdir(parents=True)
        keep_day = (NOW.date() - timedelta(days=45)).isoformat()
        drop_day = (NOW.date() - timedelta(days=46)).isoformat()
        for d in (keep_day, drop_day):
            (out10 / "sensors" / f"{d}.json").write_text(json.dumps({"day": d, "updated": "x", "status": {}, "items": {}}),
                                                          encoding="utf-8")
        state["hn_front"], state["hn_bydate"] = {"hits": []}, {"hits": []}
        sensors.collect(sandbox, out10, NOW, only=["hn"])
        remaining = sorted(p.stem for p in (out10 / "sensors").glob("*.json"))
        if drop_day in remaining or keep_day not in remaining:
            problems.append(f"phase 10: expected {keep_day} kept and {drop_day} pruned, got {remaining}")

        # 11. nothing written outside out/sensors/, vault itself untouched
        vault_before = snapshot(sandbox)
        out11 = sandbox.parent / "radar-contained"
        out11.mkdir()
        before_files = {p.relative_to(out11).as_posix() for p in out11.rglob("*") if p.is_file()}
        state["hn_front"], state["hn_bydate"] = {"hits": [hn_hit("7777", "x", 1)]}, {"hits": []}
        sensors.collect(sandbox, out11, NOW, only=["hn"])
        after_files = {p.relative_to(out11).as_posix() for p in out11.rglob("*") if p.is_file()}
        stray = {f for f in after_files - before_files if not f.startswith("sensors/")}
        if stray or snapshot(sandbox) != vault_before:
            problems.append(f"phase 11: only out/sensors/ may gain files (stray: {stray}) and the vault must be untouched")
    finally:
        sensors._request, sensors.MAX_JUDGE_PER_RUN, tavily._run = real_request, real_max_judge, real_tavily
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"12 phases ok ({len(state['calls'])} stubbed requests)"}
