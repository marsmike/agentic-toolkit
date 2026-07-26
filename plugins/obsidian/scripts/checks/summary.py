"""Summary check — audit and fix bootstrap-quality (⚙-marked) Index.md summaries via LLM."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vault_utils import (
    COG,
    ENTRY_RE,
    NoModelConfigured,
    atomic_write,
    llm_chat,
    parse_existing_index,
)

from checks import FixResult, Issue

MIN_WORDS = 5
MAX_WORDS = 25
CONTENT_TRUNCATE = 4000

SYSTEM_PROMPT = (
    "You write index entries for a personal knowledge vault. Each entry is ONE sentence\n"
    "(max 20 words) that answers: 'what is this note about, and why would I open it?'\n"
    "\n"
    "Rules:\n"
    "- Lead with the subject/topic, not a meta-description. Good: 'Home network topology\n"
    "  and VLAN plan...'. Bad: 'This note describes...', 'A guide that explains...'.\n"
    "- Include the concrete subject (tool name, domain, technique) — not just abstract\n"
    "  categories.\n"
    "- Prefer the note's primary purpose over incidental details.\n"
    "- No preamble, no markdown, no quotes. Just the sentence."
)


def _get_entry_for_note(note_path: Path, vault: Path) -> tuple[str, str, str] | None:
    """Find a note's Index.md entry. Returns (relative_key, summary, markers) or None."""
    entries = parse_existing_index(vault / "Index.md")
    try:
        rel_key = note_path.relative_to(vault).with_suffix("").as_posix()
    except ValueError:
        return None
    if rel_key in entries:
        summary, markers = entries[rel_key]
        return rel_key, summary, markers
    return None


def audit(note_path: Path, frontmatter: dict, body: str, vault: Path) -> list[Issue]:
    """Flag ⚙-marked (bootstrap-quality) summaries that are too short or too long."""
    issues: list[Issue] = []
    entry = _get_entry_for_note(note_path, vault)
    if entry is None:
        return issues
    _rel_key, summary, markers = entry
    if COG not in markers:
        return issues

    word_count = len(summary.split())
    if word_count < MIN_WORDS:
        issues.append(Issue(note_path, "summary", "warning", f"Summary too short ({word_count} words, min {MIN_WORDS})", "Regenerate summary via LLM"))
    if word_count > MAX_WORDS:
        issues.append(Issue(note_path, "summary", "warning", f"Summary too long ({word_count} words, max {MAX_WORDS})", "Regenerate summary via LLM"))
    return issues


def fix(
    note_path: Path, frontmatter: dict, body: str, vault: Path, config: Any = None,
) -> tuple[dict, str, list[FixResult]]:
    """Regenerate a bootstrap summary via LLM and update Index.md directly.

    Frontmatter and body are returned unchanged — this check only modifies Index.md.
    """
    results: list[FixResult] = []
    entry = _get_entry_for_note(note_path, vault)
    if entry is None:
        return frontmatter, body, results

    rel_key, old_summary, markers = entry
    if COG not in markers:
        return frontmatter, body, results

    word_count = len(old_summary.split())
    if MIN_WORDS <= word_count <= MAX_WORDS:
        return frontmatter, body, results

    try:
        note_content = note_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        results.append(FixResult(note_path, "summary", False, f"Could not read note: {exc}"))
        return frontmatter, body, results

    try:
        new_summary = llm_chat(SYSTEM_PROMPT, f"Note content:\n\n{note_content[:CONTENT_TRUNCATE]}", vault=vault, max_tokens=80)
    except NoModelConfigured:
        results.append(FixResult(note_path, "summary", False, "SKIPPED — no inference_model configured (see profile.example.md)"))
        return frontmatter, body, results
    except RuntimeError as exc:
        results.append(FixResult(note_path, "summary", False, f"LLM summary generation failed: {exc}"))
        return frontmatter, body, results

    index_path = vault / "Index.md"
    index_text = index_path.read_text(encoding="utf-8", errors="replace")
    new_lines, replaced = [], False
    for line in index_text.splitlines():
        m = ENTRY_RE.match(line)
        if m and m.group(1).strip() == rel_key:
            alias = f"|{m.group(2)}" if m.group(2) else ""
            suffix = f" {markers}" if markers else ""
            line = f"- [[{rel_key}{alias}]] — {new_summary}{suffix}"
            replaced = True
        new_lines.append(line)

    if replaced:
        atomic_write(index_path, "\n".join(new_lines) + "\n")
        results.append(FixResult(note_path, "summary", True, f"Regenerated summary: '{old_summary}' -> '{new_summary}'"))
    else:
        results.append(FixResult(note_path, "summary", False, "Could not find entry in Index.md for replacement"))
    return frontmatter, body, results
