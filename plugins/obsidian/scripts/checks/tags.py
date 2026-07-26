"""Tags check — domain-of-origin taxonomy audit and LLM-assisted classification.

DOMAIN_TAGS below is a *starter* taxonomy, not a fixed schema — every vault accretes its
own. Edit this list (and LEGACY_MIGRATION) to match the domains that actually recur in
your vault; the mechanism (classify into a small closed set, migrate legacy free-form
tags) is the reusable part, not the specific names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from vault_utils import NoModelConfigured, llm_chat

from checks import FixResult, Issue

# ---------------------------------------------------------------------------
# Starter domain taxonomy — replace with your own vault's recurring topics.
# ---------------------------------------------------------------------------

DOMAIN_TAGS = {
    "domain/ai-ml",
    "domain/agent-systems",
    "domain/software-engineering",
    "domain/knowledge-management",
    "domain/productivity",
    "domain/toolkit-meta",
}

DOMAIN_NAMES = {t.replace("domain/", "") for t in DOMAIN_TAGS}

# Legacy free-form tags this vault has already been observed to use, mapped onto the
# taxonomy above. Extend as your own vault's history warrants — this is a migration
# table, not a validation gate.
LEGACY_MIGRATION: dict[str, str] = {
    "ai": "domain/ai-ml",
    "machine-learning": "domain/ai-ml",
    "llm": "domain/ai-ml",
    "agents": "domain/agent-systems",
    "agent": "domain/agent-systems",
    "multi-agent": "domain/agent-systems",
    "architecture": "domain/software-engineering",
    "engineering": "domain/software-engineering",
    "devops": "domain/software-engineering",
    "note-taking": "domain/knowledge-management",
    "knowledge-management": "domain/knowledge-management",
    "pkm": "domain/knowledge-management",
    "productivity": "domain/productivity",
    "focus": "domain/productivity",
    "workflows": "domain/productivity",
}

MAX_DOMAINS = 3
CONTENT_TRUNCATE = 4000


def _build_llm_prompt() -> str:
    domain_list = "\n".join(f"- {name}" for name in sorted(DOMAIN_NAMES))
    return (
        "You are a domain classifier for an Obsidian knowledge vault.\n"
        "Given a note's title and content, identify which topic(s) it belongs to.\n\n"
        f"Valid domains (pick 1-3, ranked by relevance):\n{domain_list}\n\n"
        "Respond with ONLY a JSON object, no markdown fences, no explanation:\n"
        '{"domains": ["<primary>", "<secondary>"]}'
    )


_LLM_SYSTEM_PROMPT = _build_llm_prompt()

# Constrains generation so the model cannot emit prose, markdown fences, or malformed
# JSON — without it, small local models emit unparseable output at a high rate and the
# check silently produces nothing while looking like it ran (verified in v1: 86-93% of
# notes got no tags from an unconstrained call over 14 notes on gemma4:12b/26b).
_DOMAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "domains": {"type": "array", "items": {"type": "string", "enum": sorted(DOMAIN_NAMES)}, "maxItems": MAX_DOMAINS}
    },
    "required": ["domains"],
}


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_llm_response(raw: str) -> list[str]:
    try:
        data = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, ValueError):
        return []
    domains = data.get("domains", [])
    if not isinstance(domains, list):
        return []
    result = []
    for d in domains:
        if isinstance(d, str) and d in DOMAIN_NAMES and len(result) < MAX_DOMAINS:
            result.append(f"domain/{d}")
    return result


def _migrate_legacy_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    domains_added: set[str] = set()
    for tag in tags:
        if tag in LEGACY_MIGRATION:
            domain_tag = LEGACY_MIGRATION[tag]
            if domain_tag not in domains_added:
                result.append(domain_tag)
                domains_added.add(domain_tag)
        elif tag.startswith("domain/"):
            if tag not in domains_added:
                result.append(tag)
                domains_added.add(tag)
        else:
            result.append(tag)
    return result


def audit(note_path: Path, frontmatter: dict, body: str, vault: Path) -> list[Issue]:
    issues: list[Issue] = []
    tags: list[str] = frontmatter.get("tags", [])
    if not isinstance(tags, list):
        return issues

    domain_tags = [t for t in tags if t.startswith("domain/")]
    if not domain_tags:
        issues.append(Issue(note_path, "tags", "warning", "No domain tag found", "Run --fix to classify via LLM"))
    for t in domain_tags:
        if t not in DOMAIN_TAGS:
            issues.append(Issue(note_path, "tags", "warning", f"Non-canonical domain tag: {t}", f"Replace with one of: {', '.join(sorted(DOMAIN_TAGS))}"))
    if len(domain_tags) > MAX_DOMAINS:
        issues.append(Issue(note_path, "tags", "info", f"Domain tag count ({len(domain_tags)}) exceeds max ({MAX_DOMAINS})", "Reduce to most relevant 1-3 domains"))
    for t in tags:
        if t in LEGACY_MIGRATION:
            issues.append(Issue(note_path, "tags", "info", f"Legacy tag '{t}' should migrate to '{LEGACY_MIGRATION[t]}'", "Run --fix to auto-migrate"))
    return issues


def fix(
    note_path: Path, frontmatter: dict, body: str, vault: Path, config: Any = None,
) -> tuple[dict, str, list[FixResult]]:
    fm = dict(frontmatter)
    existing_tags: list[str] = list(fm.get("tags", []))
    results: list[FixResult] = []

    migrated = _migrate_legacy_tags(existing_tags)
    if migrated != existing_tags:
        removed = set(existing_tags) - set(migrated)
        added = set(migrated) - set(existing_tags)
        fm["tags"] = migrated
        existing_tags = migrated
        results.append(FixResult(note_path, "tags", True, f"Migrated legacy tags: removed {removed}, added {added}"))

    if any(t.startswith("domain/") for t in existing_tags):
        return fm, body, results

    title = note_path.stem
    user_content = f"Title: {title}\nDescription: {fm.get('description', '')}\n\nContent:\n{body[:CONTENT_TRUNCATE]}"

    try:
        raw = llm_chat(_LLM_SYSTEM_PROMPT, user_content, vault=vault, max_tokens=100, response_schema=_DOMAIN_SCHEMA)
        new_domains = _parse_llm_response(raw)
    except NoModelConfigured:
        results.append(FixResult(note_path, "tags", False, "SKIPPED — no inference_model configured (see profile.example.md)"))
        return fm, body, results
    except (RuntimeError, ValueError) as exc:
        results.append(FixResult(note_path, "tags", False, f"LLM classification failed: {exc}"))
        return fm, body, results

    if new_domains:
        fm["tags"] = existing_tags + [d for d in new_domains if d not in existing_tags]
        results.append(FixResult(note_path, "tags", True, f"LLM classified: {', '.join(new_domains)}"))
    else:
        results.append(FixResult(note_path, "tags", False, "LLM returned no valid domains"))

    return fm, body, results
