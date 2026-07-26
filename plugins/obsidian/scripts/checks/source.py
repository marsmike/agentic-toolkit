"""Source check — audit and fix for missing *Source: ...* lines in distilled notes."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vault_utils import NoModelConfigured, llm_chat

from checks import FixResult, Issue

SOURCE_LINE_RE = re.compile(r"^\*Source:\s*.+\*\s*$", re.MULTILINE)
H1_RE = re.compile(r"^# .+$", re.MULTILINE)
CONTENT_TRUNCATE = 4000

SYSTEM_PROMPT = (
    "Extract the source URL or citation from this note.\n"
    "If the note references an external article, paper, tool, or website, return ONLY the URL.\n"
    "If multiple URLs exist, return the most likely original source.\n"
    "If no source is identifiable, return exactly: none\n"
    "No explanation, no markdown, just the URL or \"none\"."
)

NONE_PLACEHOLDER = "(none — pre-existing vault note)"


def audit(note_path: Path, frontmatter: dict, body: str, vault: Path) -> list[Issue]:
    """Audit distilled notes for a missing *Source: ...* line."""
    if frontmatter.get("status") != "distilled":
        return []
    if SOURCE_LINE_RE.search(body):
        return []
    return [Issue(
        note=note_path, check="source", severity="warning",
        description="Distilled note missing *Source: ...* line in body",
        proposed_fix="Insert *Source: <url>* after the H1 heading (LLM-assisted)",
    )]


def fix(
    note_path: Path, frontmatter: dict, body: str, vault: Path, config: Any = None,
) -> tuple[dict, str, list[FixResult]]:
    """Fix missing source line in distilled notes. Returns (new_fm, new_body, results)."""
    fm = dict(frontmatter)
    results: list[FixResult] = []

    if fm.get("status") != "distilled" or SOURCE_LINE_RE.search(body):
        return fm, body, results

    try:
        source_value = llm_chat(SYSTEM_PROMPT, body[:CONTENT_TRUNCATE], vault=vault).strip()
    except NoModelConfigured:
        results.append(FixResult(note_path, "source", False, "SKIPPED — no inference_model configured (see profile.example.md)"))
        return fm, body, results
    except RuntimeError as exc:
        results.append(FixResult(note_path, "source", False, f"LLM call failed: {exc}"))
        return fm, body, results

    if source_value.lower() == "none":
        source_value = NONE_PLACEHOLDER
    source_line = f"*Source: {source_value}*"

    h1_match = H1_RE.search(body)
    if h1_match:
        insert_pos = h1_match.end()
        new_body = body[:insert_pos] + "\n\n" + source_line + body[insert_pos:]
    else:
        new_body = source_line + "\n\n" + body

    if not fm.get("source"):
        fm["source"] = source_value

    results.append(FixResult(note_path, "source", True, f"Inserted source line: {source_value}"))
    return fm, new_body, results
