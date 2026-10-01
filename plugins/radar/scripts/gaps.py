"""Gaps: what the feeds missed. Once a week, recent posts per interest from Kagi's news index,
judged like feed items; the strong ones are the signal that a feed is missing.

    radar.py gaps [--promote] [--json]

For every interest, its first query (or, for an epic with a gloss, its name) goes to Kagi
`enrich/news`; an interest with neither queries nor a gloss is not searched. Results published in
the last 7 days whose address the radar has not seen and the vault does not hold are judged
`worth_reading` per item x interest, exactly as `scan` judges feed items. The week's result is
`00_Memory/radar/gaps-YYYY-Www.json` (run once per ISO week; a second run that week is `exists`)
and a "Found outside your feeds" section in that week's digest, with the sites that carried
strong items as feed candidates for `discover --seed`. With `--promote`, the strong items go
through the scan's own allocation (`radar.allocation_context`, `allocation.Selector`): one run's
`promote_per_run`, must-see events first, a weighted turn for every bubble with its credit
charged, one event one promotion, every source and watched name capped. The chosen are saved to
Reader's Later list tagged `radar` and `radar/<interest>`, so the one pipeline captures and
distills them; the rest wait in the hold file, and the next scans offer them again for HOLD_DAYS.

What leaves the machine: one query per interest to Kagi; titles and snippets of what it found to
the judgment backend; with --promote, the saved addresses to Reader.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import bubbles
import fairness
import gnews
import interests as interests_mod
import judge
import kagi
import reader
import reports
import sensor_promote
from allocation import Cand, Selector
from interests import Interest
from judgments import policy
from judgments.urls import _canonical
from reader import Item
from vault_utils import atomic_write, profile_value

WINDOW_DAYS = 7


def _published(stamp: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def gaps(vault: Path, out: Path, now: datetime, promote: bool = False) -> dict[str, Any]:
    from radar import (  # lazy: radar imports this module
        RunUsage,
        judge_items,
        profile_number,  # lazy: radar imports this module
        read_jsonl,
        vault_sources,
    )

    week = reports.week_of(now.date().isoformat())
    path = out / f"gaps-{week}.json"
    if path.is_file():
        # A truncated write (killed mid-write) is not "done this week" — recompute rather than
        # leave the digest missing its "Found outside your feeds" section forever. [earned:
        # 2026-09-28 week review]
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
        else:
            return {"status": "exists", "week": week, "detail": f"{path.name} already written this week"}
    interests = interests_mod.load(vault)
    if not interests:
        return {"status": "no-interests", "detail": "no interests: set `interests_note` in Config/toolkit/radar.md"}
    reason = judge.unavailable_reason(vault)
    if reason:
        return {"status": "SKIPPED", "detail": f"judgment backend unavailable ({reason}); nothing sent"}
    ledger = kagi.ledger(out, profile_number(vault, "kagi_weekly_budget_usd", kagi.DEFAULT_WEEKLY_BUDGET_USD))

    spent_before = ledger.spent_this_week(now)
    known = {r["canonical"] for r in read_jsonl(out / "seen.jsonl")} | set(vault_sources(vault))
    since = now - timedelta(days=WINDOW_DAYS)
    items: dict[str, Item] = {}
    searched, notes = 0, []
    for it in interests:
        if not it.queries and not it.gloss:
            continue  # nothing to search by but a task title [earned: 2026-09-23, "Archive sweep — let go cleanly" as a query]
        try:
            found = kagi.news(it.queries[0] if it.queries else it.name, ledger, now)
        except kagi.NoKey:
            return {"status": "SKIPPED", "detail": "KAGI_API_KEY is not set; nothing searched"}
        except kagi.OverBudget as e:
            notes.append(str(e))
            break
        except kagi.KagiError as e:
            notes.append(f"kagi: {e}")
            continue
        searched += 1
        for r in found:
            when, canonical = _published(r["published"]), _canonical(r["url"])
            if when is None or when < since or canonical in known or canonical in items:
                continue
            host = urlparse(r["url"]).netloc.lower().removeprefix("www.")
            items[canonical] = Item(id=f"kagi:{canonical}", url=r["url"], canonical=canonical, title=r["title"],
                                    summary=r["snippet"][:600], site=host, feed=host, published=r["published"][:10],
                                    category="", saved_at=now.isoformat())
    listed = list(items.values())
    run = RunUsage()
    judged = judge_items(vault, listed, interests, run) if listed else {}
    t = policy.thresholds(run.backend or judge.load_config(vault)["backend"])
    rows = []
    for n, it in enumerate(listed):
        if n not in judged:
            continue
        p = judged[n]["p"]
        rows.append({"title": it.title, "url": it.url, "canonical": it.canonical, "site": it.site, "published": it.published,
                     "kind": judged[n]["kind"], "p": p, "backend": run.backend,
                     "worth": sorted(i for i, v in p.items() if v >= t["T_WORTH"]),
                     "strong": sorted(i for i, v in p.items() if v >= t["T_STRONG"])})
    rows.sort(key=lambda r: -max(r["p"].values()))
    strong = [r for r in rows if r["strong"]]
    sites = Counter(r["site"] for r in strong)

    result: dict[str, Any] = {"status": "ok", "week": week, "searched": searched, "found": len(listed),
                              "judged": len(rows), "strong": len(strong), "notes": notes,
                              "kagi_usd": round(ledger.spent_this_week(now) - spent_before, 4),
                              "judgment_usd": round(run.usd, 5)}
    if promote and strong:
        result |= _promote(out, strong, interests, now, vault)
    out.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps({"week": week, "rows": rows, "sites": sites.most_common(), **{k: result[k] for k in (
        "searched", "found", "strong")}}, indent=2, ensure_ascii=False) + "\n")
    return {**result, "file": str(path)}


def candidate(r: dict, evs: list, pattern) -> Cand:
    """A strong gap row (or a held one, which keeps only its strong interests' p) as an allocation
    candidate: its bubble, its event (`bubbles.event_of`) and the watched names in its title."""
    from radar import release_stream  # lazy: radar imports this module

    strong = r.get("strong")
    p = {i: float(v) for i, v in (r.get("p") or {}).items() if not strong or i in strong}
    url, title = str(r["url"]), str(r.get("title") or "")
    ev = bubbles.event_of(title, evs)
    return Cand(kind="gap", key=str(r["canonical"]), title=title, url=url,
                source=str(r.get("site") or r.get("source") or urlparse(url).netloc.lower().removeprefix("www.")),
                p=p, bubble=fairness.top_interest(p), strength=max(p.values(), default=0.0),
                last_choice=sensor_promote.last_choice(url), event=ev.key if ev else None,
                event_name=ev.name if ev else None, must_see=bool(ev and ev.must_see),
                stream=release_stream(str(r["canonical"])),
                names=frozenset(sensor_promote.named(title, pattern)), ref=r)


def held_candidates(out: Path, run_date: str, exclude: set[str], evs: list, pattern) -> list[Cand]:
    """The gap rows the hold file keeps (strong, but a weekly run had no slot for them), for the
    scan to offer again until HOLD_DAYS pass; none already promoted, held by the vault or in
    `exclude`."""
    from radar import HOLD_FILE, read_jsonl  # lazy: radar imports this module

    limit = (date.fromisoformat(run_date) - timedelta(days=policy.HOLD_DAYS)).isoformat()
    return [candidate(r, evs, pattern) for r in read_jsonl(out / HOLD_FILE)
            if r.get("kind") == "gap" and r.get("canonical") and r.get("url") and r.get("p")
            and r["canonical"] not in exclude and str(r.get("first_held", run_date)) > limit]


def save(c: Cand, out: Path, run_date: str, location: str, names: dict[str, str], stats: dict[str, Any]) -> bool:
    """Save one gap candidate to Reader (a Google News link as the publisher's URL, or not at all);
    one `promoted.jsonl` row with `via: gaps` and the address it was saved under."""
    from radar import append_jsonl  # lazy: radar imports this module

    url, canonical, google_news = c.url, c.key, None
    if gnews.is_google_news(url):
        google_news, url = canonical, gnews.resolve(url) or ""
        if not sensor_promote.usable(url):
            stats["unresolved"] = stats.get("unresolved", 0) + 1
            return False
        canonical = _canonical(url)
    note = f"[radar gap {run_date}] " + "; ".join(f"{names.get(i, i)} p={v:.2f}" for i, v in sorted(c.p.items()))
    try:
        doc_id = reader.save(url, location, ["radar", *(f"radar/{i}" for i in sorted(c.p))], note)
    except (reader.ReaderError, ValueError) as e:
        stats.setdefault("errors", []).append(str(e)[:120])
        return False
    append_jsonl(out / "promoted.jsonl", [{
        "canonical": canonical, "id": doc_id, "date": run_date, "via": "gaps", "url": url, "title": c.title,
        "source": c.source, "bubble": c.bubble, **({"event": c.event} if c.event else {}),
        **({"must_see": True} if c.must_see else {}), **({"google_news": google_news} if google_news else {})}])
    return True


def _promote(out: Path, strong: list[dict], interests: list[Interest], now: datetime, vault: Path) -> dict:
    """The week's strong items through the scan's allocation: one run's `promote_per_run`, must-see
    first, a weighted turn per bubble with its credit charged, every source, watched name and
    event capped. What is not taken waits in the hold file for the next scans.
    [earned: 2026-10-01 review — gaps saved its strongest 25 with no weights, caps or credit, and
    held nothing]"""
    from radar import allocation_context, read_jsonl, release_stream, save_allocation, write_hold  # lazy

    run_date = now.date().isoformat()
    ctx = allocation_context(vault, out, interests, run_date, now)
    done = read_jsonl(out / "promoted.jsonl")
    already = {r["canonical"] for r in done} | {r["google_news"] for r in done if r.get("google_news")}
    since = (now.date() - timedelta(days=policy.RELEASE_STREAM_DAYS)).isoformat()
    streams = {release_stream(r["canonical"]) for r in done if str(r.get("date", "")) > since} - {None}
    b_n, e_n, n_n = ctx["today"]
    sel = Selector([candidate(r, ctx["evs"], ctx["pattern"]) for r in strong if r["canonical"] not in already],
                   ctx["per_run"], ctx["credit"], caps=ctx["caps"], today_bubbles=b_n, today_events=e_n,
                   today_names=n_n, streams_taken=streams)
    location = str(profile_value(vault, "promote_location", "later"))
    names = {i.id: i.name for i in interests}
    stats: dict[str, Any] = {}
    sel.run(lambda c: save(c, out, run_date, location, names, stats))
    write_hold(out, run_date, sel.held(), already | {c.key for c in sel.taken}, kinds={"gap"})
    save_allocation(out, run_date, now, ctx, sel.credit)
    held = len(sel.held())
    return {"promoted": len(sel.taken), **({"held": held} if held else {}),
            **({"unresolved": stats["unresolved"]} if stats.get("unresolved") else {}),
            **({"promote_errors": stats["errors"]} if stats.get("errors") else {})}


def load_week(out: Path, week: str) -> dict | None:
    path = out / f"gaps-{week}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except json.JSONDecodeError:
        return None
