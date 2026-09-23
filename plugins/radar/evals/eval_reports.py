"""Eval: `feeds`, `trend` and `weekly` on a hand-made six-week series. No model, no network.

1. trend    — interest a jumps from 5 to 20 strong in about 100 (limit ~11): rising;
              b goes 5 -> 8: not rising; c exists only this week: "no baseline"; a week with
              fewer than two earlier weeks has no baseline for anyone
2. feeds    — 50 items over five weeks and nothing strong: "consider unsubscribing"; a feed whose
              strong items all serve a: "serves only a"; a productive feed gets no advice
3. weekly   — 01_Capture/Radar-Week-YYYY-Www.md with parseable frontmatter, the rising interest
              first and marked, a vault link for an item the vault has, no link into 00_Memory;
              a second write is refused, --force rewrites; nothing else in the vault changes
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "reports"
START = date(2026, 7, 20)  # a Monday, ISO week 30
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)  # Sunday of week 35


def _rows() -> list[dict]:
    rows = []
    for k in range(6):
        run = (START + timedelta(days=7 * k + 2)).isoformat()
        strong_a = 20 if k == 5 else 5
        strong_b = 8 if k == 5 else 5
        for n in range(100):
            p = {"a": 0.9 if n < strong_a else 0.1, "b": 0.9 if 50 <= n < 50 + strong_b else 0.1}
            if k == 5:
                p["c"] = 0.1
            rows.append({"run": run, "feed": "Main", "title": f"agent memory item {n}" if n < 3 else f"item {k}-{n}",
                         "url": f"https://example.org/{k}/{n}", "kind": "news", "p": p, "backend": "jev",
                         "in_vault": "04_Resources/Known-Note.md" if (k, n) == (5, 0) else
                         ("00_Memory/radar/2026-08-26.md" if (k, n) == (5, 1) else None)})
        for n in range(10):
            rows.append({"run": run, "feed": "Quiet", "title": f"quiet {k}-{n}", "url": f"https://quiet.example.org/{k}/{n}",
                         "kind": "news", "p": {"a": 0.2, "b": 0.2}, "backend": "jev"})
        rows.append({"run": run, "feed": "Mono", "title": f"mono {k}", "url": f"https://github.com/acme/mono{k}",
                     "kind": "release-or-tool", "p": {"a": 0.95, "b": 0.1}, "backend": "jev"})
    return rows


def run(vault: Path) -> dict:
    import reports
    from interests import Interest
    from vault_utils import UnparseableFrontmatter, read_frontmatter

    problems: list[str] = []
    rows = _rows()
    week = reports.week_of((START + timedelta(days=35)).isoformat())

    # 1. trend
    tr = reports.trend(rows, week)
    if not tr["a"]["rising"]:
        problems.append(f"phase 1: a (21 strong vs limit ~11) should be rising, got {tr['a']}")
    if tr["b"]["rising"]:
        problems.append(f"phase 1: b (8 strong vs limit ~9.5) must not be rising, got {tr['b']}")
    if tr["c"].get("note") != "no baseline":
        problems.append(f"phase 1: c has no earlier weeks, expected no baseline, got {tr['c']}")
    early = reports.trend(rows, reports.week_of((START + timedelta(days=7)).isoformat()))
    if any(e.get("baseline") is not None for e in early.values()):
        problems.append("phase 1: the second week has one earlier week, which is no baseline")

    # 2. feeds
    f = {x["feed"]: x for x in reports.feeds(rows, NOW)}
    if "consider unsubscribing" not in f["Quiet"]["advice"]:
        problems.append(f"phase 2: Quiet (60 items, none strong, 6 weeks) should be flagged, got {f['Quiet']}")
    if "serves only a" not in f["Mono"]["advice"]:
        problems.append(f"phase 2: Mono should serve only a, got {f['Mono']['advice']}")
    if f["Main"]["advice"]:
        problems.append(f"phase 2: Main earns its place, got advice {f['Main']['advice']}")

    # 3. weekly
    sandbox = None
    try:
        sandbox = make_sandbox(vault)
        before = snapshot(sandbox)
        interests = [Interest("a", "Agent Memory"), Interest("b", "Firmware"), Interest("c", "Birding")]
        text = reports.render_weekly(week, rows, interests, NOW)
        path = reports.write_weekly(sandbox, week, text)
        if path.relative_to(sandbox).as_posix() != f"01_Capture/Radar-Week-{week}.md":
            problems.append(f"phase 3: wrong capture path {path}")
        try:
            fm, body = read_frontmatter(path, strict=True)
        except UnparseableFrontmatter:
            fm, body = {}, ""
            problems.append("phase 3: the capture's frontmatter does not parse")
        if fm.get("status") != "draft" or fm.get("kind") != "radar-digest" or not fm.get("description"):
            problems.append(f"phase 3: frontmatter should be a draft radar-digest with a description, got {fm}")
        if "### 1. Agent Memory (rising)" not in body:
            problems.append("phase 3: the rising interest should come first and be marked")
        if "[[04_Resources/Known-Note]]" not in body or "[[00_Memory" in body:
            problems.append("phase 3: link the vault note the item is in, never 00_Memory")
        if "https://github.com/acme/mono5" not in body.split("## Repos to evaluate")[1]:
            problems.append("phase 3: a worth GitHub item should be listed under repos to evaluate")
        try:
            reports.write_weekly(sandbox, week, text)
            problems.append("phase 3: a second write must be refused without --force")
        except FileExistsError:
            pass
        reports.write_weekly(sandbox, week, text + "\n", force=True)
        changed = {p for p in snapshot(sandbox).keys() ^ before.keys()} | {
            p for p in before if snapshot(sandbox).get(p) != before[p]}
        if changed != {f"01_Capture/Radar-Week-{week}.md"}:
            problems.append(f"phase 3: weekly wrote more than its capture: {sorted(changed)}")
    finally:
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "trend, feed advice and weekly capture ok on a six-week series"}
