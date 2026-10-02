"""Read the radar's ledgers for the vault's own views: what the feeds brought, what the judge rated,
what was promoted. Read-only, from `00_Memory/radar/state.jsonl` and `promoted.jsonl`, the
cross-plugin ledgers contract/KNOWLEDGE_API.md names, using only the fields that contract lists
(`worth`, `feed` and `kind` were added to it for this reader; never radar's code: plugins depend on
core/contract only). Interest ids are slugs of the names in the radar profile's interests note;
Todoist epics carry `epic-` ids. [earned: 2026-09-25, owner's request — "I also need to see what
is moving out there": the radar's daily note sat in 00_Memory where nothing showed it]
"""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from vault_utils import read_frontmatter, read_jsonl

STATE = Path("00_Memory") / "radar" / "state.jsonl"
PROMOTED = Path("00_Memory") / "radar" / "promoted.jsonl"
DEFAULT_INTERESTS_NOTE = "03_Areas/Trend Radar Profile.md"
RISING_MIN_STRONG = 3      # radar's TREND_MIN_STRONG: fewer strong items is noise, not a rise
RISING_FACTOR = 1.5        # this week's strong against the median of the weeks before it
RISING_MIN_WEEKS = 2       # weeks of history before anything can be called rising
# A ledger row scored against an interest id the owner has since renamed or removed: neither a
# live interest (not in the current names) nor an epic (its own always-valid naming). Every such
# id collapses into this one bucket instead of listing each stale slug as if it were still a
# current interest — `name_of` names it "Retired interests". [earned: 2026-09-28 battle test —
# "ai agents multi agent systems" (an old slug) and "AI Agents, Harnesses & Reliability" (its
# rename) both showed up in What's moving, as two different interests]
RETIRED_ID = "retired"


def slug(name: str, limit: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:limit].rstrip("-")


def interest_names(vault: Path) -> dict[str, str]:
    """Interest id → display name, from the interests note the radar profile points at; an epic
    id (`epic-…`, from Todoist) is named from its slug. An interest's own `aliases:` (old names it
    was renamed from) map their slugs to the current name too, so a rename recorded there does not
    orphan the interest's own history."""
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
                for alias in it.get("aliases") or []:
                    if isinstance(alias, str) and alias.strip():
                        names[slug(alias)] = str(it["name"])
    return names


def canon(iid: str, names: dict[str, str]) -> str:
    """A raw interest id as it should be aggregated: an epic as itself; a live interest, or one of
    its `aliases:`, as the interest's current id (the slug of its current name); anything else as
    `RETIRED_ID` — a ledger row scored days or months ago against an interest the owner has since
    renamed or dropped must not resurrect that old slug as if it were still current. [earned:
    2026-10-01 — an alias kept its own slug, so What's moving listed "Local AI & Self-Hosted
    Inference" twice (122/70/32 and 42/18/3), and three other renamed interests likewise]"""
    if iid.startswith("epic-"):
        return iid
    return slug(names[iid]) if iid in names else RETIRED_ID


_GH_RELEASE_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/releases(?:/tag/.+)?/?(?:\?.*)?$")


def release_title(url: str, title: str) -> str:
    """A GitHub release feed's own title is often just the tag ("v2.1.275"), meaningless without
    the repo it's from; prefix the repo name parsed from the item's own URL, the way every other
    feed item already names what it's about. [earned: 2026-09-28 battle test — "Top feed items"
    listed bare "v2.1.275", "v2.1.283" rows with no repo in sight]"""
    m = _GH_RELEASE_RE.match(str(url or ""))
    if m and title and not title.lower().startswith(m.group(2).lower()):
        return f"{m.group(2)} {title}"
    return title


def name_of(names: dict[str, str], iid: str) -> str:
    if iid == RETIRED_ID:
        return "Retired interests"
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
        days        day → {judged, worth, strong, promoted}, oldest first (the Atlas's funnel)
    """
    names = interest_names(vault)
    promoted_rows = read_jsonl(vault / PROMOTED)
    promoted_keys = {r.get("canonical") for r in promoted_rows}
    promoted_days = Counter(str(r.get("date") or "")[:10] for r in promoted_rows)
    sensor_days = Counter(str(r.get("date") or "")[:10] for r in promoted_rows if r.get("via") == "sensors")
    per: dict[str, Counter] = defaultdict(Counter)
    weeks: dict[str, Counter] = defaultdict(Counter)
    items: list[dict] = []
    counts = Counter()
    today_counts = Counter()
    per_day: dict[str, Counter] = defaultdict(Counter)
    for r in read_jsonl(vault / STATE):
        day = str(r.get("run") or r.get("saved_at") or "")[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}$", day) or day < since:
            continue
        raw_strong = [str(i) for i in (r.get("strong") or [])]
        strong = list(dict.fromkeys(canon(i, names) for i in raw_strong))
        worth = list(dict.fromkeys(canon(str(i), names) for i in (r.get("worth") or [])))
        best, top = _best(r.get("p"))
        top = canon(top, names) if top else top
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
        for key, hit in (("judged", True), ("worth", bool(worth)), ("strong", bool(strong)), ("promoted", promoted)):
            per_day[day][key] += hit
        if day == today.isoformat():
            today_counts["judged"] += 1
            today_counts["strong"] += bool(strong)
            today_counts["promoted"] += promoted
        for iid in {canon(str(i), names) for i in (r.get("p") or {})} if isinstance(r.get("p"), dict) else []:
            per[iid]["judged"] += 1
        for iid in worth:
            per[iid]["worth"] += 1
        for iid in strong:
            per[iid]["strong"] += 1
            if promoted:
                per[iid]["promoted"] += 1
        if strong and week:  # one item, one column: under the interest it scored highest for
            p = r.get("p") if isinstance(r.get("p"), dict) else {}
            best_raw = max(raw_strong, key=lambda i: float(p.get(i, 0) or 0))
            weeks[week][canon(best_raw, names)] += 1
        if strong or worth:
            item_url = str(r.get("url") or "")
            items.append({"day": day, "title": release_title(item_url, str(r.get("title") or ""))[:160], "url": item_url,
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
            "counts": dict(counts), "today": dict(today_counts), "promoted_today": promoted_days.get(today.isoformat(), 0),
            "promoted_today_sensors": sensor_days.get(today.isoformat(), 0),
            "days": {d: {k: per_day[d].get(k, 0) for k in ("judged", "worth", "strong", "promoted")} for d in sorted(per_day)}}
