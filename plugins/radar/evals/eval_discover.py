"""Eval: `radar.py discover`, offline (stubbed Kagi, site fetches, Reader and judgment backend).

1. shapes     — GitHub repo -> releases.atom, subreddit -> .rss, Substack -> /feed; autodiscovery
                takes the RSS/Atom alternate link and skips comment feeds; RSS and Atom parse,
                an Atom `rel=self` link is not the site, a childless <description> still reads
2. budget     — a week already at the Kagi budget: no search is made, the reason is reported
3. discover   — candidates from URL shape, autodiscovery and hnrss; unreachable, dormant, thin and
                already-subscribed feeds dropped; only feeds at or above T_FEED in the OPML, each
                with its reason; queries never reach the judgment backend; Reader only read;
                nothing in the vault changes; the Kagi ledger records every search
4. seeds      — with --queries 0 and two seeds (a page and a repo URL): no search, both feeds found
                through the same autodiscovery and URL-shape paths and proposed
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "discover"
ENV_KEYS = ("TOOLKIT_RADAR_JUDGMENT_API_KEY", "OPENROUTER_API_KEY", "TOOLKIT_RADAR_JUDGMENT_BACKEND",
            "TOOLKIT_RADAR_INTERESTS_NOTE", "TOOLKIT_RADAR_TODOIST_PROJECT_ID", "KAGI_API_KEY",
            "TOOLKIT_RADAR_KAGI_WEEKLY_BUDGET_USD")
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

INTERESTS_NOTE = """---
description: Fixture interests for the radar discover eval.
status: active
interests:
  - name: Agent Memory
    gloss: How software agents store and recall what they learned across sessions.
    queries: [SECRET-QUERY-memory]
---

# Radar interests (fixture)
"""


def _rss(title: str, items: list[str], days_ago: float = 1, description: str = "") -> bytes:
    body = "".join(f"<item><title>{t}</title><pubDate>{format_datetime(NOW - timedelta(days=days_ago + n))}</pubDate></item>"
                   for n, t in enumerate(items))
    return (f'<?xml version="1.0"?><rss version="2.0"><channel><title>{title}</title><link>https://{title.lower().replace(" ", "")}.example.org/</link>'
            f"<description>{description}</description>{body}</channel></rss>").encode()


ATOM = (b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Release notes GOOD</title>'
        b'<link rel="self" href="https://github.com/acme/agent-mem/releases.atom"/>'
        b'<link rel="alternate" href="https://github.com/acme/agent-mem/releases"/>'
        + b"".join(f"<entry><title>v0.{n}</title><updated>2026-09-{20 - n:02d}T10:00:00Z</updated></entry>".encode() for n in range(4))
        + b"</feed>")

PAGE = (b'<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml">'
        b'<link rel="alternate" type="application/rss+xml" href="/comments/feed"></head></html>')

SITES = {
    "https://blog.example.org/post/1": (200, "text/html", PAGE),
    "https://blog.example.org/feed.xml": (200, "application/rss+xml", _rss("Memory Blog GOOD", ["a", "b", "c", "d"])),
    "https://github.com/acme/agent-mem/releases.atom": (200, "application/atom+xml", ATOM),
    "https://old.example.org/rss": (200, "application/rss+xml", _rss("Old Blog GOOD", ["a", "b", "c"], days_ago=90)),
    "https://thin.example.org/rss": (200, "application/rss+xml", _rss("Thin GOOD", ["a"])),
    "https://known.example.org/rss": (200, "application/rss+xml", _rss("Known Feed", ["a", "b", "c"])),
    "https://meh.example.org/rss": (200, "application/rss+xml", _rss("Meh Blog", ["x", "y", "z"])),
}
KAGI_RESULTS = [{"t": 0, "url": u} for u in (
    "https://blog.example.org/post/1", "https://github.com/acme/agent-mem", "https://old.example.org/rss",
    "https://thin.example.org/rss", "https://known.example.org/rss", "https://meh.example.org/rss",
    "https://gone.example.org/rss")]
READER_DOCS = [{"id": "r1", "title": "t", "category": "rss", "location": "archive", "parent_id": None,
                "site_name": "Known Feed", "source_url": "https://known.example.org/post",
                "saved_at": (NOW - timedelta(days=3)).isoformat()}]


def run(vault: Path) -> dict:
    import discover
    import judge
    import kagi
    import reader

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (judge._post, reader._request, reader.PAGE_DELAY_S, kagi._request, discover.fetch)
    calls: list[dict] = []
    searches: list[str] = []
    sandbox = None

    # 1. shapes
    if discover.constructed("https://github.com/acme/agent-mem/issues") != ["https://github.com/acme/agent-mem/releases.atom"] \
            or discover.constructed("https://www.reddit.com/r/LocalLLaMA/comments/x") != ["https://www.reddit.com/r/LocalLLaMA/.rss"] \
            or discover.constructed("https://someone.substack.com/p/post") != ["https://someone.substack.com/feed"] \
            or discover.constructed("https://example.org/about") != []:
        problems.append("phase 1: a URL shape did not construct its feed")
    if discover.autodiscover("https://blog.example.org/post/1", PAGE.decode()) != ["https://blog.example.org/feed.xml"]:
        problems.append("phase 1: autodiscovery must resolve the RSS link and skip comment feeds")
    atom = discover.parse_feed("u", ATOM)
    rss = discover.parse_feed("u", _rss("A Blog", ["one", "two"], description="plain text"))
    if atom is None or atom.site != "github.com" or atom.recent[:2] != ["v0.0", "v0.1"] or atom.last != "2026-09-20":
        problems.append(f"phase 1: Atom parsed wrong: {atom}")
    if rss is None or rss.description != "plain text" or rss.site != "ablog.example.org":
        problems.append(f"phase 1: RSS parsed wrong: {rss}")
    if discover.parse_feed("u", PAGE) is not None:
        problems.append("phase 1: an HTML page parsed as a feed")

    def kagi_stub(url):
        searches.append(url)
        return {"meta": {"api_balance": 10.0 - 0.025 * len(searches)}, "data": KAGI_RESULTS}

    def reader_stub(method, url, data=None):
        if method != "GET":
            problems.append(f"reader: unexpected {method} (discover must only read Reader)")
        return 200, {"results": READER_DOCS if "location=archive" in url else [], "nextPageCursor": None}, None

    def fetch_stub(url):
        if url.startswith("https://hnrss.org/newest?"):
            return 200, "application/rss+xml", _rss("Hacker News: Newest: SECRET-QUERY-memory", ["hn a", "hn b", "hn c"])
        return SITES.get(url, (404, "", b""))

    def judge_stub(url, payload, headers):
        calls.append(payload)
        answers = {}
        for qid in payload["questions"]:
            if qid.startswith("kind_"):
                answers[qid] = {"type": "choice", "choice": "practice", "probabilities": {"practice": 1.0}}
                continue
            _, key, _n = qid.split("_")
            answers[qid] = {"type": "noul", "noul": 0.9 if "GOOD" in payload["state"]["feeds"][key]["title"] else 0.3}
        return {"model": "stub-1", "usage": {"input_tokens": 100}, "answers": answers}

    try:
        sandbox = make_sandbox(vault)
        (sandbox / "03_Areas" / "Radar-Interests.md").write_text(INTERESTS_NOTE, encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "03_Areas/Radar-Interests.md"
        os.environ["TOOLKIT_RADAR_JUDGMENT_API_KEY"] = "stub-key-not-a-secret"
        reader._request, reader.PAGE_DELAY_S, kagi._request, discover.fetch, judge._post = \
            reader_stub, 0, kagi_stub, fetch_stub, judge_stub
        out = sandbox.parent / "discover-out"

        # 2. budget
        kagi.Ledger(out / "kagi-ledger.jsonl", 1.0).record({"at": NOW.isoformat(), "query": "earlier", "usd": 0.99, "balance": 10.0})
        r = discover.discover(sandbox, out, NOW)
        if searches or not any("budget" in n for n in r.get("notes", [])):
            problems.append(f"phase 2: over budget must search nothing and say so, got {len(searches)} searches, {r.get('notes')}")
        (out / "kagi-ledger.jsonl").unlink()

        # 3. discover
        before = snapshot(sandbox)
        calls.clear()
        r = discover.discover(sandbox, out, NOW)
        if r.get("status") != "ok" or r.get("searches") != 1:
            problems.append(f"phase 3: expected ok with one search, got {json.dumps({k: r.get(k) for k in ('status', 'searches', 'notes', 'detail')})}")
        want_dropped = {"unreachable or not a feed": 1, "too few items": 1, "dormant": 1, "already subscribed": 1}
        if r.get("dropped") != want_dropped:
            problems.append(f"phase 3: dropped {r.get('dropped')}, expected {want_dropped}")
        wire = json.dumps([c["state"] for c in calls])
        if "SECRET-QUERY" in wire:
            problems.append("phase 3: a search query reached the judgment backend")
        opml = ET.parse(r["opml"]).getroot()
        urls = sorted(o.get("xmlUrl") for o in opml.iter("outline") if o.get("xmlUrl"))
        if urls != ["https://blog.example.org/feed.xml", "https://github.com/acme/agent-mem/releases.atom"]:
            problems.append(f"phase 3: OPML should hold exactly the two GOOD feeds, got {urls}")
        if any("p=0.90" not in (o.get("description") or "") for o in opml.iter("outline") if o.get("xmlUrl")):
            problems.append("phase 3: every OPML outline must carry its reason")
        rows = json.loads(Path(r["opml"]).with_suffix(".json").read_text(encoding="utf-8"))
        if not any(x["title"] == "Hacker News: Agent Memory" and not x["proposed"] for x in rows):
            problems.append("phase 3: the hnrss feed should be judged, named by interest, and not proposed")
        ledger = kagi.Ledger(out / "kagi-ledger.jsonl", 1.0).rows()
        if len(ledger) != 1 or ledger[0]["usd"] != 0.025:
            problems.append(f"phase 3: the ledger should record one $0.025 search, got {ledger}")
        if snapshot(sandbox) != before:
            problems.append("phase 3: discover wrote into the vault")

        # 4. seeds
        n = len(searches)
        r = discover.discover(sandbox, sandbox.parent / "seeds", NOW, seeds=[
            "https://blog.example.org/post/1", "https://github.com/acme/agent-mem"], queries_per_interest=0)
        urls = sorted(o.get("xmlUrl") for o in ET.parse(r["opml"]).getroot().iter("outline") if o.get("xmlUrl"))
        if len(searches) != n or urls != ["https://blog.example.org/feed.xml", "https://github.com/acme/agent-mem/releases.atom"]:
            problems.append(f"phase 4: seeds must be found without searching, got {len(searches) - n} searches, {urls}")
    finally:
        judge._post, reader._request, reader.PAGE_DELAY_S, kagi._request, discover.fetch = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"4 offline phases ok ({len(calls)} stubbed judgment requests)"}
