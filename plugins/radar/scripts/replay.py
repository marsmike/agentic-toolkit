"""The acceptance replay: would the radar have surfaced what the owner clipped anyway?

    radar.py replay --since 30d --out <dir> [--exclude-last-days 7] [--feed-sample 300]

Positives are the owner's own clips in the window (Reader locations new/later/shortlist/archive,
tweets included); negatives are feed items from the same window, a seeded random sample, minus
anything that was also clipped and minus a new feed's back catalogue. Both are judged exactly as
`scan` judges, with `category` blanked: every feed item says "rss", which would give the label
away. Three scorers are compared on the same items:

  jev      max over interests of P(worth_reading)
  bm25     max over interests of BM25(title+summary; name, gloss and queries), local, no call
  recency  saved_at, the order Reader already shows

Metrics per scorer: AUC over clips and feed items saved on the same day (the radar only ever
ranks one day's items; pooled over the window, recency just finds the day a batch of bookmarks
was imported [earned: 2026-09-23 replay, 18 of 27 clips on two days, recency AUC 0.68 pooled]),
pooled AUC, and recall at the daily budget: the share of clips scoring at or above
the score that lets `BUDGET_PER_DAY` feed items a day through. The judgment ships only if it
beats BM25. Writes `replay-rows.jsonl` and `replay-report.json` to `--out` and nothing else:
not the vault, not Reader.
"""
from __future__ import annotations

import json
import math
import random
import re
import time
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import interests as interests_mod
import judge
import reader
from judgments import policy

CLIP_LOCATIONS = ("new", "later", "shortlist", "archive")
# Delivered, not clipped: newsletters land in the library on their own. [earned: 2026-09-23
# replay, three Wisereads issues counted as clips]
NOT_A_CLIP_CATEGORIES = {"email"}
BUDGET_PER_DAY = 20
SEED = 20260922
BM25_K1, BM25_B = 1.2, 0.75
_TOKEN = re.compile(r"[a-z0-9]+")


def auc(pos: list[float], neg: list[float]) -> float | None:
    """P(a random positive outscores a random negative); ties count half."""
    if not pos or not neg:
        return None
    ranked = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg])
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        mid = (i + 1 + j) / 2  # average 1-based rank of the tie block
        rank_sum += mid * sum(lbl for _, lbl in ranked[i:j])
        i = j
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def same_day_auc(pos: list[tuple[str, float]], neg: list[tuple[str, float]]) -> float | None:
    """AUC over (day, score) pairs, comparing only positives and negatives from the same day;
    each day weighted by its number of pairs."""
    num = den = 0.0
    for day in {d for d, _ in pos}:
        p = [s for d, s in pos if d == day]
        n = [s for d, s in neg if d == day]
        if p and n:
            num += auc(p, n) * len(p) * len(n)
            den += len(p) * len(n)
    return num / den if den else None


def recall_at_budget(pos: list[float], neg: list[float], fraction: float) -> float | None:
    """Share of positives at or above the score that lets `fraction` of negatives through."""
    if not pos or not neg:
        return None
    k = max(1, math.ceil(min(1.0, fraction) * len(neg)))
    threshold = sorted(neg, reverse=True)[k - 1]
    return sum(1 for s in pos if s >= threshold) / len(pos)


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def bm25(docs: list[list[str]], queries: list[list[str]]) -> list[float]:
    """max over queries of BM25(doc, query), per doc."""
    n = len(docs)
    avgdl = sum(map(len, docs)) / n if n else 0.0
    df = Counter(t for d in docs for t in set(d))
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    out = []
    for d in docs:
        tf, norm = Counter(d), BM25_K1 * (1 - BM25_B + BM25_B * len(d) / avgdl) if avgdl else BM25_K1
        best = 0.0
        for q in queries:
            s = sum(idf.get(t, 0.0) * tf[t] * (BM25_K1 + 1) / (tf[t] + norm) for t in set(q) if t in tf)
            best = max(best, s)
        out.append(best)
    return out


def _saved_ts(item: reader.Item) -> float:
    try:
        return datetime.fromisoformat(item.saved_at).timestamp()
    except ValueError:
        return 0.0


def collect(since: datetime, until: datetime, feed_sample: int, seed: int = SEED) -> tuple[list, list, dict]:
    """(clips, sampled feed items, counts). Read-only against Reader."""
    from radar import is_backlog, item_key, title_key  # lazy: radar.py imports this module

    def in_window(it: reader.Item) -> bool:
        ts = _saved_ts(it)
        return since.timestamp() <= ts < until.timestamp()

    clips, clip_keys, not_clips = [], set(), 0
    for loc in CLIP_LOCATIONS:
        for doc in reader.list_documents(loc, since):
            it = reader.to_item(doc)
            keys = {item_key(it), title_key(it)} - {""}
            if it.category in NOT_A_CLIP_CATEGORIES:
                not_clips += 1
            elif in_window(it) and not keys & clip_keys:
                clip_keys |= keys
                clips.append(it)
    feed, feed_keys, dropped = [], set(), Counter()
    for it in reader.list_feed(since):
        keys = {item_key(it), title_key(it)} - {""}
        if not in_window(it):
            dropped["outside window"] += 1
        elif keys & clip_keys:
            dropped["also clipped"] += 1
        elif keys & feed_keys:
            dropped["duplicate"] += 1
        elif is_backlog(it, since):
            dropped["backlog"] += 1
        else:
            feed_keys |= keys
            feed.append(it)
    sample = feed if not feed_sample or feed_sample >= len(feed) else random.Random(seed).sample(feed, feed_sample)
    counts = {"clips": len(clips), "delivered_not_clipped": not_clips, "clip_categories": dict(Counter(c.category or "?" for c in clips)),
              "feed_in_window": len(feed), "feed_sampled": len(sample), "feed_dropped": dict(dropped)}
    return clips, sample, counts


def replay(vault: Path, out: Path, since: datetime, until: datetime, feed_sample: int,
           max_requests: int = policy.MAX_REQUESTS_PER_RUN) -> dict[str, Any]:
    from radar import RunUsage, judge_items  # radar.py owns the judging loop scan uses

    interests = interests_mod.load(vault)
    if not interests:
        return {"status": "no-interests", "detail": "no interests: set `interests_note` in Config/toolkit/radar.md"}
    reason = judge.unavailable_reason(vault)
    if reason:
        return {"status": "SKIPPED", "detail": f"judgment backend unavailable ({reason}); nothing sent"}
    try:
        clips, feed, counts = collect(since, until, feed_sample)
    except reader.NoToken:
        return {"status": "SKIPPED", "detail": "READWISE_TOKEN is not set; nothing fetched"}
    except reader.ReaderError as e:
        return {"status": "failed", "detail": f"Reader: {e}"}
    if not clips or not feed:
        return {"status": "empty", **counts}

    items = [replace(it, category="") for it in clips + feed]
    labels = [1] * len(clips) + [0] * len(feed)
    run, started = RunUsage(), time.monotonic()
    judged = judge_items(vault, items, interests, run, max_requests)
    wall_s = round(time.monotonic() - started, 1)

    docs = [tokens(f"{it.title} {it.summary}") for it in items]
    queries = [tokens(" ".join([i.name, i.gloss, *i.queries])) for i in interests]
    scores = {"jev": [max(judged[n]["p"].values()) if n in judged else None for n in range(len(items))],
              "bm25": bm25(docs, queries),
              "recency": [_saved_ts(it) for it in items]}

    keep = [n for n in range(len(items)) if n in judged]  # every scorer on the same judged items
    days = max(1.0, (until - since).total_seconds() / 86400)
    fraction = BUDGET_PER_DAY * days / max(1, counts["feed_in_window"])
    metrics = {}
    for name, s in scores.items():
        pos = [s[n] for n in keep if labels[n]]
        neg = [s[n] for n in keep if not labels[n]]
        day = [items[n].saved_at[:10] for n in range(len(items))]
        metrics[name] = {
            "auc_same_day": _r(same_day_auc([(day[n], s[n]) for n in keep if labels[n]],
                                            [(day[n], s[n]) for n in keep if not labels[n]])),
            "auc": _r(auc(pos, neg)), "recall_at_budget": _r(recall_at_budget(pos, neg, fraction))}

    t = policy.thresholds(run.backend)
    neg_judged = [judged[n] for n in keep if not labels[n]]
    scale = counts["feed_in_window"] / max(1, len(neg_judged))
    per_interest = {i.id: {"name": i.name,
                           "worth_est": round(scale * sum(1 for j in neg_judged if j["p"].get(i.id, 0) >= t["T_WORTH"])),
                           "strong_est": round(scale * sum(1 for j in neg_judged if j["p"].get(i.id, 0) >= t["T_STRONG"])),
                           "clips_strong": sum(1 for n in keep if labels[n] and judged[n]["p"].get(i.id, 0) >= t["T_STRONG"])}
                    for i in interests}
    feed_worth = sum(1 for j in neg_judged if max(j["p"].values()) >= t["T_WORTH"])
    feed_strong = sum(1 for j in neg_judged if max(j["p"].values()) >= t["T_STRONG"])

    out.mkdir(parents=True, exist_ok=True)
    with (out / "replay-rows.jsonl").open("w", encoding="utf-8") as f:
        for n, it in enumerate(items):
            f.write(json.dumps({"label": labels[n], "title": it.title, "feed": it.feed, "url": it.url,
                           "category": (clips + feed)[n].category, "saved_at": it.saved_at,
                           "p": judged.get(n, {}).get("p"), "kind": judged.get(n, {}).get("kind"),
                           "bm25": round(scores["bm25"][n], 4)}, ensure_ascii=False) + "\n")
    report = {
        "status": "ok", "since": since.isoformat(), "until": until.isoformat(), **counts,
        "judged": len(keep), "unjudged": len(items) - len(keep),
        "budget": {"per_day": BUDGET_PER_DAY, "fraction_of_feed": round(fraction, 4)},
        "metrics": metrics,
        "jev_beats_bm25": (metrics["jev"]["auc_same_day"] or 0) > (metrics["bm25"]["auc_same_day"] or 0),
        "feed_estimate": {"in_window": counts["feed_in_window"],
                          "worth": round(scale * feed_worth), "strong": round(scale * feed_strong)},
        "per_interest": per_interest, "thresholds": t,
        "usage": {**run.as_dict(), "wall_s": wall_s,
                  "usd_per_feed_item": round(run.usd / max(1, len(items)), 7)},
    }
    (out / "replay-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)
