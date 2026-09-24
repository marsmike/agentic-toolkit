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
and strong >= TREND_MIN_STRONG.

Emerging terms: title words and adjacent-word bigrams of this week's worth feed items, plus the
owner's own clips (`clips.py`; a clip's title carries no threshold at all, so one is worth several
feed mentions), ranked by smoothed log-ratio against the same four weeks before, a bonus for
looking like a name or product (capitalised mid-title, or carrying a digit — a cheap proxy for a
proper noun with no training data), and a hard drop for a term that is this vault's own
always-there vocabulary: present in most of every scanned week regardless of topic, which the
English `STOPWORDS` below cannot know because it is not a stopword in general, only in this feed
set. [earned: 2026-09-24, owner: ~15 clips about "Jev" surfaced nothing because a clip never
entered radar state, and "claude"/"agent"/"code"/"development" — generic to this feed set — won
every week regardless]
"""
from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from clips import Clip
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
CLIP_MIN_COUNT = 2      # a term seen in this many of the owner's own clips needs no feed corroboration
CLIP_WEIGHT = 1.5       # multiplies log1p(clip mentions): nothing gated a clip, so it outweighs a feed hit
ENTITY_BONUS = 0.75     # favors capitalised/product-like tokens (see _tokens) over generic words
DF_STOP_FRAC = 0.6      # a term in this share of all scanned weeks is vault-generic, not emerging
DF_STOP_MIN_WEEKS = 4   # weeks of history needed before the auto-stoplist activates
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+.#-]{2,}")
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


def week_monday(week: str) -> date:
    y, w = week.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def baseline_weeks(week: str) -> set[str]:
    """The TREND_BASELINE_WEEKS ISO weeks before `week`."""
    monday = week_monday(week)
    return {week_of((monday - timedelta(weeks=k)).isoformat()) for k in range(1, TREND_BASELINE_WEEKS + 1)}


def clip_window_start(week: str) -> date:
    """The earliest date `emerging_terms` can use a clip from: the start of the baseline, same
    scope as the feed rows it is ranked against."""
    return week_monday(week) - timedelta(weeks=TREND_BASELINE_WEEKS)


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


def _tokens(title: str) -> list[tuple[str, bool]]:
    """(casefolded word, looks-like-a-name) for every non-stopword word in `title`. "Looks like a
    name": capitalised other than as the title's first word (every title capitalises that one
    regardless), or carrying a digit (a version or model number) — a cheap proxy for a proper
    noun or product token, with no training data and no external model."""
    out = []
    for i, w in enumerate(_WORD.findall(title)):
        cf = w.casefold().strip(".-")
        if not cf or cf in STOPWORDS:
            continue
        entity = any(ch.isdigit() for ch in w) or (i > 0 and w[0].isupper())
        out.append((cf, entity))
    return out


def _bigrams(tokens: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """Adjacent-word phrases from a title's already-stopword-filtered tokens: "model router" says
    more than "model" or "router" alone. Adjacency is in the filtered list, not the raw title, so
    a stopword between two real words is silently elided — good enough for the common case of a
    name split into two tokens ("system one"). A bigram looks like a name if either of its words
    does (`_tokens`), so "Vector Loom launches" still gets the entity bonus as a phrase, not just
    on its own two words."""
    return [(f"{a} {b}", ea or eb) for (a, ea), (b, eb) in zip(tokens, tokens[1:])]


def _auto_stopwords(rows: list[dict], min_week_frac: float = DF_STOP_FRAC,
                    min_weeks: int = DF_STOP_MIN_WEEKS) -> set[str]:
    """Terms in title words of worth items present in nearly every scanned week: this feed set's
    own generic vocabulary, not a topic. Grows with the vault's own history instead of a
    hand-maintained list, which cannot know what one particular set of feeds always talks about."""
    weeks: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        w, _ = bands(r)
        if not w:
            continue
        toks = _tokens(r.get("title") or "")
        weeks[week_of(arrived(r))] |= {t for t, _ in toks + _bigrams(toks)}
    if len(weeks) < min_weeks:
        return set()
    df: Counter[str] = Counter()
    for terms in weeks.values():
        df.update(terms)
    return {t for t, n in df.items() if n / len(weeks) >= min_week_frac}


def emerging_terms(rows: list[dict], week: str, clips: Sequence[Clip] = (), limit: int = 10) -> list[dict[str, Any]]:
    """Title words and bigrams of this week's worth feed items and the owner's own clips, ranked
    against the baseline weeks, a hard drop for this vault's always-there vocabulary
    (`_auto_stopwords`), and a preference for name-like tokens and bigrams (`_tokens`) and for
    what the owner clipped himself (`CLIP_WEIGHT`, no feed-diversity gate needed)."""
    before = baseline_weeks(week)
    auto_stop = _auto_stopwords(rows)

    def terms_of(title: str) -> list[tuple[str, bool]]:
        toks = _tokens(title)
        return [(t, e) for t, e in toks + _bigrams(toks) if t not in auto_stop]

    now_feed_c: Counter[str] = Counter()
    now_feeds: dict[str, set[str]] = defaultdict(set)
    now_clip_c: Counter[str] = Counter()
    now_entity: Counter[str] = Counter()
    now_seen: Counter[str] = Counter()
    prior_c: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    def note(term: str, title: str) -> None:
        if title and title not in examples[term] and len(examples[term]) < 3:
            examples[term].append(title)

    for r in rows:
        w, _ = bands(r)
        if not w:
            continue
        wk = week_of(arrived(r))
        title = r.get("title") or ""
        if wk == week:
            for t, entity in terms_of(title):
                now_feed_c[t] += 1
                now_seen[t] += 1
                now_entity[t] += int(entity)
                now_feeds[t].add(r.get("feed") or "?")
                note(t, title)
        elif wk in before:
            for t, _ in terms_of(title):
                prior_c[t] += 1

    for c in clips:
        if week_of(c.saved_at) != week:
            continue
        for t, entity in terms_of(c.title):
            now_clip_c[t] += 1
            now_seen[t] += 1
            now_entity[t] += int(entity)
            note(t, c.title)

    n_now, n_prior = sum(now_seen.values()) or 1, sum(prior_c.values()) or 1
    scored = []
    for t, seen in now_seen.items():
        feed_n, clip_n = now_feed_c[t], now_clip_c[t]
        strong_feed = feed_n >= TERM_MIN_COUNT and len(now_feeds[t]) >= TERM_MIN_FEEDS
        if not strong_feed and clip_n < CLIP_MIN_COUNT:
            continue
        base = math.log((seen + 1) / n_now) - math.log((prior_c[t] + 1) / n_prior)
        score = base + ENTITY_BONUS * (now_entity[t] / seen) + CLIP_WEIGHT * math.log1p(clip_n)
        scored.append({"term": t, "feed_count": feed_n, "feeds": len(now_feeds[t]), "clip_count": clip_n,
                       "examples": examples[t], "score": round(score, 3)})
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
                  gaps: dict | None = None, clips: Sequence[Clip] = ()) -> str:
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
    terms = emerging_terms(rows, week, clips)
    lines += ["", "## Topics rising", ""]
    if terms:
        for t in terms:
            evidence = [f"{t['feed_count']} feed item{'s' if t['feed_count'] != 1 else ''} ({t['feeds']} feeds)"] \
                if t["feed_count"] else []
            if t["clip_count"]:
                evidence.append(f"{t['clip_count']} of your own clips")
            title = t["examples"][0] if t["examples"] else ""
            example = f' — e.g. "{title[:100] + "…" if len(title) > 100 else title}"' if title else ""
            lines.append(f"- **{t['term']}** — {', '.join(evidence)}{example}")
    else:
        lines.append("Nothing rising above the baseline this week.")
    lines += ["", "## Next actions", "", "- [ ] Distill the key items worth keeping; delete this capture after.",
              "- [ ] Act on any feed advice above (unsubscribe in Reader, or run `radar.py discover`).", ""]
    return "\n".join(lines)


def write_weekly(vault: Path, week: str, text: str, force: bool = False, written: Path | None = None,
                 prefix: str = "Radar-Week") -> Path:
    """Write the week's capture once. `written` (00_Memory/radar/weekly.jsonl, or scout.jsonl for
    `prefix="Radar-Scout"`) remembers the weeks already written, so one distill has retired is not
    written again by the next run. Shared by `weekly` and `scout` — same file, same once-a-week
    rule, only the name differs."""
    path = vault / "01_Capture" / f"{prefix}-{week}.md"
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
