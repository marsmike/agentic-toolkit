"""Eval: dashboard_build.py writes a self-contained Dashboard.html from the vault, in a git sandbox.

1. notes    — a note distilled today is in, one outside the 84-day window is out, a backfilled
              `processed_date_estimated: true` note is out, `processed_date: unknown` is out
2. fields   — source type by address (x.com → tweet, arxiv → paper, none → own), domains from
              `domain/*` tags, kind (or `unsorted`)
3. runs     — a `pipeline …` commit's counts are parsed; a hand commit is not a run
6. radar    — the radar ledgers reach the payload: worth-or-strong items with their fate, per-interest
              counts named from the interests note, today's counts, and a javascript: url never a link
5. imports  — a run's imported items reach its run row with their fate and notes, and a clipping
              in neither inbox nor archive is counted as missing
4. safe     — a description holding `</script><script>` cannot close the data element: the page
              has exactly two script elements and the payload parses back to the same data
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "dashboard_build"
NOTE = "---\ndescription: {d}\nstatus: distilled\nprocessed_date: {p}\n{extra}---\n\n# N\n"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import dashboard_build

    problems: list[str] = []
    today = date.today()
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        res = sandbox / "04_Resources"
        notes = {
            "Eval-Dash-Tweet": NOTE.format(d="Evil </script><script>alert(1)</script> tweet", p=today.isoformat(),
                                           extra="source: https://x.com/a/status/1\nkind: tool-landmark\ntags:\n- domain/ai-ml\n"),
            "Eval-Dash-Paper": NOTE.format(d="paper", p=(today - timedelta(days=3)).isoformat(),
                                           extra="source: https://arxiv.org/abs/2601.1\n"),
            "Eval-Dash-Old": NOTE.format(d="old", p=(today - timedelta(days=200)).isoformat(), extra=""),
            "Eval-Dash-Estimated": NOTE.format(d="est", p=today.isoformat(), extra="processed_date_estimated: true\n"),
            "Eval-Dash-Unknown": NOTE.format(d="unk", p="unknown", extra=""),
        }
        for name, text in notes.items():
            (res / f"{name}.md").write_text(text, encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval"),
                     ("add", "-A"), ("commit", "-q", "-m", "hand edit"),
                     ("commit", "-q", "--allow-empty", "-m", "pipeline 2026-09-25 13:06: 7 distilled, 1 dropped, 2 failed; in: x")):
            _git(sandbox, *args)

        import imports_log
        (sandbox / "01_Capture").mkdir(exist_ok=True)
        (sandbox / "01_Capture" / "Readwise-Article-wait.md").write_text("---\nsource: https://e.org/w\n---\n# Wait\n", encoding="utf-8")
        imports_log.record(sandbox, "2026-09-25 13:06", [
            {"doc_id": "w", "capture": "01_Capture/Readwise-Article-wait.md", "via": "clip"},
            {"doc_id": "k", "found": "04_Resources/Eval-Dash-Paper.md"},
            {"doc_id": "m", "capture": "01_Capture/Readwise-Article-gone.md", "via": "clip"}])

        # radar ledgers: one strong item promoted today, one merely worth reading yesterday
        rd = sandbox / "00_Memory" / "radar"
        rd.mkdir(parents=True, exist_ok=True)
        (sandbox / "Config" / "toolkit").mkdir(parents=True, exist_ok=True)
        (sandbox / "Config" / "toolkit" / "radar.md").write_text("---\ninterests_note: 03_Areas/Eval-Interests.md\n---\n", encoding="utf-8")
        (sandbox / "03_Areas" / "Eval-Interests.md").write_text("---\ninterests:\n- name: Agent Memory\n  gloss: x\n---\n", encoding="utf-8")
        rows = [{"run": today.isoformat(), "canonical": "example.org/strong", "url": "https://example.org/strong", "title": "A strong <b>one</b>",
                 "feed": "arXiv.org", "kind": "paper", "p": {"agent-memory": 0.9, "epic-x": 0.2}, "worth": ["agent-memory"], "strong": ["agent-memory"], "in_vault": None},
                {"run": (today - timedelta(days=1)).isoformat(), "canonical": "example.org/worth", "url": "javascript:alert(1)", "title": "Worth",
                 "feed": "reddit.com", "kind": "opinion", "p": {"agent-memory": 0.72}, "worth": ["agent-memory"], "strong": [], "in_vault": None},
                {"run": today.isoformat(), "canonical": "example.org/no", "url": "https://example.org/no", "title": "No",
                 "feed": "LWN", "kind": "news", "p": {"agent-memory": 0.1}, "worth": [], "strong": [], "in_vault": None}]
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (rd / "promoted.jsonl").write_text(json.dumps({"canonical": "example.org/strong", "date": today.isoformat()}) + "\n", encoding="utf-8")
        data = dashboard_build.build(sandbox, today)
        rad = data.get("radar") or {}
        if rad.get("counts") != {"judged": 3, "worth": 2, "strong": 1, "promoted": 1} or rad.get("today") != {"judged": 2, "strong": 1, "promoted": 1}:
            problems.append(f"radar: counts {rad.get('counts')}, today {rad.get('today')}")
        if [(i["title"], i["promoted"], i["url"]) for i in rad.get("items", [])] != [("A strong <b>one</b>", True, "https://example.org/strong"), ("Worth", False, "javascript:alert(1)")]:
            problems.append(f"radar: items {rad.get('items')}")
        if rad.get("interests", {}).get("agent-memory", {}).get("name") != "Agent Memory" or rad["interests"]["agent-memory"]["strong"] != 1:
            problems.append(f"radar: interests {rad.get('interests')}")
        run = next((r for r in data["runs"] if r.get("run") == "2026-09-25 13:06"), {})
        fates = [(i["title"], i["status"], i["notes"]) for i in run.get("items", [])]
        if fates != [("Wait", "waiting", []), ("04_Resources/Eval-Dash-Paper.md", "known", ["04_Resources/Eval-Dash-Paper.md"]),
                     ("01_Capture/Readwise-Article-gone.md", "missing", [])] or data.get("missing") != 1:
            problems.append(f"imports: {fates}, missing={data.get('missing')}")
        got = {n["title"]: n for n in data["notes"] if n["title"].startswith("Eval-Dash-")}
        if set(got) != {"Eval-Dash-Tweet", "Eval-Dash-Paper"}:
            problems.append(f"notes: {sorted(got)}")
        t, p = got.get("Eval-Dash-Tweet", {}), got.get("Eval-Dash-Paper", {})
        if (t.get("type"), t.get("kind"), t.get("domains")) != ("tweet", "tool-landmark", ["ai-ml"]):
            problems.append(f"fields: tweet {t.get('type')}, {t.get('kind')}, {t.get('domains')}")
        if (p.get("type"), p.get("kind")) != ("paper", "unsorted"):
            problems.append(f"fields: paper {p.get('type')}, {p.get('kind')}")
        if dashboard_build.source_type("") != "own":
            problems.append("fields: no source is not 'own'")
        if [(r["distilled"], r["dropped"], r["failed"]) for r in data["runs"]] != [(7, 1, 2)]:
            problems.append(f"runs: {data['runs']}")

        page = dashboard_build.render(data)
        if len(re.findall(r"<script\b", page)) != 2:
            problems.append("safe: a description opened a script element")
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
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "notes, fields, runs and escaping as expected"}
