"""Eval: `feeds`, `trend` and `weekly` on a hand-made six-week series. No model, no network.

1. trend    — interest a jumps from 5 to 20 strong in about 100 (limit ~11): rising;
              b goes 5 -> 8: not rising; c exists only this week: "no baseline"; a week with
              fewer than two earlier weeks has no baseline for anyone; six loud weeks more than
              four weeks back do not mask a's rise (the baseline is the last four weeks); an item
              counts in the week it arrived in the feed (`saved_at`), not the week it was scanned
2. feeds    — 50 items over five weeks and nothing strong: "consider unsubscribing"; a feed whose
              strong items all serve a: "serves only a"; a productive feed gets no advice
3. weekly   — 01_Capture/Radar-Week-YYYY-Www.md with parseable frontmatter, the rising interest
              first and marked, a vault link for an item the vault has, no link into 00_Memory;
              a second write is refused, --force rewrites; nothing else in the vault changes; a
              week the radar never scanned gets no digest at all
4. terms    — a term generic to this feed set every week ("claude"/"agent") is auto-stoplisted once
              there is enough history, and not before; a name-like bigram ("Vector Loom") this week
              only outranks an equally-frequent generic one ("gadget update") with no capitalisation;
              a term the owner clipped several times ("jev") surfaces with zero feed corroboration,
              and only because the clips were passed in — without them it does not appear at all;
              the weekly digest's "Topics rising" section carries the same evidence
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "reports"
START = date(2026, 7, 20)  # a Monday, ISO week 30
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)  # Sunday of week 35

TERM_START = date(2026, 8, 3)  # a Monday, ISO week 32
TERM_WEEKS = 5


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


def _term_rows() -> list[dict]:
    """Every week: two generic feed items ("Claude Agent Update") from two feeds — this feed set's
    own always-there vocabulary. The last week only, also adds a name-like bigram ("Vector Loom",
    capitalised) and an equally-frequent plain one ("gadget update") from the same two feeds, to
    tell entity/bigram preference apart from raw frequency."""
    rows = []
    for k in range(TERM_WEEKS):
        run = (TERM_START + timedelta(weeks=k, days=2)).isoformat()
        for i in range(3):  # >= TERM_MIN_COUNT on its own, so a single week already qualifies
            feed = "FeedA" if i % 2 == 0 else "FeedB"
            rows.append({"run": run, "feed": feed, "title": f"Claude Agent Update {k}-{i}",
                        "url": f"https://example.org/update/{k}/{i}", "kind": "news", "p": {"a": 0.9}, "backend": "jev",
                        "saved_at": run})
        if k == TERM_WEEKS - 1:
            for i, angle in enumerate(("launches", "pricing", "docs", "demo")):
                feed = "FeedA" if i % 2 == 0 else "FeedC"
                rows.append({"run": run, "feed": feed, "title": f"Vector Loom {angle}",
                            "url": f"https://example.org/vl/{i}", "kind": "news", "p": {"a": 0.9}, "backend": "jev",
                            "saved_at": run})
                rows.append({"run": run, "feed": feed, "title": f"gadget update {i}",
                            "url": f"https://example.org/gadget/{i}", "kind": "news", "p": {"a": 0.9}, "backend": "jev",
                            "saved_at": run})
    return rows


def _term_clips(n: int = 5):
    from clips import Clip
    day = (TERM_START + timedelta(weeks=TERM_WEEKS - 1, days=3)).isoformat()
    return [Clip(path=f"01_Capture/jev-clip-{i}.md", title="Jev is trending", source="",
                saved_at=day, body="") for i in range(n)]


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
    old = [{"run": (START - timedelta(days=7 * j + 5)).isoformat(), "feed": "Main", "title": f"old {j}-{n}",
            "url": f"https://example.org/old/{j}/{n}", "kind": "news", "backend": "jev",
            "p": {"a": 0.9 if n < 60 else 0.1, "b": 0.1}} for j in range(6) for n in range(100)]
    if not reports.trend(rows + old, week)["a"]["rising"]:
        problems.append("phase 1: weeks more than four weeks back must not enter the baseline")
    late = [{**r, "run": (START + timedelta(days=37)).isoformat(), "saved_at": (START + timedelta(days=30)).isoformat() + "T09:00:00+00:00",
             "url": r["url"] + "/late"} for r in rows[:50]]
    prev = reports.week_of((START + timedelta(days=28)).isoformat())
    if reports.trend(rows + late, prev)["a"]["scanned"] != reports.trend(rows, prev)["a"]["scanned"] + 50:
        problems.append("phase 1: an item belongs to the week it arrived in the feed, not the week of the scan")

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
        # a week the radar never scanned has no digest (radar.report is what the CLI and the pipeline call)
        import radar
        state_dir = sandbox.parent / "radar-state"
        state_dir.mkdir()
        (state_dir / "state.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        r = radar.report(sandbox, state_dir, "weekly", NOW, "2026-W10")
        if r.get("status") != "empty" or snapshot(sandbox) != before:
            problems.append(f"phase 3: a week without scans must write nothing, got {r.get('status')}")
        interests = [Interest("a", "Agent Memory"), Interest("b", "Firmware"), Interest("c", "Birding")]
        text = reports.render_weekly(week, rows, interests, NOW)
        written = sandbox / "00_Memory" / "radar" / "weekly.jsonl"
        path = reports.write_weekly(sandbox, week, text, written=written)
        if path.relative_to(sandbox).as_posix() != f"01_Capture/Radar-Week-{week}.md":
            problems.append(f"phase 3: wrong capture path {path}")
        try:
            fm, body = read_frontmatter(path, strict=True)
        except UnparseableFrontmatter:
            fm, body = {}, ""
            problems.append("phase 3: the capture's frontmatter does not parse")
        if fm.get("status") != "draft" or fm.get("kind") != "radar-digest" or fm.get("via") != "radar" or not fm.get("description"):
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
        path.unlink()  # distill retired it
        try:
            reports.write_weekly(sandbox, week, text, written=written)
            problems.append("phase 3: a week already written must not be written again after distill retired it")
        except FileExistsError:
            pass
        reports.write_weekly(sandbox, week, text + "\n", force=True, written=written)
        changed = {p for p in snapshot(sandbox).keys() ^ before.keys()} | {
            p for p in before if snapshot(sandbox).get(p) != before[p]}
        if changed != {f"01_Capture/Radar-Week-{week}.md", "00_Memory/radar/weekly.jsonl"}:
            problems.append(f"phase 3: weekly wrote more than its capture: {sorted(changed)}")
    finally:
        if sandbox is not None:
            teardown_sandbox(sandbox)

    # 4. terms
    term_rows = _term_rows()
    term_week = reports.week_of(term_rows[-1]["run"])
    term_clips = _term_clips()
    with_clips = {t["term"]: t for t in reports.emerging_terms(term_rows, term_week, term_clips, limit=20)}
    without_clips = {t["term"]: t for t in reports.emerging_terms(term_rows, term_week, (), limit=20)}
    one_week_only = {t["term"]: t for t in reports.emerging_terms(term_rows[-11:], term_week, term_clips, limit=20)}

    if "claude" in with_clips or "agent" in with_clips:
        problems.append(f"phase 4: a term generic to every week must be auto-stoplisted, got {sorted(with_clips)}")
    if "claude" not in one_week_only and "agent" not in one_week_only:
        problems.append("phase 4: the auto-stoplist must not fire before there is enough history to call a term generic")
    if "vector loom" not in with_clips:
        problems.append(f"phase 4: a name-like bigram this week only should surface, got {sorted(with_clips)}")
    elif "gadget update" in with_clips and with_clips["vector loom"]["score"] <= with_clips["gadget update"]["score"]:
        problems.append("phase 4: a capitalised bigram should outrank an equally-frequent plain one")
    jev = with_clips.get("jev") or {}
    if jev.get("clip_count", 0) < 5 or jev.get("feed_count"):
        problems.append(f"phase 4: a term seen only in clips should surface with its clip count and no feed count, got {jev or 'nothing'}")
    elif not jev["examples"] or "Jev" not in jev["examples"][0]:
        problems.append(f"phase 4: a clip-only term's evidence should include a clip title, got {jev}")
    if "jev" in without_clips:
        problems.append("phase 4: without clips passed in, a clip-only term must not appear at all")

    digest = reports.render_weekly(term_week, term_rows, [Interest("a", "Agents")], NOW, clips=term_clips)
    if "## Topics rising" not in digest or "jev" not in digest.casefold() or "your own clips" not in digest:
        problems.append("phase 4: the weekly digest must show Topics rising with clip evidence")
    if "claude" in digest.casefold().split("## topics rising", 1)[1].split("## next actions")[0]:
        problems.append("phase 4: the digest's Topics rising must not list the auto-stoplisted term")

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "trend, feed advice, weekly capture and topic detection ok"}
