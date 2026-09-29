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
6. refuse: mode   — neither or both of --line/--dropped refuses, and so does --line with no
                  --note (a clip archived as "distilled" with no note, 2026-09-24 review CODE-1)
7. append         — two captures retired into the same folder end with two correct, distinct
                  manifest lines (no interleaving, nothing lost)
8. duplicate      — a clip that repeats another is archived whole with --duplicate-of (never
                  deleted), the line names what it duplicates; a target that isn't in the vault
                  refuses and moves nothing; a note a --dropped or --duplicate-of retirement merely
                  mentions is left byte-identical
9. stamping       — retiring a capture with `ingested_at` stamps the note it names with
                  `distilled_at` (now, UTC `Z`), `updated_at` equal to it, and carries the
                  capture's own `ingested_at`
10. enrichment    — a note that already carries `distilled_at`/`ingested_at` keeps its own values
                  through retirement, gets a fresh `updated_at`, and every other frontmatter line
                  (a long description, double-quoted timestamps) is left exactly as written
11. idempotent    — retiring an already-retired capture refuses and changes no note, and so does
                  a capture refused as already archived (the stamp waits for that refusal)
12. ledger        — every retirement appends one `retired` row to 00_Memory/imports.jsonl with its
                  kind (new, enriched, dropped, duplicate), notes, reason and what; a refusal none

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


def _capture(via: str | None, ingested_at: str | None = None) -> str:
    lines = ["---", f"source: {SOURCE}", "origin: readwise"]
    if via is not None:
        lines.append(f"via: {via}")
    if ingested_at is not None:
        lines.append(f'ingested_at: "{ingested_at}"')
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

STAMP_INGESTED_AT = "2026-09-01T10:00:00Z"
ALREADY_STAMPED_DISTILLED_AT = "2020-01-01T00:00:00Z"
ALREADY_STAMPED_INGESTED_AT = "2019-12-31T00:00:00Z"

ALREADY_STAMPED_NOTE = f"""---
description: A note that already carries its own timestamps, and a description long enough that re-serializing the frontmatter through YAML would wrap it onto a second line.
status: distilled
source: {SOURCE}
processed_date: 2026-09-24
distilled_at: "{ALREADY_STAMPED_DISTILLED_AT}"
ingested_at: "{ALREADY_STAMPED_INGESTED_AT}"
---

# Retire eval note with its own timestamps

*Source: [Retire eval capture]({SOURCE})*

Body text with the claim carried over.
"""


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import retire_capture as rc
    import vault_utils

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
        for t in (t1, t2):
            t.start()
        for t in (t1, t2):
            t.join()
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
        (sandbox / "01_Capture" / "Readwise-Retire-Stamp.md").write_text(
            _capture("clip", STAMP_INGESTED_AT).replace(SOURCE, SOURCE + "-stamp"), encoding="utf-8")
        (sandbox / "04_Resources" / "Retire-Eval-Stamp.md").write_text(
            GOOD_NOTE.replace(SOURCE, SOURCE + "-stamp"), encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Retire-Keep.md").write_text(
            _capture("clip", STAMP_INGESTED_AT).replace(SOURCE, SOURCE + "-keep"), encoding="utf-8")
        (sandbox / "04_Resources" / "Retire-Eval-Keep.md").write_text(
            ALREADY_STAMPED_NOTE.replace(SOURCE, SOURCE + "-keep"), encoding="utf-8")
        index = sandbox / "Index.md"
        index.write_text(index.read_text(encoding="utf-8") +
                         "\n- [[04_Resources/Retire-Eval-Good|Retire Eval Good]] — fixture\n"
                         "- [[04_Resources/Retire-Eval-Good-2|Retire Eval Good 2]] — fixture\n"
                         "- [[04_Resources/Retire-Eval-Stamp|Retire Eval Stamp]] — fixture\n"
                         "- [[04_Resources/Retire-Eval-Keep|Retire Eval Keep]] — fixture\n",
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
        try:
            rc.retire(cap("Readwise-Retire-Clip2.md"), sandbox, [], "processed", None)
            problems.append("phase 6: --line with no --note was not refused")
        except rc.RetireRefused as e:
            if "--note" not in str(e):
                problems.append(f"phase 6: --line with no --note refused for the wrong reason: {e}")
        if not cap("Readwise-Retire-Clip2.md").is_file():
            problems.append("phase 6: capture was moved by --line with no --note")

        # --- 7. append: two captures into the same folder, two correct lines ---
        rc.retire(cap("Readwise-Retire-Clip2.md"), sandbox, ["04_Resources/Retire-Eval-Good.md"], "→ enrichment only.", None)
        rc.retire(cap("Readwise-Retire-Second.md"), sandbox, ["04_Resources/Retire-Eval-Good-2.md"], "→ [[Retire-Eval-Good-2]].", None)
        lines = [ln for ln in readme.read_text(encoding="utf-8").splitlines() if ln.startswith("- `")]
        if len(lines) != 4:  # phase 2, phase 3, phase 7 (x2)
            problems.append(f"phase 7: expected 4 manifest entries, got {len(lines)}: {lines}")
        if len({ln.split("`")[1] for ln in lines}) != 4:
            problems.append(f"phase 7: manifest entries are not all distinct captures: {lines}")
        good_text = (sandbox / "04_Resources" / "Retire-Eval-Good.md").read_text(encoding="utf-8")
        if good_text.count("\nupdated_at: ") != 1:  # retired twice (phases 2, 7): replaced, not appended
            problems.append(f"phase 7: a twice-enriched note must carry exactly one updated_at line: {good_text[:400]!r}")

        # --- 8. duplicate: kept whole, never deleted; a note it only mentions is left alone ---
        good_note_path = sandbox / "04_Resources" / "Retire-Eval-Good.md"
        good_before = good_note_path.read_text(encoding="utf-8")
        (sandbox / "01_Capture" / "Readwise-Retire-Dup.md").write_text(_capture("clip"), encoding="utf-8")
        try:
            rc.retire(cap("Readwise-Retire-Dup.md"), sandbox, [], None, None, "04_Resources/No-Such-Note.md")
            problems.append("phase 8: --duplicate-of a missing file was not refused")
        except rc.RetireRefused:
            pass
        r = rc.retire(cap("Readwise-Retire-Dup.md"), sandbox, [], None, None, "04_Resources/Retire-Eval-Good.md")
        text = readme.read_text(encoding="utf-8")
        if r["mode"] != "duplicate" or not (sandbox / r["archived_to"]).is_file() or \
                "**duplicate** of `04_Resources/Retire-Eval-Good.md`, kept whole here." not in text:
            problems.append(f"phase 8: duplicate not archived as expected: {r}")
        if r["stamped"] or good_note_path.read_text(encoding="utf-8") != good_before:
            problems.append(f"phase 8: a --duplicate-of retirement changed the note it names: {r['stamped']}")

        # --- 9. stamping: distilled_at and updated_at stamped now, ingested_at carried from the capture ---
        import re as _re

        ts_re = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        stamp_note_path = sandbox / "04_Resources" / "Retire-Eval-Stamp.md"
        r = rc.retire(cap("Readwise-Retire-Stamp.md"), sandbox, ["04_Resources/Retire-Eval-Stamp.md"],
                      "→ [[Retire-Eval-Stamp]].", None)
        if r.get("stamped") != ["04_Resources/Retire-Eval-Stamp.md"]:
            problems.append(f"phase 9: retire() did not report the note as stamped: {r.get('stamped')}")
        stamped_fm, _ = vault_utils.read_frontmatter(stamp_note_path)
        if not _re.match(ts_re, str(stamped_fm.get("distilled_at") or "")):
            problems.append(f"phase 9: distilled_at not stamped in the right format: {stamped_fm.get('distilled_at')!r}")
        if stamped_fm.get("updated_at") != stamped_fm.get("distilled_at"):
            problems.append(f"phase 9: a new note's updated_at must equal its distilled_at: {stamped_fm.get('updated_at')!r}")
        if stamped_fm.get("ingested_at") != STAMP_INGESTED_AT:
            problems.append(f"phase 9: ingested_at not carried from the capture: {stamped_fm.get('ingested_at')!r}")

        # --- 10. enrichment: its own timestamps and formatting kept, updated_at stamped fresh ---
        keep_note_path = sandbox / "04_Resources" / "Retire-Eval-Keep.md"
        keep_before = keep_note_path.read_text(encoding="utf-8")
        r = rc.retire(cap("Readwise-Retire-Keep.md"), sandbox, ["04_Resources/Retire-Eval-Keep.md"],
                      "→ [[Retire-Eval-Keep]].", None)
        if r.get("stamped") != ["04_Resources/Retire-Eval-Keep.md"]:
            problems.append(f"phase 10: an enriched note was not reported stamped: {r.get('stamped')}")
        keep_fm, _ = vault_utils.read_frontmatter(keep_note_path)
        if keep_fm.get("distilled_at") != ALREADY_STAMPED_DISTILLED_AT or keep_fm.get("ingested_at") != ALREADY_STAMPED_INGESTED_AT:
            problems.append(f"phase 10: existing timestamps were overwritten: {keep_fm.get('distilled_at')!r}, {keep_fm.get('ingested_at')!r}")
        updated_at = str(keep_fm.get("updated_at") or "")
        if not _re.match(ts_re, updated_at) or updated_at <= ALREADY_STAMPED_DISTILLED_AT:
            problems.append(f"phase 10: an enriched note's updated_at was not stamped now: {updated_at!r}")
        keep_after = keep_note_path.read_text(encoding="utf-8")
        if keep_after.replace(f"updated_at: '{updated_at}'\n", "", 1) != keep_before:
            problems.append(f"phase 10: stamping changed more than the updated_at line: {keep_after[:400]!r}")

        # --- 11. idempotent: a retirement that moves nothing changes no note ---
        stamp_before = stamp_note_path.read_text(encoding="utf-8")
        try:
            rc.retire(cap("Readwise-Retire-Stamp.md"), sandbox, ["04_Resources/Retire-Eval-Stamp.md"], "again", None)
            problems.append("phase 11: re-retiring an already-retired capture was not refused")
        except rc.RetireRefused:
            pass
        cap("Readwise-Retire-Stamp.md").write_text(
            _capture("clip", STAMP_INGESTED_AT).replace(SOURCE, SOURCE + "-stamp"), encoding="utf-8")
        try:
            rc.retire(cap("Readwise-Retire-Stamp.md"), sandbox, ["04_Resources/Retire-Eval-Stamp.md"], "again", None)
            problems.append("phase 11: a capture already in the archive was not refused")
        except rc.RetireRefused as e:
            if "already archived" not in str(e):
                problems.append(f"phase 11: refused for the wrong reason: {e}")
        if stamp_note_path.read_text(encoding="utf-8") != stamp_before:
            problems.append("phase 11: a refused re-retirement restamped the note")

        # --- 12. ledger: one `retired` row per retirement, fields not prose; a refusal writes none ---
        rows = {Path(r["retired"]).stem: r for r in vault_utils.read_jsonl(sandbox / rc.LEDGER) if r.get("retired")}
        want = {"Readwise-Retire-Clip": ("new", ["04_Resources/Retire-Eval-Good.md"], None, "→ new note [[Retire-Eval-Good]]."),
                "Readwise-Retire-Radar": ("dropped", [], "arrived via radar, discard-candidate 0.9", None),
                "Readwise-Retire-Clip2": ("enriched", ["04_Resources/Retire-Eval-Good.md"], None, "→ enrichment only."),
                "Readwise-Retire-Dup": ("duplicate", [], "duplicate of 04_Resources/Retire-Eval-Good.md", None),
                "Readwise-Retire-Keep": ("enriched", ["04_Resources/Retire-Eval-Keep.md"], None, "→ [[Retire-Eval-Keep]].")}
        got = {k: (r.get("kind"), r.get("notes"), r.get("reason"), r.get("what")) for k, r in rows.items() if k in want}
        if got != want:
            problems.append(f"phase 12: ledger rows {got}")
        if len(rows) != 7 or any(not _re.match(ts_re, str(r.get("at") or "")) or "run" in r for r in rows.values()):
            problems.append(f"phase 12: expected 7 timestamped retired rows and no run key, got {sorted(rows)}")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else
            "lock serializes; move+manifest succeed for --line and --dropped; refuses a dropped clip, a bad --note, a bad mode and --line without --note; appends accumulate; "
            "new and enriched notes get updated_at and nothing else changes; a refused re-retirement stamps nothing; "
            "one structured ledger row per retirement"}
