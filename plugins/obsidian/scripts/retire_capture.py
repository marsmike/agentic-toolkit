#!/usr/bin/env python3
"""Retire one capture out of `01_Capture/` — distill invariant 6, in one call.

    retire_capture.py 01_Capture/<capture>.md --note <note> [--note <note>...] \\
        --line "<what became of it, in your own words, with [[wikilinks]] to the notes>"
    retire_capture.py 01_Capture/<capture>.md --dropped "<reason, from the dossier's triage>"

Moves the capture to `05_Archive/<Origin>-Captures-<YYYY-MM>/<stem>--FULLCAPTURE.md`
(`Origin` is the filename's own leading token, `Readwise` or `Research`), creates that
folder and its manifest `README.md` if this is the first capture retired there this month,
and appends one manifest line under an exclusive lock on the folder.

Today five workers did this by hand with `printf`: a literal `%` in one worker's text broke
that line, and two workers appending to the same manifest at once raced and lost a line
entirely (2026-09-24). This script is the one thing that touches a capture and a manifest
together — it never string-formats the line through a shell, and the lock covers the whole
create-folder-move-append sequence, not just the write.

Refuses, and moves nothing:
  - a `--note` that does not exist, or that fails `distill_check`'s hard gates for this
    capture (imported, not reimplemented — the same definition of done as the skill)
  - `--dropped` on a clip (`via: clip`, or no `via` at all): invariant 8, the owner's own
    clips never leave without a note
  - `--line` with no `--note`: a capture archived as distilled must name the note it became
  - neither, or both, of `--line` / `--dropped`

Prints one JSON object: the result on success, `{"error": ...}` on refusal (exit 1).
"""
from __future__ import annotations

import argparse
import calendar
import contextlib
import fcntl
import json
import time
from pathlib import Path
from typing import Any

from distill_check import check
from vault_utils import read_frontmatter, require_vault

OWNER_SOURCES = {"clip"}  # kept in step with distill_judge.OWNER_SOURCES; duplicated to
# avoid importing distill_judge's judgment-backend machinery into a script that must run
# with no key configured at all.


class RetireRefused(Exception):
    """A caller-visible refusal: printed as JSON, exit 1, nothing moved."""


def _origin(stem: str) -> str:
    return stem.split("-", 1)[0]


@contextlib.contextmanager
def _locked(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _manifest_header(origin: str, yyyymm: str, today: str) -> str:
    year, month = yyyymm.split("-")
    month_name = calendar.month_name[int(month)]
    fm = (f"---\ndescription: Manifest of {origin} captures archived from 01_Capture/ after "
          f"distillation, {month_name} {year} batch.\nstatus: archived\ncreated: {today}\n---\n")
    body = (f"\n# {origin} Captures — {yyyymm} — Archive Manifest\n\n"
            "Frozen provenance for captures distilled out of `01_Capture/`. Each row: capture "
            "→ where its content landed → disposition.\n")
    return fm + body


def _validate_notes(notes: list[str], capture: Path, vault: Path) -> list[str]:
    resolved = []
    for n in notes:
        note_path = Path(n) if Path(n).is_absolute() else vault / n
        if not note_path.is_file():
            raise RetireRefused(f"--note does not exist: {n}")
        report = check(note_path, capture, vault, asks=[])
        if not report["pass"]:
            failed = {g: why for g, (ok, why) in report["hard"].items() if not ok}
            raise RetireRefused(f"--note {n} fails distill_check's hard gates: {failed}")
        resolved.append(note_path.relative_to(vault).as_posix())
    return resolved


def retire(capture: Path, vault: Path, notes: list[str], line: str | None, dropped: str | None) -> dict[str, Any]:
    if bool(line) == bool(dropped):
        raise RetireRefused("give exactly one of --line or --dropped")
    if not capture.is_file():
        raise RetireRefused(f"no such capture: {capture}")
    rel = capture.relative_to(vault).as_posix() if capture.is_relative_to(vault) else str(capture)
    if not rel.startswith("01_Capture/"):
        raise RetireRefused(f"not a capture under 01_Capture/: {rel}")

    fm, _ = read_frontmatter(capture)
    via = str(fm.get("via") or "clip")
    if dropped and via in OWNER_SOURCES:
        raise RetireRefused(
            f"refusing --dropped: via={via!r} is the owner's own clip (invariant 8) — it must become a note, not be dropped")
    if line and not notes:
        raise RetireRefused("--line needs at least one --note: a distilled capture names the note it became")

    resolved_notes = _validate_notes(notes, capture, vault)

    origin = _origin(capture.stem)
    today = time.strftime("%Y-%m-%d")
    yyyymm = today[:7]
    folder = vault / "05_Archive" / f"{origin}-Captures-{yyyymm}"
    dest = folder / f"{capture.stem}--FULLCAPTURE.md"
    readme = folder / "README.md"

    with _locked(folder / ".manifest.lock"):
        folder.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise RetireRefused(f"already archived: {dest.relative_to(vault).as_posix()}")
        if not readme.exists():
            readme.write_text(_manifest_header(origin, yyyymm, today), encoding="utf-8")
        capture.rename(dest)
        if dropped:
            entry = f"- `{dest.name}` — **dropped** (never distilled): {dropped} Retired {today}.\n"
        else:
            entry = f"- `{dest.name}` — {line} Distilled {today}.\n"
        with readme.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    return {
        "capture": rel,
        "archived_to": dest.relative_to(vault).as_posix(),
        "manifest": readme.relative_to(vault).as_posix(),
        "notes": resolved_notes,
        "via": via,
        "mode": "dropped" if dropped else "line",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture")
    ap.add_argument("--note", action="append", default=[], dest="notes",
                    help="a note the capture was distilled into or enriched (repeatable; each must pass distill_check)")
    ap.add_argument("--line", help="manifest prose: what became of the capture")
    ap.add_argument("--dropped", help="manifest prose: why it was retired without a note (never for a clip)")
    args = ap.parse_args()
    vault = require_vault()
    capture = Path(args.capture) if Path(args.capture).is_absolute() else vault / args.capture

    try:
        result = retire(capture, vault, args.notes, args.line, args.dropped)
    except RetireRefused as e:
        print(json.dumps({"error": str(e)}, indent=2))
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
