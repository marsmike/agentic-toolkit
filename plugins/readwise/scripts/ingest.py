#!/usr/bin/env python3
"""Ingest: every Reader library item not yet in the vault becomes a capture in 01_Capture/.

    uv run --project plugins/readwise/scripts python3 plugins/readwise/scripts/ingest.py [--dry-run] [--json]

One run, no agent: windowed fetch since `lastSyncedAt` plus the backlog sweep of new/later/
shortlist, every location but `feed`. Both look back WINDOW_DAYS (four weeks) at most: an item saved
earlier is out of scope, however long it has waited in Later. An `rss` item (a feed item) is ingested only when the radar
promoted it (tag `radar`); the radar archives every feed item it has judged, and those are not
clips. Each capture records its provenance (`via`):

  clip        the owner saved it              distill never drops it
  newsletter  an email from a newsletter sender  distill may drop it (profile `newsletter_senders`,
                                              default Readwise; every other email is a clip)
  radar       promoted by the radar           distill may drop it; `radar_interests` say why

Dedup: `00_Memory/readwise-ingested.jsonl` (every doc id ever ingested or found in the vault),
plus existing captures in 01_Capture/ and 05_Archive/, plus any note whose `source` is the item's
address (already distilled). Nothing in Reader is deleted. An item is archived in Reader only
once its capture is settled on the remote (`archive_settled`): retired to 05_Archive/ in the
upstream branch, so the run after the one that distilled it. A coverage gap (an item fetched but neither written nor recorded) writes one DLQ
note and exits 1; the watermark only moves on a clean run.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import build_captures as bc
import readwise_api as rw
from vault_utils import contained, profile_value, read_frontmatter, require_vault, write_dlq_note, write_frontmatter

STATE_NOTE = Path("00_Memory") / "readwise-state.md"
LEDGER = Path("00_Memory") / "readwise-ingested.jsonl"
ARCHIVED = Path("00_Memory") / "readwise-archived.jsonl"
ARCHIVE_PER_RUN = 60    # Reader's update endpoint allows 50 requests a minute; GET_DELAY_S paces them
SWEEP_LOCATIONS = ("new", "later", "shortlist")
WINDOW_DAYS = 28  # the owner's scope: the last four weeks [earned: 2026-09-24, owner's request]
GET_DELAY_S = 3.1  # Reader's list endpoint (which reader_get uses) allows 20 requests a minute
MAX_429_RETRIES = 4
RETRY_429_S = 15.0
TRACKING = re.compile(r"^(utm_|ref$|ref_src$|s$|t$|si$|fbclid$|gclid$|mc_)")
DEFAULT_NEWSLETTER_SENDERS = ("Readwise",)  # emails from these may be dropped by distill; all others are clips
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


def newsletter_senders(vault: Path | None) -> tuple[str, ...]:
    """Senders whose emails are newsletters (profile `newsletter_senders`, a list or a comma list)."""
    raw = profile_value(vault, "newsletter_senders", None) if vault is not None else None
    if isinstance(raw, str):
        raw = [s for s in (p.strip() for p in raw.split(",")) if s]
    return tuple(str(s) for s in raw) if raw else DEFAULT_NEWSLETTER_SENDERS


def provenance(item: dict, senders: tuple[str, ...] = DEFAULT_NEWSLETTER_SENDERS) -> dict[str, Any]:
    """How the item reached the library. An email is a clip unless its sender (`author`) is a
    known newsletter: the owner forwards emails on purpose, and only a newsletter may be dropped
    by distill. [earned: 2026-09-24 — every email was `newsletter`, so a forwarded one could be
    discarded]"""
    names = tag_names(item)
    if "radar" in names:
        return {"via": "radar", "radar_interests": sorted(n.split("/", 1)[1] for n in names if n.startswith("radar/"))}
    if item.get("category") == "email":
        sender = str(item.get("author") or "").casefold()
        if sender and any(s.casefold() in sender for s in senders):
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
    for p in contained(vault.rglob("*.md"), vault):
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
            return max(str(fm["lastSyncedAt"]), window_start(now), key=_utc)
    return window_start(now)


def window_start(now: datetime) -> str:
    return (now - timedelta(days=WINDOW_DAYS)).isoformat()


def in_window(item: dict, start: str) -> bool:
    """Saved within the window; an item without a date is kept (it cannot be judged old)."""
    saved = str(item.get("saved_at") or item.get("created_at") or "")
    return not saved or _utc(saved) >= _utc(start)


def _utc(stamp: str) -> datetime:
    t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def set_last_synced(vault: Path, stamp: str) -> None:
    path = vault / STATE_NOTE
    fm, body = read_frontmatter(path) if path.is_file() else ({}, "\n# Readwise sync state\n")
    fm["lastSyncedAt"] = stamp
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frontmatter(path, fm, body)


def _patient(call, *args, **kwargs):
    """Retry a Reader call on 429: the list endpoint allows 20 requests a minute, and a run makes
    several list calls back to back [earned: 2026-09-23, first run against the real account]."""
    for attempt in range(MAX_429_RETRIES + 1):
        try:
            return call(*args, **kwargs)
        except rw.ReadwiseAPIError as e:
            if e.status != 429 or attempt == MAX_429_RETRIES:
                raise
            time.sleep(RETRY_429_S * (attempt + 1))
    raise AssertionError("unreachable")


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def ingest_highlights(vault: Path, items: list[dict], ledger: dict[str, dict], ids: dict[str, str],
                      sources: dict[str, str], now: datetime, dry_run: bool = False) -> tuple[list[dict], dict]:
    """Every Reader highlight or note the owner made that the vault doesn't have yet becomes part of a
    highlights capture, one per document, whatever its age: they are the owner's own words. A
    highlight whose text is already in the vault is recorded, not captured again. Returns (ledger
    rows, summary). [earned: 2026-09-25 correction run — ingest skipped every child of a document;
    101 of 123 highlights had never reached the vault]"""
    # All of them, not only this sync's window: an old highlight is still the owner's.
    listed = {str(i["id"]): i for i in items}
    try:
        for category in ("highlight", "note"):
            time.sleep(GET_DELAY_S)
            listed.update({str(i["id"]): i for i in _patient(rw.reader_list_all, category=category)})
    except rw.ReadwiseAPIError as e:  # the clippings are captured already; highlights wait for the next run
        return [], {"highlights": "failed", "detail": str(e)[:200]}
    kids = [i for i in listed.values() if i.get("parent_id") and i.get("category") in ("highlight", "note")
            and str(i["id"]) not in ledger]
    if not kids:
        return [], {"highlights": 0}
    corpus = " ".join(_norm_text(p.read_text(encoding="utf-8", errors="replace"))
                      for p in contained(vault.rglob("*.md"), vault) if p.is_file() and "/.obsidian/" not in p.as_posix())
    today, rows = now.date().isoformat(), []
    todo: dict[str, list[dict]] = {}
    for k in kids:
        text = _norm_text(k.get("content") or k.get("notes") or "")[:80]
        if text and text in corpus:
            rows.append({"doc_id": str(k["id"]), "highlight_of": str(k["parent_id"]), "found": "text in the vault", "date": today})
        else:
            todo.setdefault(str(k["parent_id"]), []).append(k)
    summary = {"highlights": len(kids), "already_in_vault": len(rows), "captures": 0}
    if dry_run:
        return [], {**summary, "would_capture": sum(len(v) for v in todo.values())}
    by_id = listed
    for n, (parent_id, hls) in enumerate(todo.items()):
        parent = by_id.get(parent_id)
        if parent is None:
            if n:
                time.sleep(GET_DELAY_S)
            try:
                parent = fetch_full(parent_id)
            except rw.ReadwiseAPIError:
                parent = {"id": parent_id}
        address = norm_url(str(parent.get("source_url") or ""))
        where = (ledger.get(parent_id) or {}).get("capture") or ids.get(parent_id) or sources.get(address) or ""
        path = bc.write_highlights_capture(vault, parent, hls, where)
        capture = path.relative_to(vault).as_posix()
        rows += [{"doc_id": str(h["id"]), "capture": capture, "via": "clip", "highlight_of": parent_id, "date": today}
                 for h in hls]
        summary["captures"] += 1
    return rows, summary


def fetch_full(doc_id: str) -> dict:
    return _patient(rw.reader_get, doc_id)


def _pushed_paths(vault: Path) -> set[str] | None:
    """Every file in the upstream branch's tree (what is on the remote, not just committed here);
    None without git or an upstream, since nothing then proves a file has left this machine."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, check=False)
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0 or not upstream.stdout.strip():
        return None
    tree = git("ls-tree", "-r", "--name-only", upstream.stdout.strip())
    return set(tree.stdout.splitlines()) if tree.returncode == 0 else None


def archive_settled(vault: Path, now: datetime, dry_run: bool = False) -> dict[str, Any]:
    """Archive in Reader every clipping whose capture is settled in the vault on the remote: retired
    to `05_Archive/` as `<stem>--FULLCAPTURE.md` (distilled, or dropped by distill's rules), or
    found already in the vault at ingest. Copies of a settled page go with it. Settled means in the
    upstream branch's tree, so it happens the run after the one that distilled it, never before
    the push. Each archive is a row in `00_Memory/readwise-archived.jsonl`; an item Reader no longer
    has is recorded as `gone`. Never deletes. [earned: 2026-09-25, owner's request — archive the
    clippings once they are definitely in the vault]"""
    pushed = _pushed_paths(vault)
    if pushed is None:
        return {"status": "skipped", "detail": "no git upstream: nothing proves a capture reached the remote"}
    done = set()
    path = vault / ARCHIVED
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(str(json.loads(line)["doc_id"]))
            except (json.JSONDecodeError, KeyError):
                continue
    retired = {Path(p).name.removesuffix("--FULLCAPTURE.md"): p for p in pushed
               if p.startswith("05_Archive/") and p.endswith("--FULLCAPTURE.md")}
    ledger = read_ledger(vault)
    settled: list[str] = []
    for doc_id, row in ledger.items():
        # A highlight is the owner's mark on a document, never archived on its own.
        if doc_id in done or "duplicate_of" in row or "highlight_of" in row:
            continue
        capture, found = row.get("capture") or "", row.get("found") or ""
        if (capture and Path(capture).stem in retired) or (found and found in pushed):
            settled.append(doc_id)
    # A copy follows its original even when the original was archived by an earlier run.
    # [earned: 2026-09-25, Copilot review of PR #34 — past the per-run cap a copy was skipped forever]
    roots = set(settled) | done
    settled += [d for d, r in ledger.items() if d not in done and r.get("duplicate_of") in roots]
    todo = settled[:ARCHIVE_PER_RUN]
    if dry_run:
        return {"status": "dry-run", "would_archive": len(settled)}
    rows, errors = [], []
    for n, doc_id in enumerate(todo):
        if n:
            time.sleep(GET_DELAY_S)
        try:
            _patient(rw.reader_archive, doc_id)
            rows.append({"doc_id": doc_id, "archived": now.date().isoformat()})
        except rw.NoTokenConfigured:
            return {"status": "SKIPPED", "detail": "READWISE_TOKEN is not set; nothing archived"}
        except rw.ReadwiseAPIError as e:
            if e.status == 404:
                rows.append({"doc_id": doc_id, "gone": now.date().isoformat()})
            else:
                errors.append(f"{doc_id}: {e}"[:200])
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    return {"status": "ok" if not errors else "partial", "archived": sum("archived" in r for r in rows),
            "gone": sum("gone" in r for r in rows), "left": len(settled) - len(todo), "errors": errors[:3]}


def ingest(vault: Path, now: datetime, dry_run: bool = False) -> dict[str, Any]:
    since = last_synced(vault, now)
    try:
        items = _patient(rw.reader_list_all, updated_after=since)
        for loc in SWEEP_LOCATIONS:
            time.sleep(GET_DELAY_S)
            items += _patient(rw.reader_list_all, location=loc)
    except rw.NoTokenConfigured:
        return {"status": "SKIPPED", "detail": "READWISE_TOKEN is not set; nothing fetched"}
    except rw.ReadwiseAPIError as e:
        return {"status": "failed", "detail": f"Reader: {e}"}

    unique = {}
    start = window_start(now)
    for it in items:
        if eligible(it) and in_window(it, start):
            unique.setdefault(str(it["id"]), it)
    ledger = read_ledger(vault)
    senders = newsletter_senders(vault)
    ids, sources = vault_index(vault)
    new_items, known_rows = [], []
    # One page saved twice in Reader is one capture: the first save of an address is the item, the
    # others are its copies, tried in turn if it cannot be fetched. [earned: 2026-09-23 — one tweet
    # saved as twitter.com/… and x.com/…?s=12 became two captures]
    batch: dict[str, str] = {}
    copies: dict[str, list[dict]] = {}
    for doc_id, it in unique.items():
        if doc_id in ledger:
            continue
        address = norm_url(str(it.get("source_url") or ""))
        where = ids.get(doc_id) or sources.get(address)
        if where:
            known_rows.append({"doc_id": doc_id, "found": where, "date": now.date().isoformat()})
        elif address and address in batch:
            copies[batch[address]].append(it)
        else:
            if address:
                batch[address] = doc_id
            copies[doc_id] = []
            new_items.append(it)

    result: dict[str, Any] = {"since": since, "fetched": len(items), "eligible": len(unique),
                              "already_in_vault": len(known_rows), "new": len(new_items),
                              "duplicates": sum(len(c) for c in copies.values())}
    if dry_run:
        by_via: dict[str, int] = {}
        for it in new_items:
            v = provenance(it, senders)["via"]
            by_via[v] = by_via.get(v, 0) + 1
        return {**result, "status": "dry-run", "by_via": by_via}

    written, rows, errors, missing = [], [], [], []
    today = now.date().isoformat()
    for n, it in enumerate(new_items):
        if n:
            time.sleep(GET_DELAY_S)
        saves = [it, *copies[str(it["id"])]]
        for cand in saves:
            prov = provenance(cand, senders)
            try:
                full = fetch_full(str(cand["id"]))
                item = {**cand, **{k: v for k, v in full.items() if v not in (None, "")}}
                path, status = bc.write_capture(vault, item, prov)
                break
            except rw.ReadwiseAPIError as e:
                errors.append(f"{cand['id']}: {e}"[:200])
        else:
            # No save of this page could be captured: nothing is settled, the next run tries again.
            missing.append(str(it["id"]))
            continue
        capture = path.relative_to(vault).as_posix() if path else ids.get(str(cand["id"]), "")
        rows.append({"doc_id": str(cand["id"]), "capture": capture, "via": prov["via"], "date": today})
        rows += [{"doc_id": str(o["id"]), "duplicate_of": str(cand["id"]), "date": today} for o in saves if o is not cand]
        if status == "written":
            written.append({"capture": capture, "via": prov["via"]})

    hl_rows, hl_summary = ingest_highlights(vault, items, ledger, ids, sources, now)
    append_ledger(vault, known_rows + rows + hl_rows)
    result["highlights"] = hl_summary
    missing.sort()
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
    vault, now = require_vault(), datetime.now(UTC)
    result = ingest(vault, now, args.dry_run)
    if result["status"] != "SKIPPED":
        result["reader_archive"] = archive_settled(vault, now, args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['status'].upper()}  " + (result.get("detail") or ", ".join(
            f"{k}={v}" for k, v in result.items() if k not in ("status", "captures"))))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
