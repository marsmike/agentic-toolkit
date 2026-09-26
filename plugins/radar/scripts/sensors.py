"""Direct momentum sensors for the signal radar: Hacker News, Hugging Face, GitHub, Reddit and a
handful of RSS/Atom feeds — pulled every ~3h by the cloud run, NOT through Reader.

    collect(vault, out, now, judge_fn=None, only=None)

Every source fetches independently and reports its own {"status", "items", "new", "detail"};
one failing never stops the others (house rule). Rows are merged by key (`f"{source}:{stable
id}"`) into that UTC day's file `out/sensors/YYYY-MM-DD.json`, rewritten atomically each run:
`first_seen` and a judged `p`/`kind` are kept, `score` becomes the max seen, `last_seen` moves and
a compact `[HH:MM, score]` pair is appended to `scores` (capped). A key already judged in any of
the last 45 day files carries its `p`/`kind` forward instead of being judged again; the rest are
handed to `judge_fn` (radar.py's wrapper around the shared judgment backend), highest score first,
capped at `MAX_JUDGE_PER_RUN`. Day files older than 45 days are pruned.

What leaves the machine: plain GETs to public HN/HF/GitHub/Reddit APIs and the RSS feeds below —
no key, ever (an optional `GITHUB_TOKEN`/`GH_TOKEN` only raises GitHub's own rate limit and is
never logged). If `judge_fn` is given, mention titles/summaries go wherever it sends them; this
module never talks to a judgment backend itself.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from entities import hf_family
from judgments.urls import _canonical
from vault_utils import atomic_write, profile_value, secret

USER_AGENT = "agentic-toolkit-radar/1.0 (+https://github.com/marsmike/agentic-toolkit)"
HTTP_TIMEOUT = 30
MAX_BYTES = 2_000_000
HOST_POLITENESS_S = 0.3          # at most one request per host this often
MAX_JUDGE_PER_RUN = 150
RETAIN_DAYS = 45
MAX_SCORES = 12
GITHUB_WINDOW_DAYS = 14
RSS_WINDOW_DAYS = 7
REDDIT_LIMIT = 40

ALL_SOURCES = ("hn", "hf", "github", "reddit", "rss")

DEFAULT_GITHUB_TOPICS = ["llm", "ai-agents", "claude-code", "mcp", "local-llm", "audio-plugin", "vst"]
DEFAULT_SUBREDDITS = ["LocalLLaMA", "ClaudeAI", "ClaudeCode", "singularity", "MachineLearning",
                       "synthesizers", "WeAreTheMusicMakers", "audioengineering"]
# kvraudio.com/xml/rss.xml 404s (checked 2026-09-26) -> dropped, no replacement guessed.
# musicradar's /feeds/all 301s to /feeds.xml, a valid RSS 2.0 feed; urllib follows the redirect.
DEFAULT_FEEDS = ["https://bedroomproducersblog.com/feed/", "https://rekkerd.org/feed/",
                 "https://www.musicradar.com/feeds/all"]

_host_last: dict[str, float] = {}


def _polite(url: str) -> None:
    """At most one request per host every HOST_POLITENESS_S; sensors runs sequentially, so a
    plain per-host timestamp (no lock) is enough."""
    host = urllib.parse.urlparse(url).netloc.lower()
    now = time.monotonic()
    wait = HOST_POLITENESS_S - (now - _host_last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _host_last[host] = time.monotonic()


def _request(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    """The one network call in this module. Evals replace it with a stub.
    Returns (status, response headers lower-cased, body); (0, {}, b"") on a network-level failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}, e.read(MAX_BYTES)
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, {}, b""


def _profile_list(vault: Path, key: str, default: list[str]) -> list[str]:
    raw = profile_value(vault, key, None)
    if raw is None:
        return list(default)
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _enabled_sources(vault: Path, only: list[str] | None) -> list[str]:
    """Profile `sensors` (comma list, default all) intersected with `only` when given."""
    names = _profile_list(vault, "sensors", list(ALL_SOURCES))
    enabled = [s for s in ALL_SOURCES if s in names]
    return [s for s in enabled if not only or s in only]


def _row(source: str, origin: str, id_: str, title: str, url: str, summary: str,
         published: str, score: float | None, entities: list[str]) -> dict[str, Any]:
    return {"source": source, "origin": origin, "id": id_, "title": title, "url": url,
            "summary": summary, "published": published, "score": score, "entities": entities}


# ---------------------------------------------------------------------------
# Hacker News (Algolia)
# ---------------------------------------------------------------------------

HN_BASE = "https://hn.algolia.com/api/v1"


def _fetch_hn(vault: Path, now: datetime) -> tuple[str, str, list[dict]]:
    since = int((now - timedelta(hours=48)).timestamp())
    urls = [f"{HN_BASE}/search?tags=front_page&hitsPerPage=60",
            f"{HN_BASE}/search_by_date?{urllib.parse.urlencode({'tags': 'story', 'numericFilters': f'points>40,created_at_i>{since}', 'hitsPerPage': 100})}"]
    rows: dict[str, dict] = {}
    problems: list[str] = []
    for url in urls:
        _polite(url)
        status, _, body = _request(url)
        if status != 200:
            problems.append(f"HTTP {status}")
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            problems.append("bad JSON")
            continue
        for hit in data.get("hits") or []:
            oid = str(hit.get("objectID") or "")
            if not oid or oid in rows:
                continue
            title = str(hit.get("title") or "")
            item_url = str(hit.get("url") or hit.get("story_url") or "") or f"https://news.ycombinator.com/item?id={oid}"
            origin = "Show HN" if title.casefold().startswith("show hn") else "Hacker News"
            points = hit.get("points")
            rows[oid] = _row("hn", origin, oid, title, item_url, f"{hit.get('num_comments') or 0} comments",
                             str(hit.get("created_at") or "")[:10],
                             float(points) if isinstance(points, (int, float)) else None, [])
    if not rows:
        return ("failed" if problems else "ok"), "; ".join(problems), []
    return ("partial" if problems else "ok"), "; ".join(problems), list(rows.values())


# ---------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------

HF_BASE = "https://huggingface.co/api"


def _fetch_hf(vault: Path, now: datetime) -> tuple[str, str, list[dict]]:
    endpoints = [(f"{HF_BASE}/models?sort=trendingScore&direction=-1&limit=60", "Hugging Face"),
                 (f"{HF_BASE}/spaces?sort=trendingScore&direction=-1&limit=20", "HF Spaces")]
    rows: dict[str, dict] = {}
    problems: list[str] = []
    for url, origin in endpoints:
        _polite(url)
        status, _, body = _request(url)
        if status != 200:
            problems.append(f"{origin}: HTTP {status}")
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            problems.append(f"{origin}: bad JSON")
            continue
        for m in data if isinstance(data, list) else []:
            mid = str(m.get("id") or m.get("modelId") or "")
            if not mid:
                continue
            score = m.get("trendingScore")
            if not isinstance(score, (int, float)):
                score = m.get("likes")
            bits = [str(m[k]) for k in ("pipeline_tag", "library_name") if m.get(k)]
            for k in ("downloads", "likes"):
                if isinstance(m.get(k), (int, float)):
                    bits.append(f"{m[k]} {k}")
            created = str(m.get("createdAt") or "")[:10]
            if created:
                bits.append(created)
            rows[mid] = _row("hf", origin, mid, mid, f"https://huggingface.co/{mid}", ", ".join(bits), created,
                             float(score) if isinstance(score, (int, float)) else None, [hf_family(mid)])
    if not rows:
        return ("failed" if problems else "ok"), "; ".join(problems), []
    return ("partial" if problems else "ok"), "; ".join(problems), list(rows.values())


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

GITHUB_BASE = "https://api.github.com/search/repositories"


def _github_headers() -> dict[str, str]:
    token = secret("GITHUB_TOKEN") or secret("GH_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_github(vault: Path, now: datetime) -> tuple[str, str, list[dict]]:
    headers = _github_headers()
    since = (now - timedelta(days=GITHUB_WINDOW_DAYS)).date().isoformat()
    topics = _profile_list(vault, "sensor_github_topics", DEFAULT_GITHUB_TOPICS)
    queries = [f"{GITHUB_BASE}?q=created:%3E{since}+stars:%3E20&sort=stars&order=desc&per_page=50"]
    queries += [f"{GITHUB_BASE}?q=topic:{t}+pushed:%3E{since}+stars:%3E50&sort=stars&order=desc&per_page=20" for t in topics]

    rows: dict[str, dict] = {}
    problems: list[str] = []
    rate_limited = False
    for url in queries:
        _polite(url)
        status, _, body = _request(url, headers)
        if status in (403, 429):
            problems.append(f"rate limited (HTTP {status})")
            rate_limited = True
            break
        if status != 200:
            problems.append(f"HTTP {status}")
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            problems.append("bad JSON")
            continue
        for it in data.get("items") or []:
            full_name = str(it.get("full_name") or "")
            if not full_name:
                continue
            desc = str(it.get("description") or "").strip()
            lang = str(it.get("language") or "").strip()
            summary = f"{desc} [{lang}]" if desc and lang else desc or lang
            stars = it.get("stargazers_count")
            rows[full_name] = _row("github", "GitHub", full_name, full_name,
                                   str(it.get("html_url") or f"https://github.com/{full_name}"), summary,
                                   str(it.get("created_at") or "")[:10],
                                   float(stars) if isinstance(stars, (int, float)) else None,
                                   [full_name.split("/", 1)[-1]])
    if rate_limited:
        return "partial", "; ".join(problems), list(rows.values())
    if not rows:
        return ("failed" if problems else "ok"), "; ".join(problems), []
    return ("partial" if problems else "ok"), "; ".join(problems), list(rows.values())


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------


def _reddit_listing(sub: str) -> tuple[bool, list[dict]]:
    """One subreddit: (blocked, rows). Tries www then old.reddit.com on a bad response."""
    for base in ("https://www.reddit.com", "https://old.reddit.com"):
        url = f"{base}/r/{sub}/hot.json?limit={REDDIT_LIMIT}"
        _polite(url)
        status, headers, body = _request(url, {"Accept": "application/json"})
        if status == 200 and "json" in headers.get("content-type", "").lower():
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                continue
            rows = []
            for child in (data.get("data") or {}).get("children") or []:
                d = child.get("data") or {}
                if d.get("stickied"):
                    continue
                rid = str(d.get("id") or "")
                if not rid:
                    continue
                ups = d.get("ups")
                created = d.get("created_utc")
                published = datetime.fromtimestamp(created, tz=UTC).date().isoformat() if isinstance(created, (int, float)) else ""
                url_ = str(d.get("url_overridden_by_dest") or "") or f"https://www.reddit.com{d.get('permalink', '')}"
                rows.append(_row("reddit", f"r/{sub}", rid, str(d.get("title") or ""), url_,
                                 f"{d.get('num_comments') or 0} comments", published,
                                 float(ups) if isinstance(ups, (int, float)) else None, []))
            return False, rows
    return True, []


def _fetch_reddit(vault: Path, now: datetime) -> tuple[str, str, list[dict]]:
    subs = _profile_list(vault, "sensor_subreddits", DEFAULT_SUBREDDITS)
    rows: dict[str, dict] = {}
    for sub in subs:
        blocked, sub_rows = _reddit_listing(sub)
        if blocked:
            return "blocked", f"r/{sub}: blocked on both hosts", list(rows.values())
        for r in sub_rows:
            rows[r["id"]] = r
    return "ok", "", list(rows.values())


# ---------------------------------------------------------------------------
# RSS / Atom
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in el if _local(c.tag) == name), None)


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _first(*els: ET.Element | None) -> ET.Element | None:
    """The first element that exists: an Element with no children of its own is falsy (its
    `bool()` is `len()`), so `a or b` silently skips a real leaf element like `<pubDate>`."""
    return next((e for e in els if e is not None), None)


def _text(el: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""


def _parse_date(text: str) -> datetime | None:
    text = (text or "").strip()
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


def _entry_link(entry: ET.Element) -> str:
    """Atom `<link href=.../>` (prefer rel=alternate), else RSS `<link>text</link>`."""
    href_links = [link for link in _children(entry, "link") if link.get("href")]
    for link in href_links:
        if link.get("rel", "alternate") == "alternate":
            return link.get("href", "")
    if href_links:
        return href_links[0].get("href", "")
    return _text(_child(entry, "link"))


def parse_feed_items(raw: bytes) -> tuple[str, list[dict]]:
    """RSS 2.0/1.0 or Atom -> (feed title, [{title, url, published: datetime|None, summary}]).
    Raises ValueError when `raw` does not parse as one of these."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f"not XML: {e}") from e
    kind = _local(root.tag).lower()
    if kind == "rss":
        head = _child(root, "channel")
        if head is None:
            raise ValueError("rss without channel")
        entries = _children(head, "item")
    elif kind == "rdf":
        head = _child(root, "channel")
        entries = _children(root, "item")
    elif kind == "feed":
        head, entries = root, _children(root, "entry")
    else:
        raise ValueError(f"unrecognised root <{kind}>")
    if head is None:
        raise ValueError("no channel/feed head")
    title = _text(_child(head, "title"))
    items = []
    for e in entries:
        summary_el = _first(_child(e, "description"), _child(e, "summary"), _child(e, "content"))
        pub_el = _first(_child(e, "pubDate"), _child(e, "published"), _child(e, "updated"), _child(e, "date"))
        items.append({"title": _text(_child(e, "title")), "url": _entry_link(e),
                     "published": _parse_date(_text(pub_el)), "summary": _text(summary_el)[:300]})
    return title, items


def _fetch_rss(vault: Path, now: datetime) -> tuple[str, str, list[dict]]:
    feeds = _profile_list(vault, "sensor_feeds", DEFAULT_FEEDS)
    cutoff = now - timedelta(days=RSS_WINDOW_DAYS)
    rows: dict[str, dict] = {}
    problems: list[str] = []
    ok_feeds = 0
    for url in feeds:
        host = urllib.parse.urlparse(url).netloc.removeprefix("www.")
        _polite(url)
        status, _, body = _request(url)
        if status != 200:
            problems.append(f"{host}: HTTP {status}")
            continue
        try:
            title, items = parse_feed_items(body)
        except ValueError as e:
            problems.append(f"{host}: {e}")
            continue
        ok_feeds += 1
        origin = title or host
        for it in items:
            if not it["url"]:
                continue
            pub = it["published"]
            if pub is not None and pub < cutoff:
                continue
            key = _canonical(it["url"])
            rows[key] = _row("rss", origin, key, it["title"], it["url"], it["summary"],
                             pub.date().isoformat() if pub else "", None, [])
    if not ok_feeds:
        return "failed", "; ".join(problems), []
    return ("partial" if problems else "ok"), "; ".join(problems), list(rows.values())


FETCHERS = {"hn": _fetch_hn, "hf": _fetch_hf, "github": _fetch_github, "reddit": _fetch_reddit, "rss": _fetch_rss}


# ---------------------------------------------------------------------------
# Day-file merge, carry-forward judging, pruning
# ---------------------------------------------------------------------------


def _load_day(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _carried_p(sensors_dir: Path, today: date) -> dict[str, dict]:
    """key -> {"p", "kind"} already judged (or already carried) in any day file within the
    retention window, today's included: a key that has one never goes back to judge_fn."""
    carried: dict[str, dict] = {}
    cutoff = today - timedelta(days=RETAIN_DAYS)
    for f in sorted(sensors_dir.glob("*.json")):
        try:
            d = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if d < cutoff:
            continue
        for key, row in (_load_day(f).get("items") or {}).items():
            if key not in carried and row.get("p") is not None:
                carried[key] = {"p": row["p"], "kind": row.get("kind")}
    return carried


def _prune(sensors_dir: Path, today: date) -> None:
    cutoff = today - timedelta(days=RETAIN_DAYS)
    for f in sensors_dir.glob("*.json"):
        try:
            d = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if d < cutoff:
            f.unlink(missing_ok=True)


def collect(vault: Path, out: Path, now: datetime, judge_fn: Any = None, only: list[str] | None = None) -> dict[str, Any]:
    sensors_dir = out / "sensors"
    sensors_dir.mkdir(parents=True, exist_ok=True)
    today = now.astimezone(UTC).date()
    now_iso = now.astimezone(UTC).isoformat()
    hhmm = now.astimezone(UTC).strftime("%H:%M")
    day_file = sensors_dir / f"{today.isoformat()}.json"

    items: dict[str, dict] = dict(_load_day(day_file).get("items") or {})
    carried = _carried_p(sensors_dir, today)

    enabled = _enabled_sources(vault, only)
    sources: dict[str, dict] = {}
    for name in ALL_SOURCES:
        if name not in enabled:
            sources[name] = {"status": "skipped", "items": 0, "new": 0, "detail": "disabled via profile `sensors`"}
            continue
        try:
            status, detail, fetched = FETCHERS[name](vault, now)
        except Exception as e:  # a source must never take the run down (house rule)
            status, detail, fetched = "failed", f"{type(e).__name__}: {e}"[:200], []
        new_count = 0
        for raw in fetched:
            key = f"{raw['source']}:{raw['id']}"
            existing = items.get(key)
            if existing is None:
                new_count += 1
                p, kind = (carried[key]["p"], carried[key]["kind"]) if key in carried else (None, None)
                items[key] = {"source": raw["source"], "origin": raw["origin"], "id": raw["id"],
                              "title": raw["title"], "url": raw["url"], "summary": raw["summary"],
                              "published": raw["published"], "score": raw["score"],
                              "first_seen": now_iso, "last_seen": now_iso, "scores": [[hhmm, raw["score"]]],
                              "p": p, "kind": kind, "entities": raw["entities"]}
            else:
                existing["title"] = raw["title"] or existing["title"]
                existing["url"] = raw["url"] or existing["url"]
                existing["summary"] = raw["summary"] or existing["summary"]
                existing["origin"] = raw["origin"] or existing["origin"]
                existing["last_seen"] = now_iso
                if raw["score"] is not None and (existing["score"] is None or raw["score"] > existing["score"]):
                    existing["score"] = raw["score"]
                existing["scores"] = (existing.get("scores") or []) + [[hhmm, raw["score"]]]
                existing["scores"] = existing["scores"][-MAX_SCORES:]
                if existing.get("p") is None and key in carried:
                    existing["p"], existing["kind"] = carried[key]["p"], carried[key]["kind"]
        sources[name] = {"status": status, "items": len(fetched), "new": new_count, "detail": detail}

    unjudged = [k for k, r in items.items() if r.get("p") is None]
    unjudged.sort(key=lambda k: -(items[k]["score"] if items[k]["score"] is not None else -1.0))
    candidates = unjudged[:MAX_JUDGE_PER_RUN]
    judged_n = 0
    if judge_fn is not None and candidates:
        results = judge_fn([items[k] for k in candidates]) or {}
        for i, key in enumerate(candidates):
            if i in results:
                items[key]["p"] = results[i].get("p")
                items[key]["kind"] = results[i].get("kind")
                judged_n += 1

    atomic_write(day_file, json.dumps({"day": today.isoformat(), "updated": now_iso, "status": sources,
                                       "items": items}, indent=2, ensure_ascii=False) + "\n")
    _prune(sensors_dir, today)

    return {"status": "ok", "sources": sources, "judged": judged_n, "file": str(day_file),
            "usage": {"unjudged": len(unjudged), "capped": len(unjudged) > MAX_JUDGE_PER_RUN, "judged": judged_n}}
