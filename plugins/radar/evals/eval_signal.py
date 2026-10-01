"""Eval: `radar.py signal` on a hand-made week — feed rows, two sensor day files, a vault with a
graph — offline (gaiafield and Kagi stubbed).

1. entities  — "Qwen 3.8 Next", "Qwen3.8-27B", "unsloth/Qwen3.8-27B-GGUF" share one key; a version,
               a size, "I've" and "128GB" are no names; "Show HN: Zither – …" names Zither
1b. merge    (pure, no sandbox) — real cases, Signal Radar 2026-10-01 04:15 UTC: Scope and Dental
               Scope share an ending, not a subject, and must not merge; Muse (fewer mentions)
               folds into Meta Muse (more), Sol into GPT-6.1 Sol, never the reverse; a jeff-shaped
               Other-sector bare name is checked with disambiguating context, not skipped or asked
               bare; "r/ClaudeAI" names no ClaudeAI entity; a demonym ("Chinese AI model …") names
               nothing on its own
2. join      — Qwen3.8 is one blip across Reddit (feed) and Hugging Face (sensor), anchored in the
               vault note tagged `qwen` with the graph hub it links to; its older note means it is
               not "new" although the feed saw it only this week
3. early     — Zither, first seen today on Hacker News (top engagement) and in an RSS feed, both of
               which ran days before, is new, in the early list and a blind spot (no note has it);
               the same RSS article also arriving through Reader is one mention, not a third family
4. filters   — an item the judge found irrelevant for every interest is no blip; a thing seen
               every day until five days ago and not since is "fading"; "Windows 11", judged
               relevant to Audio Plugins by exactly one incidental mention (real case, 2026-09-28:
               a Native Instruments forum post about a DJ controller driver), is still a blip but
               falls to Other rather than being sector-pinned by that one mention
5. sources   — the sensors' "blocked" Reddit status reaches the page; the graph reports ok
6. check     — Tavily unavailable: Kagi answers, at most CHECKS_PER_DAY names are asked, a second run the same day
               asks none again, and a hit joins the blip as family "kagi"; its calls go to its own
               ledger file, and the pipeline's spend in the other one counts against the same budget;
               with Tavily available it asks the news index first (6c); a name with 0 news hits (6d)
               falls back to a general search, still under the same ledger/budget
7. writes    — signal.json, Signal-Radar.html, Signal-Radar.md and the note's two SVGs
               (Signal-Radar-scope.svg, Signal-Radar-momentum.svg) in the radar dir, the page
               carries its data and the note embeds both SVGs and wikilinks the anchor note; the
               SVGs are well-formed, scriptless, titled, escape a hostile name, re-render byte for
               byte and draw one dot per blip the page places; nothing else in the vault changes
               but the radar dir
8. no graph  — without gaiafield the graph is "skipped" and the anchor still comes from the files
9. vocab/early (pure, no sandbox) — "Sonnet 5.5" on one mention keeps its sector because "Sonnet"
               is a sibling of "Opus"/"Fable", already in that interest's own query; "SpaceX" on
               one judged mention across three families is Other and must not card in Early
               warning; an Other thing with high relevance, or two independently-judged mentions,
               still cards; a real-sector thing always cards (real cases, 2026-09-28 second pass)
10. alias    (pure, no sandbox) — a state row judged under an id the profile's `aliases:` retired
               (real case, 2026-09-28: "AI Agents & Multi-Agent Systems" -> "AI Agents, Harnesses
               & Reliability") folds into the renamed interest's sector, not a phantom sector of
               its own; an id naming no live interest (current or aliased) resolves to nothing
11. note     (pure, no sandbox) — the note's description counts every early warning and blind
               spot, and the note lists every one of them and every signal, with each signal's
               detail (its items, notes and hubs); nothing is left to the page (2026-09-30); with no vault baseline the
               section says "no baseline yet" and lists the week's tags by count, never "0.0
               baseline"; with one, only rising/new tags, each against its baseline (real cases,
               2026-09-29)
12. hubs     (pure, stub graph) — growing hubs follow the same baseline rule: too little history
               is baseline None (not a "new hub" at 0.0); an estimated date puts no note in a
               week, but still dates its anchor (a backfilled note is not new this week)
"""
from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
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
    # the same KVR article through Reader and through the RSS sensor: one source, not two
    rows.append({"run": _day(1), "feed": "KVR Audio", "title": "Zither 1.0 granular synth released",
                 "url": "https://www.kvraudio.com/news/zither?utm_source=reader", "kind": "news",
                 "p": {local: 0.02, audio: 0.88}, "backend": "jev"})
    for n in range(5, 17):
        rows.append({"run": _day(n), "feed": "reddit.com", "title": f"Progress on Grimoire 2 build {n}",
                     "url": f"https://www.reddit.com/r/LocalLLaMA/comments/g{n}/x/", "kind": "news",
                     "p": {local: 0.7, audio: 0.05}, "backend": "jev"})
    # A generic OS name with exactly one incidental high score (real case, 2026-09-28: a Native
    # Instruments forum post about a DJ controller driver, judged relevant to Audio Plugins because
    # the post is, scores "Windows 11" itself along with it): one corroborating mention is not
    # enough to earn a sector, so this must land in Other rather than under Audio Plugins.
    # day 6, not day 0: old enough to never be "new"/"rising" (so it never competes for a
    # web-check slot in the later phases below), young enough to still be inside this window.
    rows.append({"run": _day(6), "feed": "Hacker News", "title": "Windows 11½",
                 "url": "https://definitelynotwindows.com/", "kind": "news",
                 "p": {local: 0.04, audio: 0.03}, "backend": "jev"})
    rows.append({"run": _day(6), "feed": "Native Instruments Community",
                 "title": "[SOLVED] Rane SL3 working on Windows 11 with Traktor Pro 3",
                 "url": "https://community.native-instruments.com/discussion/1/x", "kind": "news",
                 "p": {local: 0.04, audio: 0.72}, "backend": "jev"})
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
                                  ("v2.1.283", None, "v2.1.283"),
                                  ("NI Maschine 3.7: three new sequencing tools", "Maschine 3.7", "NI Maschine 3.7"),
                                  ("Save 50% on synths this weekend", None, "Save 50"),
                                  ("South Korea and the United States sign a chip pact", None, "South Korea")):
        got = E.from_title(title)
        if want and want not in got:
            problems.append(f"entities: {title!r} should name {want!r}, got {got}")
        if not_want and not_want in got or any("'" in g or "’" in g for g in got):
            problems.append(f"entities: {title!r} must not name {not_want!r}, got {got}")
    if E.from_url("https://github.com/ggml-org/llama.cpp/releases/tag/b1") != ["llama.cpp"]:
        problems.append("entities: a GitHub release address names its repo")


def _merge_checks(problems: list[str]) -> None:
    """Pure function-level checks (no sandbox) for the 2026-10-01 data-quality pass, real cases
    from the Signal Radar generated 2026-10-01 04:15 UTC (60 blips): junk blips "Machines" (the
    GitHub repo sleeping_machines merged in by pure string containment), "Scope" (merged with
    Dental Scope), "Sift" (merged with LatentSift), "Chinese" (a demonym named as a product),
    "ClaudeAI" (the subreddit r/ClaudeAI's own prefix stripped bare) and "jeff" (HOT, strength 70,
    on one real mention plus five unrelated Tavily namesakes, asked with no disambiguating
    context); and three qualified names a fragment with fewer mentions never folded into:
    Muse(12)->Meta Muse(65), Sol(2)->GPT-6.1 Sol(8), Gemini 4(3)->Gemini 4 Argon(11)."""
    import entities as E
    import signal_radar as sr

    def ent(key: str, name: str, titles: list[str]) -> sr.Entity:
        e = sr.Entity(key)
        for i, t in enumerate(titles):
            e.names[name] += 1
            e.mentions.append({"title": t, "url": f"https://example.org/{key}/{i}", "family": "rss"})
        return e

    # "Apollo View releases Scope..." and "Dental Scope – ..." are unrelated: a shared ending is
    # not a shared subject, and must not merge.
    scope = ent("scope", "Scope", ["Apollo View releases Scope, a FREE oscilloscope plugin for Mac and Windows"])
    dental = ent("dentalscope", "Dental Scope", ["Show HN: Dental Scope – Interactive 3D dental anatomy"])
    # Muse (fewer mentions, the fragment) must fold into Meta Muse (more mentions, the qualified
    # name) — never the reverse, and never stay apart for want of relatedness evidence: two of
    # Muse's own mentions name "Meta" too.
    muse = ent("muse", "Muse", [
        "Maybe don't let Muse run your Facebook Marketplace account",
        "Meta's AI agent Muse is stirring growing privacy fears",
        "YouTuber says Muse gave his address to a buyer",
        "Meta's AI agent Muse gives out a user's home address",
        "Liked Muse, so I cut the model in half",
    ])
    metamuse = ent("metamuse", "Meta Muse",
                   [f"OpenAI takes on Meta Muse with always-on Dots agents, round {i}" for i in range(12)])
    # Sol (fewer mentions) must fold into GPT-6.1 Sol (more mentions) the same way.
    sol = ent("sol", "Sol", [
        "OpenAI shelves GPT-6.1 Astra and launches lower-cost Sol",
        "With Opus 5.5 and Sonnet 5.5 both apparently outperforming Sol and Astra",
    ])
    gpt61sol = ent("gpt61sol", "GPT-6.1 Sol", [f"Introducing GPT-6.1 Sol, round {i}" for i in range(8)])

    merged = sr.merge_variants({"scope": scope, "dentalscope": dental, "muse": muse, "metamuse": metamuse,
                                "sol": sol, "gpt61sol": gpt61sol})
    if not ({"scope", "dentalscope"} <= merged.keys()):
        problems.append(f"merge: Apollo View's Scope and Dental Scope are unrelated and must keep separate keys, "
                        f"got {sorted(merged)}")
    if "muse" in merged or "metamuse" not in merged \
            or len(merged["metamuse"].mentions) != len(muse.mentions) + len(metamuse.mentions):
        problems.append(f"merge: Muse (fewer mentions) must fold into Meta Muse, not the reverse, got {sorted(merged)}")
    if "sol" in merged or "gpt61sol" not in merged \
            or len(merged["gpt61sol"].mentions) != len(sol.mentions) + len(gpt61sol.mentions):
        problems.append(f"merge: Sol (fewer mentions) must fold into GPT-6.1 Sol, not the reverse, got {sorted(merged)}")

    # jeff: a bare one-word Other-sector name (one real mention, judged 0.87 on a real interest but
    # under assign_sectors' two-mention support bar) must be checked with disambiguating context,
    # not silently skipped (the pre-2026-10-01 fix) or asked bare (how it inflated to HOT on five
    # unrelated Tavily namesakes).
    jeff_mentions = [{"p": {"small-decision-models-typed-judgments": 0.87, "local-ai-self-hosted-inference": 0.6}}]
    weight, support = sr._interest_weights(jeff_mentions)
    names = {"small-decision-models-typed-judgments": "Small Decision Models & Typed Judgments"}
    jeff = {"key": "jeff", "name": "jeff", "stage": "new", "sector": "other",
            "_interests": weight, "_interest_support": support}
    cands = sr.check_candidates([jeff], names, [])
    if len(cands) != 1 or not cands[0]["context"]:
        problems.append(f"merge: a jeff-shaped Other-sector name must be checked with disambiguating context, "
                        f"not skipped or asked bare, got {cands}")

    # a name-check row from before rows recorded their context: a one-word name's bare row is no
    # evidence (its hits are namesakes) and does not block a re-ask with context; a multi-word name's
    # row still counts; the new row records its context [earned: 2026-10-01, the 09-30 "jeff" row]
    import tempfile
    from datetime import UTC, datetime
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        now = datetime(2026, 10, 1, 14, 28, tzinfo=UTC)
        (out / "signal-tavily.jsonl").write_text(
            json.dumps({"day": "2026-09-30", "key": "jeff", "name": "jeff",
                        "hits": [{"title": "Jeffrey Kent Obituary", "url": "https://e.org/obit", "published": ""}]}) + "\n"
            + json.dumps({"day": "2026-09-30", "key": "billgates", "name": "Bill Gates",
                          "hits": [{"title": "Bill Gates on AI", "url": "https://e.org/bg", "published": ""}]}) + "\n", encoding="utf-8")
        asked: list[tuple[str, str]] = []

        def ask(name: str, context: str = "") -> list[dict]:
            asked.append((name, context))
            return [{"title": "Jeff: Jev-compatible decision models", "url": "https://e.org/jeff", "published": ""}]
        cand = {"key": "jeff", "name": "jeff", "families": ["hn"], "strength": 70, "context": "Small Decision Models"}
        mentions, status = sr._name_check(out, [cand], now, "tavily", "signal-tavily.jsonl", ask)
        titles = {m["title"] for m in mentions}
        last = json.loads((out / "signal-tavily.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        if asked != [("jeff", "Small Decision Models")] or "Jeffrey Kent Obituary" in titles \
                or not {"Bill Gates on AI", "Jeff: Jev-compatible decision models"} <= titles or last.get("context") != "Small Decision Models":
            problems.append(f"merge: a one-word name's row without a recorded context is no evidence and is asked again "
                            f"with context (recorded); got asked={asked}, mentions={sorted(titles)}, last row={last}")

    claudeai = E.from_title("Trends on r/ClaudeAI")
    if E.key("ClaudeAI") in {E.key(n) for n in claudeai}:
        problems.append(f"merge: r/ClaudeAI is a subreddit reference, must not yield a ClaudeAI entity, got {claudeai}")
    chinese = E.from_title("Anthropic says a Chinese AI model anyone can download can now build working hacks on its own")
    if E.key("Chinese") in {E.key(n) for n in chinese}:
        problems.append(f"merge: a Chinese AI model headline must not name bare 'Chinese', got {chinese}")


def _sector_and_early_checks(problems: list[str]) -> None:
    """Pure function-level checks (no sandbox) for the 2026-09-28 review's second pass, real cases:
    "Sonnet 5.5" (one mention, p=0.8 on Claude Code & Anthropic Ecosystem, whose own query already
    reads "Opus Fable pricing") should keep that sector; "SpaceX"/"Windows 11"/"Soup" (one mention
    each, no name match) should stay Other and, since Other, also stay out of Early warning unless
    they separately clear a high relevance or two independently-judged mentions."""
    import signal_radar as sr
    from interests import Interest

    claude_code = Interest(id="claude-code", name="Claude Code & Anthropic Ecosystem",
                           gloss="Claude Code as a daily engineering environment.", queries=("Opus Fable pricing",))
    music = Interest(id="music", name="Music Production & DJing", gloss="Synths, DAWs and DJ gear for producers.")
    sonnet = {"name": "Sonnet 5.5", "_interests": Counter({"claude-code": 0.8}), "_interest_support": Counter({"claude-code": 1})}
    windows = {"name": "Windows 11", "_interests": Counter({"music": 0.72}), "_interest_support": Counter({"music": 1})}
    sr.assign_sectors([sonnet, windows], {"claude-code": claude_code.name, "music": music.name}, [claude_code, music])
    if sonnet["sector"] != "claude-code":
        problems.append(f"vocab: Sonnet 5.5 (an Opus/Fable sibling) should keep claude-code on one mention, got {sonnet['sector']!r}")
    if windows["sector"] != "other":
        problems.append(f"vocab: Windows 11 names nothing in music's vocabulary, still needs two mentions, got {windows['sector']!r}")

    base = {"stage": "new", "first_seen": "2026-01-01", "families": ["hn", "kagi_news", "reddit"]}
    spacex_shape = {**base, "sector": "other", "parts": {"relevance": 0.58}, "_interest_support": Counter({"ai-agents": 1, "frontier": 1})}
    high_relevance = {**base, "sector": "other", "parts": {"relevance": 0.85}, "_interest_support": Counter({"x": 1})}
    two_sources = {**base, "sector": "other", "parts": {"relevance": 0.58}, "_interest_support": Counter({"x": 2})}
    real_sector = {**base, "sector": "claude-code", "parts": {"relevance": 0.3}, "_interest_support": Counter({"claude-code": 1})}
    if sr._early_eligible(spacex_shape):
        problems.append("early: an Other thing named by three families but only one judged mention (SpaceX's shape) must not card")
    if not sr._early_eligible(high_relevance):
        problems.append("early: an Other thing with relevance >= EARLY_OTHER_MIN_RELEVANCE should still card")
    if not sr._early_eligible(two_sources):
        problems.append("early: an Other thing with two independently-judged mentions should still card")
    if not sr._early_eligible(real_sector):
        problems.append("early: a real-sector thing needs no extra bar — assign_sectors already corroborated it")


def _alias_checks(problems: list[str]) -> None:
    """Real case, 2026-09-28: the owner renamed four interests in the Obsidian plugin ("AI Agents &
    Multi-Agent Systems" -> "AI Agents, Harnesses & Reliability" among them) and the profile note
    gained an `aliases:` list of the old names. A row judged before the rename still carries the
    old id; it must fold into the renamed interest (not sit as its own phantom sector, not drop to
    Other), and an id that is neither current nor aliased (a truly retired interest) must resolve
    to nothing."""
    import signal_radar as sr
    from interests import Interest

    renamed = Interest(id="ai-agents-harnesses-reliability", name="AI Agents, Harnesses & Reliability",
                       alias_ids=frozenset({"ai-agents-multi-agent-systems"}))
    other = Interest(id="music-production-djing", name="Music Production & DJing")
    names = {renamed.id: renamed.name, other.id: other.name}
    amap = sr.interests_mod.alias_map([renamed, other])
    resolved = sr.resolve_ids({"ai-agents-multi-agent-systems", "genuinely-retired-interest"}, names, amap)
    if resolved.get("ai-agents-multi-agent-systems") != "ai-agents-harnesses-reliability":
        problems.append(f"alias: an old id with an explicit alias should resolve to its renamed interest, got {resolved}")
    if "genuinely-retired-interest" in resolved:
        problems.append(f"alias: an id naming no live interest (current or aliased) must not resolve, got {resolved}")

    mentions = [{"p": {"ai-agents-multi-agent-systems": 0.8}}, {"p": {"ai-agents-multi-agent-systems": 0.75}}]
    weight, support = sr._interest_weights(mentions, resolved)
    blip = {"name": "Some Agent Tool", "_interests": weight, "_interest_support": support}
    sr.assign_sectors([blip], names, [renamed, other])
    if blip["sector"] != "ai-agents-harnesses-reliability":
        problems.append(f"alias: two mentions judged under the old id should earn the renamed interest's sector, got {blip['sector']!r}")


def _note_checks(problems: list[str]) -> None:
    """The Obsidian note's counts and baselines (real cases, 2026-09-29): 29 blind spots rendered as
    "8 not yet in the vault"; with no real baseline every vault tag read "new, 0.0 baseline"."""
    import signal_render as R

    blips = [{"key": f"b{i}", "name": f"Thing {i}", "stage": "new", "strength": 90 - i, "families": ["hn"]}
             for i in range(29)]
    data = {"generated": "2026-09-29T08:29:00Z", "blips": blips, "early": [b["key"] for b in blips[:10]],
            "blind_spots": [b["key"] for b in blips]}
    md = R.render_md(data)
    if "10 early warnings, 29 not yet in the vault" not in md:
        problems.append("note: the description must count every early warning and blind spot, not the shown few")
    early_sec = md.split("## Early warning", 1)[1].split("\n## ", 1)[0]
    blind_sec = md.split("## Not in your vault yet", 1)[1].split("\n## ", 1)[0]
    if early_sec.count("- **Thing ") != 10 or blind_sec.count("- **Thing ") != 29 or "howing" in md:
        problems.append("note: every early warning and blind spot is listed, none left to the page")
    if "## All 29 signals" not in md or md.count("\n| ") < 30 or md.count("\n### Thing ") != 29:
        problems.append("note: every signal gets a table row and a detail section")
    detailed = R.render_md({**data, "blips": [{**blips[0], "name": "A|B", "sector": "s1", "mentions": 3,
                                               "items": [{"title": "Post", "url": "https://x.example/p", "origin": "Hacker News",
                                                          "at": "2026-09-29", "score": 120.0}],
                                               "vault_notes": [{"path": "04_Resources/N.md", "title": "N"}],
                                               "graph": {"hubs": [{"path": "04_Resources/H.md", "title": "H"}]}}],
                            "sectors": [{"id": "s1", "name": "Sector One"}]})
    if "| A\\|B | Sector One |" not in detailed or "- [Post](https://x.example/p) — Hacker News, 2026-09-29, score 120" not in detailed \
            or "In your vault: [[04_Resources/N|N]]" not in detailed or "Connects to: [[04_Resources/H|H]]" not in detailed:
        problems.append("note: a signal's detail carries its items, notes and hubs, and a pipe in a name cannot break the table")

    tags = [{"tag": "claude", "this_week": 9, "baseline": None, "ratio": None, "rising": False, "new": False},
            {"tag": "podcast", "this_week": 5, "baseline": None, "ratio": None, "rising": False, "new": False}]
    hubs = [{"title": "Quantization", "path": "04_Resources/Concepts/Quantization.md", "this_week": 15, "baseline": None, "new": False}]
    young = R.render_md({**data, "vault": {"baseline": {"ready": False, "weeks": 2, "notes": 17}, "tags": tags},
                         "graph": {"growing_hubs": hubs}})
    if "No baseline yet" not in young or "**claude** — 9 this week" not in young or "no baseline yet" not in young \
            or "0.0 baseline" in young or "None" in young or "## Rising in your vault" in young:
        problems.append("note: without a baseline the vault section must say 'no baseline yet', list the week's "
                        "tags by count and never print a 0.0 or None baseline")
    rising = [{"tag": "qwen", "this_week": 6, "baseline": 1.25, "ratio": 4.8, "rising": True, "new": False}, *tags]
    ready = R.render_md({**data, "vault": {"baseline": {"ready": True, "weeks": 4, "notes": 40}, "tags": rising}})
    if "- **qwen** — rising, 6 this week vs 1.25 baseline" not in ready or "**claude**" in ready:
        problems.append("note: with a baseline only rising or new tags are listed, each against its baseline")


def _hub_checks(problems: list[str]) -> None:
    """Growing hubs share the vault pulse's baseline rule: with too little dated history before
    this week a hub has no baseline (None, not a "new hub" at 0.0); with enough, the mean is over
    the weeks that hold notes; a backfilled (estimated) date is no date."""
    import vault_graph

    class Linked:  # every note links to one hub
        ok = True

        def neighbors(self, path: str, direction: str = "both") -> list[dict]:
            return [{"path": "hub.md"}]

    today = NOW.date()
    this_week = {f"n{i}.md": {"title": f"N{i}", "written": (today - timedelta(days=i % 3)).isoformat()} for i in range(6)}
    thin = {f"t{i}.md": {"title": f"T{i}", "written": (today - timedelta(days=9)).isoformat()} for i in range(3)}
    rows = vault_graph.growing_hubs(Linked(), {**this_week, **thin}, today)
    if len(rows) != 1 or rows[0]["baseline"] is not None or rows[0]["new"]:
        problems.append(f"hubs: 3 notes of history are no baseline — baseline None, not a new hub, got {rows}")
    history = {f"h{i}.md": {"title": f"H{i}", "written": (today - timedelta(days=9 + 7 * (i % 2))).isoformat()} for i in range(20)}
    rows = vault_graph.growing_hubs(Linked(), {**this_week, **history}, today)
    if len(rows) != 0:
        problems.append(f"hubs: 6 this week against a baseline of 10 a week is not growing, got {rows}")
    backfilled = {"processed_date": "2026-08-12", "processed_date_estimated": True}
    if vault_graph._date(backfilled, real=True) is not None or vault_graph._date(backfilled) != "2026-08-12":
        problems.append("hubs: an estimated processed_date must not date a note's week, but still dates its anchor")


def _svg_checks(problems: list[str], out: Path, data: dict) -> None:
    """The note's two images, from the run's own data plus a name crafted to break out of the
    markup: well-formed, no script, titled and described, escaped, byte-identical on a second
    render, one blip per dot the page would place, and no crash on no data or on a single blip."""
    import xml.etree.ElementTree as ET

    import signal_render as R

    ns = "{http://www.w3.org/2000/svg}"
    hostile = '<img src=x onerror=1>&"\x01'
    evil = {**data, "blips": [*data["blips"], {**data["blips"][0], "key": "evil", "name": hostile, "strength": 99}]}
    for fname in (R.SCOPE_SVG, R.MOMENTUM_SVG):
        if not (out / fname).is_file():
            problems.append(f"svg: {fname} was not written beside signal.json")
    renders = {"scope": R.render_scope_svg, "momentum": R.render_momentum_svg}
    for name, render in renders.items():
        for label, case in (("run", data), ("hostile", evil), ("empty", {}),
                            ("one blip", {**data, "blips": data["blips"][:1]}),
                            ("one sector", {**data, "sectors": data["sectors"][:1]})):
            svg = render(case)
            try:
                root = ET.fromstring(svg)
            except ET.ParseError as exc:
                problems.append(f"svg: {name} ({label}) is not well-formed XML: {exc}")
                continue
            tags = {el.tag.removeprefix(ns) for el in root.iter()}
            if "script" in tags or "foreignObject" in tags or root.find(f"{ns}title") is None \
                    or root.find(f"{ns}desc") is None or root.get("role") != "img":
                problems.append(f"svg: {name} ({label}) needs role=img, a title and a desc, and no script, got {sorted(tags)}")
            if render(case) != svg:
                problems.append(f"svg: {name} ({label}) must render byte-identical from the same data")
            if label == "hostile" and ("<img" in svg or "\x01" in svg
                                       or not any((el.text or "").startswith("<img src=x onerror=1>&\"") for el in root.iter())):
                problems.append(f"svg: {name} must escape a feed-supplied name, not carry it as markup")
    written = (out / R.SCOPE_SVG).read_text(encoding="utf-8") if (out / R.SCOPE_SVG).is_file() else ""
    if written != R.render_scope_svg(data):
        problems.append("svg: the written scope must be the render of the written signal.json")
    ids = {s["id"] for s in evil["sectors"]}
    shown = sum(1 for b in evil["blips"] if b["sector"] in ids)  # the page places exactly these
    try:
        drawn = len(ET.fromstring(R.render_scope_svg(evil)).findall(f"{ns}g[@class='blip']"))
    except ET.ParseError:
        drawn = -1  # already reported above
    if drawn != shown or not shown:
        problems.append(f"svg: the scope must draw one dot per blip the page places ({shown}), got {drawn}")


def run(vault: Path) -> dict:
    import interests
    import kagi
    import signal_radar
    import tavily
    import vault_graph

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in ENV_KEYS}
    real = (vault_graph._run, kagi._request, tavily._run)
    kagi_calls: list[str] = []
    tavily_calls: list[list[str]] = []
    tavily_state = {"available": False}

    def tavily_stub(args):
        if tavily_state.get("error"):
            raise tavily.TavilyError("HTTP 429: rate limited")
        if not tavily_state["available"]:
            raise tavily.NoKey("TAVILY_API_KEY is not set")
        tavily_calls.append(args)
        if tavily_state.get("news_empty") and "news" in args:
            return {"results": []}
        return {"results": [{"url": f"https://www.reddit.com/r/LocalLLaMA/comments/t{len(tavily_calls)}/zither/",
                             "title": "Zither is out", "content": "", "score": 0.9}]}
    tavily._run = tavily_stub

    def kagi_stub(url, body=None):
        kagi_calls.append(url)
        return {"meta": {"api_balance": 10.0 - 0.002 * len(kagi_calls)},
                "data": [{"t": 0, "url": f"https://news.example.org/{len(kagi_calls)}", "title": "Zither review",
                          "published": _day(1) + "T10:00:00Z"}]}

    sandbox = None
    try:
        _entity_checks(problems)
        _merge_checks(problems)
        _sector_and_early_checks(problems)
        _alias_checks(problems)
        _note_checks(problems)
        _hub_checks(problems)
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
        w11 = blips.get("windows11")
        if not w11:
            problems.append(f"misfile: expected a windows11 blip (relevance clears the bar once), got {sorted(blips)}")
        elif w11["sector"] != "other":
            problems.append("misfile: windows11 has only one mention that scores Audio Plugins "
                            f"(a Native Instruments forum post that happens to name it) — one is not a sector, "
                            f"got {w11['sector']}")
        z = blips.get("zither")
        if not z or z["stage"] != "new" or "zither" not in data["early"] or "zither" not in data["blind_spots"] \
                or set(z["families"]) != {"hn", "rss"} or z["mentions"] != 2:
            problems.append(f"early: zither should be new, early and a blind spot from hn+rss, got {z and (z['stage'], z['families'])} "
                            f"early={data['early']} blind={data['blind_spots']}")
        # a blind spot is the owner's business: sectored, or unsectored but relevant [earned: 2026-10-01]
        spot = lambda sector, rel: signal_radar.blind_spot({"strength": 50, "in_vault": 0, "sector": sector, "parts": {"relevance": rel}})  # noqa: E731
        if not spot("frontier-models-labs", 0.54) or spot("other", 0.37) or not spot("other", 0.74) \
                or signal_radar.blind_spot({"strength": 50, "in_vault": 2, "sector": "frontier", "parts": {"relevance": 0.9}}):
            problems.append("blind: a sectored or relevant unsectored thing no note has is a blind spot; 'Delhi' (other, 0.37) is not")
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
        if '<base target="_blank">' not in html.split("</head>", 1)[0]:
            problems.append("writes: links must open at the top level (<base target=\"_blank\">), not in the artifact frame")
        if "[[04_Resources/Qwen-Notes" not in md:
            problems.append("writes: the note must wikilink the anchor note")
        if "![[Signal-Radar-scope.svg]]" not in md or "![[Signal-Radar-momentum.svg]]" not in md or "obsidian://" in md:
            problems.append("writes: the note must embed both SVGs as wikilinks, never an obsidian:// link")
        if not {"00_Memory/radar/Signal-Radar-scope.svg", "00_Memory/radar/Signal-Radar-momentum.svg"} <= set(r.get("files", [])):
            problems.append(f"writes: the result must list both SVGs among its files, got {r.get('files')}")
        _svg_checks(problems, out, data)
        changed = {p for p, v in snapshot(sandbox).items() if before.get(p) != v}
        outside = sorted(p for p in changed if not p.startswith("00_Memory/radar/"))
        if outside:
            problems.append(f"writes: only the radar dir may change, also changed {outside}")
        if r["status"] != "ok":
            problems.append(f"writes: status {r['status']}")

        # 6: the check with Tavily unavailable falls back to Kagi, twice on the same day
        os.environ["KAGI_API_KEY"] = "stub-kagi-not-a-secret"
        signal_radar.write(sandbox, out, NOW, check=True)
        first = len(kagi_calls)
        data = json.loads((out / "signal.json").read_text(encoding="utf-8"))
        signal_radar.write(sandbox, out, NOW + timedelta(hours=3), check=True)
        if not 1 <= first <= signal_radar.CHECKS_PER_DAY or len(kagi_calls) != first:
            problems.append(f"kagi: expected 1..{signal_radar.CHECKS_PER_DAY} calls once, got {first} then {len(kagi_calls)}")
        ks = next((x for x in data["sources"] if x["family"] == "kagi"), {})
        if "Tavily skipped" not in ks.get("detail", "") or tavily_calls:
            problems.append(f"check: Kagi answers only because Tavily was skipped, and says so, got {ks}")
        z = next((b for b in data["blips"] if b["key"] == "zither"), None)
        if not z or "kagi" not in z["families"]:
            problems.append(f"kagi: a hit should join zither as family kagi, got {z and z['families']}")

        # 6b: its own ledger file, one budget with the pipeline's
        if not (out / "kagi-ledger-signal.jsonl").is_file() or (out / "kagi-ledger.jsonl").is_file():
            problems.append("kagi: the Signal Radar must write kagi-ledger-signal.jsonl and never kagi-ledger.jsonl")
        (out / "kagi-ledger.jsonl").write_text(json.dumps({"at": (NOW + timedelta(days=1)).isoformat(), "kind": "news",
                                                           "query": "gaps", "usd": 0.999, "balance": 5.0}) + "\n", encoding="utf-8")
        (out / "signal-kagi.jsonl").unlink()  # nothing asked yet: the next check would ask again
        calls = len(kagi_calls)
        data = signal_radar.build(sandbox, out, NOW + timedelta(days=1, hours=1), check=True)
        ks = next((x for x in data["sources"] if x["family"] == "kagi"), {})
        if len(kagi_calls) != calls or ks.get("status") != "skipped" or "budget" not in ks.get("detail", ""):
            problems.append(f"kagi: the pipeline's spend must count against the Signal Radar's budget, got {ks}")

        # 6b2: Tavily installed but failing (rate limit): the check still falls back to Kagi
        tavily_state["error"] = True
        (out / "kagi-ledger.jsonl").unlink()
        calls = len(kagi_calls)
        data = signal_radar.build(sandbox, out, NOW + timedelta(days=1, hours=2), check=True)
        ks = next((x for x in data["sources"] if x["family"] == "kagi"), {})
        if len(kagi_calls) == calls or "failed" not in ks.get("detail", ""):
            problems.append(f"check: a failing Tavily must hand the check to Kagi and say why, got {ks}")
        tavily_state["error"] = False

        # 6c: Tavily available: it asks (through tvly), Kagi is not called, its own ledger and log
        tavily_state["available"] = True
        calls = len(kagi_calls)
        data = signal_radar.build(sandbox, out, NOW + timedelta(days=2, hours=1), check=True)
        ts = next((x for x in data["sources"] if x["family"] == "tavily"), {})
        asked = {c[1].strip('"') for c in tavily_calls}
        z = next((b for b in data["blips"] if b["name"] in asked), None)
        if not tavily_calls or len(tavily_calls) > signal_radar.CHECKS_PER_DAY or len(kagi_calls) != calls:
            problems.append(f"tavily: expected 1..{signal_radar.CHECKS_PER_DAY} tvly calls and no Kagi call, "
                            f"got {len(tavily_calls)} and {len(kagi_calls) - calls}")
        if ts.get("status") != "ok" or not z or "tavily" not in z["families"]:
            problems.append(f"tavily: a hit should join the asked name ({asked}) as family tavily, got {ts} {z and z['families']}")
        if tavily_calls and not {"--depth", "basic", "--time-range", "week", "--topic", "news"} <= set(tavily_calls[0]):
            problems.append(f"tavily: the check is a basic search over the week, news topic first, got {tavily_calls[0]}")
        if not (out / "tavily-ledger-signal.jsonl").is_file() or not (out / "signal-tavily.jsonl").is_file():
            problems.append("tavily: the Signal Radar must write tavily-ledger-signal.jsonl and signal-tavily.jsonl")

        # 6d: a name too new for Tavily's news index (0 hits) falls back to a general search, still
        # under the same ledger/budget, and a hit from that fallback still joins the blip
        (out / "signal-tavily.jsonl").unlink()  # let this name be asked again
        tavily_state["news_empty"] = True
        n = len(tavily_calls)
        data = signal_radar.build(sandbox, out, NOW + timedelta(days=2, hours=2), check=True)
        tavily_state["news_empty"] = False
        made = tavily_calls[n:]
        if len(made) < 2 or "news" not in made[0] or "news" in made[1]:
            problems.append(f"6d: an empty news search must fall back to a general one (still budgeted), got {made}")
        ts = next((x for x in data["sources"] if x["family"] == "tavily"), {})
        if ts.get("status") != "ok" or ts.get("items") != 1 or not any("tavily" in b["families"] for b in data["blips"]):
            problems.append(f"6d: the fallback's hit should still join a blip as family tavily, got {ts}")

        # 8: no graph
        def no_graph(args, timeout=None):
            raise FileNotFoundError("gaiafield")
        vault_graph._run = no_graph
        data = signal_radar.build(sandbox, out, NOW)
        q = next((b for b in data["blips"] if b["key"] == "qwen38"), None)
        if data["graph"]["status"] != "skipped" or not q or q["in_vault"] < 1 or q["graph"]["neighborhood"] != 0:
            problems.append(f"no graph: expected skipped with the file anchor kept, got {data['graph']['status']} {q and q['in_vault']}")
    finally:
        vault_graph._run, kagi._request, tavily._run = real
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"8 offline checks ok ({len(kagi_calls)} stubbed Kagi calls)"}
