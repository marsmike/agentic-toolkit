"""Read the radar's ledgers for the vault's own views: what the feeds brought, what the judge rated,
what was promoted. Read-only, from `00_Memory/radar/state.jsonl` and `promoted.jsonl`, the
cross-plugin ledgers contract/KNOWLEDGE_API.md names, using only the fields that contract lists
(`worth`, `feed` and `kind` were added to it for this reader; never radar's code: plugins depend on
core/contract only). Interest ids are slugs of the names in the radar profile's interests note;
Todoist epics carry `epic-` ids. [earned: 2026-09-25, owner's request — "I also need to see what
is moving out there": the radar's daily note sat in 00_Memory where nothing showed it]
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from vault_utils import read_frontmatter

STATE = Path("00_Memory") / "radar" / "state.jsonl"
PROMOTED = Path("00_Memory") / "radar" / "promoted.jsonl"
DEFAULT_INTERESTS_NOTE = "03_Areas/Trend Radar Profile.md"
RISING_MIN_STRONG = 3      # radar's TREND_MIN_STRONG: fewer strong items is noise, not a rise
RISING_FACTOR = 1.5        # this week's strong against the median of the weeks before it
RISING_MIN_WEEKS = 2       # weeks of history before anything can be called rising


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def slug(name: str, limit: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:limit].rstrip("-")


def interest_names(vault: Path) -> dict[str, str]:
    """Interest id → display name, from the interests note the radar profile points at; an epic
    id (`epic-…`, from Todoist) is named from its slug."""
    names: dict[str, str] = {}
    rel = os.environ.get("TOOLKIT_RADAR_INTERESTS_NOTE")
    if not rel:
        radar_profile = vault / "Config" / "toolkit" / "radar.md"
        fm = read_frontmatter(radar_profile)[0] if radar_profile.is_file() else {}
        rel = str(fm.get("interests_note") or DEFAULT_INTERESTS_NOTE)
    note = vault / rel
    if note.is_file():
        fm, _ = read_frontmatter(note)
        for it in fm.get("interests") or []:
            if isinstance(it, dict) and it.get("name"):
                names[slug(it["name"])] = str(it["name"])
    return names


def name_of(names: dict[str, str], iid: str) -> str:
    if iid in names:
        return names[iid]
    if iid.startswith("epic-"):
        return "Epic: " + iid[5:].replace("-", " ")
    return iid.replace("-", " ")


def _best(p: object) -> tuple[float, str]:
    if not isinstance(p, dict) or not p:
        return 0.0, ""
    iid, val = max(((k, v) for k, v in p.items() if isinstance(v, (int, float))), key=lambda kv: kv[1], default=("", 0.0))
    return float(val), str(iid)


def load(vault: Path, since: str, today: date) -> dict[str, Any]:
    """Everything a view needs, for rows judged on or after `since` (YYYY-MM-DD):

        items       worth-or-strong rows, newest first: day, title, url, feed, kind, p (best), top
                    (its interest), strong [ids], worth [ids], promoted, in_vault
        interests   id → {name, judged, worth, strong, promoted} over the window
        weeks       ISO week label → {interest id → strong items, each once, under its top interest},
                    oldest first, last 8 weeks
        rising      interest ids whose strong count this week beats RISING_FACTOR × the median of
                    the earlier weeks with data (at least RISING_MIN_WEEKS), and RISING_MIN_STRONG
        counts      judged, worth, strong, promoted over the window; and for `today`
    """
    names = interest_names(vault)
    promoted_keys = {r.get("canonical") for r in _rows(vault / PROMOTED)}
    promoted_days = Counter(str(r.get("date") or "")[:10] for r in _rows(vault / PROMOTED))
    per: dict[str, Counter] = defaultdict(Counter)
    weeks: dict[str, Counter] = defaultdict(Counter)
    items: list[dict] = []
    counts = Counter()
    today_counts = Counter()
    for r in _rows(vault / STATE):
        day = str(r.get("run") or r.get("saved_at") or "")[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}$", day) or day < since:
            continue
        strong = [str(i) for i in (r.get("strong") or [])]
        worth = [str(i) for i in (r.get("worth") or [])]
        best, top = _best(r.get("p"))
        promoted = r.get("canonical") in promoted_keys
        try:
            y, w, _ = date.fromisoformat(day).isocalendar()
            week = f"{y}-W{w:02d}"
        except ValueError:
            week = ""
        counts["judged"] += 1
        counts["worth"] += bool(worth)
        counts["strong"] += bool(strong)
        counts["promoted"] += promoted
        if day == today.isoformat():
            today_counts["judged"] += 1
            today_counts["strong"] += bool(strong)
            today_counts["promoted"] += promoted
        for iid in (r.get("p") or {}) if isinstance(r.get("p"), dict) else []:
            per[iid]["judged"] += 1
        for iid in worth:
            per[iid]["worth"] += 1
        for iid in strong:
            per[iid]["strong"] += 1
            if promoted:
                per[iid]["promoted"] += 1
        if strong and week:  # one item, one column: under the interest it scored highest for
            p = r.get("p") if isinstance(r.get("p"), dict) else {}
            weeks[week][max(strong, key=lambda i: float(p.get(i, 0) or 0))] += 1
        if strong or worth:
            items.append({"day": day, "title": str(r.get("title") or "")[:160], "url": str(r.get("url") or ""),
                          "feed": str(r.get("feed") or ""), "kind": str(r.get("kind") or ""), "p": round(best, 2),
                          "top": top, "strong": strong, "worth": worth, "promoted": promoted,
                          "in_vault": bool(r.get("in_vault"))})
    items.sort(key=lambda it: (it["day"], it["p"]), reverse=True)
    y, w, _ = today.isocalendar()
    this_week = f"{y}-W{w:02d}"
    weeks.setdefault(this_week, Counter())  # a quiet week is a zero column, and never mistaken for an older one
    week_labels = sorted(k for k in weeks if k <= this_week)[-8:]
    rising: list[str] = []
    if len(week_labels) > RISING_MIN_WEEKS:
        for iid in {i for w in week_labels for i in weeks[w]}:
            earlier = sorted(weeks[w].get(iid, 0) for w in week_labels[:-1])
            median = (earlier[len(earlier) // 2] if len(earlier) % 2 else
                      (earlier[len(earlier) // 2 - 1] + earlier[len(earlier) // 2]) / 2) if earlier else 0
            now = weeks[this_week].get(iid, 0)
            if now >= RISING_MIN_STRONG and now >= RISING_FACTOR * max(median, 1):
                rising.append(iid)
    interests = {iid: {"name": name_of(names, iid), **{k: per[iid].get(k, 0) for k in ("judged", "worth", "strong", "promoted")}}
                 for iid in sorted(per, key=lambda i: (-per[i]["strong"], -per[i]["worth"], i))}
    return {"items": items, "interests": interests, "weeks": {w: dict(weeks[w]) for w in week_labels},
            "rising": sorted(rising, key=lambda i: -weeks[this_week].get(i, 0)),
            "counts": dict(counts), "today": dict(today_counts), "promoted_today": promoted_days.get(today.isoformat(), 0)}
