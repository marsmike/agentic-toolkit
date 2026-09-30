"""Eval: sensor items promoted to Reader (`sensor_promote.py`) and the web check's candidates
(`signal_radar.check_candidates`), offline (stubbed Reader).

1. rules      — a lab announcement is saved whatever its p; an HN item with SENSOR_HN_MOMENTUM points
                and T_WORTH is saved; a title naming a watched lab or model at T_WORTH is saved, and
                one below it is not; a strong Kagi News item is saved; a strong Hugging Face item
                is not (not a promote source); in that order, tagged radar/sensors, one
                promoted.jsonl row each with via: sensors
2. skips      — already promoted, held by the vault, another outlet's copy of a saved story (a
                paywalled outlet loses a tie to an open one), a
                bare youtube.com/watch, an item only in a day file older than the window, one
                published before the window, and a lab's customer story that only its own RSS
                carried (below LAB_RSS_MIN_P) are never saved; `Metadata` does not match the watched name `Meta`
3. budget     — at most the run's budget, however many were promoted earlier that day (the budget
                is per run); a second run saves nothing new; a Reader failure is reported, not raised
4. check      — the web check never spends a check on an Other-sector name, asks watched names
                first, and gives a one-word name its interest's name as context
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "sensor_promote"
NOW = datetime(2026, 9, 30, 6, 58, tzinfo=UTC)
DAY = NOW.date().isoformat()
T = {"T_WORTH": 0.70, "T_STRONG": 0.80}
WATCH = ["OpenAI", "GPT", "Claude", "Meta", "Muse"]
KNOWN_NOTE = "---\ndescription: known\nstatus: distilled\nsource: https://held.example.org/story\n---\n# k\n"


def _item(source: str, title: str, url: str, p: float, score: float | None = None, published: str = DAY) -> dict:
    return {"source": source, "origin": source, "title": title, "url": url, "summary": "", "published": published,
            "score": score, "p": {"frontier": p, "other-interest": 0.1}, "kind": "news", "entities": []}


ITEMS = {
    "hn:1": _item("hn", "DevDay 2026 Recap", "https://openai.com/index/devday-2026-recap/", 0.31, 87),
    "hn:2": _item("hn", "A fast new database engine", "https://db.example.org/launch", 0.72, 805),
    "hn:3": _item("hn", "A fast new database engine", "https://db2.example.org/quiet", 0.72, 40),
    "kagi_news:a": _item("kagi_news", "OpenAI shelves GPT-6.1 Astra after safety tests", "https://www.ft.com/content/astra", 0.9),
    "kagi_news:b": _item("kagi_news", "OpenAI shelves GPT-6.1 Astra after safety tests flag risks", "https://npr.example.org/astra", 0.9),
    "kagi_news:c": _item("kagi_news", "Claude gets a new plan", "https://news.example.org/claude", 0.65),
    "kagi_news:d": _item("kagi_news", "Metadata standards body meets", "https://std.example.org/meta", 0.72),
    "kagi_news:e": _item("kagi_news", "Muse agent draws scrutiny", "https://www.youtube.com/watch", 0.9),
    "kagi_news:f": _item("kagi_news", "Chip maker opens a new fab", "https://fab.example.org/news", 0.86),
    "rss:1": _item("rss", "Already promoted story about GPT", "https://done.example.org/x", 0.9),
    "rss:2": _item("rss", "A story the vault holds about GPT", "https://held.example.org/story", 0.9),
    "hf:1": _item("hf", "org/strong-model", "https://huggingface.co/org/strong-model", 0.95),
    "rss:3": _item("rss", "Proaction boosts sales 60% with Codex", "https://openai.com/index/proaction/", 0.4),
    "kagi_news:g": _item("kagi_news", "Solar farm record output", "https://solar.example.org/x", 0.9, published="2026-09-20"),
}
OLD = {"hn:old": _item("hn", "Introducing GPT-5 old news", "https://openai.com/index/old/", 0.9, 900)}


def run(vault: Path) -> dict:
    import radar
    import reader
    import sensor_promote
    import signal_radar

    problems: list[str] = []
    real = reader._request
    saves: list[dict] = []
    fail = {"on": False}
    sandbox = None

    def reader_stub(method, url, data=None):
        if method != "POST" or not url.endswith("/save/"):
            problems.append(f"reader: sensor promotion may only save, got {method} {url}")
        if fail["on"]:
            return 500, None, "boom"
        saves.append(data)
        return 201, {"id": f"saved{len(saves)}"}, None

    try:
        sandbox = make_sandbox(vault)
        (sandbox / "04_Resources" / "Held.md").write_text(KNOWN_NOTE, encoding="utf-8")
        reader._request = reader_stub
        out = sandbox.parent / "radar"
        (out / "sensors").mkdir(parents=True)
        (out / "sensors" / f"{DAY}.json").write_text(json.dumps({"day": DAY, "items": ITEMS}), encoding="utf-8")
        (out / "sensors" / "2026-09-20.json").write_text(json.dumps({"day": "2026-09-20", "items": OLD}), encoding="utf-8")
        (out / "promoted.jsonl").write_text(json.dumps({"canonical": "done.example.org/x", "date": "2026-09-29"}) + "\n",
                                            encoding="utf-8")
        known = set(radar.vault_sources(sandbox))
        names = {"frontier": "Frontier Models & Labs"}

        # 1 + 2. rules and skips
        r = sensor_promote.promote(out, T, DAY, 50, "later", known, names, WATCH)
        urls = [s["url"] for s in saves]
        want = ["https://openai.com/index/devday-2026-recap/", "https://db.example.org/launch",
                "https://npr.example.org/astra", "https://fab.example.org/news"]
        if urls != want:
            problems.append(f"phase 1: expected lab, momentum, watched, strong in order {want}, got {urls}")
        if saves and (saves[0]["tags"] != ["radar", "radar/frontier"]
                      or not saves[0]["notes"].startswith("[radar sensors") or "lab announcement" not in saves[0]["notes"]):
            problems.append(f"phase 1: a save is tagged radar/<interest> only, its note says sensors and why; got {saves[0]}")
        rows = [json.loads(ln) for ln in (out / "promoted.jsonl").read_text(encoding="utf-8").splitlines()[1:]]
        if len(rows) != len(want) or any(x.get("via") != "sensors" or not x.get("title") for x in rows):
            problems.append(f"phase 1: one promoted.jsonl row per save, via sensors, with its title; got {rows}")
        if r.get("sensors_by_rule") != {"lab": 1, "momentum": 1, "watched": 1, "strong": 1}:
            problems.append(f"phase 1: the result counts saves per rule, got {r}")
        for bad in ("done.example.org", "held.example.org", "ft.com", "youtube.com", "std.example.org",
                    "openai.com/index/old", "huggingface.co", "db2.example.org", "news.example.org",
                    "openai.com/index/proaction", "solar.example.org"):
            if any(bad in u for u in urls):
                problems.append(f"phase 2: {bad} must not be saved")

        # 3. budget, a second run, a Reader failure
        saves.clear()
        if sensor_promote.promote(out, T, DAY, 50, "later", known, names, WATCH) or saves:
            problems.append(f"phase 3: a second run the same day saves nothing new, got {len(saves)}")
        (out / "promoted.jsonl").write_text("", encoding="utf-8")
        sensor_promote.promote(out, T, DAY, 2, "later", known, names, WATCH)
        if len(saves) != 2:
            problems.append(f"phase 3: a budget of 2 saves two, got {len(saves)}")
        # 49 promoted earlier today do not count against this run [earned: 2026-09-30 — a daily
        # cap spent by 07:11 UTC starved every later run]
        (out / "promoted.jsonl").write_text("".join(json.dumps({"canonical": f"f{n}", "date": DAY}) + "\n" for n in range(49)),
                                            encoding="utf-8")
        saves.clear()
        sensor_promote.promote(out, T, DAY, 3, "later", known, names, WATCH)
        if len(saves) != 3:
            problems.append(f"phase 3: a run's budget of 3 saves three whatever the day promoted before, got {len(saves)}")
        (out / "promoted.jsonl").write_text("", encoding="utf-8")
        fail["on"] = True
        r = sensor_promote.promote(out, T, DAY, 50, "later", known, names, WATCH)
        if r.get("sensors_promoted") != 0 or not r.get("sensors_promote_errors"):
            problems.append(f"phase 3: a Reader failure is reported, not raised, got {r}")
        fail["on"] = False

        # 4. the web check's candidates
        def blip(name, sector, families=1, strength=50):
            return {"key": name.lower(), "name": name, "stage": "new", "sector": sector,
                    "families": ["hn"] * families, "strength": strength}
        cands = signal_radar.check_candidates(
            [blip("jeff", "other", strength=66), blip("Delhi", "other"), blip("Traktor", "music"),
             blip("GPT-6.1 Sol", "frontier", families=2), blip("Ember-1", "frontier")],
            {"music": "Music Production & DJing", "frontier": "Frontier Models & Labs"}, WATCH)
        by = {c["name"]: c for c in cands}
        if set(by) != {"Traktor", "GPT-6.1 Sol", "Ember-1"}:
            problems.append(f"phase 4: Other-sector names are never checked, got {sorted(by)}")
        if not by.get("GPT-6.1 Sol", {}).get("watched") or by.get("Ember-1", {}).get("watched"):
            problems.append("phase 4: a watched name is marked watched, another is not")
        if by.get("Traktor", {}).get("context") != "Music Production DJing" or by.get("Ember-1", {}).get("context"):
            problems.append(f"phase 4: only a one-word name gets its interest as context, got {by.get('Traktor')}")
        asked = []
        signal_radar._name_check(out, cands, NOW, "tavily", "signal-tavily.jsonl",
                                 lambda name, context="": asked.append(name) or [])
        if asked[:1] != ["GPT-6.1 Sol"]:
            problems.append(f"phase 4: watched names are asked first, got {asked}")
    finally:
        reader._request = real
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "4 offline phases ok (rules, skips, budget, web-check candidates)"}
