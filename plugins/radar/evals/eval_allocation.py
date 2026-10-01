"""Eval: even, weighted promotion — bubbles, events, the selector, the hold queue, the briefing.

1. weights    — sqrt(1 + notes) + sqrt(1 + notes this month) per bubble (tags or
                radar_interests), a rising bubble ×RISING_BOOST, an epic without tags the median,
                the profile's `bubble_weights` by id or by name
2. events     — a fresh Signal Radar entity in a sector is an event; a place (sector other), an
                old one and a term the interests use (Jev) are not; "Meta Muse" folds into "Muse";
                an early warning or strength ≥ 75 from ≥ 3 families is must-see
3. selector   — must-see first whatever the credit; every bubble's first item of the day before
                anyone's second; then turns in proportion to weight; one event one promotion (a
                lab's post represents it, the rest ride along as `also`); an event at its day's
                cap is covered; a rejected pick costs no slot; the rest is held, best first
4. credit     — each run adds budget × weight share, a new day halves what was left, clamped
5. hold       — a held feed item stays in Reader and comes back next run; after HOLD_DAYS it is
                archived and written to missed.jsonl; a sensor row that leaves unpromoted is missed
6. briefing   — bubbles heaviest first; ★ must-see, ⏳ held, ✗ missed, → the note, queued; a link is
                the address as saved (the row's `url`, else as a note or capture wrote it), never the
                lower-cased canonical key [earned: 2026-10-01 — a TradingView link was a 404]
[earned: 2026-09-30 — Music 23 promotions, Local AI and AI Agents 1 each, Muse 14 of a run]
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "allocation"
DAY = "2026-09-30"


def _cand(key, bubble, strength=0.9, **kw):
    from allocation import Cand
    return Cand(kind=kw.pop("kind", "sensor"), key=key, title=kw.pop("title", key), url=f"https://{key}",
                source=kw.pop("source", key), p={bubble: strength}, bubble=bubble, strength=strength, **kw)


def run(vault: Path) -> dict:
    import briefing
    import bubbles
    import radar
    import reader
    from allocation import Caps, Selector, credit_for_run
    from interests import Interest

    problems: list[str] = []

    # 1. weights
    ints = [Interest(id="agents", name="AI Agents", tags=("ai-agents",)),
            Interest(id="music", name="Music Production", tags=("music",)),
            Interest(id="local", name="Local AI", tags=("local-ai",)),
            Interest(id="epic-x", name="Epic X")]
    counts = {"agents": (80, 15), "music": (8, 3), "local": (24, 8)}
    w = bubbles.weights(ints, counts)
    if not math.isclose(w["agents"], math.sqrt(81) + math.sqrt(16)) or not math.isclose(w["music"], math.sqrt(9) + 2):
        problems.append(f"phase 1: sqrt(1+n) + sqrt(1+recent), got {w}")
    if not math.isclose(w["epic-x"], sorted([w["agents"], w["music"], w["local"]])[1]):
        problems.append(f"phase 1: an epic without tags weighs the median, got {w['epic-x']}")
    w2 = bubbles.weights(ints, counts, rising={"music"}, overrides={"Music Production": 0.5, "local": 2})
    if not math.isclose(w2["music"], w["music"] * bubbles.RISING_BOOST * 0.5) or not math.isclose(w2["local"], w["local"] * 2):
        problems.append(f"phase 1: rising boost and overrides by name and id, got {w2}")

    # 2. events
    today = date.fromisoformat(DAY)
    signal = {"early": ["devday"], "blips": [
        {"key": "muse", "name": "Muse", "stage": "hot", "first_seen": "2026-09-26", "strength": 83, "families": ["a", "b", "c", "d"], "sector": "frontier"},
        {"key": "metamuse", "name": "Meta Muse", "stage": "hot", "first_seen": "2026-09-24", "strength": 80, "families": ["a"], "sector": "frontier"},
        {"key": "devday", "name": "DevDay", "stage": "new", "first_seen": "2026-09-29", "strength": 60, "families": ["a"], "sector": "frontier"},
        {"key": "delhi", "name": "Delhi", "stage": "new", "first_seen": "2026-09-29", "strength": 62, "families": ["a", "b"], "sector": "other"},
        {"key": "jev", "name": "Jev", "stage": "hot", "first_seen": "2026-09-21", "strength": 77, "families": ["a", "b", "c"], "sector": "dm"},
        {"key": "claudecode", "name": "Claude Code", "stage": "hot", "first_seen": "2025-11-07", "strength": 74, "families": ["a"], "sector": "cc"},
        {"key": "ember", "name": "Ember-1", "stage": "rising", "first_seen": "2026-09-27", "strength": 50, "families": ["a"], "sector": "local"}]}
    eints = [Interest(id="dm", name="Decision models", gloss="TypeSafe's Jev and System One models")]
    evs = bubbles.events(signal, eints, today)
    by = {e.key: e for e in evs}
    if set(by) != {"muse", "devday", "ember"}:
        problems.append(f"phase 2: fresh sector entities not named by the interests are events, got {sorted(by)}")
    if not (by.get("muse") and by["muse"].must_see and by.get("devday") and by["devday"].must_see and not by["ember"].must_see):
        problems.append(f"phase 2: must-see is early or strong from many families, got {evs}")
    for title, want in (("Meta's Muse tops five million", "muse"), ("Meta Muse for small business", "muse"),
                        ("Ember-1 weights on HF", "ember"), ("Amusement park AI", None)):
        got = bubbles.event_of(title, evs)
        if (got.key if got else None) != want:
            problems.append(f"phase 2: {title!r} names {want}, got {got}")

    # 3. selector
    caps = Caps(per_source_run=9, per_name_run=9, per_name_day=9, per_event_day=3, sensor_share=None, must_share=0.5)
    credit = credit_for_run({}, {"agents": 3.0, "music": 1.0}, 8, new_day=True)
    pool = [_cand(f"a{i}", "agents", 0.9 - i / 100) for i in range(10)] + [_cand(f"m{i}", "music", 0.99 - i / 100) for i in range(10)]
    sel = Selector(pool, 8, credit, caps=caps)
    sel.run(lambda c: True)
    got = Counter(c.bubble for c in sel.taken)
    if got != Counter({"agents": 6, "music": 2}):
        problems.append(f"phase 3: weights 3:1 over 8 promotions give 6:2, got {dict(got)}")
    if [c.bubble for c in sel.taken[:2]] != ["music", "agents"] and [c.bubble for c in sel.taken[:2]] != ["agents", "music"]:
        problems.append("phase 3: both bubbles get their first item of the day before anyone's second")
    first = Selector([_cand(f"a{i}", "agents") for i in range(5)] + [_cand("q0", "quiet", 0.81)], 2,
                     {"agents": 5.0, "quiet": -3.0}, caps=caps, today_bubbles=Counter({"agents": 4}))
    first.run(lambda c: True)
    if "quiet" not in {c.bubble for c in first.taken}:
        problems.append("phase 3: a bubble with nothing today goes first, whatever its credit")
    ev = [_cand("outlet.example/muse", "frontier", 0.95, event="muse", last_choice=True),
          _cand("openai.com/muse", "frontier", 0.80, event="muse", lab=True, source="OpenAI News"),
          _cand("feed.example/muse", "frontier", 0.9, event="muse", kind="feed"),
          _cand("must.example/x", "music", 0.75, event="devday", must_see=True)]
    sel = Selector(ev, 5, {"frontier": 10.0, "music": -10.0}, caps=caps)
    sel.run(lambda c: True)
    keys = [c.key for c in sel.taken]
    if keys[:1] != ["must.example/x"] or "openai.com/muse" not in keys or len([k for k in keys if "muse" in k]) != 1:
        problems.append(f"phase 3: must-see first; one promotion for the event, its lab post; got {keys}")
    rep = next((c for c in sel.taken if c.key == "openai.com/muse"), None)
    if rep is None or {a.key for a in rep.also} != {"outlet.example/muse", "feed.example/muse"}:
        problems.append("phase 3: the event's other copies ride along as `also`")
    capped = Selector(ev[:3], 5, {}, caps=caps, today_events=Counter({"muse": 3}))
    if capped.next() is not None or len(capped.covered) != 3:
        problems.append("phase 3: an event at its day's cap is covered, nothing promoted")
    rej = Selector([_cand("x1", "agents"), _cand("x2", "agents", 0.8)], 1, {}, caps=caps)
    rej.run(lambda c: c.key != "x1")
    if [c.key for c in rej.taken] != ["x2"] or [c.key for c in rej.rejected] != ["x1"]:
        problems.append("phase 3: a rejected pick costs no slot")
    rest = Selector([_cand(f"h{i}", "agents", 0.9 - i / 10) for i in range(4)], 1, {}, caps=caps)
    rest.run(lambda c: True)
    if [c.key for c in rest.held()] != ["h1", "h2", "h3"]:
        problems.append(f"phase 3: the rest is held, best first, got {[c.key for c in rest.held()]}")
    one = Selector([_cand(f"s{i}", "agents", source="arXiv") for i in range(5)], 5, {},
                   caps=Caps(per_source_run=2, sensor_share=None))
    one.run(lambda c: True)
    many = Selector([_cand(f"s{i}", f"b{i % 3}", source="arXiv") for i in range(9)], 9, {},
                    caps=Caps(per_source_run=2, sensor_share=None))
    many.run(lambda c: True)
    if len(one.taken) != 2 or len(many.taken) != 4:
        problems.append(f"phase 3: one source gives a bubble per_source_run and all bubbles twice that, "
                        f"got {len(one.taken)} and {len(many.taken)}")
    over = Selector([_cand(f"o{i}", "agents") for i in range(5)] + [_cand("q", "music", 0.8)], 5,
                    {"agents": 0.5, "music": 0.2}, caps=caps, today_bubbles=Counter({"agents": 1, "music": 1}))
    over.run(lambda c: True)
    # agents 0.5 → -0.5 → -1.5 (one past its share), music 0.2 → -0.8; then agents waits with budget left
    if Counter(c.bubble for c in over.taken) != Counter({"agents": 2, "music": 1}) or len(over.held()) != 3:
        problems.append(f"phase 3: a bubble more than OVERDRAFT past its share waits, "
                        f"got {Counter(c.bubble for c in over.taken)}, {len(over.held())} held")

    # 4. credit
    c1 = credit_for_run({"agents": 4.0, "music": -2.0}, {"agents": 3.0, "music": 1.0}, 8, new_day=True)
    if not (math.isclose(c1["agents"], 8.0) and math.isclose(c1["music"], 1.0)):
        problems.append(f"phase 4: halved at a new day, plus the share, clamped to the budget; got {c1}")

    # 5. hold, via settle
    sandbox = None
    real_request = reader._request
    promoted, archived = [], []

    def stub(method, url, data=None):
        if method == "PATCH" and url.endswith("/bulk_update/"):
            for u in data["updates"]:
                (promoted if u["location"] == "later" else archived).append(u["id"])
            return 200, {"results": [{"id": u["id"], "success": True} for u in data["updates"]]}, None
        return 200, {"results": [], "nextPageCursor": None}, None

    try:
        sandbox = make_sandbox(vault)
        reader._request = stub
        from reader import Item
        out = sandbox.parent / "hold"
        out.mkdir()
        items = [Item(id=f"f{i}", url=f"https://feed{i}.example.org/p", canonical=f"feed{i}.example.org/p", title=f"Feed item {i}",
                      summary="", site=f"feed{i}", feed=f"feed{i}", published="", category="rss", saved_at="") for i in range(3)]
        rows = [{"canonical": it.canonical, "backend": "jev", "p": {"agents": 0.95 - i / 100}} for i, it in enumerate(items)]
        radar.settle(items, {it.canonical for it in items}, rows, {}, DAY, True, True, "later", out, per_run=1)
        if promoted != ["f0"] or "f1" in archived or "f2" in archived:
            problems.append(f"phase 5: one promoted, the two held stay in Reader; promoted {promoted}, archived {archived}")
        if [r.get("url") for r in radar.read_jsonl(out / "promoted.jsonl")] != ["https://feed0.example.org/p"]:
            problems.append("phase 5: a feed promotion's ledger row carries the item's URL")
        from allocation import Cand
        held = [Cand(kind="feed", key=it.canonical, title=it.title, url=it.url, source=it.feed, p={"agents": 0.9},
                     bubble="agents", strength=0.9, ref=it) for it in items[1:]]
        radar.write_hold(out, DAY, held, {"feed0.example.org/p"})
        promoted.clear()
        archived.clear()
        radar.settle([], set(), rows, {}, "2026-10-01", True, True, "later", out, per_run=1)
        if promoted != ["f1"]:
            problems.append(f"phase 5: a held item comes back first next run (not fetched again), got {promoted}")
        promoted.clear()
        archived.clear()
        radar.settle([], set(), rows, {}, "2026-10-04", True, True, "later", out, per_run=0)
        missed = [json.loads(x) for x in (out / radar.MISSED_FILE).read_text().splitlines()] if (out / radar.MISSED_FILE).exists() else []
        if "f2" not in archived or not any(m["canonical"] == "feed2.example.org/p" for m in missed):
            problems.append(f"phase 5: after HOLD_DAYS a held item is archived and missed; archived {archived}, missed {missed}")
        sens = [Cand(kind="sensor", key="gone.example.org/x", title="Gone story", url="https://gone.example.org/x", source="HN",
                     p={"agents": 0.9}, bubble="agents", strength=0.9)]
        radar.write_hold(out, DAY, sens, set())
        radar.write_hold(out, DAY, [], set())
        missed = [json.loads(x) for x in (out / radar.MISSED_FILE).read_text().splitlines()]
        if not any(m["canonical"] == "gone.example.org/x" and "sensor window" in m["why"] for m in missed):
            problems.append("phase 5: a sensor row that leaves unpromoted is missed")

        # 6. briefing
        alloc = {"weights": {"agents": 3.0, "music": 1.0}, "events": [{"key": "muse", "name": "Muse", "must_see": True}]}
        promoted_rows = [{"canonical": "a.example/1", "date": DAY, "bubble": "music", "title": "Synth news", "source": "Rekkerd"},
                         {"canonical": "b.example/2", "date": DAY, "bubble": "agents", "title": "Muse launch", "event": "muse",
                          "must_see": True, "source": "OpenAI News"},
                         {"canonical": "c.example/3", "date": DAY, "bubble": "agents", "title": "Harness paper", "source": "arXiv"}]
        held_rows = [{"canonical": "d.example/4", "bubble": "agents", "title": "Held paper", "url": "https://d.example/4",
                      "source": "arXiv", "first_held": DAY, "strength": 0.9}]
        missed_rows = [{"canonical": "e.example/5", "bubble": "music", "title": "Lost plugin", "url": "https://e.example/5",
                        "missed": DAY, "why": "held 3 days, never promoted"}]
        text = briefing.render(DAY, [Interest(id="agents", name="AI Agents"), Interest(id="music", name="Music")], alloc,
                               promoted_rows, held_rows, missed_rows,
                               {"b.example/2": "04_Resources/Muse-Launch.md", "c.example/3": "01_Capture/Readwise-x.md"},
                               datetime(2026, 9, 30, 12, tzinfo=UTC))
        if text.index("## AI Agents") > text.index("## Music") or "## Must-see" not in text or "★ **Muse**" not in text:
            problems.append("phase 6: must-see leads, then bubbles heaviest first")
        if "→ [[04_Resources/Muse-Launch]]" not in text or "queued for distill" not in text or "⏳" not in text or "✗" not in text:
            problems.append("phase 6: → note, queued, ⏳ held and ✗ missed are shown")
        (sandbox / "05_Archive" / "X").mkdir(parents=True, exist_ok=True)
        (sandbox / "05_Archive" / "X" / "cap--FULLCAPTURE.md").write_text("---\nsource: https://m.example/7\n---\n", encoding="utf-8")
        (sandbox / "04_Resources" / "Merged-Note.md").write_text(
            "---\nsource: https://first.example/1\nsources:\n  - https://first.example/1\n  - https://m.example/7\n---\n# M\n",
            encoding="utf-8")
        (sandbox / "04_Resources" / "Case-Note.md").write_text(
            "---\nsource: https://www.Example.org/news/ID_AbC123/story/\n---\n# C\n", encoding="utf-8")
        urls: dict[str, str] = {}
        idx = briefing.note_index(sandbox, urls)
        if idx.get("m.example/7") != "04_Resources/Merged-Note.md":
            problems.append(f"phase 6: an item merged into a note's `sources` maps to that note, not its archived capture; got {idx.get('m.example/7')}")
        cased = briefing.render(DAY, [Interest(id="agents", name="AI Agents")], alloc,
                                [{"canonical": "example.org/news/id_abc123/story", "date": DAY, "bubble": "agents", "title": "Old row"},
                                 {"canonical": "x.example/Y", "date": DAY, "bubble": "agents", "title": "New row",
                                  "url": "https://x.example/Y?ref=1"}],
                                [], [], idx, datetime(2026, 9, 30, 12, tzinfo=UTC), urls=urls)
        if "(https://www.Example.org/news/ID_AbC123/story/)" not in cased or "(https://x.example/Y?ref=1)" not in cased:
            problems.append(f"phase 6: links are the address as saved, not the lower-cased key: {cased}")
        if briefing._tail("05_Archive/X/cap--FULLCAPTURE.md") != " · archived":
            problems.append("phase 6: the archive is never linked")
        if radar.briefing_cmd(sandbox, sandbox / "00_Memory" / "no-radar-here", datetime(2026, 9, 30, tzinfo=UTC))["status"] != "skipped":
            problems.append("phase 6: `briefing` skips a vault without radar state")
        bdir = sandbox.parent / "brief"
        bdir.mkdir()
        (bdir / "promoted.jsonl").write_text(json.dumps({"canonical": "z.example/1", "date": DAY, "title": "Z"}) + "\n", encoding="utf-8")
        if radar.briefing_cmd(sandbox, bdir, datetime(2026, 9, 30, 21, tzinfo=UTC)).get("status") != "ok" or not (bdir / f"Bubbles-{DAY}.md").exists():
            problems.append("phase 6: `briefing` rebuilds the day's briefing")
        if "weight 75%" not in text:
            problems.append("phase 6: each bubble shows its weight share")
        legacy = briefing.render(DAY, [Interest(id="agents", name="AI Agents")], alloc,
                                 [{"canonical": "old.example/1", "date": DAY, "title": "Before bubbles"},
                                  {"canonical": "odd.example/2", "date": DAY, "title": "Unjudged"}], [], [], {},
                                 datetime(2026, 9, 30, 12, tzinfo=UTC), {"old.example/1": "agents"})
        if "## AI Agents" not in legacy or "## Other" not in legacy or "Before bubbles" not in legacy.split("## Other")[0]:
            problems.append("phase 6: a row without `bubble` lands in its judged bubble, else Other")
    finally:
        reader._request = real_request
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "6 offline phases ok (weights, events, selector, credit, hold, briefing)"}
