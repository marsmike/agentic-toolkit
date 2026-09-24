"""What the radar's state says over time: feed yield, trends, the weekly capture. No model call.

    radar.py feeds  [--json]            which feeds earn their place
    radar.py trend  [--json]            which interests are rising this week
    radar.py weekly [--week YYYY-WW]    01_Capture/Radar-Week-YYYY-WW.md, for the distill pipeline

Everything reads `00_Memory/radar/state.jsonl`. Bands are recomputed from each row's p with the
current thresholds for the row's backend, so a threshold change applies to history too.

Trend: per interest and ISO week of arrival (the item's `saved_at` in the feed, else its scan
date), rate = strong / scanned. The baseline is the median rate of the TREND_BASELINE_WEEKS weeks
before and needs at least TREND_MIN_WEEKS of them ("no baseline" otherwise). With
lambda = baseline x this week's scanned, an interest is rising when strong > lambda + 2 sqrt(lambda)
and strong >= TREND_MIN_STRONG. Emerging terms (experimental): title words of this week's worth
items, seen at least 3 times from at least 2 feeds, ranked by smoothed log-ratio against the same
four weeks before.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from interests import Interest
from judgments import policy
from vault_utils import atomic_write

FEED_UNSUBSCRIBE_WEEKS = 4
FEED_UNSUBSCRIBE_MIN_ITEMS = 40
FEED_ONE_INTEREST_SHARE = 0.80
TREND_MIN_WEEKS = 2
# The baseline looks back four weeks, no further: interests drift, and a topic that was loud in
# spring must not mask one rising now. [earned: 2026-09-24, owner: "the last four weeks only"]
TREND_BASELINE_WEEKS = 4
TREND_MIN_STRONG = 3
TERM_MIN_COUNT = 3
TERM_MIN_FEEDS = 2
_WORD = re.compile(r"[a-z][a-z0-9+.#-]{2,}")
STOPWORDS = set("""the and for with from into over under your you our are was were this that these those
how what why when who via new using use based towards toward between about than then not can will its
their them they has have had more most less least all any each other such only also just now one two
""".split())


def week_of(day: str) -> str:
    y, w, _ = date.fromisoformat(day[:10]).isocalendar()
    return f"{y}-W{w:02d}"


def arrived(row: dict) -> str:
    """The day an item reached the feed; a first scan covers several days, and a missed run must
    not move its items into the next week. [earned: 2026-09-24 — the first scan's 391 items,
    saved over eight days, all counted in the week of the scan]"""
    return str(row.get("saved_at") or row["run"])[:10]


def baseline_weeks(week: str) -> set[str]:
    """The TREND_BASELINE_WEEKS ISO weeks before `week`."""
    y, w = week.split("-W")
    monday = date.fromisocalendar(int(y), int(w), 1)
    return {week_of((monday - timedelta(weeks=k)).isoformat()) for k in range(1, TREND_BASELINE_WEEKS + 1)}


def bands(row: dict) -> tuple[set[str], set[str]]:
    """(worth interest ids, strong interest ids) under the current thresholds."""
    t = policy.thresholds(row.get("backend") or "jev")
    p = row.get("p") or {}
    return ({i for i, v in p.items() if v >= t["T_WORTH"]}, {i for i, v in p.items() if v >= t["T_STRONG"]})


# ---------------------------------------------------------------------------
# feeds
# ---------------------------------------------------------------------------


def feeds(rows: list[dict], now: datetime) -> list[dict[str, Any]]:
    by_feed: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_feed[r.get("feed") or "?"].append(r)
    out = []
    for feed, fr in by_feed.items():
        strong_by_interest: Counter[str] = Counter()
        worth = strong = 0
        last_strong = ""
        for r in fr:
            w, s = bands(r)
            worth += bool(w)
            strong += bool(s)
            strong_by_interest.update(s)
            if s and r["run"] > last_strong:
                last_strong = r["run"]
        first = min(r["run"] for r in fr)
        weeks_seen = (now.date() - date.fromisoformat(first)).days / 7
        advice = []
        if strong == 0 and weeks_seen >= FEED_UNSUBSCRIBE_WEEKS and len(fr) >= FEED_UNSUBSCRIBE_MIN_ITEMS:
            advice.append("consider unsubscribing")
        top = strong_by_interest.most_common(1)
        if top and strong >= TREND_MIN_STRONG and top[0][1] / sum(strong_by_interest.values()) >= FEED_ONE_INTEREST_SHARE:
            advice.append(f"serves only {top[0][0]}")
        out.append({
            "feed": feed, "scanned": len(fr), "worth": worth, "strong": strong,
            "yield": round(strong / len(fr), 3), "interests": dict(strong_by_interest.most_common()),
            "weeks_since_strong": round((now.date() - date.fromisoformat(last_strong)).days / 7, 1) if last_strong else None,
            "weeks_seen": round(weeks_seen, 1), "advice": advice,
        })
    return sorted(out, key=lambda f: (-f["strong"], -f["scanned"]))


# ---------------------------------------------------------------------------
# trend
# ---------------------------------------------------------------------------


def trend(rows: list[dict], week: str) -> dict[str, dict[str, Any]]:
    """Per interest: this week's scanned/strong, the baseline and whether it is rising."""
    weekly: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        wk = week_of(arrived(r))
        _, s = bands(r)
        for iid in r.get("p") or {}:
            weekly[iid][wk][0] += 1
            weekly[iid][wk][1] += iid in s
    out = {}
    before = baseline_weeks(week)
    for iid, weeks in weekly.items():
        scanned, strong = weeks.get(week, [0, 0])
        prior = [st / sc for wk, (sc, st) in weeks.items() if wk in before and sc]
        entry: dict[str, Any] = {"scanned": scanned, "strong": strong, "prior_weeks": len(prior)}
        if len(prior) < TREND_MIN_WEEKS:
            entry.update(baseline=None, rising=False, note="no baseline")
        else:
            base = statistics.median(prior)
            lam = base * scanned
            limit = lam + 2 * math.sqrt(lam)
            entry.update(baseline=round(base, 4), expected=round(lam, 2), limit=round(limit, 2),
                         rising=strong > limit and strong >= TREND_MIN_STRONG)
        out[iid] = entry
    return out


def _terms(title: str) -> set[str]:
    return {w.strip(".-") for w in _WORD.findall(title.casefold())} - STOPWORDS


def emerging_terms(rows: list[dict], week: str, limit: int = 10) -> list[dict[str, Any]]:
    now_c: Counter[str] = Counter()
    now_feeds: dict[str, set[str]] = defaultdict(set)
    prior_c: Counter[str] = Counter()
    before = baseline_weeks(week)
    for r in rows:
        w, _ = bands(r)
        if not w:
            continue
        terms = _terms(r.get("title") or "")
        wk = week_of(arrived(r))
        if wk == week:
            now_c.update(terms)
            for t in terms:
                now_feeds[t].add(r.get("feed") or "?")
        elif wk in before:
            prior_c.update(terms)
    n_now, n_prior = sum(now_c.values()) or 1, sum(prior_c.values()) or 1
    scored = [{"term": t, "count": c, "feeds": len(now_feeds[t]),
               "score": round(math.log((c + 1) / n_now) - math.log((prior_c[t] + 1) / n_prior), 3)}
              for t, c in now_c.items() if c >= TERM_MIN_COUNT and len(now_feeds[t]) >= TERM_MIN_FEEDS]
    return sorted(scored, key=lambda x: -x["score"])[:limit]


# ---------------------------------------------------------------------------
# weekly capture
# ---------------------------------------------------------------------------


def last_complete_week(today: date) -> str:
    return week_of((today - timedelta(days=today.isoweekday())).isoformat())


def _link(r: dict) -> str:
    title = (r.get("title") or r.get("url") or "untitled").replace("[", "(").replace("]", ")")
    return f"[{title}]({r['url']})" if r.get("url") else title


def _vault_ref(path: str | None) -> str:
    """A wikilink to where the vault already has it; never into 00_Memory."""
    if not path or path.startswith("00_Memory/"):
        return ""
    return f" · already in vault: [[{path.removesuffix('.md')}]]"


def render_weekly(week: str, rows: list[dict], interests: list[Interest], now: datetime, per_interest: int = 3,
                  gaps: dict | None = None) -> str:
    names = {i.id: i.name for i in interests}
    wk_rows = [r for r in rows if week_of(arrived(r)) == week]
    strong_rows = {iid: [] for iid in names}
    worth_n = strong_n = 0
    for r in wk_rows:
        w, s = bands(r)
        worth_n += bool(w)
        strong_n += bool(s)
        for iid in s & names.keys():
            strong_rows[iid].append(r)
    tr = trend(rows, week)
    rising = [iid for iid in names if tr.get(iid, {}).get("rising")]
    ordered = sorted((i for i in names if strong_rows[i]), key=lambda i: (i not in rising, -len(strong_rows[i])))

    lines = [
        "---",
        f"description: Radar week {week} — {len(wk_rows)} feed items judged, {strong_n} strong, {worth_n} worth reading",
        f"source: Reader feed items judged by the radar, ISO week {week}",
        f"created: {now.date().isoformat()}",
        "kind: radar-digest",
        "via: radar",
        "status: draft",
        "tags:",
        "  - radar",
        "---",
        "",
        f"# Radar week {week}",
        "",
        f"{len(wk_rows)} feed items judged against {len(names)} interests: **{strong_n} strong, {worth_n} worth reading.**",
        "",
        "## Rising",
        "",
    ]
    if rising:
        for iid in rising:
            e = tr[iid]
            lines.append(f"- **{names[iid]}**: {e['strong']} strong of {e['scanned']} (expected {e['expected']}, limit {e['limit']})")
    elif any(e.get("baseline") is not None for e in tr.values()):
        lines.append("Nothing rose above its baseline this week.")
    else:
        lines.append("No baseline yet: trends need two earlier weeks of scans.")
    lines += ["", "## Key items", ""]
    n = 0
    for iid in ordered:
        top = sorted(strong_rows[iid], key=lambda r: -r["p"][iid])[:per_interest]
        n += 1
        lines += [f"### {n}. {names[iid]}{' (rising)' if iid in rising else ''}", ""]
        for r in top:
            lines.append(f"- {_link(r)} — {r.get('feed') or '?'} · {r.get('kind') or '?'} · p={r['p'][iid]:.2f}{_vault_ref(r.get('in_vault'))}")
        if len(strong_rows[iid]) > per_interest:
            lines.append(f"- … and {len(strong_rows[iid]) - per_interest} more strong items")
        lines.append("")
    if not ordered:
        lines += ["No strong items this week.", ""]

    repos = sorted({(r["url"], r.get("title") or "") for r in wk_rows
                    if "github.com/" in (r.get("url") or "") and bands(r)[0]})
    lines += ["## Repos to evaluate", ""]
    lines += [f"- [{t or u}]({u})" for u, t in repos] or ["None this week."]
    lines += ["", "## Feeds", "", "| Feed | scanned | worth | strong | advice |", "|---|---:|---:|---:|---|"]
    for f in feeds(rows, now):
        wk = [r for r in wk_rows if (r.get("feed") or "?") == f["feed"]]
        if wk or f["advice"]:
            w = sum(1 for r in wk if bands(r)[0])
            s = sum(1 for r in wk if bands(r)[1])
            lines.append(f"| {f['feed']} | {len(wk)} | {w} | {s} | {', '.join(f['advice'])} |")
    if gaps:
        strong_gaps = [g for g in gaps.get("rows", []) if g.get("strong")]
        lines += ["", "## Found outside your feeds", ""]
        lines += [f"- {_link(g)} — {g.get('site') or '?'} · p={max(g['p'].values()):.2f} · "
                  f"{', '.join(names.get(i, i) for i in g['strong'])}" for g in strong_gaps[:10]] or ["Nothing strong this week."]
        if gaps.get("sites"):
            lines += ["", "Sites that carried them, candidates for `radar.py discover --seed`: "
                      + ", ".join(f"{s} ({n})" for s, n in gaps["sites"][:8])]
    terms = emerging_terms(rows, week)
    lines += ["", "## Emerging terms (experimental)", ""]
    lines.append(" · ".join(f"{t['term']} ({t['count']})" for t in terms) if terms else "None yet.")
    lines += ["", "## Next actions", "", "- [ ] Distill the key items worth keeping; delete this capture after.",
              "- [ ] Act on any feed advice above (unsubscribe in Reader, or run `radar.py discover`).", ""]
    return "\n".join(lines)


def write_weekly(vault: Path, week: str, text: str, force: bool = False, written: Path | None = None) -> Path:
    """Write the week's capture once. `written` (00_Memory/radar/weekly.jsonl) remembers the weeks
    already written, so a digest distill has retired is not written again by the next run."""
    path = vault / "01_Capture" / f"Radar-Week-{week}.md"
    done = written.is_file() and any(json.loads(ln).get("week") == week for ln in written.read_text(encoding="utf-8").splitlines() if ln.strip()) if written else False
    if (path.exists() or done) and not force:
        raise FileExistsError(f"the capture for {week} was already written (it may be distilled or half distilled); --force rewrites it")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, text)
    if written is not None:
        written.parent.mkdir(parents=True, exist_ok=True)
        with written.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"week": week, "capture": path.relative_to(vault).as_posix()}) + "\n")
    return path
