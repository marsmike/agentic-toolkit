"""Eval: daily_build.py writes the pipeline's block into each UTC day's 00_Daily/ note, in a git sandbox.

Fixture days are far from any date in the example vault (2031), each run pinned with `--today`.

1. create     — today's and yesterday's notes are created (frontmatter that parses, one block, the
                header says "UTC day"); the day before yesterday is never touched
2. content    — Distilled today: distilled_at's UTC day (an offset or unquoted YAML timestamp moved to
                UTC; 23:30Z and 00:30Z on different days), processed_date without one, never an
                estimated date, newest first; Changed today from updated_at, not repeating a distilled
                note (and nothing at all where no note has updated_at); Radar: the day's strong items,
                capped with "… and N more"; runs from `pipeline …` commits plus last_run (a vault
                with no run row in its ledger); Stuck: the day's active DLQ notes as obsidian://
                links, a resolved one left out; a `status: review` note never distilled is no one's
3. links      — titles with `|`, `]]`, `#` and `%% daily:end %%` break no wikilink and no marker; a
                description's own [[link]] is not carried over; a path with `#` gets an obsidian://
                link; every wikilink resolves to a note under 02–04 or an existing daily note
4. idempotent — a second run changes no byte
5. yesterday  — the first run of a new day rebuilds yesterday once (its → link); later runs leave it
6. hand text  — text before and after the markers survives byte for byte (CRLF too); a note without
                markers gets the block appended after its untouched text
7. malformed  — a start marker without an end: the file is untouched, reported, one DLQ note
8. quiet day  — "Nothing distilled", no runs or stuck section, no error
9. ledger     — with run rows in 00_Memory/imports.jsonl, the day's runs and totals are those rows,
                not the commits; a legacy row without counts counts as a run, "counts not recorded"
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
from pathlib import Path

import yaml
from _sandbox import make_sandbox, teardown_sandbox

NAME = "daily_build"
DAY, PREV, NEXT = "2031-03-14", "2031-03-13", "2031-03-15"
START, END = "%% daily:start %%", "%% daily:end %%"


def _note(title: str, desc: str, **fields: str) -> str:
    extra = "".join(f"{k}: {v}\n" for k, v in fields.items())
    return f"---\ntitle: {json.dumps(title)}\ndescription: {json.dumps(desc)}\nstatus: distilled\n{extra}---\n\n# N\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False).stdout


def _run(daily_build, today: str) -> dict:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        daily_build.main(["--json", "--today", today])
    return json.loads(out.getvalue())


def _section(text: str, title: str) -> str:
    m = re.search(rf"^### {re.escape(title)}.*?\n\n((?:- .*\n)*)", text, re.M)
    return m.group(1) if m else ""


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(folder.glob("*.md"))}


def run(vault: Path) -> dict:
    import sys

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import daily_build

    problems: list[str] = []
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        res, daily = sandbox / "04_Resources", sandbox / "00_Daily"
        notes = {
            "Eval-Daily-Late.md": _note("Late", "late", distilled_at=f"{DAY}T23:30:00Z", processed_date=DAY),
            "Eval-Daily-Next.md": _note("Next day", "next", distilled_at=f"{NEXT}T00:30:00Z", processed_date=NEXT),
            "Eval-Daily-Offset.md": _note(
                "Offset", "offset", distilled_at=f'"{NEXT}T01:30:00+02:00"', processed_date=NEXT
            ),
            "Eval-Daily-Morning.md": _note("Morning", "morning", distilled_at=f'"{DAY}T08:00:00Z"', processed_date=DAY),
            "Eval-Daily-Dateonly.md": _note("Date only", "date only", processed_date=DAY),
            "Eval-Daily-Estimated.md": _note(
                "Estimated", "estimated", processed_date=DAY, processed_date_estimated="true"
            ),
            "Eval-Daily-Weird.md": _note(
                "A | B ]] C # D %% daily:end %% and %%% too",
                "see [[Nowhere Note]] and [[x|y]] too",
                distilled_at=f"{DAY}T12:00:00Z",
                processed_date=DAY,
                updated_at=f"{DAY}T13:00:00Z",
            ),
            "Eval-Daily-C#-Sharp.md": _note(
                "C sharp", "hash in the path", distilled_at=f"{DAY}T11:00:00Z", processed_date=DAY
            ),
            "Eval-Daily-Touched.md": _note(
                "Touched", "touched", processed_date="2031-01-01", updated_at=f"{DAY}T09:15:00Z"
            ),
        }
        # never distilled: a real processed_date, but no distilled_at and not `status: distilled`
        notes["Eval-Daily-Review.md"] = _note("Review", "review", processed_date=DAY).replace(
            "status: distilled", "status: review"
        )
        for name, text in notes.items():
            (res / name).write_text(text, encoding="utf-8")
        radar = sandbox / "00_Memory" / "radar"
        radar.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "run": DAY,
                "canonical": f"s{i}",
                "url": f"https://s{i}.example/",
                "title": f"Strong {i:02d}",
                "strong": ["t1"],
                "p": {"t1": 0.5 + i / 100},
            }
            for i in range(12)
        ]
        rows += [
            {
                "run": PREV,
                "canonical": "old",
                "url": "https://old.example/",
                "title": "Strong yesterday",
                "strong": ["t1"],
                "p": {"t1": 0.99},
            },
            {
                "run": DAY,
                "canonical": "weak",
                "url": "https://weak.example/",
                "title": "Weak one",
                "strong": [],
                "p": {"t1": 0.1},
            },
        ]
        (radar / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (sandbox / "00_Memory" / "pipeline-state.json").write_text(
            json.dumps({"last_run": {"at": f"{DAY}T12:00:00.5+00:00", "distilled": 2, "dropped": 0, "failed": 1}}),
            encoding="utf-8",
        )
        (sandbox / "00_Memory" / "dlq" / f"{DAY}-eval-stuck.md").write_text(
            f"---\ndescription: Eval stuck thing\nstatus: active\ncreated: {DAY}\n---\n# x\n", encoding="utf-8"
        )
        (sandbox / "00_Memory" / "dlq" / f"{DAY}-eval-resolved.md").write_text(
            f"---\ndescription: Eval resolved thing\nstatus: resolved\ncreated: {DAY}\n---\n# x\n", encoding="utf-8"
        )
        for args in (
            ("init", "-q"),
            ("config", "user.email", "eval@example.org"),
            ("config", "user.name", "eval"),
            ("add", "-A"),
            ("commit", "-q", "-m", "base"),
            ("commit", "-q", "--allow-empty", "-m", f"pipeline {DAY} 08:00: 3 distilled, 1 dropped, 0 failed; x"),
            ("commit", "-q", "--allow-empty", "-m", f"pipeline {PREV} 23:00: 9 distilled, 0 dropped, 0 failed"),
        ):
            _git(sandbox, *args)

        # 1. create
        stats = _run(daily_build, DAY)
        today, prev = daily / f"{DAY}.md", daily / f"{PREV}.md"
        if not today.is_file() or not prev.is_file() or (daily / "2031-03-12.md").exists():
            problems.append(
                f"phase 1: today's and yesterday's notes created, never earlier; got {sorted(p.name for p in daily.glob('*'))}"
            )
            return {"eval": NAME, "pass": False, "detail": "; ".join(problems)}
        text = today.read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---", 2)[1])
        if str(fm.get("created")) != DAY or "daily" not in (fm.get("tags") or []) or "generated_by" in fm:
            problems.append(f"phase 1: minimal frontmatter (created, tags: daily, no generated_by); got {fm}")
        if text.count(START) != 1 or text.count(END) != 1 or f"{DAY} (UTC day)" not in text:
            problems.append("phase 1: one block, its header naming the UTC day")

        # 2. content
        dist, changed = _section(text, "Distilled today"), _section(text, "Changed today")
        order = [dist.find(f"Eval-Daily-{n}|") for n in ("Late", "Offset", "Weird", "Morning", "Dateonly")]
        if -1 in order or order != sorted(order):
            problems.append(
                f"phase 2: distilled that UTC day, newest first (23:30Z, 01:30+02:00, 12:00, 08:00, date-only); got {dist!r}"
            )
        if "Eval-Daily-Next|" in dist or "Estimated" in dist or "Eval-Daily-Touched" in dist or "Eval-Daily-Review" in dist:
            problems.append(
                f"phase 2: 00:30Z is the next day's, an estimated date is no one's, a note never distilled is not; got {dist!r}"
            )
        if "Eval-Daily-Touched|" not in changed or "Weird" in changed or not text.count("### Changed today (1)"):
            problems.append(f"phase 2: Changed today holds the updated note, not the distilled one; got {changed!r}")
        prev_text = prev.read_text(encoding="utf-8")
        if "### Changed today (0)" not in prev_text:
            problems.append("phase 2: a day on which no note has updated_at shows Changed today (0), no error")
        rad = _section(text, "Radar today")
        if (
            "Strong 11" not in rad
            or "Strong 00" in rad
            or "… and 2 more" not in rad
            or "yesterday" in rad
            or "Weak" in rad
        ):
            problems.append(f"phase 2: the day's strong radar items, strongest first, capped; got {rad!r}")
        runs = _section(text, "Pipeline runs today")
        if "In all: 5 distilled, 1 dropped, 1 failed" not in runs or "08:00 UTC" not in runs or "12:00 UTC" not in runs:
            problems.append(f"phase 2: runs from the day's pipeline commit and last_run; got {runs!r}")
        if "9 distilled" not in _section(prev_text, "Pipeline runs today"):
            problems.append("phase 2: yesterday's note counts yesterday's pipeline commit")
        stuck = _section(text, "Stuck today")
        if "Eval stuck thing" not in stuck or "obsidian://open?vault=" not in stuck or "[[00_Memory" in text:
            problems.append(f"phase 2: the day's DLQ note as an obsidian:// link, never a wikilink; got {stuck!r}")
        if "Eval resolved thing" in text or "### Stuck today (1)" not in text:
            problems.append(f"phase 2: a resolved DLQ note is not stuck; got {stuck!r}")

        # 3. links
        for page in daily.glob("*.md"):
            body = page.read_text(encoding="utf-8")
            if body.count(START) != 1 or body.count(END) != 1 or body.count("%%") != 4:
                problems.append(f"phase 3: {page.name} holds exactly one start and one end marker")
            for inner in re.findall(r"\[\[(.*?)\]\]", body):
                target = inner.split("|", 1)[0]
                ok = (target.startswith("00_Daily/") and (sandbox / f"{target}.md").is_file()) or (
                    target.startswith(("02_Projects/", "03_Areas/", "04_Resources/"))
                    and (sandbox / f"{target}.md").is_file()
                )
                if not ok:
                    problems.append(f"phase 3: {page.name} has a dead or disallowed wikilink [[{inner}]]")
        if "Nowhere Note" in text and "[[Nowhere" in text:
            problems.append("phase 3: a description's own wikilink must not be carried over")
        if "C sharp ([open](obsidian://" not in dist:
            problems.append(f"phase 3: a path with '#' gets an obsidian:// link; got {dist!r}")
        if f"[[00_Daily/{PREV}|←]]" not in text or f"[[00_Daily/{DAY}|→]]" not in prev_text or "|→]]" in text:
            problems.append("phase 3: prev/next links only to daily notes that exist")

        # 4. idempotent
        before = _snapshot(daily)
        again = _run(daily_build, DAY)
        if _snapshot(daily) != before or again.get("changed"):
            problems.append(f"phase 4: a second run changes nothing; changed {again.get('changed')}")

        # 5. yesterday: the first run of NEXT rebuilds DAY once (→ link, a note distilled after it was built)
        (res / "Eval-Daily-Latecomer.md").write_text(
            _note("Latecomer", "stamped just before midnight", distilled_at=f"{DAY}T23:59:00Z", processed_date=DAY),
            encoding="utf-8",
        )
        oldest = prev.read_bytes()
        _run(daily_build, NEXT)
        text = today.read_text(encoding="utf-8")
        nxt = (daily / f"{NEXT}.md").read_text(encoding="utf-8")
        if f"[[00_Daily/{NEXT}|→]]" not in text or "Eval-Daily-Latecomer|" not in text:
            problems.append("phase 5: the first run of a new day rebuilds yesterday (→ link, its last notes)")
        if "Eval-Daily-Next|" not in nxt or "Eval-Daily-Late|" in nxt:
            problems.append(f"phase 5: 00:30Z lands on the next UTC day; got {_section(nxt, 'Distilled today')!r}")
        if prev.read_bytes() != oldest:
            problems.append("phase 5: a day further back than yesterday is never rebuilt")
        (res / "Eval-Daily-Straggler.md").write_text(
            _note("Straggler", "after the fact", distilled_at=f"{DAY}T22:00:00Z", processed_date=DAY), encoding="utf-8"
        )
        settled = today.read_bytes()
        _run(daily_build, NEXT)
        if today.read_bytes() != settled:
            problems.append("phase 5: once today's note has its block, yesterday's is left as it is")

        # 6. hand text, before and after the markers (CRLF), and a note without markers
        hand_day, bare_day = "2031-04-02", "2031-04-20"
        head, tail = "---\ntags: [daily]\n---\r\nMorning, by hand.\r\n\r\n", "\r\n\r\nEvening, by hand. [[Nowhere]]\r\n"
        hand = daily / f"{hand_day}.md"
        hand.write_bytes((head + f"{START}\r\nold block\r\n{END}" + tail).encode("utf-8"))
        # the day before bare_day is built first; bare_day's note then exists by hand (the owner
        # clicked it in the Calendar before any run), so the first run of bare_day still rebuilds it
        _run(daily_build, "2031-04-19")
        (res / "Eval-Daily-Midnight.md").write_text(
            _note("Midnight", "just before midnight", distilled_at="2031-04-19T23:58:00Z", processed_date="2031-04-19"),
            encoding="utf-8",
        )
        bare = daily / f"{bare_day}.md"
        bare_text = "# My day\n\nNo markers here, no final newline"
        bare.write_bytes(bare_text.encode("utf-8"))
        _run(daily_build, hand_day)
        _run(daily_build, bare_day)
        eve = (daily / "2031-04-19.md").read_text(encoding="utf-8")
        if "Eval-Daily-Midnight|" not in eve or f"[[00_Daily/{bare_day}|→]]" not in eve:
            problems.append("phase 6: a hand-made note without a block still makes its first run rebuild yesterday")
        got = hand.read_bytes().decode("utf-8")
        if not got.startswith(head) or not got.endswith(tail) or "old block" in got or "Nothing distilled" not in got:
            problems.append("phase 6: text before and after the markers is kept byte for byte, the block replaced")
        got = bare.read_bytes().decode("utf-8")
        if not got.startswith(bare_text + "\n\n" + START) or not got.endswith(END + "\n"):
            problems.append("phase 6: a note without markers keeps its text and gets the block appended")
        settled = bare.read_bytes(), hand.read_bytes()
        _run(daily_build, bare_day)
        _run(daily_build, hand_day)
        if (bare.read_bytes(), hand.read_bytes()) != settled:
            problems.append("phase 6: rerunning a hand-written note changes nothing")

        # 7. malformed markers
        bad_day = "2031-05-10"
        bad = daily / f"{bad_day}.md"
        bad_bytes = f"Mine.\n{START}\nno end marker, and my text after it\n".encode()
        bad.write_bytes(bad_bytes)
        for _ in range(2):
            stats = _run(daily_build, bad_day)
        dlq = list((sandbox / "00_Memory" / "dlq").glob(f"*daily-markers-{bad_day}*.md"))
        if bad.read_bytes() != bad_bytes or f"00_Daily/{bad_day}.md" not in stats.get("malformed", []) or len(dlq) != 1:
            problems.append(
                f"phase 7: malformed markers: file untouched, reported, one DLQ note; got {stats}, {len(dlq)} DLQ"
            )

        # 8. quiet day
        quiet = "2031-06-01"
        stats = _run(daily_build, quiet)
        text = (daily / f"{quiet}.md").read_text(encoding="utf-8")
        if (
            "- Nothing distilled" not in text
            or "Pipeline runs today" in text
            or "Stuck today" in text
            or stats.get("distilled")
        ):
            problems.append(f"phase 8: a quiet day gets a block saying so; got {text!r}")

        # 9. ledger: once imports.jsonl has run rows, the day's runs are those rows, never the commits
        # (the 08:00 commit above has no row here); a legacy row without counts still counts as a run
        ledger = sandbox / "00_Memory" / "imports.jsonl"
        ledger.write_text(
            "".join(
                json.dumps(r) + "\n"
                for r in (
                    {"kind": "run", "run": f"{DAY} 03:00", "at": f"{DAY}T03:00:04Z", "distilled": 4, "dropped": 2,
                     "failed": 0, "shallow": True, "items": []},
                    {"run": f"{DAY} 06:00", "items": []},
                    {"kind": "run", "run": f"{DAY} 09:00", "at": f"{DAY}T09:00:02Z", "distilled": 1, "dropped": 0,
                     "failed": 1, "shallow": True, "items": []},
                )
            ),
            encoding="utf-8",
        )
        _run(daily_build, DAY)
        runs = _section(today.read_text(encoding="utf-8"), "Pipeline runs today")
        want = [
            "- In all: 5 distilled, 2 dropped, 1 failed (1 run(s) without recorded counts)",
            "- 03:00 UTC: 4 distilled, 2 dropped, 0 failed",
            "- 06:00 UTC: counts not recorded",
            "- 09:00 UTC: 1 distilled, 0 dropped, 1 failed",
        ]
        if runs.splitlines() != want or "### Pipeline runs today (3)" not in today.read_text(encoding="utf-8"):
            problems.append(f"phase 9: the day's runs come from the ledger's run rows; got {runs!r}")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {
        "eval": NAME,
        "pass": not problems,
        "detail": "; ".join(problems)
        if problems
        else "UTC day, hand text kept, yesterday once, malformed reported, safe links, quiet day",
    }
