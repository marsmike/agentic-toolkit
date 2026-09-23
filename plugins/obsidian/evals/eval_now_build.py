"""Eval: now_build.py writes Now.md and the Pipeline board from the vault's state, in a git sandbox.

Fixture: after a base commit, a `pipeline …` commit adds one note and changes another, and a
hand commit adds a third; the radar state holds a strong item from this week, one from a month
ago and a weak one; one capture is parked, one DLQ note is open and one resolved.

1. week      — New holds the pipeline's new note (not the hand-committed one), Enriched the changed one
2. radar     — only this week's strong item
3. stuck     — the parked capture and the open DLQ note, not the resolved one; the inbox leaves the
               parked capture out
4. board     — Kanban frontmatter, the four lanes in order, every card a `- [ ]` line, settings JSON
5. bases     — every view Now.md embeds exists in the shipped Vault.base
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

import yaml
from _sandbox import make_sandbox, teardown_sandbox

NAME = "now_build"
NOTE = "---\ndescription: {d}\nstatus: distilled\nprocessed_date: {p}\n---\n\n# N\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def _callout(text: str, title: str) -> str:
    m = re.search(rf"^> \[!\w+\] {re.escape(title)}.*?\n((?:>.*\n)*)", text, re.M)
    return m.group(1) if m else ""


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import now_build

    problems: list[str] = []
    today = date.today()
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval"),
                     ("add", "-A"), ("commit", "-q", "-m", "base")):
            _git(sandbox, *args)
        res = sandbox / "04_Resources"
        (res / "Eval-Pipeline-New.md").write_text(NOTE.format(d="new", p=today.isoformat()), encoding="utf-8")
        enriched = next(p for p in sorted((res / "Concepts").glob("*.md")))
        enriched.write_text(enriched.read_text(encoding="utf-8") + "\nEnriched.\n", encoding="utf-8")
        _git(sandbox, "add", "-A")
        _git(sandbox, "commit", "-q", "-m", "pipeline 2026-09-23 12:00: 1 distilled, 0 dropped, 0 failed")
        (res / "Eval-Hand-Note.md").write_text(NOTE.format(d="hand", p="2020-01-01"), encoding="utf-8")
        _git(sandbox, "add", "-A")
        _git(sandbox, "commit", "-q", "-m", "hand note")

        radar = sandbox / "00_Memory" / "radar"
        radar.mkdir(parents=True, exist_ok=True)
        rows = [
            {"run": today.isoformat(), "canonical": "a", "url": "https://a.example/x", "title": "Strong this week",
             "strong": ["t1"], "p": {"t1": 0.9}},
            {"run": (today - timedelta(days=30)).isoformat(), "canonical": "b", "url": "https://b.example/y",
             "title": "Strong last month", "strong": ["t1"], "p": {"t1": 0.95}},
            {"run": today.isoformat(), "canonical": "c", "url": "https://c.example/z", "title": "Weak", "strong": [], "p": {"t1": 0.2}},
        ]
        (radar / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        captures = sorted((sandbox / "01_Capture").glob("*.md"))
        parked = captures[0].relative_to(sandbox).as_posix()
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"parked": [parked]}), encoding="utf-8")
        dlq = sandbox / "00_Memory" / "dlq"
        for p in dlq.glob("*.md"):
            p.unlink()
        (dlq / "2026-09-20-open.md").write_text("---\nstatus: active\n---\n# open\n", encoding="utf-8")
        (dlq / "2026-09-19-done.md").write_text("---\nstatus: resolved\n---\n# done\n", encoding="utf-8")

        now_build.main([])
        now = (sandbox / "Now.md").read_text(encoding="utf-8")
        board = (sandbox / "Boards" / "Pipeline.md").read_text(encoding="utf-8")

        # 1. week
        new, enr = _callout(now, "New this week"), _callout(now, "Enriched this week")
        if "Eval-Pipeline-New" not in new or "Eval-Hand-Note" in new or enriched.stem not in enr:
            problems.append(f"phase 1: new/enriched from the pipeline commit only; new={new!r} enriched={enr!r}")
        # 2. radar
        rad = _callout(now, "Radar")
        if "Strong this week" not in rad or "last month" in rad or "Weak" in rad:
            problems.append(f"phase 2: only this week's strong item; got {rad!r}")
        # 3. stuck
        stuck, inbox = _callout(now, "Stuck"), _callout(now, "Inbox")
        if Path(parked).stem not in stuck or "2026-09-20-open" not in stuck or "done" in stuck:
            problems.append(f"phase 3: parked capture and open DLQ only; got {stuck!r}")
        if Path(parked).stem in inbox or f"Inbox ({len(captures) - 1} waiting)" not in now:
            problems.append("phase 3: the inbox must leave the parked capture out")
        # 4. board
        fm = yaml.safe_load(board.split("---", 2)[1])
        lanes = re.findall(r"^## (.+)$", board, re.M)
        cards = [ln for ln in board.split("%% kanban:settings")[0].splitlines() if ln.startswith("- ")]
        settings = re.search(r"%% kanban:settings\n```\n(.*?)\n```\n%%", board, re.S)
        if fm.get("kanban-plugin") != "board" or lanes != ["Inbox", "Stuck", "Radar this week", "New notes this week"]:
            problems.append(f"phase 4: kanban frontmatter and lanes; got {fm.get('kanban-plugin')}, {lanes}")
        if not cards or any(not c.startswith("- [ ] ") for c in cards) or not settings or "board" not in json.loads(settings.group(1)).values():
            problems.append("phase 4: every card a '- [ ]' line and a parseable settings block")
        # 5. bases
        shipped = Path(__file__).resolve().parent.parent / "obsidian" / "Vault.base"
        views = {v["name"] for v in yaml.safe_load(shipped.read_text(encoding="utf-8"))["views"]}
        embedded = set(re.findall(r"!\[\[Vault\.base#([^\]]+)\]\]", now))
        if not embedded or embedded - views:
            problems.append(f"phase 5: embedded views missing from Vault.base: {sorted(embedded - views) or 'none embedded'}")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "week from pipeline commits, radar, stuck, Kanban board, embedded views exist"}
