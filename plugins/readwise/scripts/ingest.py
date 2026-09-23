#!/usr/bin/env python3
"""Ingest: every Reader library item not yet in the vault becomes a capture in 01_Capture/.

    uv run --project plugins/readwise/scripts python3 plugins/readwise/scripts/ingest.py [--dry-run] [--json]

One run, no agent: windowed fetch since `lastSyncedAt` plus the backlog sweep of new/later/
shortlist, every location but `feed`. An `rss` item (a feed item) is ingested only when the radar
promoted it (tag `radar`); the radar archives every feed item it has judged, and those are not
clips. Each capture records its provenance (`via`):

  clip        the owner saved it              distill never drops it
  newsletter  delivered by email              distill may drop it
  radar       promoted by the radar           distill may drop it; `radar_interests` say why

Dedup: `00_Memory/readwise-ingested.jsonl` (every doc id ever ingested or found in the vault),
plus existing captures in 01_Capture/ and 05_Archive/, plus any note whose `source` is the item's
address (already distilled). Nothing in Reader is moved or deleted: Later stays the owner's
reading queue. A coverage gap (an item fetched but neither written nor recorded) writes one DLQ
note and exits 1; the watermark only moves on a clean run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import build_captures as bc
import readwise_api as rw
from vault_utils import read_frontmatter, require_vault, write_dlq_note, write_frontmatter

STATE_NOTE = Path("00_Memory") / "readwise-state.md"
LEDGER = Path("00_Memory") / "readwise-ingested.jsonl"
SWEEP_LOCATIONS = ("new", "later", "shortlist")
FIRST_SYNC_DAYS = 30
GET_DELAY_S = 3.1  # Reader's list endpoint (which reader_get uses) allows 20 requests a minute
MAX_429_RETRIES = 4
TRACKING = re.compile(r"^(utm_|ref$|ref_src$|s$|t$|si$|fbclid$|gclid$|mc_)")
NOT_CONTENT = {".obsidian", ".trash", ".git", ".smart-env", "00_Memory"}


def norm_url(url: str) -> str:
    """Scheme-, www-, trailing-slash- and tracking-parameter-insensitive address."""
    if not url or not url.startswith("http"):
        return ""
    s = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(s.query) if not TRACKING.match(k)])
    host = s.netloc.lower().removeprefix("www.").replace("mobile.twitter.com", "x.com").replace("twitter.com", "x.com")
    return urlunsplit(("", host, s.path.rstrip("/"), query, "")).lstrip("/")


def tag_names(item: dict) -> list[str]:
    tags = item.get("tags") or {}
    if isinstance(tags, dict):
        return [str(k) for k in tags]
    return [str(t.get("name") if isinstance(t, dict) else t) for t in tags]


def provenance(item: dict) -> dict[str, Any]:
    names = tag_names(item)
    if "radar" in names:
        return {"via": "radar", "radar_interests": sorted(n.split("/", 1)[1] for n in names if n.startswith("radar/"))}
    if item.get("category") == "email":
        return {"via": "newsletter"}
    return {"via": "clip"}


def eligible(item: dict) -> bool:
    if item.get("location") == rw.NOT_A_CLIPPING_LOCATION or item.get("parent_id"):
        return False
    return item.get("category") != "rss" or "radar" in tag_names(item)


def read_ledger(vault: Path) -> dict[str, dict]:
    path = vault / LEDGER
    rows = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    rows[str(r["doc_id"])] = r
                except (json.JSONDecodeError, KeyError):
                    continue
    return rows


def append_ledger(vault: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path = vault / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def vault_index(vault: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(readwise_doc_id -> path, normalised source address -> path) over the whole vault."""
    ids: dict[str, str] = {}
    sources: dict[str, str] = {}
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault)
        if rel.parts and rel.parts[0] in NOT_CONTENT:
            continue
        try:
            fm, _ = read_frontmatter(p)
        except Exception:  # an unreadable note must not stop ingest; vault_yaml_repair reports it
            continue
        if fm.get("readwise_doc_id"):
            ids.setdefault(str(fm["readwise_doc_id"]), rel.as_posix())
        src = fm.get("source")
        for u in src if isinstance(src, list) else [src]:
            if isinstance(u, str) and (n := norm_url(u)):
                sources.setdefault(n, rel.as_posix())
    return ids, sources


def last_synced(vault: Path, now: datetime) -> str:
    path = vault / STATE_NOTE
    if path.is_file():
        fm, _ = read_frontmatter(path)
        if fm.get("lastSyncedAt"):
            return str(fm["lastSyncedAt"])
    return (now - timedelta(days=FIRST_SYNC_DAYS)).isoformat()


def set_last_synced(vault: Path, stamp: str) -> None:
    path = vault / STATE_NOTE
    fm, body = read_frontmatter(path) if path.is_file() else ({}, "\n# Readwise sync state\n")
    fm["lastSyncedAt"] = stamp
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(path, fm, body)


def fetch_full(doc_id: str) -> dict:
    for attempt in range(MAX_429_RETRIES + 1):
        try:
            return rw.reader_get(doc_id)
        except rw.ReadwiseAPIError as e:
            if e.status != 429 or attempt == MAX_429_RETRIES:
                raise
            time.sleep(60)
    raise AssertionError("unreachable")


def ingest(vault: Path, now: datetime, dry_run: bool = False) -> dict[str, Any]:
    since = last_synced(vault, now)
    try:
        items = rw.reader_list_all(updated_after=since)
        for loc in SWEEP_LOCATIONS:
            items += rw.reader_list_all(location=loc)
    except rw.NoTokenConfigured:
        return {"status": "SKIPPED", "detail": "READWISE_TOKEN is not set; nothing fetched"}
    except rw.ReadwiseAPIError as e:
        return {"status": "failed", "detail": f"Reader: {e}"}

    unique = {}
    for it in items:
        if eligible(it):
            unique.setdefault(str(it["id"]), it)
    ledger = read_ledger(vault)
    ids, sources = vault_index(vault)
    new_items, known_rows = [], []
    for doc_id, it in unique.items():
        if doc_id in ledger:
            continue
        where = ids.get(doc_id) or sources.get(norm_url(str(it.get("source_url") or "")))
        if where:
            known_rows.append({"doc_id": doc_id, "found": where, "date": now.date().isoformat()})
        else:
            new_items.append(it)

    result: dict[str, Any] = {"since": since, "fetched": len(items), "eligible": len(unique),
                              "already_in_vault": len(known_rows), "new": len(new_items)}
    if dry_run:
        by_via: dict[str, int] = {}
        for it in new_items:
            v = provenance(it)["via"]
            by_via[v] = by_via.get(v, 0) + 1
        return {**result, "status": "dry-run", "by_via": by_via}

    written, rows, errors = [], [], []
    for n, it in enumerate(new_items):
        if n:
            time.sleep(GET_DELAY_S)
        prov = provenance(it)
        try:
            full = fetch_full(str(it["id"]))
            item = {**it, **{k: v for k, v in full.items() if v not in (None, "")}}
            path, status = bc.write_capture(vault, item, prov)
        except rw.ReadwiseAPIError as e:
            errors.append(f"{it['id']}: {e}"[:200])
            continue
        capture = path.relative_to(vault).as_posix() if path else ids.get(str(it["id"]), "")
        rows.append({"doc_id": str(it["id"]), "capture": capture, "via": prov["via"], "date": now.date().isoformat()})
        if status == "written":
            written.append({"capture": capture, "via": prov["via"]})

    append_ledger(vault, known_rows + rows)
    missing = sorted({str(it["id"]) for it in new_items} - {r["doc_id"] for r in rows})
    result |= {"written": len(written), "by_via": {v: sum(1 for w in written if w["via"] == v) for v in ("clip", "newsletter", "radar")},
               "captures": [w["capture"] for w in written]}
    if missing:
        dlq = write_dlq_note(
            vault, slug=f"readwise-ingest-gap-{now.strftime('%Y%m%d-%H%M')}",
            title=f"Readwise ingest left {len(missing)} item(s) uncaptured",
            what_happened=f"Fetched but not written: {', '.join(missing[:20])}. Errors: {'; '.join(errors[:3])}",
            why_recorded="Every clipping must become a capture; the watermark was not moved, so the next run retries them.",
            resolution="Usually a transient API error: the next run picks them up. If one keeps failing, check it in Reader.",
            confidence="high")
        return {**result, "status": "failed", "missing": missing, "dlq": str(dlq)}
    set_last_synced(vault, now.isoformat())
    return {**result, "status": "ok"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest every new Reader library item as a capture")
    ap.add_argument("--dry-run", action="store_true", help="count what would be captured, write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    result = ingest(require_vault(), datetime.now(UTC), args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['status'].upper()}  " + (result.get("detail") or ", ".join(
            f"{k}={v}" for k, v in result.items() if k not in ("status", "captures"))))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
