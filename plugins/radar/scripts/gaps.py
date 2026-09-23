"""Gaps: what the feeds missed. Once a week, recent posts per interest from Kagi's news index,
judged like feed items; the strong ones are the signal that a feed is missing.

    radar.py gaps [--promote] [--json]

For every interest, its first query (or its name) goes to Kagi `enrich/news`; results published in
the last 7 days whose address the radar has not seen and the vault does not hold are judged
`worth_reading` per item x interest, exactly as `scan` judges feed items. The week's result is
`00_Memory/radar/gaps-YYYY-Www.json` (run once per ISO week; a second run that week is `exists`)
and a "Found outside your feeds" section in that week's digest, with the sites that carried
strong items as feed candidates for `discover --seed`. With `--promote`, the strongest strong
items are saved to Reader's Later list tagged `radar` and `radar/<interest>`, within the same daily
promotion budget as `scan`, so the one pipeline captures and distills them.

What leaves the machine: one query per interest to Kagi; titles and snippets of what it found to
the judgment backend; with --promote, the saved addresses to Reader.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import interests as interests_mod
import judge
import kagi
import reader
import reports
from judgments import policy
from judgments.urls import _canonical
from reader import Item
from vault_utils import profile_value

WINDOW_DAYS = 7


def _published(stamp: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def gaps(vault: Path, out: Path, now: datetime, promote: bool = False) -> dict[str, Any]:
    from radar import RunUsage, judge_items, read_jsonl, vault_sources  # lazy: radar imports this module

    week = reports.week_of(now.date().isoformat())
    path = out / f"gaps-{week}.json"
    if path.exists():
        return {"status": "exists", "week": week, "detail": f"{path.name} already written this week"}
    interests = interests_mod.load(vault)
    if not interests:
        return {"status": "no-interests", "detail": "no interests: set `interests_note` in Config/toolkit/radar.md"}
    reason = judge.unavailable_reason(vault)
    if reason:
        return {"status": "SKIPPED", "detail": f"judgment backend unavailable ({reason}); nothing sent"}
    ledger = kagi.Ledger(out / "kagi-ledger.jsonl",
                         float(profile_value(vault, "kagi_weekly_budget_usd", kagi.DEFAULT_WEEKLY_BUDGET_USD)))

    spent_before = ledger.spent_this_week(now)
    known = {r["canonical"] for r in read_jsonl(out / "seen.jsonl")} | set(vault_sources(vault))
    since = now - timedelta(days=WINDOW_DAYS)
    items: dict[str, Item] = {}
    searched, notes = 0, []
    for it in interests:
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
        result |= _promote(out, strong, {i.id: i.name for i in interests}, now, vault)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"week": week, "rows": rows, "sites": sites.most_common(), **{k: result[k] for k in (
        "searched", "found", "strong")}}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {**result, "file": str(path)}


def _promote(out: Path, strong: list[dict], names: dict[str, str], now: datetime, vault: Path) -> dict:
    """Save the strongest to Reader within what is left of the day's promotion budget."""
    from radar import append_jsonl, read_jsonl

    run_date = now.date().isoformat()
    ledger = out / "promoted.jsonl"
    done = read_jsonl(ledger)
    budget = max(0, policy.PROMOTE_PER_DAY - sum(1 for r in done if r.get("date") == run_date))
    already = {r["canonical"] for r in done}
    location = str(profile_value(vault, "promote_location", "later"))
    saved, errors = 0, []
    for r in [r for r in strong if r["canonical"] not in already][:budget]:
        p = {i: r["p"][i] for i in r["strong"]}
        note = f"[radar gap {run_date}] " + "; ".join(f"{names.get(i, i)} p={v:.2f}" for i, v in sorted(p.items()))
        try:
            doc_id = reader.save(r["url"], location, ["radar", *(f"radar/{i}" for i in sorted(p))], note)
        except reader.ReaderError as e:
            errors.append(str(e)[:120])
            continue
        append_jsonl(ledger, [{"canonical": r["canonical"], "id": doc_id, "date": run_date, "via": "gaps"}])
        saved += 1
    return {"promoted": saved, **({"promote_errors": errors} if errors else {})}


def load_week(out: Path, week: str) -> dict | None:
    path = out / f"gaps-{week}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except json.JSONDecodeError:
        return None
