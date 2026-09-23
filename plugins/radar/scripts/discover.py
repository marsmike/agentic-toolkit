"""Feed discovery: which feeds would serve the owner's interests that Reader does not carry yet.

    radar.py discover [--interest ID ...] [--seed URL ...] [--queries N] [--out DIR]

Per interest: its first `QUERIES_PER_INTEREST` queries go to Kagi (`<query> blog`); every
result yields candidate feeds by construction from the URL's shape (GitHub repo -> releases.atom,
subreddit -> .rss, Substack -> /feed, Medium author -> feed) and by RSS/Atom autodiscovery on
the page; one hnrss.org search feed per interest is added by construction, and every `--seed`
(a page or a feed URL someone suggests) goes through the same path. Each candidate is
fetched and parsed; a feed with fewer than FEED_MIN_ITEMS items, silent for more than
FEED_MAX_SILENCE_DAYS, or on a site Reader already delivers is dropped. The rest are judged:
`feed_worth` per feed x interest and `feed_kind` per feed, from the feed's title, description
and latest item titles. Feeds at or above T_FEED for some interest go into an OPML for import in
Reader (there is no subscription API), with the reason on every outline.

Writes `feeds-discovered-DATE.opml` and `.json` and the Kagi ledger to --out. Reader is only read.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import quoteattr

import interests as interests_mod
import judge
import kagi
import reader
from interests import Interest
from judgments import policy
from judgments import questions as Q
from judgments.state import in_chunks
from vault_utils import profile_value

USER_AGENT = "agentic-toolkit-radar/1.0 (feed discovery)"
FETCH_TIMEOUT = 15
MAX_BYTES = 2_000_000
FETCH_WORKERS = 8
RECENT_TITLES = 8
HOST_INTERVAL_S = 2.0           # at most one request per host this often; parallel bursts
RETRY_429_S = 10.0              # to one host draw 429s [earned: 2026-09-23, reddit.com]
_host_lock = threading.Lock()
_host_next: dict[str, float] = {}
FEEDS_PER_REQUEST = 8
_ALT_LINK = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r'(\w+)\s*=\s*("[^"]*"|\'[^\']*\')')
_FEED_PATH = re.compile(r"(\.xml|\.rss|\.atom|/feed/?|/rss/?|/atom/?)$", re.I)


@dataclass
class Feed:
    url: str
    title: str = ""
    site: str = ""
    description: str = ""
    recent: list[str] = field(default_factory=list)
    last: str = ""
    per_week: float = 0.0
    found_for: set[str] = field(default_factory=set)
    via: str = ""

    def state(self) -> dict[str, str]:
        return {"title": self.title, "description": self.description[:300], "site": self.site,
                "recent": " | ".join(self.recent)}


def _wait_for_host(url: str) -> None:
    host = urllib.parse.urlparse(url).netloc.lower()
    with _host_lock:
        now = time.monotonic()
        start = max(now, _host_next.get(host, now))
        _host_next[host] = start + HOST_INTERVAL_S
    time.sleep(start - now)


def fetch(url: str) -> tuple[int, str, bytes]:
    """The one network call to arbitrary sites, spaced per host, one retry on 429. Evals
    replace it with a stub."""
    status, ctype, raw = _fetch_once(url)
    if status == 429:
        time.sleep(RETRY_429_S)
        status, ctype, raw = _fetch_once(url)
    return status, ctype, raw


def _fetch_once(url: str) -> tuple[int, str, bytes]:
    _wait_for_host(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, "", b""


def constructed(url: str) -> list[str]:
    """Feed URLs that follow from a page URL's shape alone."""
    u = urllib.parse.urlparse(url)
    host, parts = u.netloc.lower().removeprefix("www."), [p for p in u.path.split("/") if p]
    if host == "github.com" and len(parts) >= 2:
        return [f"https://github.com/{parts[0]}/{parts[1]}/releases.atom"]
    if host.endswith("reddit.com") and len(parts) >= 2 and parts[0] == "r":
        return [f"https://www.reddit.com/r/{parts[1]}/.rss"]
    if host.endswith(".substack.com"):
        return [f"https://{host}/feed"]
    if host == "medium.com" and parts and parts[0].startswith("@"):
        return [f"https://medium.com/feed/{parts[0]}"]
    if _FEED_PATH.search(u.path):
        return [url]
    return []


def autodiscover(page_url: str, html: str) -> list[str]:
    out = []
    for tag in _ALT_LINK.findall(html[:200_000]):
        attrs = {k.lower(): v[1:-1] for k, v in _ATTR.findall(tag)}
        if "alternate" in attrs.get("rel", "").lower() and re.search(r"(rss|atom)\+xml", attrs.get("type", ""), re.I):
            if attrs.get("href") and "comments" not in attrs["href"].lower():
                out.append(urllib.parse.urljoin(page_url, attrs["href"]))
    return out[:2]


def hnrss(interest: Interest) -> str:
    q = interest.queries[0] if interest.queries else interest.name
    return f"https://hnrss.org/newest?{urllib.parse.urlencode({'q': q, 'points': 50})}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in el if _local(c.tag) == name), None)


def _first(*els: ET.Element | None) -> ET.Element | None:
    """The first element that exists (an Element without children is falsy, so `or` is wrong)."""
    return next((e for e in els if e is not None), None)


def _site_link(head: ET.Element) -> str:
    for link in (c for c in head if _local(c.tag) == "link"):
        if link.get("href") is None:
            return _text(link)
        if link.get("rel", "alternate") == "alternate":
            return link.get("href", "")
    return ""


def _text(el: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _date(text: str) -> datetime | None:
    text = text.strip()
    if not text:
        return None
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def parse_feed(url: str, raw: bytes) -> Feed | None:
    """RSS 2.0, RSS 1.0 or Atom; None when it is not a feed."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    kind = _local(root.tag).lower()
    if kind == "rss":
        chan = _child(root, "channel")
        if chan is None:
            return None
        head, entries = chan, [c for c in chan if _local(c.tag) == "item"]
    elif kind == "rdf":
        head = _child(root, "channel")
        entries = [c for c in root if _local(c.tag) == "item"]
    elif kind == "feed":
        head, entries = root, [c for c in root if _local(c.tag) == "entry"]
    else:
        return None
    if head is None:
        return None
    site = _site_link(head) or url
    dates = []
    for e in entries:
        for name in ("pubDate", "date", "published", "updated"):
            if (d := _date(_text(_child(e, name)))) is not None:
                dates.append(d)
                break
    dates.sort(reverse=True)
    per_week = 0.0
    if len(dates) >= 2:
        span_weeks = max(1.0, (dates[0] - dates[-1]).total_seconds() / (7 * 86400))
        per_week = round(len(dates) / span_weeks, 1)
    return Feed(url=url, title=_text(_child(head, "title")),
                site=urllib.parse.urlparse(site).netloc.lower().removeprefix("www."),
                description=_text(_first(_child(head, "description"), _child(head, "subtitle"))),
                recent=[t for t in (_text(_child(e, "title")) for e in entries[:RECENT_TITLES]) if t],
                last=dates[0].date().isoformat() if dates else "", per_week=per_week)


def subscribed_sites(since: datetime) -> set[str]:
    """Hosts and site names Reader already delivers as RSS (feed and archive: judged items move)."""
    sites: set[str] = set()
    for loc in ("feed", "archive"):
        for d in reader.list_documents(loc, since):
            if d.get("category") == "rss":
                it = reader.to_item(d)
                sites.add(urllib.parse.urlparse(it.url).netloc.lower().removeprefix("www."))
                sites.add(it.site.casefold())
    return sites - {""}


def _judge_feeds(vault: Path, feeds: list[Feed], interests: list[Interest], usage: dict) -> dict[int, dict]:
    interest_state = {it.id: it.state() for it in interests}

    def ask(chunk: list[Feed], offset: int) -> dict[int, dict]:
        keys = [f"f{offset + j}" for j in range(len(chunk))]
        state = {"interests": interest_state, "feeds": {k: f.state() for k, f in zip(keys, chunk, strict=True)}}
        questions = {f"kind_{k}": Q.feed_kind(k) for k in keys}
        questions |= {f"w_{k}_{n}": Q.feed_worth(k, it.id) for k in keys for n, it in enumerate(interests)}
        try:
            answers, u = judge.judge(vault, state, questions)
        except judge.StateTooLarge:
            raise
        except judge.JudgmentFailed as e:
            usage["errors"].append(str(e)[:200])
            return {}
        usage["requests"] += u.requests
        usage["usd"] += u.usd
        out = {}
        for j, k in enumerate(keys):
            p = {it.id: round(answers[f"w_{k}_{n}"].p, 4) for n, it in enumerate(interests)
                 if f"w_{k}_{n}" in answers and answers[f"w_{k}_{n}"].p is not None}
            if p:
                kind = answers.get(f"kind_{k}")
                out[offset + j] = {"p": p, "kind": kind.top if kind else None}
        return out

    return in_chunks(feeds, FEEDS_PER_REQUEST, ask)


def render_opml(run_date: str, picks: list[dict], names: dict[str, str]) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0">',
             f"  <head><title>Radar: discovered feeds {run_date}</title></head>", "  <body>"]
    by_interest: dict[str, list[dict]] = {}
    for f in picks:
        by_interest.setdefault(f["best"], []).append(f)
    for iid, feeds in by_interest.items():
        lines.append(f"    <outline text={quoteattr(names[iid])}>")
        for f in feeds:
            why = (f"{names[iid]} p={f['p'][iid]:.2f}; {f['kind'] or '?'}; ~{f['per_week']}/week; "
                   f"latest {f['last'] or '?'}; found via {f['via']}")
            lines.append(f"      <outline type=\"rss\" text={quoteattr(f['title'] or f['url'])} "
                         f"title={quoteattr(f['title'] or f['url'])} xmlUrl={quoteattr(f['url'])} "
                         f"htmlUrl={quoteattr('https://' + f['site'] if f['site'] else f['url'])} "
                         f"description={quoteattr(why)}/>")
        lines.append("    </outline>")
    lines += ["  </body>", "</opml>", ""]
    return "\n".join(lines)


def discover(vault: Path, out: Path, now: datetime, only: list[str] | None = None,
             seeds: list[str] | None = None, queries_per_interest: int = policy.QUERIES_PER_INTEREST) -> dict[str, Any]:
    interests = [i for i in interests_mod.load(vault) if not only or i.id in only]
    if not interests:
        return {"status": "no-interests", "detail": "no matching interests"}
    reason = judge.unavailable_reason(vault)
    if reason:
        return {"status": "SKIPPED", "detail": f"judgment backend unavailable ({reason}); nothing sent"}
    ledger = kagi.Ledger(out / "kagi-ledger.jsonl",
                         float(profile_value(vault, "kagi_weekly_budget_usd", kagi.DEFAULT_WEEKLY_BUDGET_USD)))
    try:
        known = subscribed_sites(now - timedelta(days=60))
    except reader.NoToken:
        return {"status": "SKIPPED", "detail": "READWISE_TOKEN is not set; cannot tell subscribed feeds"}
    except reader.ReaderError as e:
        return {"status": "failed", "detail": f"Reader: {e}"}

    candidates: dict[str, Feed] = {}
    pages: list[tuple[str, str]] = []  # (page url, interest id)
    spent_before, searches, notes = ledger.spent_this_week(now), 0, []

    def add(url: str, iid: str, via: str) -> None:
        f = candidates.setdefault(url, Feed(url=url, via=via))
        f.found_for.add(iid)

    for url in seeds or []:
        built = constructed(url)
        for u in built:
            candidates.setdefault(u, Feed(url=u, via="seed"))
        if not built:
            pages.append((url, ""))
    for it in interests:
        add(hnrss(it), it.id, "hnrss")
        for q in it.queries[:queries_per_interest]:
            try:
                results = kagi.search(f"{q} blog", ledger, now=now)
            except kagi.NoKey:
                return {"status": "SKIPPED", "detail": "KAGI_API_KEY is not set; nothing searched"}
            except kagi.OverBudget as e:
                notes.append(str(e))
                break
            except kagi.KagiError as e:
                notes.append(f"kagi: {e}")
                continue
            searches += 1
            for r in results[:policy.PAGES_PER_QUERY]:
                built = constructed(r["url"])
                for u in built:
                    add(u, it.id, "url shape")
                if not built:
                    pages.append((r["url"], it.id))

    def page_feeds(pair: tuple[str, str]) -> list[tuple[str, str]]:
        status, ctype, raw = fetch(pair[0])
        if status != 200 or "html" not in ctype.lower():
            return []
        return [(u, pair[1]) for u in autodiscover(pair[0], raw.decode("utf-8", errors="replace"))]

    with ThreadPoolExecutor(FETCH_WORKERS) as pool:
        for found in pool.map(page_feeds, pages):
            for u, iid in found:
                if iid:
                    add(u, iid, "autodiscovery")
                else:
                    candidates.setdefault(u, Feed(url=u, via="seed"))

    def load(f: Feed) -> Feed | None:
        status, _, raw = fetch(f.url)
        parsed = parse_feed(f.url, raw) if status == 200 else None
        if parsed is None:
            return None
        parsed.found_for, parsed.via = f.found_for, f.via
        if f.via == "hnrss":  # its own title is the search query; queries never enter a judgment
            parsed.title, parsed.description = "Hacker News stories with 50+ points", ""
        return parsed

    dropped: dict[str, int] = {"unreachable or not a feed": 0, "too few items": 0, "dormant": 0, "already subscribed": 0}
    feeds: list[Feed] = []
    silence = (now - timedelta(days=policy.FEED_MAX_SILENCE_DAYS)).date().isoformat()
    with ThreadPoolExecutor(FETCH_WORKERS) as pool:
        for f in pool.map(load, candidates.values()):
            if f is None:
                dropped["unreachable or not a feed"] += 1
            elif len(f.recent) < policy.FEED_MIN_ITEMS:
                dropped["too few items"] += 1
            elif not f.last or f.last < silence:
                dropped["dormant"] += 1
            elif f.site in known or f.title.casefold() in known:
                dropped["already subscribed"] += 1
            else:
                feeds.append(f)
    feeds = list({f.url if f.via == "hnrss" else (f.site, f.title.casefold()): f for f in feeds}.values())

    usage: dict[str, Any] = {"requests": 0, "usd": 0.0, "errors": []}
    judged = _judge_feeds(vault, feeds, interests, usage) if feeds else {}
    t = policy.thresholds(judge.load_config(vault)["backend"])
    names = {i.id: i.name for i in interests}
    rows = []
    for n, f in enumerate(feeds):
        if n not in judged:
            continue
        p = judged[n]["p"]
        best = max(p, key=p.get)
        title = f"Hacker News: {names[sorted(f.found_for)[0]]}" if f.via == "hnrss" else f.title
        rows.append({"url": f.url, "title": title, "site": f.site, "kind": judged[n]["kind"], "p": p, "best": best,
                     "found_for": sorted(f.found_for), "via": f.via, "per_week": f.per_week, "last": f.last,
                     "recent": f.recent[:3], "proposed": p[best] >= t["T_FEED"]})
    rows.sort(key=lambda r: -r["p"][r["best"]])
    picks = [r for r in rows if r["proposed"]]

    run_date = now.date().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    opml = out / f"feeds-discovered-{run_date}.opml"
    opml.write_text(render_opml(run_date, picks, names), encoding="utf-8")
    (out / f"feeds-discovered-{run_date}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"status": "ok", "searches": searches, "kagi_usd": round(ledger.spent_this_week(now) - spent_before, 4),
            "candidates": len(candidates), "dropped": dropped, "judged": len(rows), "proposed": len(picks),
            "per_interest": {names[i]: sum(1 for r in picks if r["best"] == i) for i in names},
            "judgment": {"requests": usage["requests"], "usd": round(usage["usd"], 5), "errors": usage["errors"][:3]},
            "notes": notes, "opml": str(opml)}
