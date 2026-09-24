"""Reader v3 client for the radar: the feed items Reader aggregates.

Radar's own stdlib client, not an import of the readwise plugin's (no cross-plugin imports,
contract/KNOWLEDGE_API.md). It reads `location=feed`, the items the readwise plugin drops by
design, and never fetches a body: title, summary, site and category are what gets judged. Its
one write is `bulk_update` of location, tags and notes: a recorded item leaves the feed for the
archive, or with --promote a strong one for Later (both reversible in the app). Nothing is ever
deleted. [Mike, 2026-09-23: judged items off the feed]

A feed item carries no feed id: `source` is the constant "Reader RSS" and `url` is the Reader
link, so the feed is `site_name` and the address is `source_url`. [verified against a live
item 2026-09-22]
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from judgments.urls import _canonical
from vault_utils import secret

READER_BASE = "https://readwise.io/api/v3"
FEED_LOCATION = "feed"
PAGE_DELAY_S = 3.0              # list and bulk_update are both limited to 20/minute
BULK_MAX = 50                   # bulk_update accepts at most 50 updates per call
MAX_429_RETRIES = 5
HTTP_TIMEOUT = 30


class NoToken(RuntimeError):
    """READWISE_TOKEN is not set. Callers report SKIPPED, never crash."""


class ReaderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Item:
    id: str
    url: str
    canonical: str
    title: str
    summary: str
    site: str
    feed: str
    published: str
    category: str
    saved_at: str
    notes: str = ""

    def state(self) -> dict[str, str]:
        """What a judgment backend sees of an item: no ids, no reading signals."""
        return {"title": self.title, "summary": self.summary, "site": self.site, "category": self.category}


def _token() -> str:
    tok = secret("READWISE_TOKEN")
    if not tok:
        raise NoToken("READWISE_TOKEN is not set")
    return tok


def _request(method: str, url: str, data: dict | None = None) -> tuple[int, Any, float | None]:
    """The one network call in this module. Evals replace it with a stub.
    Returns (status, parsed body, Retry-After seconds or None)."""
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Authorization": f"Token {_token()}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw else None), None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        retry = e.headers.get("Retry-After") if e.headers else None
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"error": raw[:300]}
        return e.code, parsed, float(retry) if retry and retry.isdigit() else None
    except urllib.error.URLError as e:
        raise ReaderError(f"request failed: {e}") from e


def _call(method: str, url: str, data: dict | None = None, ok: tuple[int, ...] = (200,)) -> Any:
    for _ in range(MAX_429_RETRIES):
        status, body, retry_after = _request(method, url, data)
        if status == 429:
            time.sleep(retry_after or 60)
            continue
        if status not in ok:
            raise ReaderError(f"{method} {url.split('?')[0]} failed ({status}): {str(body)[:200]}")
        return body
    raise ReaderError(f"{method} {url.split('?')[0]}: still rate-limited after {MAX_429_RETRIES} retries")


def _get(url: str) -> Any:
    return _call("GET", url)


UPDATABLE = {"id", "location", "tags", "notes"}
LOCATIONS = {"archive", "later", "shortlist", "new"}  # never "feed" back, never a delete


def bulk_update(updates: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Apply `{id, location[, tags, notes]}` updates, 50 per call. Returns (done, failed) ids; a
    207 reports per-item failures, which are returned rather than raised."""
    for u in updates:
        if set(u) - UPDATABLE or u.get("location") not in LOCATIONS:
            raise ValueError(f"refusing a Reader update outside location/tags/notes: {u}")
    done: list[str] = []
    failed: list[str] = []
    for start in range(0, len(updates), BULK_MAX):
        if start:
            time.sleep(PAGE_DELAY_S)
        chunk = updates[start:start + BULK_MAX]
        body = _call("PATCH", f"{READER_BASE}/bulk_update/", {"updates": chunk}, ok=(200, 207)) or {}
        ok = {str(r.get("id")) for r in body.get("results") or [] if r.get("success")}
        done += [u["id"] for u in chunk if u["id"] in ok]
        failed += [u["id"] for u in chunk if u["id"] not in ok]
    return done, failed


def save(url: str, location: str, tags: list[str], notes: str = "") -> str:
    """Save a page found outside the feeds into the library (the gap search's promotion). Returns
    the new document's id. Same guard as bulk_update: a library location, never the feed."""
    if location not in LOCATIONS or not url.startswith("http"):
        raise ValueError(f"refusing a Reader save to {location!r} of {url!r}")
    body = _call("POST", f"{READER_BASE}/save/", {"url": url, "location": location, "tags": tags,
                                                   **({"notes": notes} if notes else {})}, ok=(200, 201)) or {}
    return str(body.get("id") or "")


def archive(ids: list[str]) -> tuple[list[str], list[str]]:
    return bulk_update([{"id": i, "location": "archive"} for i in ids])


def _published(raw: Any) -> str:
    if isinstance(raw, (int, float)):  # Reader sends epoch milliseconds for some items
        return datetime.fromtimestamp(raw / 1000, tz=UTC).date().isoformat()
    return str(raw or "")[:10]


def to_item(doc: dict) -> Item:
    address = str(doc.get("source_url") or doc.get("url") or "")
    site = str(doc.get("site_name") or "")
    return Item(
        id=str(doc["id"]),
        url=address,
        canonical=_canonical(address),
        title=str(doc.get("title") or "").strip(),
        summary=str(doc.get("summary") or "").strip(),
        site=site,
        feed=site or _canonical(address).split("/", 1)[0],
        published=_published(doc.get("published_date")),
        category=str(doc.get("category") or ""),
        saved_at=str(doc.get("saved_at") or ""),
        notes=str(doc.get("notes") or ""),
    )


def list_documents(location: str, since: datetime) -> list[dict]:
    """Every top-level document in `location` saved at or after `since`. Filters `saved_at` in
    code because `updatedAfter` also returns old items touched since; drops children
    (`parent_id`: highlights and notes)."""
    params = {"location": location, "updatedAfter": since.isoformat(), "pageSize": "100"}
    out: list[dict] = []
    cursor = None
    while True:
        if cursor:
            params["pageCursor"] = cursor
        page = _get(f"{READER_BASE}/list/?{urllib.parse.urlencode(params)}") or {}
        out.extend(page.get("results") or [])
        cursor = page.get("nextPageCursor")
        if not cursor:
            break
        time.sleep(PAGE_DELAY_S)
    keep = []
    for d in out:
        when = _when(d.get("saved_at"))
        if not d.get("parent_id") and when is not None and when >= since:
            keep.append(d)
    return keep


def _when(stamp: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(stamp)).astimezone(UTC)
    except ValueError:
        return None


def list_feed(since: datetime) -> list[Item]:
    return [to_item(d) for d in list_documents(FEED_LOCATION, since)]
