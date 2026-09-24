"""Eval: retire_capture.py does invariant 6 in one call, and refuses what it must.

Five workers moved today's captures by hand: a `printf` with a literal `%` broke a manifest
line, and two concurrent appends raced. This script is the one thing that touches a capture
and its folder's manifest together, under a lock.

1. lock         — `_locked()` actually serializes: a second acquirer waits for the first to
                  release, not just "usually finishes in order"
2. success/line — a valid capture + a note that passes distill_check moves the capture to
                  05_Archive/<Origin>-Captures-<YYYY-MM>/<stem>--FULLCAPTURE.md, creates the
                  folder and a manifest README with a real header, and appends one correct line
3. success/dropped — a non-owner capture (`via: radar`) may be dropped with a reason; the line
                  says so and the capture still moves
4. refuse: clip dropped — `--dropped` on `via: clip` (and on no `via` at all) refuses and moves
                  nothing (invariant 8)
5. refuse: bad note — a `--note` that doesn't exist, and one that fails a distill_check hard
                  gate, both refuse and move nothing
6. refuse: mode   — neither or both of --line/--dropped refuses
7. append         — two captures retired into the same folder end with two correct, distinct
                  manifest lines (no interleaving, nothing lost)

Offline: judgment keys are removed so distill_check's soft findability/preservation calls (which
need a backend) never run; retire_capture only needs the hard gates, which don't.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "retire_capture"
KEY_ENVS = ("TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
SOURCE = "https://example.org/retire-eval-article"


def _capture(via: str | None) -> str:
    lines = ["---", f"source: {SOURCE}", "origin: readwise"]
    if via is not None:
        lines.append(f"via: {via}")
    lines += ["---", "", "# Retire eval capture", "", f"*Source: [{SOURCE}]({SOURCE})*", "",
              "## Full Text", "", "A claim with a number: 100% of gates catch what they are shown to catch."]
    return "\n".join(lines) + "\n"


GOOD_NOTE = f"""---
description: A note that passes every hard gate.
status: distilled
source: {SOURCE}
processed_date: 2026-09-24
---

# Retire eval note

*Source: [Retire eval capture]({SOURCE})*

Body text with the claim carried over.
"""

BAD_NOTE = """---
description: A note missing from Index.md.
status: distilled
source: https://example.org/retire-eval-article
processed_date: 2026-09-24
---

# Retire eval note without an index line
"""


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import retire_capture as rc

    problems: list[str] = []
    saved = {k: os.environ.pop(k, None) for k in KEY_ENVS}
    sandbox = None
    try:
        sandbox = make_sandbox(vault)

        # --- 1. lock mutual exclusion ---
        lock_path = sandbox / "05_Archive" / "Lock-Test" / ".manifest.lock"
        events: list[str] = []
        started = threading.Event()

        def holder():
            with rc._locked(lock_path):
                events.append("holder-in")
                started.set()
                time.sleep(0.3)
                events.append("holder-out")

        def waiter():
            started.wait()
            with rc._locked(lock_path):
                events.append("waiter-in")

        t1, t2 = threading.Thread(target=holder), threading.Thread(target=waiter)
        t1.start(); t2.start(); t1.join(); t2.join()
        if events != ["holder-in", "holder-out", "waiter-in"]:
            problems.append(f"phase 1: lock did not serialize: {events}")

        # --- fixtures for the rest ---
        (sandbox / "01_Capture" / "Readwise-Retire-Clip.md").write_text(_capture("clip"), encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Retire-NoVia.md").write_text(_capture(None), encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Retire-Radar.md").write_text(_capture("radar"), encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Retire-Second.md").write_text(
            _capture("clip").replace(SOURCE, SOURCE + "-2"), encoding="utf-8")
        (sandbox / "04_Resources" / "Retire-Eval-Good.md").write_text(GOOD_NOTE, encoding="utf-8")
        (sandbox / "04_Resources" / "Retire-Eval-Good-2.md").write_text(
            GOOD_NOTE.replace(SOURCE, SOURCE + "-2"), encoding="utf-8")
        (sandbox / "04_Resources" / "Retire-Eval-Bad.md").write_text(BAD_NOTE, encoding="utf-8")
        index = sandbox / "Index.md"
        index.write_text(index.read_text(encoding="utf-8") +
                         "\n- [[04_Resources/Retire-Eval-Good|Retire Eval Good]] — fixture\n"
                         "- [[04_Resources/Retire-Eval-Good-2|Retire Eval Good 2]] — fixture\n",
                         encoding="utf-8")

        def cap(name: str) -> Path:
            return sandbox / "01_Capture" / name

        # --- 2. success / --line ---
        r = rc.retire(cap("Readwise-Retire-Clip.md"), sandbox, ["04_Resources/Retire-Eval-Good.md"],
                      "→ new note [[Retire-Eval-Good]].", None)
        month = time.strftime("%Y-%m")
        dest = sandbox / "05_Archive" / f"Readwise-Captures-{month}" / "Readwise-Retire-Clip--FULLCAPTURE.md"
        readme = sandbox / "05_Archive" / f"Readwise-Captures-{month}" / "README.md"
        if cap("Readwise-Retire-Clip.md").exists() or not dest.is_file():
            problems.append("phase 2: capture was not moved to the expected archive path")
        if r["archived_to"] != dest.relative_to(sandbox).as_posix() or r["notes"] != ["04_Resources/Retire-Eval-Good.md"]:
            problems.append(f"phase 2: unexpected result {r}")
        text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        if "description: Manifest of Readwise captures" not in text or "status: archived" not in text:
            problems.append(f"phase 2: manifest header missing or wrong: {text[:200]!r}")
        if "- `Readwise-Retire-Clip--FULLCAPTURE.md` — → new note [[Retire-Eval-Good]]. Distilled" not in text:
            problems.append(f"phase 2: manifest line missing or malformed: {text!r}")

        # --- 3. success / --dropped (non-owner capture) ---
        r = rc.retire(cap("Readwise-Retire-Radar.md"), sandbox, [], None, "arrived via radar, discard-candidate 0.9")
        if r["mode"] != "dropped" or r["via"] != "radar":
            problems.append(f"phase 3: unexpected result {r}")
        text = readme.read_text(encoding="utf-8")
        if "**dropped** (never distilled): arrived via radar" not in text:
            problems.append("phase 3: dropped manifest line missing or malformed")

        # --- 4. refuse: dropping a clip (a fresh one: phase 2 already moved the first; same
        # source as Retire-Eval-Good.md so phase 7 can reuse that note for it too) ---
        (sandbox / "01_Capture" / "Readwise-Retire-Clip2.md").write_text(_capture("clip"), encoding="utf-8")
        for name in ("Readwise-Retire-Clip2.md", "Readwise-Retire-NoVia.md"):
            try:
                rc.retire(cap(name), sandbox, [], None, "should be refused")
                problems.append(f"phase 4: --dropped on {name} was not refused")
            except rc.RetireRefused as e:
                if "invariant 8" not in str(e):
                    problems.append(f"phase 4: {name} refused for the wrong reason: {e}")
            if not cap(name).is_file():
                problems.append(f"phase 4: {name} was moved despite being refused")

        # --- 5. refuse: bad --note ---
        try:
            rc.retire(cap("Readwise-Retire-Clip2.md"), sandbox, ["04_Resources/No-Such-Note.md"], "x", None)
            problems.append("phase 5: a nonexistent --note was not refused")
        except rc.RetireRefused:
            pass
        try:
            rc.retire(cap("Readwise-Retire-Clip2.md"), sandbox, ["04_Resources/Retire-Eval-Bad.md"], "x", None)
            problems.append("phase 5: a --note failing distill_check was not refused")
        except rc.RetireRefused as e:
            if "hard gates" not in str(e):
                problems.append(f"phase 5: wrong refusal reason: {e}")
        if not cap("Readwise-Retire-Clip2.md").is_file():
            problems.append("phase 5: capture was moved despite a refused --note")

        # --- 6. refuse: mode ---
        for line, dropped in ((None, None), ("x", "y")):
            try:
                rc.retire(cap("Readwise-Retire-Clip2.md"), sandbox, [], line, dropped)
                problems.append(f"phase 6: line={line!r} dropped={dropped!r} was not refused")
            except rc.RetireRefused:
                pass

        # --- 7. append: two captures into the same folder, two correct lines ---
        rc.retire(cap("Readwise-Retire-Clip2.md"), sandbox, ["04_Resources/Retire-Eval-Good.md"], "→ enrichment only.", None)
        rc.retire(cap("Readwise-Retire-Second.md"), sandbox, ["04_Resources/Retire-Eval-Good-2.md"], "→ [[Retire-Eval-Good-2]].", None)
        lines = [ln for ln in readme.read_text(encoding="utf-8").splitlines() if ln.startswith("- `")]
        if len(lines) != 4:  # phase 2, phase 3, phase 7 (x2)
            problems.append(f"phase 7: expected 4 manifest entries, got {len(lines)}: {lines}")
        if len({ln.split("`")[1] for ln in lines}) != 4:
            problems.append(f"phase 7: manifest entries are not all distinct captures: {lines}")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else
            "lock serializes; move+manifest succeed for --line and --dropped; refuses a dropped clip, a bad --note, and a bad mode; appends accumulate"}
