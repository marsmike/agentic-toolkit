#!/usr/bin/env python3
"""Readwise API client — Reader v3 (primary) + Classic v2 (supplementary, Kindle/Apple Books).

Python port of v1's `readwise-api.sh`, stdlib-only (urllib) to keep scripts/pyproject.toml's
dependency list minimal. The token is read from the `READWISE_TOKEN` environment variable —
never from the vault, never from a profile note, never hard-coded (contract/PROFILE.md's
Secrets rule). Get a token at https://readwise.io/access_token.

CLI usage (mostly for debugging — the ingest skill drives this as a library):

    uv run --project scripts python3 scripts/readwise_api.py auth
    uv run --project scripts python3 scripts/readwise_api.py list --category tweet --location new
    uv run --project scripts python3 scripts/readwise_api.py get <doc_id>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

READER_BASE = "https://readwise.io/api/v3"
CLASSIC_BASE = "https://readwise.io/api/v2"

# location=feed is an RSS subscription item, never an explicit save — see references/api.md.
NOT_A_CLIPPING_LOCATION = "feed"


class NoTokenConfigured(RuntimeError):
    """READWISE_TOKEN is not set. Callers should skip/degrade cleanly, never crash noisily
    at import time or during a SessionStart hook."""


class ReadwiseAPIError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _token(token: str | None = None) -> str:
    import os

    tok = token or os.environ.get("READWISE_TOKEN")
    if not tok:
        raise NoTokenConfigured(
            "READWISE_TOKEN is not set. Add it to your environment (see profile.example.md's "
            "Secrets section) — never write the value into the vault or the repo."
        )
    return tok


def _request(method: str, url: str, token: str, data: dict | None = None, timeout: int = 30) -> Any:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Authorization": f"Token {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return e.code, (json.loads(raw) if raw else {"error": raw})
    except urllib.error.URLError as e:
        raise ReadwiseAPIError(f"request failed: {e}. URL: {url}") from e


def auth(token: str | None = None) -> bool:
    status, _ = _request("GET", f"{CLASSIC_BASE}/auth/", _token(token))
    return status == 204


def reader_list(
    category: str | None = None,
    location: str | None = None,
    updated_after: str | None = None,
    page_cursor: str | None = None,
    page_size: int = 100,
    token: str | None = None,
) -> dict:
    """One page of Reader v3 `/list/`. Use reader_list_all() to paginate + filter feed noise."""
    params: dict[str, str] = {"pageSize": str(page_size)}
    if category:
        params["category"] = category
    if location:
        params["location"] = location
    if updated_after:
        params["updatedAfter"] = updated_after
    if page_cursor:
        params["pageCursor"] = page_cursor
    url = f"{READER_BASE}/list/?{urllib.parse.urlencode(params)}"
    status, data = _request("GET", url, _token(token))
    if status != 200:
        raise ReadwiseAPIError(f"reader_list failed ({status}): {data}", status=status)
    return data


def reader_list_all(
    category: str | None = None,
    location: str | None = None,
    updated_after: str | None = None,
    token: str | None = None,
    delay_s: float = 3.0,
    exclude_feed: bool = True,
) -> list[dict]:
    """Paginate `/list/` to exhaustion. Filters out `location: feed` (RSS noise, never a
    clipping — see references/api.md) unless the caller explicitly asked for that location."""
    tok = _token(token)
    results: list[dict] = []
    cursor = None
    while True:
        page = reader_list(category=category, location=location, updated_after=updated_after,
                            page_cursor=cursor, token=tok)
        results.extend(page.get("results", []))
        cursor = page.get("nextPageCursor")
        if not cursor:
            break
        time.sleep(delay_s)
    if exclude_feed and location != NOT_A_CLIPPING_LOCATION:
        results = [r for r in results if r.get("location") != NOT_A_CLIPPING_LOCATION]
    return results


def reader_get(doc_id: str, token: str | None = None) -> dict:
    """Fetch one Reader document WITH full HTML content.

    List responses return `content: null` — this is the only way to get the real body
    (and any URLs embedded in it). See references/api.md's withHtmlContent gotcha.
    """
    url = f"{READER_BASE}/list/?{urllib.parse.urlencode({'id': doc_id, 'withHtmlContent': 'true'})}"
    status, data = _request("GET", url, _token(token))
    if status != 200:
        raise ReadwiseAPIError(f"reader_get({doc_id}) failed ({status}): {data}", status=status)
    results = (data or {}).get("results") or []
    if not results:
        raise ReadwiseAPIError(f"reader_get({doc_id}): no document returned")
    return results[0]


def reader_delete(doc_id: str, token: str | None = None) -> bool:
    status, _ = _request("DELETE", f"{READER_BASE}/delete/{doc_id}/", _token(token))
    return status == 204


def reader_archive(doc_id: str, token: str | None = None) -> dict:
    status, data = _request("PATCH", f"{READER_BASE}/update/{doc_id}/", _token(token),
                             data={"location": "archive"})
    if status not in (200, 204):
        raise ReadwiseAPIError(f"reader_archive({doc_id}) failed ({status}): {data}", status=status)
    return data or {}


def classic_export_all(
    category: str | None = None,
    updated_after: str | None = None,
    token: str | None = None,
    delay_s: float = 3.0,
) -> list[dict]:
    """Paginate Classic v2 `/export/` — a single call is NOT the full library (see
    references/api.md: 44% of a real library was invisible from one page on 2026-07-24)."""
    tok = _token(token)
    results: list[dict] = []
    cursor = None
    while True:
        params: dict[str, str] = {}
        if category:
            params["category"] = category
        if updated_after:
            params["updatedAfter"] = updated_after
        if cursor:
            params["pageCursor"] = cursor
        url = f"{CLASSIC_BASE}/export/?{urllib.parse.urlencode(params)}"
        status, data = _request("GET", url, tok)
        if status != 200:
            raise ReadwiseAPIError(f"classic_export_all failed ({status}): {data}", status=status)
        results.extend((data or {}).get("results", []))
        cursor = (data or {}).get("nextPageCursor")
        if not cursor:
            break
        time.sleep(delay_s)
    return results


def classic_highlight_delete(highlight_id: str | int, token: str | None = None) -> bool:
    status, _ = _request("DELETE", f"{CLASSIC_BASE}/highlights/{highlight_id}/", _token(token))
    return status == 204


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth")

    p_list = sub.add_parser("list")
    p_list.add_argument("--category")
    p_list.add_argument("--location")
    p_list.add_argument("--updated-after")

    p_get = sub.add_parser("get")
    p_get.add_argument("doc_id")

    args = ap.parse_args()
    try:
        if args.cmd == "auth":
            print("authenticated" if auth() else "auth_failed")
            return 0
        if args.cmd == "list":
            items = reader_list_all(category=args.category, location=args.location,
                                     updated_after=args.updated_after)
            print(json.dumps(items, indent=2))
            return 0
        if args.cmd == "get":
            print(json.dumps(reader_get(args.doc_id), indent=2))
            return 0
    except NoTokenConfigured as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ReadwiseAPIError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(_main())
