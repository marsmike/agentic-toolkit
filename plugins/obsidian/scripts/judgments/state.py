"""State builders shared by every caller of judge.py: what one note looks like on the wire."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vault_utils import profile_value, read_frontmatter

NOTE_CHARS = 1500  # description + this much body is enough to tell what a note is about


def note_payload(path: Path, vault: Path, chars: int = NOTE_CHARS) -> dict[str, Any]:
    fm, body = read_frontmatter(path)
    return {
        "title": path.stem,
        "path": path.relative_to(vault).as_posix(),
        "description": str(fm.get("description") or ""),
        "source": str(fm.get("source") or ""),
        "body_head": body.strip()[:chars],
    }


def domain_glosses(vault: Path, default: dict[str, str]) -> dict[str, str]:
    """The vault's domain taxonomy: profile key `domains` ({name: one-line meaning}, or a
    plain list of names), else the shipped starter set. Names are the part after `domain/`."""
    configured = profile_value(vault, "domains", None)
    if isinstance(configured, dict) and configured:
        return {str(k).removeprefix("domain/"): str(v or "") for k, v in configured.items()}
    if isinstance(configured, list) and configured:
        return {str(k).removeprefix("domain/"): "" for k in configured}
    return dict(default)
