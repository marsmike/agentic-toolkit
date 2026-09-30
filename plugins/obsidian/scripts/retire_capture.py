#!/usr/bin/env python3
"""Retire one capture out of `01_Capture/` — distill invariant 6, in one call.

    retire_capture.py 01_Capture/<capture>.md --note <note> [--note <note>...] \\
        --line "<what became of it, in your own words, with [[wikilinks]] to the notes>"
    retire_capture.py 01_Capture/<capture>.md --dropped "<reason, from the dossier's triage>"
    retire_capture.py 01_Capture/<capture>.md --duplicate-of <capture, archived capture or note>

Moves the capture to `05_Archive/<Origin>-Captures-<YYYY-MM>/<stem>--FULLCAPTURE.md`
(`<stem>-2--FULLCAPTURE.md` and on when another capture of the same name is already there;
`Origin` is the filename's own leading token, `Readwise` or `Research`), creates that
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
  - `--duplicate-of` a path that does not exist in the vault
  - not exactly one of `--line` / `--dropped` / `--duplicate-of`

Nothing is ever deleted: a duplicate is archived whole like any other capture, its manifest line
naming what it duplicates. [earned: 2026-09-25, owner's request — keep every clipping in the
vault; deleting duplicates and stubs was the one way a clipping could leave without a trace]

Before the capture moves, every `--note` it names is stamped with `distilled_at` (now, UTC) and
the capture's own `ingested_at` (carried over) — deterministically, never left to the skill to
write, and never overwriting a value the note already carries. [earned: 2026-09-28 — the owner
asked for the ingest and distill date and time on every report and note] Each also gets
`updated_at` (the same now) every time, new note or enriched one: the only record of when the
pipeline last changed it, since git resets `file.mtime`. It is stamped under the manifest lock,
after the already-archived refusal, so a retirement that moves nothing changes no note.
[earned: 2026-09-29 — the owner asked for "recently changed notes"; a pull touched 133 mtimes]

After the move it appends one row to the pipeline's ledger, `00_Memory/imports.jsonl`, under that
ledger's own lock: `{"retired": <capture>, "at", "kind", "notes", "reason", "what", "archived_to"}`,
`kind` one of `new` (a `--note` got its first `distilled_at` here), `enriched` (every `--note` was
distilled before), `dropped` or `duplicate`; `reason` is the `--dropped` text or what it duplicates;
`what` is the `--line`. The manifest line stays the human record; every page reads the row.
[earned: 2026-09-29 — pages parsed the manifest's prose for what a capture became, and a `--line`
without a wikilink named no note at all]

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
from vault_utils import (
    append_jsonl,
    inside,
    jsonl_lock,
    read_frontmatter,
    require_vault,
    set_frontmatter_fields,
    utc_timestamp,
)

LEDGER = Path("00_Memory") / "imports.jsonl"  # imports_log.LOG; not imported, imports_log reads the archive

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
        note_path = vault / n
        if not inside(note_path, vault) or not note_path.is_file():
            raise RetireRefused(f"--note does not exist: {n}")
        report = check(note_path, capture, vault, asks=[])
        if not report["pass"]:
            failed = {g: why for g, (ok, why) in report["hard"].items() if not ok}
            raise RetireRefused(f"--note {n} fails distill_check's hard gates: {failed}")
        resolved.append(note_path.relative_to(vault).as_posix())
    return resolved


def _stamp_notes(vault: Path, notes: list[str], capture_ingested_at: str | None) -> bool:
    """Deterministically stamp every note the capture became or enriched: `updated_at` to now,
    always; `distilled_at` to the same now and `ingested_at` carried from the capture, each only
    where the note has none yet (an earlier distillation's own timestamps stand). Never left to
    the skill/LLM to write. Called under the manifest lock, after the already-archived refusal and
    before the capture moves, while its own frontmatter (and `ingested_at`) is still readable.
    contract/VAULT_SCHEMA.md; the module docstring says what earned each field. True when any note
    got its first `distilled_at` here: the capture became a new note, not only an enrichment."""
    now = utc_timestamp()
    first = False
    for rel in notes:
        path = vault / rel
        fm, _ = read_frontmatter(path, strict=True)
        fields = {}
        if not fm.get("ingested_at") and capture_ingested_at:
            fields["ingested_at"] = capture_ingested_at
        if not fm.get("distilled_at"):
            fields["distilled_at"] = now
            first = True
        set_frontmatter_fields(path, {**fields, "updated_at": now})
        # The edit is textual, so prove it: the note still parses and carries exactly this stamp.
        if read_frontmatter(path, strict=True)[0].get("updated_at") != now:
            raise RetireRefused(f"--note {rel} did not take its updated_at stamp; capture not moved")
    return first


def _same_capture(archived: Path, fm: dict[str, Any], capture: Path) -> bool:
    """The archived file is this capture retired before (refuse), not another capture that happens
    to share its name (archive beside it). Two untitled Google News items both became
    `…-Google-News-2026-09-30.md`; the second could never be retired. [earned: 2026-09-30]"""
    old, _ = read_frontmatter(archived)
    for key in ("readwise_doc_id", "source"):
        if old.get(key) and fm.get(key):
            return str(old[key]) == str(fm[key])
    return archived.read_bytes() == capture.read_bytes()


def retire(capture: Path, vault: Path, notes: list[str], line: str | None, dropped: str | None,
           duplicate_of: str | None = None) -> dict[str, Any]:
    if sum(map(bool, (line, dropped, duplicate_of))) != 1:
        raise RetireRefused("give exactly one of --line, --dropped or --duplicate-of")
    if not capture.is_file():
        raise RetireRefused(f"no such capture: {capture}")
    # Resolved, not as written: `01_Capture/../../.env` or a symlink would move a file from outside
    # the inbox into the vault, where the agent may read it. [earned: 2026-09-24, review-01 SEC-1]
    inbox = (vault / "01_Capture").resolve()
    rel = capture.relative_to(vault).as_posix() if capture.is_relative_to(vault) else str(capture)
    if not rel.startswith("01_Capture/") or not capture.resolve().is_relative_to(inbox):
        raise RetireRefused(f"not a capture under 01_Capture/: {rel}")

    fm, _ = read_frontmatter(capture)
    via = str(fm.get("via") or "clip")
    if dropped and via in OWNER_SOURCES:
        raise RetireRefused(
            f"refusing --dropped: via={via!r} is the owner's own clip (invariant 8) — it must become a note, not be dropped")
    if duplicate_of:
        target = vault / duplicate_of
        if not inside(target, vault) or not target.is_file() or target.resolve() == capture.resolve():
            raise RetireRefused(f"--duplicate-of is not another file in the vault: {duplicate_of}")
    if line and not notes:
        raise RetireRefused("--line needs at least one --note: a distilled capture names the note it became")

    resolved_notes = _validate_notes(list(dict.fromkeys(notes)), capture, vault)
    ingested_at = fm.get("ingested_at") if isinstance(fm.get("ingested_at"), str) else None

    origin = _origin(capture.stem)
    today = time.strftime("%Y-%m-%d")
    yyyymm = today[:7]
    folder = vault / "05_Archive" / f"{origin}-Captures-{yyyymm}"
    readme = folder / "README.md"

    with _locked(folder / ".manifest.lock"):
        folder.mkdir(parents=True, exist_ok=True)
        n = 1
        while True:
            dest = folder / f"{capture.stem}{'' if n == 1 else f'-{n}'}--FULLCAPTURE.md"
            if not dest.exists():
                break
            if _same_capture(dest, fm, capture):
                raise RetireRefused(f"already archived: {dest.relative_to(vault).as_posix()}")
            n += 1
        first = _stamp_notes(vault, resolved_notes, ingested_at)
        if not readme.exists():
            readme.write_text(_manifest_header(origin, yyyymm, today), encoding="utf-8")
        capture.rename(dest)
        if duplicate_of:
            entry = f"- `{dest.name}` — **duplicate** of `{duplicate_of}`, kept whole here. Retired {today}.\n"
            kind, reason = "duplicate", f"duplicate of {duplicate_of}"
        elif dropped:
            entry = f"- `{dest.name}` — **dropped** (never distilled): {dropped} Retired {today}.\n"
            kind, reason = "dropped", dropped.strip()
        else:
            entry = f"- `{dest.name}` — {line} Distilled {today}.\n"
            kind, reason = "new" if first else "enriched", None
        with readme.open("a", encoding="utf-8") as fh:
            fh.write(entry)
        row = {"retired": rel, "at": utc_timestamp(), "kind": kind, "notes": resolved_notes,
               "reason": reason, "what": line.strip() if line else None,
               "archived_to": dest.relative_to(vault).as_posix(),
               **({"duplicate_of": duplicate_of} if duplicate_of else {})}
        with jsonl_lock(vault / LEDGER):
            append_jsonl(vault / LEDGER, row)

    return {
        "capture": rel,
        "archived_to": dest.relative_to(vault).as_posix(),
        "manifest": readme.relative_to(vault).as_posix(),
        "notes": resolved_notes,
        "stamped": resolved_notes,
        "via": via,
        "mode": "duplicate" if duplicate_of else "dropped" if dropped else "line",
        "kind": kind,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture")
    ap.add_argument("--note", action="append", default=[], dest="notes",
                    help="a note the capture was distilled into or enriched (repeatable; each must pass distill_check)")
    ap.add_argument("--line", help="manifest prose: what became of the capture")
    ap.add_argument("--dropped", help="manifest prose: why it was retired without a note (never for a clip)")
    ap.add_argument("--duplicate-of", help="vault path of the capture or note this one duplicates (any via)")
    args = ap.parse_args()
    vault = require_vault()
    capture = Path(args.capture) if Path(args.capture).is_absolute() else vault / args.capture

    try:
        result = retire(capture, vault, args.notes, args.line, args.dropped, args.duplicate_of)
    except RetireRefused as e:
        print(json.dumps({"error": str(e)}, indent=2))
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
