"""Eval: `radar.py signal` on a hand-made week — feed rows, two sensor day files, a vault with a
graph — offline (gaiafield and Kagi stubbed).

1. entities  — "Qwen 3.8 Next", "Qwen3.8-27B", "unsloth/Qwen3.8-27B-GGUF" share one key; a version,
               a size, "I've" and "128GB" are no names; "Show HN: Zither – …" names Zither
2. join      — Qwen3.8 is one blip across Reddit (feed) and Hugging Face (sensor), anchored in the
               vault note tagged `qwen` with the graph hub it links to; its older note means it is
               not "new" although the feed saw it only this week
3. early     — Zither, first seen today on Hacker News (top engagement) and in an RSS feed, both of
               which ran days before, is new, in the early list and a blind spot (no note has it)
4. filters   — an item the judge found irrelevant for every interest is no blip; a thing seen
               every day until five days ago and not since is "fading"
5. sources   — the sensors' "blocked" Reddit status reaches the page; the graph reports ok
6. kagi      — with a key, at most KAGI_CHECKS_PER_DAY names are asked, a second run the same day
               asks none again, and a hit joins the blip as family "kagi"
7. writes    — signal.json, Signal-Radar.html and Signal-Radar.md in the radar dir, the page
               carries its data and the note wikilinks the anchor note; nothing else in the vault
               changes but the radar dir
8. no graph  — without gaiafield the graph is "skipped" and the anchor still comes from the files
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "signal"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
ENV_KEYS = ("KAGI_API_KEY", "TOOLKIT_RADAR_INTERESTS_NOTE", "TOOLKIT_RADAR_TODOIST_PROJECT_ID",
            "TOOLKIT_GAIAFIELD_BIN")
INTERESTS_NOTE = """---
interests:
- name: Local AI Inference
  gloss: "Running open models on one's own hardware."
- name: Audio Plugins
  gloss: "New synths and effects for music production."
---
# Signal interests
"""
QWEN_NOTE = """---
created: 2026-08-01
tags: [domain/ai-ml, qwen, local-ai, W31-2026]
---
# Qwen notes

Runs well on two cards. See [[Local AI Hub]].
"""
HUB_NOTE = """---
created: 2026-05-01
tags: [domain/ai-ml]
---
# Local AI Hub
"""


def _day(n: int) -> str:
    return (NOW.date() - timedelta(days=n)).isoformat()


def _rows(local: str, audio: str) -> list[dict]:
    rows = []
    for n, title in ((0, "Qwen 3.8 Next is amazing"), (1, "Qwen3.8-27B on 2x3060"), (1, "I've tried Qwen 3.8 with 128GB")):
        rows.append({"run": _day(n), "saved_at": _day(n) + "T08:00:00+00:00", "feed": "reddit.com", "title": title,
                     "url": f"https://www.reddit.com/r/LocalLLaMA/comments/{n}{len(rows)}/x/", "kind": "news",
                     "p": {local: 0.9, audio: 0.05}, "backend": "jev"})
    for n in (0, 1):
        rows.append({"run": _day(n), "feed": "arXiv.org", "title": "BoringBench: a study of tables",
                     "url": f"https://arxiv.org/abs/2609.{n}", "kind": "paper", "p": {local: 0.1, audio: 0.05}, "backend": "jev"})
    for n in range(5, 17):
        rows.append({"run": _day(n), "feed": "reddit.com", "title": f"Progress on Grimoire 2 build {n}",
                     "url": f"https://www.reddit.com/r/LocalLLaMA/comments/g{n}/x/", "kind": "news",
                     "p": {local: 0.7, audio: 0.05}, "backend": "jev"})
    return rows


def _sensor_days(out: Path, local: str, audio: str) -> None:
    folder = out / "sensors"
    folder.mkdir(parents=True, exist_ok=True)
    today = {"day": _day(0), "updated": NOW.isoformat(),
             "status": {"hn": {"status": "ok", "items": 2, "detail": ""}, "hf": {"status": "ok", "items": 1, "detail": ""},
                        "reddit": {"status": "blocked", "items": 0, "detail": "HTTP 403"}},
             "items": {
                 "hn:1": {"source": "hn", "origin": "Show HN", "id": "1", "title": "Show HN: Zither – a free VST3 granular synth",
                          "url": "https://zither.example.org/", "summary": "120 comments", "score": 450,
                          "first_seen": NOW.isoformat(), "p": {local: 0.05, audio: 0.9}},
                 "hn:2": {"source": "hn", "origin": "Hacker News", "id": "2", "title": "Ask HN: What are you working on",
                          "url": "https://news.ycombinator.com/item?id=2", "score": 40, "first_seen": NOW.isoformat(),
                          "p": {local: 0.1, audio: 0.1}},
                 "hf:unsloth/Qwen3.8-27B-GGUF": {"source": "hf", "origin": "Hugging Face", "id": "unsloth/Qwen3.8-27B-GGUF",
                                                 "title": "unsloth/Qwen3.8-27B-GGUF", "url": "https://huggingface.co/unsloth/Qwen3.8-27B-GGUF",
                                                 "score": 300, "first_seen": NOW.isoformat(), "entities": ["Qwen3.8"],
                                                 "p": {local: 0.85, audio: 0.02}}}}
    yesterday = {"day": _day(1), "status": {}, "items": {
        "rss:kvr": {"source": "rss", "origin": "KVR Audio", "id": "kvr", "title": "Zither 1.0 granular synth released",
                    "url": "https://www.kvraudio.com/news/zither", "score": None,
                    "first_seen": _day(0) + "T01:00:00+00:00", "p": {local: 0.02, audio: 0.85}}}}
    # Four days ago every source already ran, so today's first sightings are past each horizon.
    earlier = {"day": _day(4), "status": {}, "items": {
        f"{src}:old": {"source": src, "origin": src, "id": "old", "title": f"Quiet {src} item", "url": f"https://{src}.example.org/old",
                       "score": 1, "first_seen": _day(4) + "T01:00:00+00:00", "p": {local: 0.1, audio: 0.1}}
        for src in ("hn", "hf", "rss")}}
    (folder / f"{_day(4)}.json").write_text(json.dumps(earlier), encoding="utf-8")
    (folder / f"{_day(0)}.json").write_text(json.dumps(today), encoding="utf-8")
    (folder / f"{_day(1)}.json").write_text(json.dumps(yesterday), encoding="utf-8")


def _graph_stub(args, timeout=None):
    cmd = args[0]
    if cmd == "index":
        return {"total_nodes": 2}
    if cmd == "stats":
        return {"nodes": 2, "edges": 1, "top_linked": [{"path": "04_Resources/Local AI Hub.md", "in_degree": 1}]}
    if cmd == "neighbors":
        if args[1] == "04_Resources/Qwen-Notes.md":
            return [{"path": "04_Resources/Local AI Hub.md", "title": "Local AI Hub", "depth": 1}]
        return []
    raise subprocess.CalledProcessError(2, args)


def _entity_checks(problems: list[str]) -> None:
    import entities as E
    keys = {E.key(n) for n in ("Qwen 3.8", "Qwen3.8-27B") } | {E.key(E.hf_family("unsloth/Qwen3.8-27B-GGUF"))}
    if keys != {"qwen38"}:
        problems.append(f"entities: Qwen spellings must share one key, got {keys}")
    for title, want, not_want in (("Show HN: Zither – a free VST3 granular synth", "Zither", None),
                                  ("I've tried Qwen 3.8 with 128GB", "Qwen 3.8", "128GB"),
                                  ("v2.1.283", None, "v2.1.283")):
        got = E.from_title(title)
        if want and want not in got:
            problems.append(f"entities: {title!r} should name {want!r}, got {got}")
        if not_want and not_want in got or any("'" in g or "’" in g for g in got):
            problems.append(f"entities: {title!r} must not name {not_want!r}, got {got}")
    if E.from_url("https://github.com/ggml-org/llama.cpp/releases/tag/b1") != ["llama.cpp"]:
        problems.append("entities: a GitHub release address names its repo")


def run(vault: Path) -> dict:
    import interests
    import kagi
    import signal_radar
    import vault_graph

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (vault_graph._run, kagi._request)
    kagi_calls: list[str] = []

    def kagi_stub(url, body=None):
        kagi_calls.append(url)
        return {"meta": {"api_balance": 10.0 - 0.002 * len(kagi_calls)},
                "data": [{"t": 0, "url": f"https://news.example.org/{len(kagi_calls)}", "title": "Zither review",
                          "published": _day(1) + "T10:00:00Z"}]}

    sandbox = None
    try:
        _entity_checks(problems)
        sandbox = make_sandbox(vault)
        (sandbox / "03_Areas" / "Sig-Interests.md").write_text(INTERESTS_NOTE, encoding="utf-8")
        (sandbox / "04_Resources" / "Qwen-Notes.md").write_text(QWEN_NOTE, encoding="utf-8")
        (sandbox / "04_Resources" / "Local AI Hub.md").write_text(HUB_NOTE, encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "03_Areas/Sig-Interests.md"
        os.environ["TOOLKIT_RADAR_TODOIST_PROJECT_ID"] = ""
        ids = {it.name: it.id for it in interests.from_note(sandbox)}
        local, audio = ids["Local AI Inference"], ids["Audio Plugins"]
        out = sandbox / "00_Memory" / "radar"
        out.mkdir(parents=True, exist_ok=True)
        (out / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in _rows(local, audio)), encoding="utf-8")
        _sensor_days(out, local, audio)
        vault_graph._run, kagi._request = _graph_stub, kagi_stub
        before = snapshot(sandbox)

        # 2–5, 7: no Kagi key
        r = signal_radar.write(sandbox, out, NOW)
        data = json.loads((out / "signal.json").read_text(encoding="utf-8"))
        blips = {b["key"]: b for b in data["blips"]}
        q = blips.get("qwen38")
        if not q:
            problems.append(f"join: no qwen38 blip, got {sorted(blips)}")
        else:
            if not {"reddit", "hf"} <= set(q["families"]):
                problems.append(f"join: qwen38 should carry reddit and hf, got {q['families']}")
            if q["in_vault"] < 1 or not any(h["path"] == "04_Resources/Local AI Hub.md" for h in q["graph"]["hubs"]):
                problems.append(f"join: qwen38 should be anchored with hub Local AI Hub, got {q['in_vault']} {q['graph']}")
            if q["stage"] == "new" or q["first_seen"] != "2026-08-01":
                problems.append(f"join: an older note makes qwen38 not new, got {q['stage']} {q['first_seen']}")
            if q["sector"] != local:
                problems.append(f"join: qwen38 belongs to {local}, got {q['sector']}")
        z = blips.get("zither")
        if not z or z["stage"] != "new" or "zither" not in data["early"] or "zither" not in data["blind_spots"] \
                or not {"hn", "rss"} <= set(z["families"]):
            problems.append(f"early: zither should be new, early and a blind spot from hn+rss, got {z and (z['stage'], z['families'])} "
                            f"early={data['early']} blind={data['blind_spots']}")
        if any(k.startswith("boringbench") for k in blips):
            problems.append("filters: an irrelevant arXiv item must not become a blip")
        g = blips.get("grimoire2")
        if not g or g["stage"] != "fading":
            problems.append(f"filters: grimoire2 should be fading, got {g and g['stage']}")
        if any(k in blips for k in ("128gb", "ive", "ivetried")):
            problems.append("filters: units and contractions are no names")
        src = {s["family"]: s["status"] for s in data["sources"]}
        if src.get("reddit") != "blocked" or src.get("graph") != "ok":
            problems.append(f"sources: expected reddit blocked and graph ok, got {src}")
        html = (out / "Signal-Radar.html").read_text(encoding="utf-8")
        md = (out / "Signal-Radar.md").read_text(encoding="utf-8")
        if "Zither" not in html or "application/json" not in html:
            problems.append("writes: the page must embed its data")
        if "[[04_Resources/Qwen-Notes" not in md:
            problems.append("writes: the note must wikilink the anchor note")
        changed = {p for p, v in snapshot(sandbox).items() if before.get(p) != v}
        outside = sorted(p for p in changed if not p.startswith("00_Memory/radar/"))
        if outside:
            problems.append(f"writes: only the radar dir may change, also changed {outside}")
        if r["status"] != "ok":
            problems.append(f"writes: status {r['status']}")

        # 6: Kagi, twice on the same day
        os.environ["KAGI_API_KEY"] = "stub-kagi-not-a-secret"
        signal_radar.write(sandbox, out, NOW, use_kagi=True)
        first = len(kagi_calls)
        data = json.loads((out / "signal.json").read_text(encoding="utf-8"))
        signal_radar.write(sandbox, out, NOW + timedelta(hours=3), use_kagi=True)
        if not 1 <= first <= signal_radar.KAGI_CHECKS_PER_DAY or len(kagi_calls) != first:
            problems.append(f"kagi: expected 1..{signal_radar.KAGI_CHECKS_PER_DAY} calls once, got {first} then {len(kagi_calls)}")
        z = next((b for b in data["blips"] if b["key"] == "zither"), None)
        if not z or "kagi" not in z["families"]:
            problems.append(f"kagi: a hit should join zither as family kagi, got {z and z['families']}")

        # 8: no graph
        def no_graph(args, timeout=None):
            raise FileNotFoundError("gaiafield")
        vault_graph._run = no_graph
        data = signal_radar.build(sandbox, out, NOW)
        q = next((b for b in data["blips"] if b["key"] == "qwen38"), None)
        if data["graph"]["status"] != "skipped" or not q or q["in_vault"] < 1 or q["graph"]["neighborhood"] != 0:
            problems.append(f"no graph: expected skipped with the file anchor kept, got {data['graph']['status']} {q and q['in_vault']}")
    finally:
        vault_graph._run, kagi._request = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"8 offline checks ok ({len(kagi_calls)} stubbed Kagi calls)"}
