"""Even promotion: every interest gets a turn, no source takes the run.

Both promotion paths (the sensors in `sensor_promote`, the Reader feed in `radar.settle`) rank
their candidates strongest first. On its own that lets one busy topic or one prolific source take
a whole run: on 2026-09-30 the sensors took 42 of the day's 50 promotions before the feed got any,
one Google News search (Meta/Muse) held 155 of the day's sensor items, and 14 of 20 promotions in
one run were one story. [earned: 2026-09-30 — the owner: "we need to ingest sources evenly"]

`interleave` reorders a ranked list round-robin by topic (each topic's best first, then each
topic's second, …), keeping the ranking inside every topic and ordering topics by their best
item. The callers then walk that order and cap each source per run.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")


def interleave(ranked: Iterable[T], topic_of: Callable[[T], str]) -> list[T]:
    """Round-robin by topic over a list already ranked best first."""
    groups: dict[str, list[T]] = {}
    for item in ranked:
        groups.setdefault(topic_of(item), []).append(item)
    order: list[T] = []
    depth = 0
    while True:
        layer = [g[depth] for g in groups.values() if depth < len(g)]
        if not layer:
            return order
        order += layer
        depth += 1


def top_interest(p: dict[str, float]) -> str:
    """The interest an item is strongest for: its topic for the round-robin."""
    return max(p, key=p.get) if p else ""
