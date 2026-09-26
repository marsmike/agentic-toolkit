"""The owner's own vault as a trend source: what he is writing and clipping, and which topics
are accelerating in HIS notes — read straight from the vault's files, never through the obsidian
plugin (AGENTS.md "Hard rules": plugins depend on core/contract only, never a sibling plugin).

    from vault_pulse import pulse
    pulse(vault, now)  # -> {"mentions", "daily", "week", "tags", "domains", "interests", "skipped"}

Content notes are every `*.md` under `02_Projects/`, `03_Areas/`, `04_Resources/` (via `contained`,
so a symlink out of the vault is not one), dated by frontmatter `created` (fallback
`processed_date`); a note carrying neither, or frontmatter that doesn't parse, is skipped and
counted, never guessed at. Clips (`clips.load`) are the second half: what the owner chose to read
himself, no threshold or feed gate in between.

Tag filtering — a tag namespace/pattern check, plus a document-frequency cut on top of it. The
named patterns (`domain/*`, `readwise/*` and bare `readwise`, `source/*`, `W\\d\\d-\\d{4}`, and a
small set of PARA/lifecycle markers that describe the note's own role rather than its topic) are
provenance and structure, not momentum: a note tagged `domain/ai-ml` or `readwise/concept` says
where it sits or where it came from, not what is rising. `domain/*` is pulled out into its own
`domain` field instead of being dropped outright, since which domain is accelerating is exactly a
pulse question. On top of the named patterns, any tag that still covers most of the tagged corpus
(`_DF_STOP_FRAC` of tagged mentions, once there are enough of them to call anything "most") is cut
too: a vault accretes its own always-there tags no fixed list can anticipate, the same problem
`reports.py`'s `_auto_stopwords` solves for feed titles.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import clips as clips_mod
from vault_utils import UnparseableFrontmatter, contained, read_frontmatter

CONTENT_FOLDERS = ("02_Projects", "03_Areas", "04_Resources")
DAILY_DAYS = 28
BASELINE_WEEKS = 4
TAG_TOP = 30
TAG_EXAMPLES_CAP = 3

# A tag present on this share of the tagged corpus (once there are enough tagged mentions to
# judge) is this vault's own generic vocabulary, not a trend — same idea as reports.py's
# DF_STOP_FRAC, applied to vault tags instead of feed-item title words.
_DF_STOP_FRAC = 0.5
_DF_STOP_MIN_DOCS = 20

_DOMAIN_TAG = re.compile(r"^domain/(.+)$")
_WEEK_TAG = re.compile(r"^W\d{2}-\d{4}$")
# PARA/lifecycle markers seen tagging a note's own role rather than its subject (`status`,
# `kind` and `type` already carry this in frontmatter; a vault sometimes repeats it as a tag).
_STATUS_TAGS = {"active", "draft", "review", "distilled", "archived", "area", "reference"}
_H1 = re.compile(r"^#\s+(.+)$", re.M)


def _is_source_or_status_tag(tag: str) -> bool:
    return tag == "readwise" or tag.startswith("readwise/") or tag.startswith("source/") or tag in _STATUS_TAGS


def _title(body: str, path: Path) -> str:
    m = _H1.search(body)
    return m.group(1).strip() if m else path.stem


def _specific_tags(fm: dict) -> tuple[list[str], str | None]:
    """A note/clip's topical tags (drops domain/*, readwise/*, source/*, week tags and PARA/
    lifecycle markers) plus its first domain/* value, if any."""
    raw = fm.get("tags") or []
    if isinstance(raw, str):
        raw = [raw]
    domain: str | None = None
    kept: list[str] = []
    for t in raw:
        t = str(t).strip()
        if not t:
            continue
        if m := _DOMAIN_TAG.match(t):
            if domain is None:
                domain = m.group(1)
            continue
        if _WEEK_TAG.match(t) or _is_source_or_status_tag(t):
            continue
        kept.append(t)
    return kept, domain


def _interest_ids(fm: dict) -> list[str]:
    raw = fm.get("radar_interests") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(x).strip() for x in raw if str(x).strip()]


def _content_paths(vault: Path) -> list[Path]:
    paths: list[Path] = []
    for folder in CONTENT_FOLDERS:
        d = vault / folder
        if d.is_dir():
            paths.extend(d.rglob("*.md"))
    return contained(paths, vault)


def _note_mention(path: Path, vault: Path, fm: dict, body: str, day: str) -> dict[str, Any]:
    tags, domain = _specific_tags(fm)
    kind = str(fm.get("kind") or "").strip() or path.relative_to(vault).parts[0]
    return {
        "at": day,
        "family": "vault",
        "origin": f"note:{kind}",
        "title": _title(body, path),
        "url": path.relative_to(vault).as_posix(),
        "summary": str(fm.get("description") or "")[:200],
        "score": None,
        "eng_pct": None,
        "p": None,
        "tags": tags,
        "entities": [],
        "interests": _interest_ids(fm),
        "domain": domain,
    }


def _clip_mention(clip: clips_mod.Clip, vault: Path) -> dict[str, Any]:
    try:
        fm, _ = read_frontmatter(vault / clip.path)
    except OSError:
        fm = {}
    tags, domain = _specific_tags(fm)
    return {
        "at": clip.saved_at,
        "family": "vault",
        "origin": "clip",
        "title": clip.title,
        "url": clip.path,
        "summary": clip.source,
        "score": None,
        "eng_pct": None,
        "p": None,
        "tags": tags,
        "entities": [],
        "interests": _interest_ids(fm),
        "domain": domain,
    }


def _apply_df_stop(mentions: Sequence[dict]) -> None:
    doc_freq: Counter[str] = Counter()
    tagged_docs = 0
    for m in mentions:
        if m["tags"]:
            tagged_docs += 1
            doc_freq.update(set(m["tags"]))
    if tagged_docs < _DF_STOP_MIN_DOCS:
        return
    stop = {t for t, n in doc_freq.items() if n / tagged_docs >= _DF_STOP_FRAC}
    if not stop:
        return
    for m in mentions:
        if m["tags"]:
            m["tags"] = [t for t in m["tags"] if t not in stop]


def _mention_date(m: dict) -> date:
    return date.fromisoformat(m["at"][:10])


def _week_range(today: date, back: int) -> tuple[date, date]:
    """Inclusive (start, end) of the 7-day window `back` weeks before this week (back=0: this
    week, ending today)."""
    end = today - timedelta(days=7 * back)
    return end - timedelta(days=6), end


def _daily(mentions: Sequence[dict], today: date, n_days: int = DAILY_DAYS) -> list[dict[str, Any]]:
    notes_by_day: Counter[date] = Counter()
    clips_by_day: Counter[date] = Counter()
    for m in mentions:
        (clips_by_day if m["origin"] == "clip" else notes_by_day)[_mention_date(m)] += 1
    out = []
    for i in range(n_days - 1, -1, -1):
        d = today - timedelta(days=i)
        out.append({"date": d.isoformat(), "notes": notes_by_day.get(d, 0), "clips": clips_by_day.get(d, 0)})
    return out


def _week_summary(mentions: Sequence[dict], today: date) -> dict[str, Any]:
    def counts(is_clip: bool) -> tuple[int, list[int]]:
        start, end = _week_range(today, 0)
        this_week = sum(1 for m in mentions if (m["origin"] == "clip") == is_clip and start <= _mention_date(m) <= end)
        weekly = []
        for back in range(1, BASELINE_WEEKS + 1):
            s, e = _week_range(today, back)
            weekly.append(sum(1 for m in mentions if (m["origin"] == "clip") == is_clip and s <= _mention_date(m) <= e))
        return this_week, weekly

    notes_this, notes_weekly = counts(False)
    clips_this, clips_weekly = counts(True)
    return {
        "notes": notes_this,
        "clips": clips_this,
        "baseline_notes": statistics.median(notes_weekly),
        "baseline_clips": statistics.median(clips_weekly),
    }


def _weekly_series(mentions: Sequence[dict], today: date,
                    keys_of: Callable[[dict], Iterable[str]]) -> dict[str, tuple[int, list[int]]]:
    """For every key `keys_of(mention)` yields: (this week's count, [count per prior week,
    oldest... nearest]). Shared by tags/domains/interests — same rolling-week counting, different
    key and different final shape."""
    this_start, this_end = _week_range(today, 0)
    bounds = [_week_range(today, b) for b in range(1, BASELINE_WEEKS + 1)]
    this_c: Counter[str] = Counter()
    weekly: dict[str, list[int]] = defaultdict(lambda: [0] * BASELINE_WEEKS)
    for m in mentions:
        keys = list(keys_of(m))
        if not keys:
            continue
        d = _mention_date(m)
        in_this = this_start <= d <= this_end
        back_idx = next((i for i, (s, e) in enumerate(bounds) if s <= d <= e), None)
        for k in keys:
            if in_this:
                this_c[k] += 1
            if back_idx is not None:
                weekly[k][back_idx] += 1
    keys = set(this_c) | set(weekly)
    return {k: (this_c.get(k, 0), weekly.get(k, [0] * BASELINE_WEEKS)) for k in keys}


def _tag_examples(mentions: Sequence[dict], today: date, cap: int = TAG_EXAMPLES_CAP) -> dict[str, list[dict]]:
    start, end = _week_range(today, 0)
    out: dict[str, list[dict]] = defaultdict(list)
    for m in mentions:
        if not (start <= _mention_date(m) <= end):
            continue
        for t in m["tags"]:
            if len(out[t]) < cap:
                out[t].append({"title": m["title"], "path": m["url"]})
    return out


def _rising(this_week: int, baseline: float) -> bool:
    return this_week >= 3 and this_week >= 2 * baseline + 1


def _tag_stats(mentions: Sequence[dict], today: date) -> list[dict[str, Any]]:
    series = _weekly_series(mentions, today, lambda m: m["tags"])
    examples = _tag_examples(mentions, today)
    out = []
    for tag, (this_week, weekly) in series.items():
        baseline = sum(weekly) / BASELINE_WEEKS
        out.append({
            "tag": tag, "this_week": this_week, "baseline": round(baseline, 2),
            "ratio": round(this_week / baseline, 2) if baseline else None,
            "rising": _rising(this_week, baseline),
            "new": baseline == 0 and this_week >= 2,
            "examples": examples.get(tag, []),
        })
    out.sort(key=lambda x: (x["rising"], x["new"], x["this_week"] - x["baseline"]), reverse=True)
    return out[:TAG_TOP]


def _domain_stats(mentions: Sequence[dict], today: date) -> list[dict[str, Any]]:
    series = _weekly_series(mentions, today, lambda m: [m["domain"]] if m.get("domain") else [])
    out = []
    for domain, (this_week, weekly) in series.items():
        baseline = sum(weekly) / BASELINE_WEEKS
        out.append({
            "domain": domain, "this_week": this_week, "baseline": round(baseline, 2),
            "ratio": round(this_week / baseline, 2) if baseline else None,
            "rising": _rising(this_week, baseline),
        })
    out.sort(key=lambda x: (x["rising"], x["this_week"] - x["baseline"]), reverse=True)
    return out


def _interest_stats(mentions: Sequence[dict], today: date) -> list[dict[str, Any]]:
    series = _weekly_series(mentions, today, lambda m: m.get("interests") or [])
    out = [{"id": iid, "this_week": tw, "baseline": round(sum(weekly) / BASELINE_WEEKS, 2)}
           for iid, (tw, weekly) in series.items()]
    out.sort(key=lambda x: -x["this_week"])
    return out


def pulse(vault: Path, now: datetime, days: int = 56) -> dict[str, Any]:
    """The owner's notes and clips from the last `days`, and which tags/domains/interests are
    accelerating in them this week against the four weeks before."""
    today = now.date()
    since = today - timedelta(days=days)
    mentions: list[dict[str, Any]] = []
    skipped = 0

    for path in _content_paths(vault):
        try:
            fm, body = read_frontmatter(path, strict=True)
        except (UnparseableFrontmatter, OSError):
            skipped += 1
            continue
        day_str = str(fm.get("created") or fm.get("processed_date") or "")[:10]
        try:
            day = date.fromisoformat(day_str)
        except ValueError:
            skipped += 1
            continue
        if day < since:
            continue
        mentions.append(_note_mention(path, vault, fm, body, day.isoformat()))

    for clip in clips_mod.load(vault, since):
        mentions.append(_clip_mention(clip, vault))

    _apply_df_stop(mentions)
    mentions.sort(key=lambda m: (m["at"], m["title"]))

    return {
        "mentions": mentions,
        "daily": _daily(mentions, today),
        "week": _week_summary(mentions, today),
        "tags": _tag_stats(mentions, today),
        "domains": _domain_stats(mentions, today),
        "interests": _interest_stats(mentions, today),
        "skipped": skipped,
    }
