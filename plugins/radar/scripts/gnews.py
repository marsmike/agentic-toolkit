"""Google News links → the publisher's own URL, before anything is saved to Reader.

Google News RSS (the sensor feeds' `when:3d` searches) and Kagi News hand over
`news.google.com/rss/articles/<id>` links. Reader cannot follow one: it saves a document with no
title and no text, ingest writes a capture named "Google News" with a DLQ note, and the second such
capture of a day collides with the first in the archive. [earned: 2026-09-30 — 210 of the day's
989 sensor items were Google News links; two DLQ notes and one failed capture in one day]

An old-format id carries the URL in its base64 payload. A current one (`AU_yqL…`) is resolved the
way the Google News page resolves it: its article page gives a signature and a timestamp, and
`batchexecute` returns the URL for them. `resolve()` never raises: None means "leave it out".

What leaves the machine: the Google News article id, to news.google.com.
"""
from __future__ import annotations

import base64
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

HOST = "news.google.com"
TIMEOUT = 15
# The article page serves its signature only to a browser-like client.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
_ID = re.compile(r"news\.google\.com/(?:rss/)?articles/([A-Za-z0-9_-]+)")


def is_google_news(url: str) -> bool:
    return bool(_ID.search(url or ""))


def _request(url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> str:
    """One HTTP call; the evals replace this."""
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def _from_payload(aid: str) -> str | None:
    """The old format: the URL sits in the decoded id itself."""
    try:
        raw = base64.urlsafe_b64decode(aid + "=" * (-len(aid) % 4))
    except (ValueError, TypeError):
        return None
    if b"AU_yqL" in raw[:12]:
        return None
    m = re.search(rb"https?://[\x21-\x7e]+", raw)
    return m.group(0).decode("ascii") if m else None


def resolve(url: str) -> str | None:
    """The publisher's URL behind a Google News link, or None when it cannot be had."""
    m = _ID.search(url or "")
    if not m:
        return None
    aid = m.group(1)
    direct = _from_payload(aid)
    if direct:
        return direct
    try:
        page = _request(f"https://{HOST}/rss/articles/{aid}")
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="(\d+)"', page)
        if not (sg and ts):
            return None
        inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None,
                                 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts.group(1)), sg.group(1)]
        body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])}).encode()
        text = _request(f"https://{HOST}/_/DotsSplashUi/data/batchexecute", body,
                        {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        payload = json.loads(text.split("\n\n", 1)[1])
        found = json.loads(payload[0][2])[1]
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, IndexError, KeyError, TypeError):
        return None
    return found if isinstance(found, str) and found.startswith("http") and HOST not in found else None
