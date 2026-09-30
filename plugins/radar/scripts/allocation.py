"""Choosing a run's promotions: must-see first, then a weighted turn for every bubble.

One selector for both paths (sensor items saved by URL, Reader feed items moved to Later). Given
the run's candidates, their bubbles' weights and credit, it hands out one candidate at a time;
the caller promotes it and reports back (`done`), so a candidate that fails (a Google News link
that does not resolve) costs no slot.

1. **One event, one promotion.** Candidates naming the same event (`bubbles.event_of`) are one
   story: the best copy represents it (a lab's own post, then the feed, then an open outlet, a
   paywall or Google News last, then strength) and the rest ride along as `also`. An event takes
   one promotion a run and at most `per_event_day` a day.
2. **Must-see lane.** A must-see event's representative and a lab's own announcement go first,
   up to `must_share` of the run, whatever the bubbles' credit says.
3. **Weighted turns.** Every bubble earns `budget × weight / Σweights` credit a run and pays one
   per promotion (credit carries across runs, clamped, halved at a new day). The next pick is the
   best candidate of the bubble with the most credit, except that a bubble with nothing promoted
   yet today goes first: every bubble with a strong item gets at least one a day. A bubble more
   than OVERDRAFT past its share waits (its items are held), even with budget left.
4. **Caps** on every pick but a must-see one: one source (`per_source_run` a run within one
   bubble, twice that across bubbles: arXiv and reddit carry several bubbles, and a shared cap
   held back the heaviest ones in the 2026-09-30 replay), one watched
   name (`per_name_run`, `per_name_day`), one GitHub release stream, and the sensors' share
   (`sensor_share` of the run while feed candidates remain).

What is not picked is `held()`: the caller keeps it for the next run (the sensors' window, the
feed's hold file) and reports it in the briefing, so nothing strong is dropped unseen.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

CREDIT_CLAMP = 1.0  # credit stays within ±(this × the run's budget)
# A bubble this far past its share waits for its credit to come back, even with budget left: the
# weights are the point, not the volume. Replaying 2026-09-30, Music (4.5% of the weight) took 19%
# of the day because the source caps blocked the others and the spare slots flowed to it.
OVERDRAFT = 1.0


@dataclass
class Cand:
    kind: str                      # "sensor" or "feed"
    key: str                       # canonical URL
    title: str
    url: str
    source: str                    # the feed, the Google News search, "Hacker News", a lab's blog
    p: dict[str, float]
    bubble: str                    # the interest it is strongest for
    strength: float                # its best p
    lab: bool = False              # a lab's own announcement
    last_choice: bool = False      # a paywall or a Google News redirect
    event: str | None = None
    event_name: str | None = None
    must_see: bool = False
    stream: str | None = None      # a GitHub release stream
    names: frozenset[str] = frozenset()   # watched names in its title
    ref: Any = None
    also: list[Cand] = field(default_factory=list)


@dataclass
class Caps:
    per_source_run: int = 3
    per_name_run: int = 2
    per_name_day: int = 6
    per_event_day: int = 3
    sensor_share: float | None = 0.5
    must_share: float = 0.5


def _preference(c: Cand) -> tuple:
    return (not c.lab, c.last_choice, c.kind != "feed", -c.strength)


def credit_for_run(credit: dict[str, float], weights: dict[str, float], budget: int, new_day: bool) -> dict[str, float]:
    """This run's credit: yesterday's halved at a new day, plus each bubble's share of the budget."""
    total = sum(w for w in weights.values() if w > 0) or 1.0
    limit = CREDIT_CLAMP * max(1, budget)
    out = {}
    for b, w in weights.items():
        c = credit.get(b, 0.0) * (0.5 if new_day else 1.0) + budget * max(0.0, w) / total
        out[b] = max(-limit, min(limit, c))
    return out


class Selector:
    def __init__(self, cands: list[Cand], budget: int, credit: dict[str, float], *, caps: Caps,
                 today_bubbles: Counter | None = None, today_events: Counter | None = None,
                 today_names: Counter | None = None, streams_taken: set[str] | None = None):
        self.budget = max(0, budget)
        self.caps = caps
        self.credit = dict(credit)
        self.weighted = bool(credit)   # no credit: every bubble alike, and no overdraft
        self.today_bubbles = Counter(today_bubbles or {})
        self.today_events = Counter(today_events or {})
        self.today_names = Counter(today_names or {})
        self.streams = set(streams_taken or ())
        self.run_sources: Counter = Counter()
        self.run_source_bubble: Counter = Counter()
        self.run_names: Counter = Counter()
        self.run_events: set[str] = set()
        self.taken: list[Cand] = []
        self.rejected: list[Cand] = []
        self.covered: list[Cand] = []   # an event's other copies, and events at their day's cap
        self.sensors = 0
        self.must = 0
        reps: list[Cand] = []
        by_event: dict[str, list[Cand]] = {}
        for c in cands:
            if c.event:
                by_event.setdefault(c.event, []).append(c)
            else:
                reps.append(c)
        for ev, group in by_event.items():
            group.sort(key=_preference)
            if self.today_events[ev] >= caps.per_event_day:
                self.covered += group
                continue
            head = group[0]
            head.also = group[1:]
            head.must_see = any(c.must_see for c in group)
            reps.append(head)
        self.pool: dict[str, list[Cand]] = {}
        for c in sorted(reps, key=lambda c: (not c.lab, -c.strength)):
            self.pool.setdefault(c.bubble, []).append(c)
        self.lane = [c for c in sorted(reps, key=lambda c: (not c.must_see, not c.lab, -c.strength))
                     if c.must_see or c.lab]

    # ---- the caps -------------------------------------------------------------------------------
    def _feed_left(self) -> bool:
        return any(c.kind == "feed" for cs in self.pool.values() for c in cs)

    def _fits(self, c: Cand, must: bool) -> bool:
        if c.event and c.event in self.run_events:
            return False
        if c.stream and c.stream in self.streams:
            return False
        if (self.run_source_bubble[(c.source, c.bubble)] >= self.caps.per_source_run
                or self.run_sources[c.source] >= 2 * self.caps.per_source_run):
            return False
        if must:
            return True
        if not c.lab and any(self.run_names[n] >= self.caps.per_name_run or self.today_names[n] >= self.caps.per_name_day
                             for n in c.names):
            return False
        if (c.kind == "sensor" and self.caps.sensor_share is not None and self._feed_left()
                and self.sensors >= math.ceil(self.budget * self.caps.sensor_share)):
            return False
        return True

    # ---- the walk -------------------------------------------------------------------------------
    def next(self) -> Cand | None:
        if len(self.taken) >= self.budget:
            return None
        if self.must < math.ceil(self.budget * self.caps.must_share):
            for c in self.lane:
                if self._fits(c, must=True):
                    return c
        order = sorted((b for b, cs in self.pool.items()
                        if cs and (not self.weighted or self.today_bubbles[b] == 0 or self.credit.get(b, 0.0) > -OVERDRAFT)),
                       key=lambda b: (self.today_bubbles[b] > 0, -self.credit.get(b, 0.0)))
        for b in order:
            for c in self.pool[b]:
                if self._fits(c, must=False):
                    return c
        return None

    def done(self, c: Cand, ok: bool) -> None:
        for cs in self.pool.values():
            if c in cs:
                cs.remove(c)
        if c in self.lane:
            self.lane.remove(c)
        if not ok:
            self.rejected.append(c)
            return
        self.taken.append(c)
        if c.must_see or c.lab:
            self.must += 1
        if c.kind == "sensor":
            self.sensors += 1
        self.run_sources[c.source] += 1
        self.run_source_bubble[(c.source, c.bubble)] += 1
        for n in c.names:
            self.run_names[n] += 1
            self.today_names[n] += 1
        if c.event:
            self.run_events.add(c.event)
            self.today_events[c.event] += 1
        if c.stream:
            self.streams.add(c.stream)
        self.today_bubbles[c.bubble] += 1
        self.credit[c.bubble] = self.credit.get(c.bubble, 0.0) - 1.0

    def run(self, promote) -> list[Cand]:
        """Walk to the end: `promote(c)` returns whether it worked."""
        while (c := self.next()) is not None:
            self.done(c, bool(promote(c)))
        return self.taken

    def held(self) -> list[Cand]:
        """Strong candidates this run did not take and did not reject, best first."""
        return sorted((c for cs in self.pool.values() for c in cs), key=lambda c: -c.strength)
