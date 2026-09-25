"""Eval: dashboard_build.py writes a self-contained Dashboard.html from the vault, in a git sandbox.

1. notes    — a note distilled today is in, one outside the 84-day window is out, a backfilled
              `processed_date_estimated: true` note is out, `processed_date: unknown` is out
2. fields   — source type by address (x.com → tweet, arxiv → paper, none → own), domains from
              `domain/*` tags, kind (or `unsorted`)
3. runs     — a `pipeline …` commit's counts are parsed; a hand commit is not a run
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

        data = dashboard_build.build(sandbox, today)
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
