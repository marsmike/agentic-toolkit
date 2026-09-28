"""Eval: backfill_timestamps.py proposes ingested_at/distilled_at from git history, never guesses
a time, writes nothing without --apply, and is idempotent.

1. propose  — a capture missing ingested_at and a distilled note missing both fields each get a
              row from the oldest commit that added the file, converted to UTC `Z`; a field the
              file already carries is left alone
2. dry run  — propose() alone (no --apply) writes nothing to disk
3. apply    — --apply writes the proposed fields plus their own `*_estimated: true`
4. idempotent — a second propose() after apply() finds nothing left to propose; a second apply()
              changes nothing further
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "backfill_timestamps"

CAPTURE = "---\nsource: https://example.org/backfill-capture\ncategory: article\nvia: clip\n---\n\n# Backfill capture\n"
NOTE_MISSING_BOTH = ("---\ndescription: missing both timestamps\nstatus: distilled\n"
                      "source: https://example.org/backfill-note\nprocessed_date: 2026-09-10\n---\n\n# N\n")
NOTE_HAS_INGESTED = ("---\ndescription: already has ingested_at\nstatus: distilled\n"
                      "source: https://example.org/backfill-note-2\nprocessed_date: 2026-09-10\n"
                      'ingested_at: "2026-09-01T00:00:00Z"\n---\n\n# N2\n')


def _git(root: Path, *args: str, when: str | None = None) -> None:
    env = dict(os.environ)
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False, env=env)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import backfill_timestamps as bt
    from vault_utils import read_frontmatter

    problems: list[str] = []
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval")):
            _git(sandbox, *args)

        cap = sandbox / "01_Capture" / "Readwise-Article-backfill.md"
        cap.write_text(CAPTURE, encoding="utf-8")
        _git(sandbox, "add", "--", "01_Capture/Readwise-Article-backfill.md")
        _git(sandbox, "commit", "-q", "-m", "add capture", when="2026-08-01T10:00:00+00:00")

        note1 = sandbox / "04_Resources" / "Eval-Backfill-Note.md"
        note1.write_text(NOTE_MISSING_BOTH, encoding="utf-8")
        _git(sandbox, "add", "--", "04_Resources/Eval-Backfill-Note.md")
        _git(sandbox, "commit", "-q", "-m", "add note", when="2026-08-02T11:30:00+00:00")

        note2 = sandbox / "04_Resources" / "Eval-Backfill-Note-2.md"
        note2.write_text(NOTE_HAS_INGESTED, encoding="utf-8")
        _git(sandbox, "add", "--", "04_Resources/Eval-Backfill-Note-2.md")
        _git(sandbox, "commit", "-q", "-m", "add note 2", when="2026-08-03T12:00:00+00:00")

        # --- 1 & 2: propose is a pure dry run ---
        rows = bt.propose(sandbox)
        by_path = {(r["path"], r["field"]): r["value"] for r in rows}
        if by_path.get(("01_Capture/Readwise-Article-backfill.md", "ingested_at")) != "2026-08-01T10:00:00Z":
            problems.append(f"phase 1: capture ingested_at not proposed from its first commit, got {by_path}")
        if by_path.get(("04_Resources/Eval-Backfill-Note.md", "ingested_at")) != "2026-08-02T11:30:00Z" or \
                by_path.get(("04_Resources/Eval-Backfill-Note.md", "distilled_at")) != "2026-08-02T11:30:00Z":
            problems.append(f"phase 1: note missing both fields not proposed correctly, got {by_path}")
        if ("04_Resources/Eval-Backfill-Note-2.md", "ingested_at") in by_path:
            problems.append("phase 1: a field the note already carries must not be proposed again")
        if by_path.get(("04_Resources/Eval-Backfill-Note-2.md", "distilled_at")) != "2026-08-03T12:00:00Z":
            problems.append(f"phase 1: note-2's missing distilled_at not proposed, got {by_path}")

        cap_fm_before, _ = read_frontmatter(cap)
        note1_fm_before, _ = read_frontmatter(note1)
        if cap_fm_before.get("ingested_at") or note1_fm_before.get("distilled_at"):
            problems.append("phase 2: propose() (no --apply) must not write anything")

        # --- 3: --apply writes the fields plus their own *_estimated flag ---
        written = bt.apply(sandbox, rows)
        if sorted(written) != sorted({r["path"] for r in rows}):
            problems.append(f"phase 3: apply() did not report every changed file, got {written}")
        cap_fm, _ = read_frontmatter(cap)
        if cap_fm.get("ingested_at") != "2026-08-01T10:00:00Z" or cap_fm.get("ingested_at_estimated") is not True:
            problems.append(f"phase 3: capture not written with ingested_at + ingested_at_estimated, got {cap_fm}")
        note1_fm, _ = read_frontmatter(note1)
        if note1_fm.get("distilled_at_estimated") is not True or note1_fm.get("ingested_at_estimated") is not True:
            problems.append(f"phase 3: note-1 missing its *_estimated flags, got {note1_fm}")
        note2_fm, _ = read_frontmatter(note2)
        if note2_fm.get("ingested_at") != "2026-09-01T00:00:00Z" or note2_fm.get("ingested_at_estimated") is True:
            problems.append(f"phase 3: note-2's real ingested_at must survive untouched, got {note2_fm}")
        if note2_fm.get("distilled_at_estimated") is not True:
            problems.append(f"phase 3: note-2's newly-proposed distilled_at needs its own estimated flag, got {note2_fm}")

        # --- 4: idempotent ---
        rows2 = bt.propose(sandbox)
        if rows2:
            problems.append(f"phase 4: a second propose() after apply() must find nothing left, got {rows2}")
        written2 = bt.apply(sandbox, rows2)
        if written2:
            problems.append(f"phase 4: a second apply() must change nothing, got {written2}")
        cap_fm_again, _ = read_frontmatter(cap)
        if cap_fm_again != cap_fm:
            problems.append("phase 4: re-running left the capture's frontmatter different")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else
            "proposes from git history, dry run writes nothing, --apply writes with *_estimated, idempotent"}
