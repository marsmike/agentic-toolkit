"""The owner's own clips, read straight from the vault's files — never through the readwise
plugin (`AGENTS.md` "Hard rules": plugins depend on core/contract only, never a sibling plugin).

A clip is any note whose frontmatter says `via: clip`: live in `01_Capture/`, or archived under
`05_Archive/*/*--FULLCAPTURE.md` once distilled. Dated by `saved_at` (falling back to `created`
for the rare clip that predates the field). This is what the owner chose to read himself, with no
threshold or feed gate between him and the capture — a signal `00_Memory/radar/state.jsonl` (feed
items the radar judged) does not carry at all. [earned: 2026-09-24, owner: ~15 clips about "Jev"
in one week surfaced nothing in `emerging_terms`, because a clip never entered radar state]

Two callers: `reports.emerging_terms` (title words only) and `scout.py` (also the body, for the
links a clip's own content carries — a video or article's source, or a research note's citations).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vault_utils import contained, read_frontmatter

_H1 = re.compile(r"^#\s+(.+)$", re.M)


@dataclass(frozen=True)
class Clip:
    path: str      # vault-relative
    title: str
    source: str    # frontmatter `source`, "" if none
    saved_at: str  # ISO date, 10 chars
    body: str      # markdown body, frontmatter stripped (for link mining; empty is fine unused)


def _title(body: str, path: Path) -> str:
    m = _H1.search(body)
    return m.group(1).strip() if m else path.stem


def _candidate_paths(vault: Path) -> list[Path]:
    live = sorted((vault / "01_Capture").glob("*.md")) if (vault / "01_Capture").is_dir() else []
    archived = sorted((vault / "05_Archive").glob("*/*--FULLCAPTURE.md")) if (vault / "05_Archive").is_dir() else []
    return contained(live + archived, vault)  # a link out of the vault is not a clip (Copilot review of #28)


def load(vault: Path, since: date) -> list[Clip]:
    """Every clip (`via: clip`) saved at or after `since`, oldest first."""
    out: list[Clip] = []
    for path in _candidate_paths(vault):
        try:
            fm, body = read_frontmatter(path)
        except OSError:
            continue
        if str(fm.get("via") or "").strip().lower() != "clip":
            continue
        saved = str(fm.get("saved_at") or fm.get("created") or "")[:10]
        try:
            when = date.fromisoformat(saved)
        except ValueError:
            continue
        if when < since:
            continue
        out.append(Clip(path=path.relative_to(vault).as_posix(), title=_title(body, path),
                         source=str(fm.get("source") or ""), saved_at=saved, body=body))
    return sorted(out, key=lambda c: c.saved_at)
