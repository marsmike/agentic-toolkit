"""The owner's bubbles: how much each interest weighs, and which stories are events.

Promotion used to be one ranking, strongest first. On 2026-09-30 that gave Music Production 23
promotions and Local AI and AI Agents one each (27 and 23 strong items), while one news story
(Meta Muse) took 14 of a run. [earned: 2026-09-30 — the owner: "I do not want to miss anything
important, but need a weighted selection of what happened in my bubbles"]

**Weights.** An interest (a bubble) weighs what the vault says the owner spends on it:
`sqrt(1 + notes) + sqrt(1 + notes this month)`, where a note belongs to a bubble by its tags
(`Interest.tags`) or its `radar_interests`. The square roots keep a big bubble from drowning the
small ones; the month term follows current focus. A bubble the Signal Radar calls rising weighs
RISING_BOOST more. A Portfolio epic (no tags) weighs the median. The profile's `bubble_weights`
(interest id or name → multiplier) has the last word, e.g. `music-production-djing: 0.5`.

**Events.** A Signal Radar entity first seen within EVENT_DAYS, in one of the owner's sectors
(not "other": a place name is not a story) and not a phrase the interests already use (Jev and
Qwen are topics, not events), is an event: every candidate whose title names it is coverage of
that one story. An event is **must-see** when it is an early warning, or at MUST_SEE_STRENGTH
or more from MUST_SEE_FAMILIES independent source families.

Pure over its inputs (the interests, the vault's notes, `signal.json`); nothing leaves the machine.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from interests import Interest

EVENT_DAYS = 10
MUST_SEE_STRENGTH = 75
MUST_SEE_FAMILIES = 3
RISING_BOOST = 1.5
ACTIVE_FOLDERS = ("02_Projects", "03_Areas", "04_Resources")
_FM = re.compile(r"\A---\n(.*?)\n---", re.S)


def _frontmatter(text: str) -> dict[str, Any]:
    import yaml  # the radar's scripts already depend on PyYAML through interests

    m = _FM.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _as_set(value: Any) -> set[str]:
    if isinstance(value, str):
        value = [value]
    return {str(v).lower().lstrip("#") for v in value or [] if v}


def note_counts(vault: Path, interests: list[Interest], today: date) -> dict[str, tuple[int, int]]:
    """(all notes, notes processed in the last 30 days) per interest id."""
    month = (today - timedelta(days=30)).isoformat()
    tags = {i.id: {t.lower() for t in i.tags} for i in interests}
    counts = {i.id: [0, 0] for i in interests}
    for folder in ACTIVE_FOLDERS:
        root = vault / folder
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            try:
                fm = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            note_tags = _as_set(fm.get("tags"))
            radar = _as_set(fm.get("radar_interests"))
            recent = str(fm.get("processed_date") or "") >= month
            for iid, want in tags.items():
                if (want and note_tags & want) or iid in radar:
                    counts[iid][0] += 1
                    counts[iid][1] += recent
    return {k: (v[0], v[1]) for k, v in counts.items()}


def weights(interests: list[Interest], counts: dict[str, tuple[int, int]], rising: set[str] = frozenset(),
            overrides: dict[str, Any] | None = None) -> dict[str, float]:
    """Each interest's weight; they need not sum to anything, the allocator normalises."""
    raw: dict[str, float] = {}
    for i in interests:
        if i.tags:
            n, recent = counts.get(i.id, (0, 0))
            raw[i.id] = math.sqrt(1 + n) + math.sqrt(1 + recent)
    median = statistics.median(raw.values()) if raw else 2.0
    out = {i.id: raw.get(i.id, median) for i in interests}
    for iid in rising:
        if iid in out:
            out[iid] *= RISING_BOOST
    by_name = {i.name.lower(): i.id for i in interests}
    for key, mult in (overrides or {}).items():
        iid = key if key in out else by_name.get(str(key).lower())
        try:
            if iid:
                out[iid] *= max(0.0, float(mult))
        except (TypeError, ValueError):
            continue
    return out


@dataclass(frozen=True)
class Event:
    key: str
    name: str
    strength: float
    must_see: bool


def _phrase(name: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z]|-[a-z])", re.I)


def events(signal: dict[str, Any], interests: list[Interest], today: date) -> list[Event]:
    """The Signal Radar's fresh entities that are stories, strongest first; a name inside another
    ("Muse" in "Meta Muse") folds into the shorter one, so both headlines are one story."""
    since = (today - timedelta(days=EVENT_DAYS)).isoformat()
    vocab = " ".join(f"{i.name} {i.gloss} {' '.join(i.queries)} {' '.join(i.tags)}" for i in interests).lower()
    early = set(signal.get("early") or [])
    found: list[Event] = []
    for b in signal.get("blips") or []:
        name = str(b.get("name") or "").strip()
        if len(name) < 3 or str(b.get("first_seen") or "") < since or b.get("sector") in (None, "", "other"):
            continue
        if b.get("stage") not in ("new", "rising", "hot") or _phrase(name).search(vocab):
            continue
        strong = b.get("strength", 0) >= MUST_SEE_STRENGTH and len(b.get("families") or []) >= MUST_SEE_FAMILIES
        found.append(Event(str(b.get("key") or name.lower()), name, float(b.get("strength", 0)),
                           b.get("key") in early or strong))
    # fold "Meta Muse" into "Muse": the shorter name is the story, the longer one a headline of it
    folded: dict[str, Event] = {}
    for ev in sorted(found, key=lambda e: len(e.name)):
        home = next((f for f in folded.values() if _phrase(f.name).search(ev.name)), None)
        if home is None:
            folded[ev.key] = ev
        else:
            folded[home.key] = Event(home.key, home.name, max(home.strength, ev.strength), home.must_see or ev.must_see)
    return sorted(folded.values(), key=lambda e: -e.strength)


def event_of(title: str, evs: list[Event]) -> Event | None:
    """The strongest event a title names, or None."""
    return next((e for e in evs if _phrase(e.name).search(title or "")), None)


def rising(signal: dict[str, Any]) -> set[str]:
    return {t["id"] for t in signal.get("interest_trend") or [] if t.get("rising") and t.get("id")}


def load_signal(out: Path) -> dict[str, Any]:
    """`signal.json` as the Signal Radar routine last wrote it; {} when missing or broken."""
    try:
        data = json.loads((out / "signal.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
