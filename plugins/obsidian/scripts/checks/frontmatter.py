"""Frontmatter check — rule-based audit, LLM-assisted fix for vault note frontmatter."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from vault_utils import NoModelConfigured, llm_chat

from checks import FixResult, Issue

# Lifecycle values per contract/VAULT_SCHEMA.md. "capture" is deliberately absent — a note
# under 01_Capture/ is out of scope for this check (discover_notes never walks 01_Capture).
VALID_STATUSES = {"draft", "review", "distilled", "active", "archived"}
CONTENT_TRUNCATE = 4000

DESCRIPTION_PROMPT = """Write a one-line description (max 15 words) for this vault note.
The description should capture what this note IS, not what it contains.
Lead with the subject. No preamble, no quotes, no markdown. Just the description.

Examples:
- "Rust vector type fundamentals from the Rust Book"
- "Weekly review template for active projects"
- "AI safety alignment principles and value learning overview"
- "Home network topology and VLAN plan for the lab migration"
"""

STATUS_PROMPT = """Classify this vault note's lifecycle status. Return ONLY one of these words:
- "distilled" — a processed knowledge note with clear structure, citations, and insights
- "active" — a working document, reference, or ongoing project/area note
- "draft" — written but not yet reviewed
- "archived" — outdated or completed material no longer actively used

No explanation, just the single word."""


def audit(note_path: Path, frontmatter: dict, body: str, vault: Path) -> list[Issue]:
    """Audit frontmatter for missing or invalid fields."""
    issues: list[Issue] = []

    status = frontmatter.get("status")
    if status is None:
        issues.append(Issue(
            note=note_path, check="frontmatter", severity="error",
            description="Missing status field", proposed_fix="Add status: active",
        ))
    elif status not in VALID_STATUSES:
        issues.append(Issue(
            note=note_path, check="frontmatter", severity="error",
            description=f"Invalid status '{status}' (valid: {', '.join(sorted(VALID_STATUSES))})",
            proposed_fix="Change status to active",
        ))

    tags = frontmatter.get("tags")
    if tags is None:
        issues.append(Issue(
            note=note_path, check="frontmatter", severity="warning",
            description="Missing tags field", proposed_fix="Add tags: []",
        ))
    elif not isinstance(tags, list):
        issues.append(Issue(
            note=note_path, check="frontmatter", severity="warning",
            description="Tags should be a list, not a string",
            proposed_fix="Convert comma-separated tags string to list",
        ))

    if not frontmatter.get("description"):
        issues.append(Issue(
            note=note_path, check="frontmatter", severity="info",
            description="Missing description field", proposed_fix="Generate description via LLM",
        ))

    if status == "distilled":
        if not frontmatter.get("source"):
            issues.append(Issue(
                note=note_path, check="frontmatter", severity="error",
                description="Distilled note missing source field",
                proposed_fix="Add source: (none — <context>) or the real URL",
            ))
        if not frontmatter.get("processed_date"):
            issues.append(Issue(
                note=note_path, check="frontmatter", severity="error",
                description="Distilled note missing processed_date field",
                proposed_fix="Add processed_date",
            ))

    return issues


def fix(
    note_path: Path, frontmatter: dict, body: str, vault: Path, config: Any = None,
) -> tuple[dict, str, list[FixResult]]:
    """Fix frontmatter issues. Returns (new_frontmatter, new_body, results).

    `config` is accepted for interface compatibility with vault_normalize's dispatch but
    unused — LLM configuration is read from the vault's profile via vault_utils.
    """
    fm = dict(frontmatter)
    results: list[FixResult] = []

    status = fm.get("status")
    if status is None or status not in VALID_STATUSES:
        old_status = status
        new_status = "active"  # honest fallback — never guess "distilled" without evidence
        if body.strip():
            try:
                result = llm_chat(
                    STATUS_PROMPT,
                    f"Note title: {note_path.stem}\n\nNote content:\n\n{body[:CONTENT_TRUNCATE]}",
                    vault=vault, temperature=0.1, max_tokens=20,
                )
                candidate = result.strip().lower().strip("\"'")
                if candidate in VALID_STATUSES:
                    new_status = candidate
            except NoModelConfigured:
                pass  # fall through to the "active" default — no crash, no guess beyond it
            except RuntimeError:
                pass
        fm["status"] = new_status
        via = "" if new_status == "active" and old_status is None else " (via LLM)"
        if old_status is None:
            results.append(FixResult(note_path, "frontmatter", True, f"Added status: {new_status}{via}"))
        else:
            results.append(FixResult(note_path, "frontmatter", True, f"Changed invalid status '{old_status}' to {new_status}{via}"))

    tags = fm.get("tags")
    if tags is None:
        fm["tags"] = []
        results.append(FixResult(note_path, "frontmatter", True, "Added missing tags: []"))
    elif isinstance(tags, str):
        fm["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        results.append(FixResult(note_path, "frontmatter", True, "Converted tags string to list"))

    if not fm.get("description") and body.strip():
        try:
            desc = llm_chat(
                DESCRIPTION_PROMPT,
                f"Note title: {note_path.stem}\n\nNote content:\n\n{body[:CONTENT_TRUNCATE]}",
                vault=vault, temperature=0.2, max_tokens=60,
            )
            desc = desc.strip().strip("\"'").rstrip(".")
            fm["description"] = desc
            results.append(FixResult(note_path, "frontmatter", True, f"Added description: {desc}"))
        except NoModelConfigured:
            results.append(FixResult(note_path, "frontmatter", False, "SKIPPED description — no inference_model configured (see profile.example.md)"))
        except RuntimeError as exc:
            results.append(FixResult(note_path, "frontmatter", False, f"LLM description generation failed: {exc}"))

    # Distilled notes need source and processed_date. Never write "unknown" — it reads as
    # filled while carrying no information, so the gap stops being reported and is never
    # revisited. For processed_date it is actively harmful: "unknown" doesn't parse as a
    # date, so the note is permanently excluded from any future --since selection.
    if fm.get("status") == "distilled":
        if not fm.get("source"):
            fm["source"] = "(none — not recorded at distill time)"
            results.append(FixResult(note_path, "frontmatter", True, "Added source: (none — not recorded at distill time)"))
        if not fm.get("processed_date"):
            today = _dt.date.today().isoformat()
            fm["processed_date"] = today
            results.append(FixResult(note_path, "frontmatter", True, f"Added processed_date: {today}"))

    return fm, body, results
