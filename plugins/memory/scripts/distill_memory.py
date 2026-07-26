"""distill-memory's scriptable core: idempotent note write/update, and the
undistilled-session listing that feeds skills/distill-memory's Phase 1 (analyze).

The judgment work — reading a session's transcript pointer, classifying a candidate
learning as sop/warning/fact, proposing a slug/title/body, deciding new-vs-update — is
done by the invoking agent per skills/distill-memory/references/workflow.md; it isn't
scriptable and isn't attempted here. What *is* scriptable, and is exercised directly by
evals/eval_distill_idempotent.py, is the write step below: given a confirmed
candidate, create-or-update its note under 00_Memory/notes/ without ever duplicating
it — the part of "distill" that must behave identically no matter who or what proposed
the candidate.
"""
from __future__ import annotations

import time
from pathlib import Path

import memory_vault as mv

VALID_KINDS = ("sop", "warning", "fact")


def list_undistilled_sessions(vault: Path) -> list[Path]:
    """Session records under 00_Memory/sessions/ not yet marked `distilled: true`."""
    sessions_dir = Path(vault) / "00_Memory" / "sessions"
    if not sessions_dir.is_dir():
        return []
    undistilled = []
    for path in sorted(sessions_dir.glob("*.md")):
        fm, _ = mv.read_note(path)
        if not fm.get("distilled"):
            undistilled.append(path)
    return undistilled


def mark_session_distilled(session_path: Path) -> None:
    fm, body = mv.read_note(session_path)
    fm["distilled"] = True
    mv.write_note(session_path, fm, body)


def write_memory_note(
    vault: Path,
    kind: str,
    slug: str,
    title: str,
    body_text: str,
    source: str,
    tags: list[str] | None = None,
    today: str | None = None,
) -> tuple[Path, bool]:
    """Create-or-update `00_Memory/notes/<slug>.md`.

    Idempotent by (slug, source): calling this again with a `source` already recorded
    on that note is a no-op — the file is left byte-for-byte unchanged, not merely
    "not duplicated". A genuinely new `source` for an existing slug appends to
    `sources` and bumps `updated`, still writing to the same path.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")
    today = today or time.strftime("%Y-%m-%d")
    notes_dir = Path(vault) / "00_Memory" / "notes"
    dest = notes_dir / f"{slug}.md"

    if dest.is_file():
        fm, existing_body = mv.read_note(dest)
        sources = fm.get("sources") or []
        if source in sources:
            return dest, False  # already recorded — true no-op
        fm["sources"] = [*sources, source]
        fm["updated"] = today
        mv.write_note(dest, fm, existing_body)
        return dest, False

    resolved_tags = tags if tags is not None else mv.profile_value(
        vault, "default_tags", ["agent/memory", "domain/toolkit-meta"]
    )
    frontmatter = {
        "description": title,
        "kind": kind,
        "status": "active",
        "created": today,
        "updated": today,
        "sources": [source],
        "tags": resolved_tags,
    }
    mv.write_note(dest, frontmatter, body_text)
    return dest, True
