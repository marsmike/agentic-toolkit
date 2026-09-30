"""Promote sensor items: the news the Signal Radar's sensors saw becomes captures, not only momentum.

`scan --promote` calls `promote()` before it settles the feed. It reads the sensor day files of the
last SENSOR_PROMOTE_WINDOW_DAYS (`sensors/YYYY-MM-DD.json`, written by the Signal Radar routine;
read only here, so the two-writer table holds) and saves to Reader Later, where the pipeline's
ingest turns them into captures, every item from SENSOR_PROMOTE_SOURCES that is one of:

1. a lab's own announcement (`policy.LAB_ANNOUNCEMENTS`), whatever the judge made of its title
   when Hacker News or Kagi News carried it, LAB_RSS_MIN_P when only the lab's own feed did;
2. on Hacker News with at least SENSOR_HN_MOMENTUM points and worth reading for some interest;
3. naming a watched lab or model (profile `watch`: OpenAI, GPT, Claude, Gemini, …) and worth
   reading for some interest (T_WORTH);
4. strong for some interest (T_STRONG), the feed's own bar.

published within the window (a newly added feed's week of back catalogue is not news), in that
order, strongest first within each, within the run's `promote_per_run` (the feed gets what the
sensors leave). An item already promoted, held by the vault, or another outlet's
copy of a story promoted in the window (title-word overlap, SENSOR_SAME_STORY) is skipped. A Google
News link is saved as the publisher's own URL (`gnews.resolve`), or not at all: Reader cannot
follow one. [earned: 2026-09-30 — untitled "Google News" captures, two DLQ notes, one failed] Every
save is one `promoted.jsonl` row with `via: sensors`; its Reader note starts `[radar sensors`
(a `radar/…` tag would become an interest in the capture's `radar_interests`). A Reader failure never fails the scan.
[earned: 2026-09-30, OpenAI DevDay 2026 and GPT-6.1 Sol sat in the sensors for two days and never
reached the vault]

What leaves the machine: the chosen items' URLs, to Reader.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import gnews
import reader
from judgments import policy
from judgments.urls import _canonical

_WORD = re.compile(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]")
_STOP = {"the", "and", "for", "with", "after", "from", "that", "this", "its", "new", "into", "over", "says"}


def words(title: str) -> set[str]:
    return {w for w in _WORD.findall(title.lower()) if len(w) > 2 and w not in _STOP}


def same_story(a: set[str], b: set[str]) -> bool:
    return bool(a and b) and len(a & b) / len(a | b) >= policy.SENSOR_SAME_STORY


def lab_announcement(url: str) -> bool:
    u = urlparse(url)
    host = u.netloc.lower().removeprefix("www.")
    prefixes = policy.LAB_ANNOUNCEMENTS.get(host)
    return bool(prefixes) and any(u.path.startswith(p) for p in prefixes)


def usable(url: str) -> bool:
    """An address that names one page. Kagi News sometimes hands over a bare
    `https://www.youtube.com/watch` for a video story; saving it gives Reader YouTube's front page."""
    u = urlparse(url)
    if not u.scheme.startswith("http") or not u.netloc:
        return False
    return not (u.netloc.lower().removeprefix("www.").removeprefix("m.") == "youtube.com" and u.path == "/watch" and "v=" not in u.query)


def last_choice(url: str) -> bool:
    """A Google News redirect (the outlet's own URL is better) or a paywalled outlet (the capture
    holds a headline): taken only when no other outlet's copy of the story comes first."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host.endswith("news.google.com") or any(host == h or host.endswith("." + h) for h in policy.PAYWALLED)


def load_items(out: Path, today: date) -> list[dict]:
    """Sensor items of the window, one per key, each as last seen, with the day it was first seen."""
    items: dict[str, dict] = {}
    for n in range(policy.SENSOR_PROMOTE_WINDOW_DAYS - 1, -1, -1):
        day = (today - timedelta(days=n)).isoformat()
        path = out / "sensors" / f"{day}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key, it in (data.get("items") or {}).items():
            if isinstance(it, dict) and usable(str(it.get("url") or "")):
                items[key] = {**it, "key": key, "day": items.get(key, {}).get("day", day)}
    return list(items.values())


def watch_pattern(names: list[str]) -> re.Pattern[str] | None:
    """One case-insensitive pattern for the watched names, each ending at a non-letter: `GPT`
    matches "GPT-6.1" and "GPT 6.1", `Claude` matches "Claude's", `Meta` does not match "metadata"."""
    names = [n.strip() for n in names if n.strip()]
    if not names:
        return None
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in names) + r")(?![a-z])", re.I)


def rank(it: dict, t: dict[str, float], watch: re.Pattern[str] | None = None) -> tuple[int, float] | None:
    """(rule, -p) for an item that qualifies: 0 lab announcement, 1 momentum, 2 watched, 3 strong."""
    if it.get("source") not in policy.SENSOR_PROMOTE_SOURCES:
        return None
    p = max((it.get("p") or {}).values(), default=0.0)
    if lab_announcement(it["url"]) and (it.get("source") != "rss" or p >= policy.LAB_RSS_MIN_P):
        return 0, -p
    if it.get("source") == "hn" and (it.get("score") or 0) >= policy.SENSOR_HN_MOMENTUM and p >= t["T_WORTH"]:
        return 1, -p
    if watch is not None and p >= t["T_WORTH"] and watch.search(it.get("title", "")):
        return 2, -p
    if p >= t["T_STRONG"]:
        return 3, -p
    return None


def promote(out: Path, t: dict[str, float], run_date: str, budget: int, location: str,
            known: set[str], names: dict[str, str], watch: list[str] | None = None) -> dict[str, Any]:
    from radar import append_jsonl, read_jsonl  # lazy: radar imports this module

    ledger = out / "promoted.jsonl"
    done = read_jsonl(ledger)
    if budget <= 0:
        return {}
    since = (date.fromisoformat(run_date) - timedelta(days=policy.SENSOR_PROMOTE_WINDOW_DAYS)).isoformat()
    already = {r["canonical"] for r in done} | {r["google_news"] for r in done if r.get("google_news")} | known
    stories = [words(r["title"]) for r in done if r.get("title") and str(r.get("date", "")) > since]
    ranked = []
    pattern = watch_pattern(watch or [])
    for it in load_items(out, date.fromisoformat(run_date)):
        r = rank(it, t, pattern)
        if r is not None:
            ranked.append(((r[0], last_choice(it["url"]), r[1]), it))
    ranked.sort(key=lambda x: x[0])
    saved, unresolved, errors, rules = 0, 0, [], {0: 0, 1: 0, 2: 0, 3: 0}
    for (rule, _, _), it in ranked:
        if saved >= budget:
            break
        url = it["url"]
        canonical = _canonical(url)
        w = words(it.get("title", ""))
        if canonical in already or any(same_story(w, s) for s in stories):
            continue
        published = str(it.get("published") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published) and published <= since:
            continue
        google_news = None
        if gnews.is_google_news(url):
            google_news, url = canonical, gnews.resolve(url) or ""
            if not usable(url):
                unresolved += 1
                continue
            canonical = _canonical(url)
            if canonical in already or canonical in known:
                continue
        p = it.get("p") or {}
        tagged = sorted(i for i, v in p.items() if v >= t["T_WORTH"]) or ([max(p, key=p.get)] if p else [])
        why = ("lab announcement", f"{it.get('score') or 0:.0f} HN points", "watched name", "strong")[rule]
        note = f"[radar sensors {run_date}] {why}; " + "; ".join(f"{names.get(i, i)} p={p[i]:.2f}" for i in tagged)
        try:
            doc_id = reader.save(url, location, ["radar", *(f"radar/{i}" for i in tagged)], note)
        except (reader.ReaderError, ValueError) as e:
            errors.append(str(e)[:120])
            continue
        append_jsonl(ledger, [{"canonical": canonical, "id": doc_id, "date": run_date, "via": "sensors",
                               "source": it.get("source"), "title": it.get("title", ""),
                               **({"google_news": google_news} if google_news else {})}])
        already |= {canonical, google_news} - {None}
        stories.append(w)
        saved += 1
        rules[rule] += 1
    if not saved and not errors and not unresolved:
        return {}
    return {"sensors_promoted": saved, "sensors_by_rule": {"lab": rules[0], "momentum": rules[1], "watched": rules[2], "strong": rules[3]},
            **({"sensors_unresolved": unresolved} if unresolved else {}),
            **({"sensors_promote_errors": errors} if errors else {})}
