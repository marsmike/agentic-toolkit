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

        roles = {r["role"]: r for r in data.get("routines", [])}
        if set(roles) != {"pipeline", "radar", "watchdog"} or not all(re.match(r"^\d+ \S+ \* \* \*$", r["cron"]) for r in roles.values()):
            problems.append(f"runs: the three routines with their daily schedules come from cloud/routines.json, got {data.get('routines')}")

        day = data["funnel"].get(today.isoformat())
        if day != {"judged": 6, "worth": 4, "strong": 3, "promoted": 1}:
            problems.append(f"funnel: today's counts are 6 judged, 4 worth, 3 strong, 1 promoted, got {day}")

        page = atlas_build.render(data)
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
            "detail": "; ".join(problems) or "landscape, inflow, runs, funnel and escaping as expected"}
