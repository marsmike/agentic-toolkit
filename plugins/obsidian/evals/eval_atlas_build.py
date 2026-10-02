"""Eval: atlas_build.py writes Atlas.html, the vault's topics and the way knowledge comes in, in a git sandbox.

Every check compares against a build of the same sandbox before the fixture, so the example
vault's own notes never decide the outcome.

1. landscape — a note counts in each of its domains; one distilled today is "added" today, one
               200 days old is counted but never added; a link from one domain's note to
               another's raises both directions of the matrix; topic tags keep `claude-code` and
               drop process tags (`readwise`, a week tag, `project/…`); a title comes from the H1
2. inflow    — an item's lane (an own save, sensor news by the radar's promoted row, a feed
               pick, a newsletter); its outcome (`new`/`enriched` from its retired row, a legacy
               fate from its prose); its notes (named, else the notes citing its source under any
               spelling of the address) and their domains; minutes from ingest to retirement
3. runs      — pipeline runs from the ledger with their counts; a `signal radar …` commit is a
               radar run with its numbers; a `(sync)` hand-edit commit is a sync; a plain hand
               edit is no run; the three cloud routines' daily schedules from `cloud/routines.json`
4. funnel    — the radar's day counts: judged, worth, strong, promoted
5. safe      — a title holding `</script><script>` cannot close the data element: the page has
               exactly two script elements and the payload parses back to the same data
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "atlas_build"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _note(day: str, domains: list[str], extra: str = "", body: str = "# N\n", tags: list[str] | None = None) -> str:
    tag_lines = "".join(f"- {t}\n" for t in [*(f"domain/{d}" for d in domains), *(tags or [])])
    return (f"---\ndescription: d\nstatus: distilled\nprocessed_date: {day}\n{extra}tags:\n{tag_lines}---\n\n{body}")


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import atlas_build
    import imports_log

    problems: list[str] = []
    today = date.today()
    now = datetime.now(UTC).replace(microsecond=0)
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval"),
                     ("add", "-A"), ("commit", "-q", "-m", "example vault")):
            _git(sandbox, *args)
        before = atlas_build.build(sandbox, today)
        dom = lambda data, d: next((x for x in data["domains"] if x["id"] == d), None)  # noqa: E731

        # 1. landscape: three ai-ml notes (so the domain shows even in an empty example vault), one
        # agent-systems note linking to one of them, and an old note outside the window
        res = sandbox / "04_Resources"
        res.mkdir(exist_ok=True)
        files = {
            "Eval-Atlas-Hub": _note(today.isoformat(), ["eval-ai"], body="# Hub </script><script>alert(1)</script>\n",
                                    tags=["claude-code", "readwise", "w39-2026", "project/x"]),
            "Eval-Atlas-Two": _note(today.isoformat(), ["eval-ai"], tags=["claude-code"]),
            "Eval-Atlas-Old": _note((today - timedelta(days=200)).isoformat(), ["eval-ai"]),
            "Eval-Atlas-Spoke": _note((today - timedelta(days=1)).isoformat(), ["eval-agents"],
                                      extra="source: https://example.org/spoke?utm_source=x\n",
                                      body="# Spoke\n\nSee [[Eval-Atlas-Hub]] and [[Eval-Atlas-Two]].\n"),
            "Eval-Atlas-Third": _note((today - timedelta(days=1)).isoformat(), ["eval-agents"]),
            "Eval-Atlas-Fourth": _note((today - timedelta(days=1)).isoformat(), ["eval-agents"]),
        }
        for name, text in files.items():
            (res / f"{name}.md").write_text(text, encoding="utf-8")

        # 2. inflow: four items of one run, retired (or not) the way the pipeline does it
        cap = "01_Capture/Readwise-{}.md"
        ingested = (now - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
        retired_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        captures = {  # name → (via, title, source)
            "Save": ("clip", "Mine", "https://e.org/a"), "Sensor": ("radar", "Sensor", "https://e.org/b"),
            "Feed": ("radar", "Feed pick", "https://www.example.org/spoke/"), "News": ("newsletter", "Letter", ""),
        }
        (sandbox / "01_Capture").mkdir(exist_ok=True)
        for name, (via, title, source) in captures.items():
            (sandbox / cap.format(name)).write_text(
                f"---\nvia: {via}\n{'source: ' + source + chr(10) if source else ''}category: article\n"
                f"ingested_at: '{ingested}'\n---\n# {title}\n", encoding="utf-8")
        ids = {"Save": "save1", "Sensor": "sens1", "Feed": "feed1", "News": "news1"}
        run_label = now.strftime("%Y-%m-%d %H:%M")
        imports_log.record(sandbox, run_label, [{"doc_id": ids[n], "capture": cap.format(n), "via": v} for n, (v, _, _) in captures.items()],
                           at=now.strftime("%Y-%m-%dT%H:%M:%SZ"), distilled=3, dropped=0, failed=0, shallow=False,
                           summary="3 distilled, 0 dropped, 0 failed")
        archive = sandbox / "05_Archive" / "Readwise-Captures-eval"
        archive.mkdir(parents=True, exist_ok=True)
        for name in ("Save", "Sensor", "Feed"):  # retired; the newsletter waits in the inbox
            src = sandbox / cap.format(name)
            src.rename(archive / f"{src.stem}--FULLCAPTURE.md")
        retired = [
            {"retired": cap.format("Save"), "at": retired_at, "kind": "new", "notes": ["04_Resources/Eval-Atlas-Hub.md"], "what": "new note"},
            {"retired": cap.format("Sensor"), "at": retired_at, "kind": "enriched", "notes": ["Eval-Atlas-Spoke"], "what": "L1 on Spoke"},
            {"retired": cap.format("Feed"), "at": retired_at, "kind": "enriched", "notes": [], "what": "folded into the spoke note"},
        ]
        with (sandbox / imports_log.LOG).open("a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in retired))
        rd = sandbox / "00_Memory" / "radar"
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "promoted.jsonl").write_text(
            json.dumps({"id": "sens1", "canonical": "e.org/b", "date": today.isoformat(), "via": "sensors"}) + "\n"
            + json.dumps({"id": "feed1", "canonical": "example.org/spoke", "date": today.isoformat()}) + "\n", encoding="utf-8")
        state = [{"run": today.isoformat(), "canonical": f"e.org/{i}", "url": f"https://e.org/{i}", "title": str(i), "feed": "f",
                  "kind": "paper", "p": {"x": 0.9 if i < 2 else 0.2}, "worth": ["x"] if i < 3 else [], "strong": ["x"] if i < 2 else []}
                 for i in range(5)] + [{"run": today.isoformat(), "canonical": "e.org/b", "url": "https://e.org/b", "title": "b",
                                        "feed": "f", "kind": "news", "p": {"x": 0.95}, "worth": ["x"], "strong": ["x"]}]
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in state), encoding="utf-8")

        # 3. runs: a radar commit, a sync commit and a plain hand edit
        _git(sandbox, "add", "-A")
        _git(sandbox, "commit", "-q", "-m", "vault: hand edits — a session's own")
        _git(sandbox, "commit", "-q", "--allow-empty", "-m", "signal radar 2026-09-30 20:30: 60 signals, 12 early, 20 blind spots")
        _git(sandbox, "commit", "-q", "--allow-empty", "-m", f"vault: hand edits {run_label} (sync)")

        data = atlas_build.build(sandbox, today)
        # the quality rows: [path, day, title, links in, links out, description chars, names a source]
        q = {r[0]: r for r in data.get("quality", [])}
        hub, spoke = q.get("04_Resources/Eval-Atlas-Hub"), q.get("04_Resources/Eval-Atlas-Spoke")
        if not hub or not spoke or "04_Resources/Eval-Atlas-Old" in q:
            problems.append(f"quality: a row per note distilled in the window and none for the old note, got {sorted(q)[:8]}")
        elif hub[3:7] != [1, 0, 1, False] or spoke[3:7] != [0, 2, 1, True]:
            problems.append(f"quality: Hub has 1 link in and no source, Spoke 2 links out and a source, got {hub[3:7]}, {spoke[3:7]}")
        ai, agents = dom(data, "eval-ai"), dom(data, "eval-agents")
        if not ai or not agents or ai["notes"] != 3 or agents["notes"] != 3:
            problems.append(f"landscape: eval-ai and eval-agents must hold 3 notes each, got {ai and ai['notes']}, {agents and agents['notes']}")
        else:
            if ai["added"] != {today.isoformat(): 2}:
                problems.append(f"landscape: eval-ai must have 2 added today and the 200-day-old note none, got {ai['added']}")
            ids = [d["id"] for d in data["domains"]]
            i, j = ids.index("eval-agents"), ids.index("eval-ai")
            if data["matrix"][i][j] < 2 or data["matrix"][j][i] != 0:
                problems.append(f"landscape: two links from eval-agents to eval-ai, none back, got {data['matrix'][i][j]} / {data['matrix'][j][i]}")
            if [h["p"] for h in ai["hubs"]][:2] != ["04_Resources/Eval-Atlas-Hub", "04_Resources/Eval-Atlas-Two"]:
                problems.append(f"landscape: the linked notes lead eval-ai's hubs, got {ai['hubs']}")
            if not any(h["t"].startswith("Hub </script>") for h in ai["hubs"]):
                problems.append(f"landscape: a title comes from the note's H1, got {[h['t'] for h in ai['hubs']]}")
            if ai["kinds"] != [["no kind", 3]]:
                problems.append(f"landscape: a resource without a kind counts as 'no kind', got {ai['kinds']}")
            if ai["topics"] != [["claude-code", 2]]:
                problems.append(f"landscape: topics keep claude-code and drop process tags, got {ai['topics']}")
        tags = {t[0]: t for t in data["tags"]}
        if "claude-code" not in tags or {"readwise", "w39-2026", "project/x"} & set(tags):
            problems.append(f"landscape: topic tags must keep claude-code and drop process tags, got {sorted(tags)[:20]}")
        if data["totals"]["notes"] != before["totals"]["notes"] + 6:
            problems.append(f"landscape: six notes added, totals went {before['totals']['notes']} → {data['totals']['notes']}")

        rows = {r["t"]: r for r in data["inflow"] if r["t"] in ("Mine", "Sensor", "Feed pick", "Letter")}
        want = {"Mine": ("save", "new", ["04_Resources/Eval-Atlas-Hub"], ["eval-ai"]),
                "Sensor": ("sensor", "enriched", ["04_Resources/Eval-Atlas-Spoke"], ["eval-agents"]),
                "Feed pick": ("feed", "enriched", ["04_Resources/Eval-Atlas-Spoke"], ["eval-agents"]),
                "Letter": ("newsletter", "waiting", [], [])}
        for title, (lane, out, notes, doms) in want.items():
            r = rows.get(title, {})
            if (r.get("lane"), r.get("out"), r.get("notes"), r.get("dom")) != (lane, out, notes, doms):
                problems.append(f"inflow: {title} should be {lane}/{out} → {notes} {doms}, got "
                                f"{r.get('lane')}/{r.get('out')} → {r.get('notes')} {r.get('dom')}")
        if rows.get("Mine", {}).get("min") != 30 or "min" in rows.get("Letter", {}):
            problems.append(f"inflow: ingest to retirement is 30 minutes, none for a waiting item; got {rows.get('Mine', {}).get('min')}")
        legacy = atlas_build._outcome({"status": "distilled", "detail": "L2 enrichment: launch line"})
        if (legacy, atlas_build._outcome({"status": "distilled", "detail": "new tool note"}), atlas_build._outcome({"status": "dropped"})) \
                != ("enriched", "new", "dropped"):
            problems.append(f"inflow: a legacy fate's outcome comes from its prose, got {legacy}")
        keys = {atlas_build.source_key(u) for u in ("https://www.Example.org/spoke/", "http://example.org/spoke?utm_source=y")}
        if keys != {"example.org/spoke"} or atlas_build.source_key("https://youtube.com/watch?v=abc&t=3") != "youtube.com/watch?v=abc" \
                or atlas_build.source_key("own words") != "":
            problems.append(f"inflow: source keys must ignore scheme, www., a trailing slash and tracking queries, got {keys}")

        runs = data["runs"]
        pipe = [r for r in runs if r["r"] == "pipeline" and r["at"] == now.strftime("%Y-%m-%dT%H:%M:%SZ")]
        radar = [r for r in runs if r["r"] == "radar"]
        syncs = [r for r in runs if r["r"] == "sync"]
        if len(pipe) != 1 or pipe[0]["n"] != 3 or [r["s"] for r in radar] != ["60 signals, 12 early, 20 blind spots"] or len(syncs) != 1:
            problems.append(f"runs: one pipeline run (3 distilled), one radar run, one sync, no hand edit; got {runs}")

        # a copy of the script outside the repo (CI runs the generators from /tmp/<dir>/) finds no
        # snapshot and says so, rather than failing on a fixed path depth [earned: 2026-10-01]
        if atlas_build.routines_file(Path("/tmp/eval-copy/atlas_build.py")) is not None:
            problems.append("runs: a script outside the toolkit checkout must find no routines snapshot")
        roles = {r["role"]: r for r in data.get("routines", [])}
        if set(roles) != {"pipeline", "radar", "watchdog"} or not all(re.match(r"^\d+ \S+ \* \* \*$", r["cron"]) for r in roles.values()):
            problems.append(f"runs: the three routines with their daily schedules come from cloud/routines.json, got {data.get('routines')}")

        day = data["funnel"].get(today.isoformat())
        if day != {"judged": 6, "worth": 4, "strong": 3, "promoted": 1}:
            problems.append(f"funnel: today's counts are 6 judged, 4 worth, 3 strong, 1 promoted, got {day}")

        # 5. what each interest brought and the strongest items [earned: 2026-10-01]: an alias maps
        # "x" to its interest; a retired interest is left out of the rows; an older day keeps its 3
        # best; a non-web address loses its link
        names_env = os.environ.get("TOOLKIT_RADAR_INTERESTS_NOTE")
        (sandbox / "00_Memory" / "eval-interests.md").write_text(
            "---\ninterests:\n  - name: Eval Interest\n    aliases: [x]\n  - name: Second Interest\n---\n", encoding="utf-8")
        os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = "00_Memory/eval-interests.md"
        try:
            old = (today - timedelta(days=20)).isoformat()
            extra = [{"run": old, "canonical": f"e.org/old{i}", "url": f"https://e.org/old{i}", "title": f"old {i}", "feed": "f",
                      "kind": "paper", "p": {"second-interest": 0.8 + i / 100}, "worth": ["second-interest"], "strong": ["second-interest"]}
                     for i in range(5)]
            extra += [{"run": today.isoformat(), "canonical": "e.org/js", "url": "javascript:alert(1)", "title": "js", "feed": "f",
                       "kind": "news", "p": {"x": 0.99}, "worth": ["x"], "strong": ["x"]},
                      {"run": today.isoformat(), "canonical": "e.org/gone", "url": "https://e.org/gone", "title": "gone", "feed": "f",
                       "kind": "news", "p": {"dropped-interest": 0.97}, "worth": ["dropped-interest"], "strong": ["dropped-interest"]}]
            with (rd / "state.jsonl").open("a", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(r) + "\n" for r in extra))
            view = atlas_build.build(sandbox, today)["radar"]
        finally:
            if names_env is None:
                os.environ.pop("TOOLKIT_RADAR_INTERESTS_NOTE", None)
            else:
                os.environ["TOOLKIT_RADAR_INTERESTS_NOTE"] = names_env
        ev, second = view["interests"].get("eval-interest", {}), view["interests"].get("second-interest", {})
        if ev.get("name") != "Eval Interest" or ev.get("days", {}).get(today.isoformat()) != [5, 4, 1] or sum(ev.get("weeks", [])) != 4 \
                or second.get("days") != {old: [5, 5, 0]} or "retired" in view["interests"]:
            problems.append(f"radar: per interest, today's eval-interest is 5 worth, 4 strong, 1 promoted (4 strong this week), "
                            f"the second interest's 5 strong are on one older day, no retired row; got {view['interests']}")
        tops = {t["t"]: t for t in view["top"]}
        if [t["t"] for t in view["top"] if t["d"] == old] != ["old 4", "old 3", "old 2"] or tops.get("js", {}).get("u") != "" \
                or tops.get("b", {}).get("u") != "https://e.org/b" or tops.get("b", {}).get("s") != "promoted" \
                or tops.get("gone", {}).get("i") != "retired":
            problems.append(f"radar: an older day keeps its 3 best, a javascript: address loses its link, a promoted item says so; "
                            f"got {view['top']}")

        page = atlas_build.render(data)
        if 'id="ints"' not in page or 'id="tops"' not in page:
            problems.append("radar: the page lacks the interests and strongest-items panels")
        if len(re.findall(r"<script\b", page)) != 2:
            problems.append("safe: a title opened a script element")
        m = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
        if not m or json.loads(m.group(1)) != json.loads(json.dumps(data)):
            problems.append("safe: embedded data does not round-trip")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) or "landscape, inflow, runs, funnel, interests and escaping as expected"}
