"""State builders shared by every caller of judge.py: what one note looks like on the wire."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

import judge
from vault_utils import profile_value, read_frontmatter

T = TypeVar("T")

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
    plain list of names), else the shipped starter set. Names are the part after `domain/`.
    The env override `TOOLKIT_OBSIDIAN_DOMAINS` is a string like every env override: either a
    JSON object/array, or a comma-separated list of names."""
    configured = profile_value(vault, "domains", None)
    if isinstance(configured, str) and configured.strip():
        text = configured.strip()
        try:
            configured = json.loads(text) if text[0] in "[{" else [n.strip() for n in text.split(",") if n.strip()]
        except json.JSONDecodeError:
            configured = [n.strip() for n in text.split(",") if n.strip()]
    if isinstance(configured, dict) and configured:
        return {str(k).removeprefix("domain/"): str(v or "") for k, v in configured.items()}
    if isinstance(configured, list) and configured:
        return {str(k).removeprefix("domain/"): "" for k in configured}
    return dict(default)


def in_chunks(items: Sequence[T], size: int, ask: Callable[[Sequence[T], int], dict]) -> dict:
    """Call `ask(chunk, offset)` per chunk of `items` and merge the dicts it returns. A chunk
    the backend refuses for size (judge.StateTooLarge) is split in two and retried, down to a
    single item, which is then dropped: state made of notes or pairs splits cleanly, so this is
    the one place that knows how. [earned: 2026-09-22, first run on a 1,476-note vault, where
    40 real-length notes per request exceeded the backend's input limit twice]"""
    merged: dict = {}
    for start in range(0, len(items), size):
        merged.update(_ask_split(items[start:start + size], start, ask))
    return merged


def _ask_split(chunk: Sequence[T], offset: int, ask: Callable[[Sequence[T], int], dict]) -> dict:
    try:
        return ask(chunk, offset)
    except judge.StateTooLarge:
        if len(chunk) == 1:
            return {}
        mid = len(chunk) // 2
        return _ask_split(chunk[:mid], offset, ask) | _ask_split(chunk[mid:], offset + mid, ask)
