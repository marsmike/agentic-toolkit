"""Eval: now_build.py writes Now.md and the Pipeline board from the vault's state, in a sandbox.

Fixture: notes whose distilled date (`distilled_at`, else `processed_date`; estimated or not) and
`updated_at` fall in or before the week; the radar state holds a strong item from this week, one
from a month ago and a weak one; one capture is parked, one DLQ note is open and one resolved.

0. shape     — the status block (health, generated line, last run, stuck/inbox counts) comes first, then the
               live views (Recently changed, Recently distilled), then Stuck and Inbox, then the
               week's lists as folded callouts (`> [!tip]- …`)
1. week      — from frontmatter only (stats `source: frontmatter`): New holds the notes distilled in
               the window, newest first, Index.md never (2026-09-24 review IMPL-GLM-4); a root
               `status: active` note is new no more than any other undistilled one, since the shared
               distilled rule (2026-09-29); a note distilled before the week, with an estimated
               or non-date date, or never distilled (`status: review` or `active`, a processed_date
               or not), is not new; a note updated in the window but distilled before it (or
               estimated) is enriched once and never also new; one with both dates in the window
               is new only
1d. one rule — Distilled per day counts today exactly the notes distilled today (not the estimated
               ones, not the `status: review` one with today's processed_date: 2026-09-29 audit, 92
               on a day whose runs distilled 17), which is what `imports_log.day_totals` says the
               day's runs distilled; the callout titles name their measure
1b. history  — the same lists with no git at all and after one commit of everything: a count never
               depends on how much history a checkout has (2026-09-29: a shallow clone's "52 new")
1c. honesty  — Enriched's title says "counted since <first updated_at>" while the window opens
               before the vault's first `updated_at`, and not once a stamp predates the window
2. radar     — only this week's strong item
3. stuck     — the parked capture and the open DLQ note, not the resolved one; the inbox leaves the
               parked capture out
4. board     — Kanban frontmatter, the four lanes in order, every card a `- [ ]` line, settings JSON
5. bases     — every view Now.md embeds exists in the shipped Vault.base, Recently changed among them
6. no dead links on the docs site — Now.md/Pipeline.md never wikilink into 00_Memory/, 01_Capture/
               or 00_Daily/ (docs.yml excludes them), and the nav line never links [[Log]] when
               Log.md doesn't exist (2026-09-28 repo audit A1/A2)
7. signal    — no signal.json, no Signal Radar line; with one, its new/hot/rising blips (not steady)
               labelled with the file's own time; the Signal Radar note and today's daily note are
               linked (by obsidian://, never a wikilink) once they exist; a malformed file drops the line
8. quiet     — nothing parked, no open DLQ note, no capture: one "Nothing stuck · inbox empty" line,
               no Stuck or Inbox section, the live views still there
9. receipt   — `watchdog.health` first: late with no run row, healthy, failing, stuck, late with the
               run's absolute time (never "N h ago"), left out when health cannot run; the last run's
               receipt from its ledger row (funnel, counts, the shallow flag only when set) and up to
               three of its drops with their reasons (none shown when the row has none; an earlier
               run's drop and a distilled capture never), "… and N more"; a run row without counts
               falls back to pipeline-state.json's last run
10. topics   — New topics: this week's concept notes (Concepts/ or `kind: concept`), four and how many
               more; no line in a week without one
11. blind    — Not in your vault yet: signal.json's blind spots, the five strongest by name and how
               many more; one alone has no "more"; none, no line
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from _sandbox import make_sandbox, teardown_sandbox

NAME = "now_build"
NOTE = "---\ndescription: {d}\nstatus: distilled\n{fm}---\n\n# N\n"
EXCLUDED = ("00_Memory/", "01_Capture/", "00_Daily/")
QUIET = "Nothing stuck · inbox empty"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def _callout(text: str, title: str) -> str:
    m = re.search(rf"^> \[!\w+\]-? {re.escape(title)}.*?\n((?:>.*\n)*)", text, re.M)
    return m.group(1) if m else ""


def _dead(text: str) -> list[str]:
    return [m for m in re.findall(r"\[\[([^\]|]+)", text) if m.startswith(EXCLUDED)]


def _status(text: str) -> list[str]:
    """The status block's non-empty lines: after the header, up to the link row."""
    block = text.split("Never edit it by hand.\n", 1)[-1].split("\n[[Maps/Overview", 1)[0]
    return [ln for ln in block.splitlines() if ln.strip()]


def _chart(text: str) -> dict[str, int]:
    """Distilled per day as {MM-DD: count}."""
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"^> (\d\d-\d\d) █* *(\d+)$", text, re.M)}


def _run_row(at: datetime, **facts) -> dict:
    return {"kind": "run", "run": at.strftime("%Y-%m-%d %H:%M"), "at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "distilled": 0, "dropped": 0, "failed": 0, "shallow": False, "summary": "", "items": [], **facts}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import imports_log
    import now_build
    import watchdog

    problems: list[str] = []
    # One UTC day for the fixture and every build (`--today`): a local date near midnight would
    # move the window under the fixture.
    today = datetime.now(UTC).date()
    at = f"--today={today}"
    since = today - timedelta(days=now_build.WEEK)
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        base_today = dict(now_build.per_day(sandbox, today))[today.isoformat()]  # the example vault's own
        res = sandbox / "04_Resources"
        fixture = {
            "Eval-New": f"distilled_at: '{today}T09:00:00Z'\nupdated_at: '{today}T09:00:00Z'\n",
            "Eval-Both": f"distilled_at: '{today}T08:00:00+00:00'\nprocessed_date: 2020-01-01\nupdated_at: '{today}T11:00:00Z'\n",
            "Eval-Earlier": f"processed_date: {today - timedelta(days=2)}\n",
            "Eval-Legacy": "processed_date: 2020-01-01\n",
            "Eval-Unknown": "processed_date: unknown\n",
            "Eval-Estimated": f"processed_date: {today}\nprocessed_date_estimated: true\nupdated_at: '{today}T10:00:00Z'\n",
            "Eval-Est-At": f"distilled_at: '{today}T06:00:00Z'\ndistilled_at_estimated: true\nprocessed_date: {since - timedelta(days=9)}\n",
            "Eval-Enriched": f"processed_date: {since - timedelta(days=3)}\nupdated_at: '{today}T07:00:00Z'\n",
            "Eval-Kind-Concept": f"kind: concept\ndistilled_at: '{today}T05:00:00Z'\n",
            **{f"Concepts/Eval-Concept-{i}": f"distilled_at: '{today}T04:0{i}:00Z'\n" for i in range(6)},
            "Concepts/Eval-Concept-Old": "distilled_at: '2020-01-01T00:00:00Z'\n",
        }
        for name, fm in fixture.items():
            (res / f"{name}.md").write_text(NOTE.format(d=name, fm=fm), encoding="utf-8")
        # Carries today's processed_date but was never distilled: counted by neither New nor the chart
        # (2026-09-29 audit: 75 such notes put 92 on a day whose runs distilled 17)
        (res / "Eval-Review.md").write_text(
            NOTE.format(d="review", fm=f"processed_date: {today}\n").replace("status: distilled", "status: review"), encoding="utf-8")
        distilled_today = 2 + 1 + 6  # Eval-New, Eval-Both, Eval-Kind-Concept, Eval-Concept-0…5
        (res / "Eval-Undistilled.md").write_text("---\ndescription: project\nstatus: active\ncreated: 2020-01-01\n---\n\n# P\n", encoding="utf-8")
        (sandbox / "Eval-Root-Profile.md").write_text(
            f"---\ndescription: root\nstatus: active\nprocessed_date: {today - timedelta(days=1)}\n---\n\n# R\n", encoding="utf-8")
        (sandbox / "Eval-Root-Undated.md").write_text("---\ndescription: root\nstatus: active\n---\n\n# R\n", encoding="utf-8")
        (sandbox / "Index.md").write_text((sandbox / "Index.md").read_text(encoding="utf-8") + "\n", encoding="utf-8")

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

        now_build.main([at])  # the sandbox has no .git at all
        now = (sandbox / "Now.md").read_text(encoding="utf-8")
        board = (sandbox / "Boards" / "Pipeline.md").read_text(encoding="utf-8")

        # 0. shape
        if not re.search(r"\*Generated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC · no run yet\*", now):
            problems.append("phase 0: Now.md is missing its own 'Generated ... UTC · <last run>' status line")
        if _status(now)[0] != "**⚠ late** · no pipeline run recorded":
            problems.append(f"phase 9: no run in the ledger, the health line says late first; got {_status(now)[:1]}")
        marks = [now.find(s) for s in ("**⚠ late**", "*Generated", "**2 stuck** · **", "![[Vault.base#Recently changed]]",
                                       "![[Vault.base#Recently distilled]]", "> [!warning] Stuck (2)",
                                       "> [!abstract]- Inbox (", "> [!success]- New this week")]
        if -1 in marks or marks != sorted(marks):
            problems.append(f"phase 0: status, live views, Stuck, Inbox, then the week, in that order; positions {marks}")
        if not all(f"> [!{k}]- {t}" in now for k, t in (("info", "Enriched this week"), ("tip", "Radar: strong"),
                                                         ("note", "Distilled per day"))):
            problems.append("phase 0: the week's long lists are folded callouts")
        if QUIET in now or "**Signal Radar**" in now:
            problems.append("phase 0/7: a busy vault without signal.json shows no quiet line and no Signal Radar line")

        # 1. week
        new, enr = _callout(now, "New this week"), _callout(now, "Enriched this week")
        stats = now_build.build(sandbox, today)[1]
        if stats["source"] != "frontmatter" or "git history" in now:
            problems.append(f"phase 1: the week is counted from frontmatter and never mentions git; source={stats['source']!r}")
        if not (0 <= new.find("Eval-New") < new.find("Eval-Both") < new.find("Eval-Earlier")):
            problems.append(f"phase 1: New holds the notes distilled in the window (distilled_at before processed_date), newest first; new={new!r}")
        if any(n in new + enr for n in ("Eval-Legacy", "Eval-Unknown", "Eval-Undistilled", "Eval-Root-Undated", "Eval-Est-At",
                                        "Eval-Review", "Eval-Root-Profile", "[[Index")):
            problems.append(f"phase 1: a note distilled before the week, with a non-date or estimated date, or never "
                            f"distilled (`status: review` or `active` with a processed_date too) is in neither list, "
                            f"Index.md never; new={new!r} enriched={enr!r}")
        # 1d. one rule: the chart counts today exactly the notes New counts for today, and the runs'
        # own totals for the day (`imports_log.day_totals`) say the same number
        chart = _chart(now)
        if chart.get(today.isoformat()[5:]) != base_today + distilled_today or stats["per_day"][today.isoformat()] != chart.get(today.isoformat()[5:]):
            problems.append(f"phase 1d: Distilled per day counts only distilled notes, never an estimated date or a "
                            f"`status: review` note's processed_date: today {chart.get(today.isoformat()[5:])}, want "
                            f"{base_today} + {distilled_today}")
        ledger = sandbox / "00_Memory" / "imports.jsonl"
        ledger.write_text("".join(json.dumps({"kind": "run", "run": f"{today} {h}", "at": f"{today}T{h}:00Z", "distilled": n,
                                              "dropped": 0, "failed": 0, "summary": "", "items": []}) + "\n"
                                  for h, n in (("03:00", 4), ("06:00", distilled_today - 4))), encoding="utf-8")
        totals = imports_log.day_totals(imports_log.runs(sandbox), today.isoformat())
        if totals["distilled"] != chart.get(today.isoformat()[5:], 0) - base_today:
            problems.append(f"phase 1d: the chart's notes distilled today differ from the runs' day_totals {totals}")
        ledger.unlink()
        if "> [!success]- New this week (" not in now or " notes distilled)" not in now:
            problems.append("phase 1d: New's title names its measure, notes distilled")
        if "Eval-Estimated" in new or "Eval-Enriched" in new or "Eval-New" in enr or "Eval-Both" in enr:
            problems.append(f"phase 1: a note is new or enriched, never both; new={new!r} enriched={enr!r}")
        if not (0 <= enr.find("Eval-Estimated") < enr.find("Eval-Enriched")) or enr.count("Eval-Enriched") != 1:
            problems.append(f"phase 1: Enriched holds the notes updated in the window but not distilled in it "
                            f"(an estimated date among them), once each, newest first; enriched={enr!r}")

        # 1b. history: a checkout with one commit of everything (a shallow clone's view) lists
        # exactly what one with no git at all does
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval"),
                     ("add", "-A"), ("commit", "-q", "-m", "pipeline 2026-09-27 12:35: 1 distilled, 0 dropped, 0 failed")):
            _git(sandbox, *args)
        now_build.main([at])
        again = (sandbox / "Now.md").read_text(encoding="utf-8")
        if (_callout(again, "New this week"), _callout(again, "Enriched this week")) != (new, enr):
            problems.append("phase 1b: New/Enriched differ between no git history and a single commit")

        # 1c. honesty: every updated_at is from today, so the window opens before the first one
        if f"Enriched this week (2 notes changed; counted since {today}, when updated_at started)" not in now:
            problems.append(f"phase 1c: Enriched says it counts since the first updated_at ({today})")
        (res / "Eval-Old-Stamp.md").write_text(
            NOTE.format(d="old", fm=f"processed_date: 2020-01-01\nupdated_at: '{since - timedelta(days=1)}T12:00:00Z'\n"), encoding="utf-8")
        now_build.main([at])
        stamped = (sandbox / "Now.md").read_text(encoding="utf-8")
        if "counted since" in stamped or "> [!info]- Enriched this week (2 notes changed)\n" not in stamped or "Eval-Old-Stamp" in stamped:
            problems.append("phase 1c: once an updated_at predates the window, no 'counted since', and that note is in neither list")
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
        if not embedded or embedded - views or not {"Recently changed", "Stuck", "Inbox"} <= embedded:
            problems.append(f"phase 5: embedded views missing from Vault.base: {sorted(embedded - views) or 'none embedded'}")
        # 6. no dead links on the docs site: no wikilink into an excluded folder, and [[Log]] only
        # when Log.md exists (it doesn't here — no log_vault.py call in this fixture)
        for name, text in (("Now.md", now), ("Boards/Pipeline.md", board)):
            if bad := _dead(text):
                problems.append(f"phase 6: {name} wikilinks into an excluded folder: {bad}")
        if "[[Log]]" in now or "[[Log|" in now:
            problems.append("phase 6: Now.md links [[Log]] although Log.md does not exist in the fixture")
        if "obsidian://open?vault=" not in stuck or "obsidian://open?vault=" not in inbox:
            problems.append(f"phase 6: Stuck/Inbox should reference 00_Memory/01_Capture notes via an obsidian:// link, not a wikilink; stuck={stuck!r} inbox={inbox!r}")

        # 7. signal: another routine's file, labelled with its own time; the Signal Radar note, today's
        # daily note and the two artifact URLs join the link row once they exist
        utc_today = today
        blips = [{"name": n, "stage": s, "strength": v} for n, s, v in
                 (("Hot Thing", "hot", 80), ("Steady Thing", "steady", 70), ("New [Thing]", "new", 60), ("Rising Thing", "rising", 50))]
        (radar / "signal.json").write_text(json.dumps({"generated": f"{utc_today}T08:30:00Z", "blips": blips}), encoding="utf-8")
        (radar / "Signal-Radar.md").write_text("# Signal Radar\n", encoding="utf-8")
        (sandbox / "00_Daily").mkdir(exist_ok=True)
        (sandbox / "00_Daily" / f"{utc_today}.md").write_text("# Today\n", encoding="utf-8")
        for rel, anchor, key in (("Config/toolkit/radar.md", "plugin: radar\n", "signal_artifact_url"),
                                 ("Config/toolkit/obsidian.md", "plugin: obsidian\n", "report_artifact_url")):
            profile = sandbox / rel
            text = profile.read_text(encoding="utf-8").replace(f"{key}: null\n", "")
            profile.write_text(text.replace(anchor, f"{anchor}{key}: https://claude.ai/artifact/{key}\n", 1), encoding="utf-8")
        now_build.main([at])
        now = (sandbox / "Now.md").read_text(encoding="utf-8")
        line = next((ln for ln in now.splitlines() if ln.startswith("**Signal Radar**")), "")
        if (line != "**Signal Radar** (as of 08:30 UTC): Hot Thing (hot, 80) · New (Thing) (new, 60) · Rising Thing (rising, 50)"
                or now.find(line) > now.find("![[Vault.base#Recently changed]]")):
            problems.append(f"phase 7: the new/hot/rising blips, as of the file's own time, above the live views; got {line!r}")
        nav = next((ln for ln in now.splitlines() if ln.startswith("[[Maps/Overview")), "")
        want = ("Today ([open](obsidian://", "Signal Radar ([open](obsidian://", "[Signal Radar (claude.ai)](https://claude.ai/artifact/signal_artifact_url)",
                "[Last run report (claude.ai)](https://claude.ai/artifact/report_artifact_url)")
        if not all(w in nav for w in want) or _dead(now):
            problems.append(f"phase 7: the link row names today's note and the Signal Radar note by obsidian://, and both artifacts; got {nav!r}")
        (radar / "signal.json").write_text(json.dumps({"generated": f"{utc_today - timedelta(days=1)}T23:10:00Z", "blips": []}), encoding="utf-8")
        now_build.main([at])
        now = (sandbox / "Now.md").read_text(encoding="utf-8")
        if f"**Signal Radar** (as of {utc_today - timedelta(days=1)} 23:10 UTC): nothing new, hot or rising" not in now:
            problems.append("phase 7: a signal.json from before today carries its date, and no blip says so")
        (radar / "signal.json").write_text("{", encoding="utf-8")
        now_build.main([at])
        if "**Signal Radar**" in (sandbox / "Now.md").read_text(encoding="utf-8"):
            problems.append("phase 7: a malformed signal.json drops the line")

        # 8. quiet: nothing parked, no open DLQ note, no capture
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps({"parked": []}), encoding="utf-8")
        for p in [*dlq.glob("*.md"), *(sandbox / "01_Capture").glob("*.md")]:
            p.unlink()
        now_build.main([at])
        now = (sandbox / "Now.md").read_text(encoding="utf-8")
        sections = ("] Stuck (", "] Inbox (", "#Stuck]]", "#Inbox]]")
        if QUIET not in now or any(s in now for s in sections) or "![[Vault.base#Recently changed]]" not in now:
            problems.append("phase 8: an all-quiet Now.md says so in one line, with no Stuck or Inbox section")

        # 9. health and the last run's receipt, from the ledger alone: the drops the run retired
        # (between the run before and its own row), each with its own reason or none
        clock = datetime.now(UTC).replace(second=0, microsecond=0)
        prev, last = clock - timedelta(hours=3), clock - timedelta(minutes=1)

        def hhmm(moment: datetime) -> str:
            return moment.strftime("%H:%M UTC" if moment.date() == today else "%Y-%m-%d %H:%M UTC")

        def retired(name: str, minutes: int, kind: str = "dropped", reason: str | None = None) -> dict:
            return {"retired": f"01_Capture/{name}.md", "at": (prev + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "kind": kind, "notes": [], "reason": reason, "what": None}

        def rebuild(rows: list[dict]) -> list[str]:
            ledger.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            now_build.main([at])
            return _status((sandbox / "Now.md").read_text(encoding="utf-8"))

        summary = "4 distilled, 4 dropped, 0 failed; in: radar 12 judged, 2 promoted; readwise 3 new (2 clip, 1 radar); 0 in the inbox"
        rows = [retired("Eval-Drop-Old", -60, reason="an earlier run's"), _run_row(prev, distilled=1),
                retired("Eval-Drop-A", 10, reason="off [topic]"), retired("Eval-Dup", 11, "duplicate", "duplicate of 01_Capture/X.md"),
                retired("Eval-Drop-None", 12), retired("Eval-Distilled", 13, "new"), retired("Eval-Drop-D", 14, reason="too thin"),
                _run_row(last, distilled=4, dropped=4, shallow=True, summary=summary,
                         items=[{"capture": "01_Capture/Eval-Drop-A.md", "title": "A [bracketed] title"}])]
        lines = rebuild(rows)
        receipt = (f" · last run {hhmm(last)} · in: radar 12 judged, 2 promoted · readwise 3 new (2 clip, 1 radar)"
                   f" → 4 distilled, 4 dropped, 0 failed · history shallow*")
        want = [f"**✅ healthy** · pipeline {hhmm(last)}", receipt, "- dropped: A (bracketed) title — off (topic)",
                "- dropped: Eval-Dup — duplicate of 01_Capture/X.md", "- dropped: Eval-Drop-None", "- … and 1 more", QUIET]
        if len(lines) < len(want) or lines[0] != want[0] or not lines[1].endswith(receipt) or lines[2:7] != want[2:]:
            problems.append(f"phase 9: health, then the receipt with its funnel, counts and shallow flag, then up to "
                            f"{now_build.DROPS_SHOW} drops of this run with their reasons (none invented); got {lines[:7]}")
        rows[-1] |= {"shallow": False, "failed": 1}
        lines = rebuild(rows)
        if "history shallow" in lines[1] or lines[0] != f"**⛔ failing** · pipeline {hhmm(last)} · the last run failed 1 capture(s)":
            problems.append(f"phase 9: no shallow flag when history is whole; a failed capture is failing; got {lines[:2]}")
        (dlq / "2026-09-29-open.md").write_text("---\nstatus: active\n---\n# open\n", encoding="utf-8")
        rows[-1]["failed"] = 0
        if (got := rebuild(rows)[0]) != f"**⏸ stuck** · pipeline {hhmm(last)} · 1 open DLQ note(s)":
            problems.append(f"phase 9: an open DLQ note is stuck; got {got!r}")
        (dlq / "2026-09-29-open.md").unlink()
        late = clock - timedelta(hours=10)
        if (got := rebuild([_run_row(late)])[0]) != f"**⚠ late** · pipeline {hhmm(late)}":
            problems.append(f"phase 9: late names the last run's time, never 'N h ago'; got {got!r}")
        real = watchdog.health
        watchdog.health = lambda *a, **k: 1 / 0
        try:
            lines = rebuild(rows)
        finally:
            watchdog.health = real
        if not lines[0].startswith("*Generated") or not lines[0].endswith(receipt.replace(" · history shallow", "")):
            problems.append(f"phase 9: when health cannot run its line is left out, the rest stays; got {lines[:1]}")
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(json.dumps(
            {"parked": [], "last_run": {"at": "2026-09-29T10:03:00Z", "distilled": 2, "dropped": 1, "failed": 0}}), encoding="utf-8")
        lines = rebuild([{"run": last.strftime("%Y-%m-%d %H:%M"), "items": []}])
        if not lines[1].endswith(" · last run 2026-09-29 10:03 UTC: 2 distilled, 1 dropped, 0 failed*") or lines[2] != QUIET:
            problems.append(f"phase 9: a run row without counts falls back to pipeline-state.json's last run; got {lines[:3]}")

        # 10. new topics: the concept notes New counts, newest first, four at most; none in a quiet week
        now = (sandbox / "Now.md").read_text(encoding="utf-8")
        topics = next((ln for ln in _status(now) if ln.startswith("**New topics:** ")), "")
        n = now_build.build(sandbox, today)[1]["topics"]
        if (topics.count("[[") != 4 or not topics.endswith(f" … and {n - 4} more") or "Eval-Kind-Concept" not in topics
                or "Eval-Concept-5" not in topics or "Eval-Concept-0" in topics or "Eval-Concept-Old" in topics or _dead(topics)):
            problems.append(f"phase 10: New topics lists this week's concept notes (folder or kind), four, then how many more; got {topics!r}")
        if "**New topics:**" in now_build.build(sandbox, today + timedelta(days=400))[0]["Now.md"]:
            problems.append("phase 10: a week without a new concept note has no New topics line")

        # 11. not in your vault yet: the radar's strongest blind spots by name, and how many more
        spots = [{"key": f"b{i}", "name": "Blind [7]" if i == 7 else f"Blind {i}", "stage": "steady", "strength": 50 + i}
                 for i in range(1, 8)]
        anchored = {"key": "a", "name": "Anchored", "stage": "steady", "strength": 99}
        for keys, want in ((["b2", "b7", "b1", "b5", "b3", "b6", "b4"],
                            "**Not in your vault yet:** Blind (7) · Blind 6 · Blind 5 · Blind 4 · Blind 3 (+2 more, see the Signal Radar)"),
                           (["b1"], "**Not in your vault yet:** Blind 1"), ([], None)):
            (radar / "signal.json").write_text(json.dumps({"generated": f"{today}T08:30:00Z", "blips": [anchored, *spots],
                                                           "blind_spots": keys}), encoding="utf-8")
            lines = rebuild(rows)
            got = next((ln for ln in lines if ln.startswith("**Not in your vault yet:**")), None)
            if got != want or " · radar 08:30 UTC" not in lines[0]:
                problems.append(f"phase 11: blind spots {keys}: want {want!r}, got {got!r}; health names the radar's time: {lines[0]!r}")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else ("status first, folded week lists, one distilled rule, radar, stuck, "
                                                            "Kanban board, embedded views exist, signal, quiet, health, receipt, "
                                                            "new topics, blind spots")}
