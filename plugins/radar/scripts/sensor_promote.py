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
copy of a story promoted in the window (title-word overlap, SENSOR_SAME_STORY) is skipped. A
watched name takes at most `promote_per_name_per_run` of a run and `promote_per_name_per_day` of a
day (profile; defaults SENSOR_PER_NAME_PER_RUN and SENSOR_PER_NAME_PER_DAY), and one source (a
feed, a Google News search, Hacker News, a lab's own blog) at most `per_source_run` of a run; a
held-back lab post stays in the window and goes first next run. Past the labs' own
announcements, candidates are taken round-robin by interest (`fairness.interleave`).
(a lab's own announcement always goes, and counts), so one story cannot fill the run. A Google
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
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import bubbles
import fairness
import gnews
import reader
from allocation import Cand, Caps, Selector
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
    matches "GPT-6.1" and "GPT 6.1", `Claude` matches "Claude's", `Meta` does not match "metadata"
    or "Meta-Instrument" (a hyphen and a letter make another word, a hyphen and a digit a version).
    [earned: 2026-09-30 — a plugin host's "Meta-Instrument" took one of Meta's two slots]"""
    names = [n.strip() for n in names if n.strip()]
    if not names:
        return None
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in names) + r")(?![a-z]|-[a-z])", re.I)


def named(title: str, pattern: re.Pattern[str] | None) -> set[str]:
    """The watched names a title carries, lower-cased: "Meta's Muse vs ChatGPT" → {meta, muse, chatgpt}."""
    return {m.lower() for m in pattern.findall(title or "")} if pattern else set()


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


def candidates(out: Path, t: dict[str, float], run_date: str, known: set[str],
               pattern: re.Pattern[str] | None = None, evs: list | None = None) -> list[Cand]:
    """The window's sensor items that qualify (`rank`) and are neither promoted, held by the vault,
    a copy of a story promoted in the window, nor published before it; each as an allocation
    candidate with its bubble, its event (`bubbles.event_of`, else a title-overlap story of this
    run) and the watched names in its title."""
    from radar import read_jsonl  # lazy: radar imports this module

    done = read_jsonl(out / "promoted.jsonl")
    since = (date.fromisoformat(run_date) - timedelta(days=policy.SENSOR_PROMOTE_WINDOW_DAYS)).isoformat()
    already = {r["canonical"] for r in done} | {r["google_news"] for r in done if r.get("google_news")} | known
    stories = [words(r["title"]) for r in done if r.get("title") and str(r.get("date", "")) > since]
    found: list[Cand] = []
    local: list[tuple[set[str], str]] = []   # this run's title-overlap stories: (words, event key)
    for it in load_items(out, date.fromisoformat(run_date)):
        r = rank(it, t, pattern)
        if r is None:
            continue
        canonical = _canonical(it["url"])
        w = words(it.get("title", ""))
        published = str(it.get("published") or "")[:10]
        if canonical in already or any(same_story(w, s) for s in stories) or \
                (re.fullmatch(r"\d{4}-\d{2}-\d{2}", published) and published <= since):
            continue
        already.add(canonical)
        p = {k: float(v) for k, v in (it.get("p") or {}).items()}
        ev = bubbles.event_of(it.get("title", ""), evs or [])
        key, name, must = (ev.key, ev.name, ev.must_see) if ev else (None, None, False)
        if key is None:
            twin = next((k for ws, k in local if same_story(w, ws)), None)
            key = twin or f"story:{canonical}"
            local.append((w, key))
            name = None if twin is None else it.get("title")
        found.append(Cand(kind="sensor", key=canonical, title=str(it.get("title") or ""), url=it["url"],
                          source=str(it.get("origin") or it.get("source") or ""), p=p,
                          bubble=fairness.top_interest(p), strength=max(p.values(), default=0.0),
                          lab=r[0] == 0, last_choice=last_choice(it["url"]), event=key, event_name=name,
                          must_see=must, names=frozenset(named(it.get("title", ""), pattern)),
                          ref={"item": it, "rule": r[0]}))
    return found


RULE_WHY = ("lab announcement", "{score} HN points", "watched name", "strong")


def save(c: Cand, out: Path, t: dict[str, float], run_date: str, location: str, names: dict[str, str],
         known: set[str], stats: dict[str, Any]) -> bool:
    """Save one sensor candidate to Reader (a Google News link as the publisher's URL, or not at
    all), with the other outlets of its story in the note; one `promoted.jsonl` row."""
    from radar import append_jsonl  # lazy: radar imports this module

    it, rule = c.ref["item"], c.ref["rule"]
    url, canonical, google_news = c.url, c.key, None
    if gnews.is_google_news(url):
        google_news, url = canonical, gnews.resolve(url) or ""
        if not usable(url):
            stats["unresolved"] = stats.get("unresolved", 0) + 1
            return False
        canonical = _canonical(url)
        if canonical in known or canonical in stats.setdefault("saved", set()):
            return False
    tagged = sorted(i for i, v in c.p.items() if v >= t["T_WORTH"]) or ([c.bubble] if c.bubble else [])
    why = RULE_WHY[rule].format(score=f"{it.get('score') or 0:.0f}")
    if c.must_see:
        why = f"must-see ({c.event_name or 'event'}); {why}"
    also = [a.url for a in c.also if not gnews.is_google_news(a.url)][:3]
    note = f"[radar sensors {run_date}] {why}; " + "; ".join(f"{names.get(i, i)} p={c.p[i]:.2f}" for i in tagged)
    if also:
        note += "; also covered by " + ", ".join(also)
    try:
        doc_id = reader.save(url, location, ["radar", *(f"radar/{i}" for i in tagged)], note)
    except (reader.ReaderError, ValueError) as e:
        stats.setdefault("errors", []).append(str(e)[:120])
        return False
    append_jsonl(out / "promoted.jsonl", [{
        "canonical": canonical, "id": doc_id, "date": run_date, "via": "sensors", "source": it.get("source"),
        "title": c.title, "bubble": c.bubble, **({"event": c.event} if c.event and not c.event.startswith("story:") else {}),
        **({"must_see": True} if c.must_see else {}), **({"google_news": google_news} if google_news else {})}])
    stats.setdefault("saved", set()).add(canonical)
    rules = stats.setdefault("by_rule", {"lab": 0, "momentum": 0, "watched": 0, "strong": 0})
    rules[("lab", "momentum", "watched", "strong")[rule]] += 1
    return True


def today_counts(out: Path, run_date: str, pattern: re.Pattern[str] | None) -> tuple[Counter, Counter, Counter]:
    """Today's promotions (both paths) by bubble, by event and by watched name."""
    from radar import read_jsonl  # lazy: radar imports this module

    bubbles_n, events_n, names_n = Counter(), Counter(), Counter()
    for r in read_jsonl(out / "promoted.jsonl"):
        if r.get("date") != run_date:
            continue
        if r.get("bubble"):
            bubbles_n[r["bubble"]] += 1
        if r.get("event"):
            events_n[r["event"]] += 1
        for n in named(r.get("title", ""), pattern):
            names_n[n] += 1
    return bubbles_n, events_n, names_n


def promote(out: Path, t: dict[str, float], run_date: str, budget: int, location: str,
            known: set[str], names: dict[str, str], watch: list[str] | None = None,
            per_name_run: int | None = None, per_name_day: int | None = None,
            per_source_run: int | None = None, evs: list | None = None) -> dict[str, Any]:
    """The sensors alone, every bubble alike: `scan --promote` allocates sensors and feed together
    (`allocation`); this is the same walk over the sensor candidates only."""
    if budget <= 0:
        return {}
    pattern = watch_pattern(watch or [])
    cands = candidates(out, t, run_date, known, pattern, evs)
    b_n, e_n, n_n = today_counts(out, run_date, pattern)
    caps = Caps(per_source_run=policy.PROMOTE_PER_SOURCE_PER_RUN if per_source_run is None else per_source_run,
                per_name_run=policy.SENSOR_PER_NAME_PER_RUN if per_name_run is None else per_name_run,
                per_name_day=policy.SENSOR_PER_NAME_PER_DAY if per_name_day is None else per_name_day,
                per_event_day=policy.PER_EVENT_PER_DAY, sensor_share=None, must_share=1.0)
    sel = Selector(cands, budget, {}, caps=caps, today_bubbles=b_n, today_events=e_n, today_names=n_n)
    stats: dict[str, Any] = {}
    sel.run(lambda c: save(c, out, t, run_date, location, names, known, stats))
    return report(sel, stats)


def report(sel: Selector, stats: dict[str, Any]) -> dict[str, Any]:
    saved = sum(1 for c in sel.taken if c.kind == "sensor")
    held = sum(1 for c in sel.held() if c.kind == "sensor")
    if not saved and not held and not stats.get("errors") and not stats.get("unresolved"):
        return {}
    return {"sensors_promoted": saved,
            "sensors_by_rule": stats.get("by_rule", {"lab": 0, "momentum": 0, "watched": 0, "strong": 0}),
            **({"sensors_held": held} if held else {}),
            **({"sensors_unresolved": stats["unresolved"]} if stats.get("unresolved") else {}),
            **({"sensors_promote_errors": stats["errors"]} if stats.get("errors") else {})}
