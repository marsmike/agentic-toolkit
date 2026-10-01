"""The day in the owner's bubbles: `00_Memory/radar/Bubbles-<YYYY-MM-DD>.md`, rebuilt every scan.

The notes are the deep layer; this is the weighted selection to read in two minutes. Bubbles
come heaviest first (their weight from `allocation.json`), each with what the radar promoted
today (★ must-see, → the note it became once distilled), what it is holding for a later run,
and what it missed (held HOLD_DAYS and never promoted, or left the sensor window unpromoted).
Must-see events lead the page with how many outlets carried them. The daily note embeds it.
[earned: 2026-09-30 — the owner: "a weighted selection of what happened in my bubbles"]

Reads only the radar's own files (`promoted.jsonl`, `promote_hold.jsonl`, `missed.jsonl`,
`allocation.json`) and the vault's sources; nothing leaves the machine.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from interests import Interest

HELD_SHOWN = 5


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        pass
    return rows


def _link(title: str, url: str) -> str:
    title = (title or url or "").replace("[", "(").replace("]", ")").replace("\n", " ").strip()
    return f"[{title}]({url})" if url else title


def _tail(note: str | None) -> str:
    """Where a promoted item is now: its note (02–04 only; the archive is never linked), the inbox
    waiting for distill, or archived without a note of its own (dropped, or merged under another)."""
    if not note:
        return ""
    if note.startswith("01_Capture/"):
        return " · queued for distill"
    if note.startswith("05_Archive/"):
        return " · archived"
    return f" → [[{note[:-3] if note.endswith('.md') else note}]]"


ACTIVE = ("02_Projects/", "03_Areas/", "04_Resources/")


def note_index(vault: Path, urls: dict[str, str] | None = None) -> dict[str, str]:
    """canonical source → the note that holds it: a note in 02–04 by its `source` or any of its
    `sources` (an enrichment adds the item there), else the capture in the inbox or archive.
    With `urls`, also canonical → the address as written there: the link for a promotion
    recorded before its row carried `url` (the canonical key is lower-cased, and a path is not
    always case-insensitive). [earned: 2026-10-01 — a Reuters link on TradingView, lower-cased
    from its key, was a 404 in the briefing]"""
    from radar import _canonical, contained, read_frontmatter  # lazy: radar imports this module

    index: dict[str, str] = {}
    for path in contained(vault.rglob("*.md"), vault):
        rel = path.relative_to(vault).as_posix()
        if not rel.startswith(ACTIVE + ("01_Capture/", "05_Archive/")):
            continue
        try:
            fm, _ = read_frontmatter(path)
        except OSError:
            continue
        found = []
        for key in ("source", "sources"):
            v = fm.get(key)
            found += v if isinstance(v, list) else [v]
        for src in found:
            if isinstance(src, str) and src.startswith("http"):
                c = _canonical(src)
                if c not in index or (rel.startswith(ACTIVE) and not index[c].startswith(ACTIVE)):
                    index[c] = rel
                if urls is not None:
                    urls.setdefault(c, src.strip())
    return index


OTHER = "other"


def bubble_index(out: Path) -> dict[str, str]:
    """canonical → the interest it was strongest for, from the radar's own judgments (the feed's
    state.jsonl, the sensor day files): a promotion recorded before rows carried `bubble` still
    lands in its bubble."""
    import re

    index: dict[str, str] = {}
    for r in _read_jsonl(out / "state.jsonl"):
        p = r.get("p") or {}
        if r.get("canonical") and p:
            index[r["canonical"]] = max(p, key=p.get)
        if r.get("canonical") and r.get("title"):
            index["title:" + r["canonical"]] = str(r["title"])
    for path in sorted((out / "sensors").glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8")).get("items") or {}
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        for it in items.values():
            p = (it or {}).get("p") or {}
            url = str((it or {}).get("url") or "")
            key = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
            if url and p:
                index.setdefault(key, max(p, key=p.get))
            if url and it.get("title"):
                index.setdefault("title:" + key, str(it["title"]))
    return index


def render(day: str, interests: list[Interest], alloc: dict[str, Any], promoted: list[dict], held: list[dict],
           missed: list[dict], notes: dict[str, str], now: datetime, index: dict[str, str] | None = None,
           urls: dict[str, str] | None = None) -> str:
    names = {i.id: i.name for i in interests} | {OTHER: "Other"}
    index = index or {}
    urls = urls or {}

    def url_of(r: dict) -> str:
        """The address as saved: the row's own, else as the vault wrote it, else the canonical key."""
        c = r.get("canonical", "")
        return r.get("url") or urls.get(c) or (f"https://{c}" if c else "")

    for r in promoted + held + missed:
        if not r.get("bubble"):
            r["bubble"] = index.get(r.get("canonical", "")) or index.get(r.get("google_news", "")) or OTHER
        if not r.get("title"):
            r["title"] = index.get("title:" + r.get("canonical", "")) or index.get("title:" + r.get("google_news", "")) or ""
    weights: dict[str, float] = alloc.get("weights") or {}
    total = sum(weights.values()) or 1.0
    today = [r for r in promoted if r.get("date") == day]
    missed_today = [r for r in missed if r.get("missed") == day]
    events = {e["key"]: e for e in alloc.get("events") or []}
    order = sorted(set(weights) | {r.get("bubble") for r in today + held + missed_today if r.get("bubble")},
                   key=lambda b: -weights.get(b, 0.0))
    lines = ["---", f"description: \"Bubbles {day}: {len(today)} promoted, {len(held)} held, "
             f"{len(missed_today)} missed across {sum(1 for b in order if any(r.get('bubble') == b for r in today))} bubbles.\"",
             "status: active", f"created: {day}", "tags:", "  - domain/toolkit-meta", "---", "",
             f"# Bubbles {day}", "",
             f"*Rebuilt {now.strftime('%H:%M')} UTC by the radar scan. ★ must-see · → the note it became · "
             "held items go first next run.*", ""]
    must = [r for r in today if r.get("must_see")] + [r for r in held if r.get("must_see")]
    if must:
        lines += ["## Must-see", ""]
        for r in must:
            ev = events.get(r.get("event") or "", {})
            state = "promoted" if r in today else "held"
            tail = _tail(notes.get(r.get("canonical", "")))
            lines.append(f"- ★ **{ev.get('name') or r.get('title')}** — {_link(r.get('title', ''), url_of(r))} "
                         f"({state}, {names.get(r.get('bubble'), r.get('bubble'))}){tail}")
        lines.append("")
    for b in order:
        got = [r for r in today if r.get("bubble") == b]
        wait = [r for r in held if r.get("bubble") == b]
        lost = [r for r in missed_today if r.get("bubble") == b]
        if not (got or wait or lost):
            continue
        share = weights.get(b, 0.0) / total
        lines += [f"## {names.get(b, b)}", "",
                  f"weight {share:.0%} · {len(got)} promoted · {len(wait)} held · {len(lost)} missed", ""]
        for r in got:
            tail = _tail(notes.get(r.get("canonical", "")))
            star = "★ " if r.get("must_see") else ""
            lines.append(f"- {star}{_link(r.get('title') or r.get('canonical', ''), url_of(r))} — {r.get('source') or r.get('via', 'feed')}{tail}")
        for r in sorted(wait, key=lambda r: -float(r.get("strength") or 0))[:HELD_SHOWN]:
            lines.append(f"- ⏳ {_link(r.get('title', ''), r.get('url', ''))} — {r.get('source', '')}, held since {r.get('first_held')}")
        if len(wait) > HELD_SHOWN:
            lines.append(f"- ⏳ … and {len(wait) - HELD_SHOWN} more held")
        for r in lost:
            lines.append(f"- ✗ {_link(r.get('title', ''), r.get('url', ''))} — missed: {r.get('why', '')}")
        lines.append("")
    if len(lines) < 14:
        lines += ["Nothing promoted, held or missed yet today.", ""]
    return "\n".join(lines)


def write(vault: Path, out: Path, day: str, interests: list[Interest], now: datetime) -> Path:
    from radar import atomic_write  # lazy: radar imports this module

    try:
        alloc = json.loads((out / "allocation.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        alloc = {}
    urls: dict[str, str] = {}
    notes = note_index(vault, urls)
    text = render(day, interests, alloc, _read_jsonl(out / "promoted.jsonl"), _read_jsonl(out / "promote_hold.jsonl"),
                  _read_jsonl(out / "missed.jsonl"), notes, now, bubble_index(out), urls)
    path = out / f"Bubbles-{day}.md"
    atomic_write(path, text)
    return path
