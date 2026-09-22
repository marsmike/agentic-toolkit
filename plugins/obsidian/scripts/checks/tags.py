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

from judgments.state import domain_glosses
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


def domain_names(vault: Path) -> set[str]:
    """The vault's own taxonomy if its profile sets `domains` (see profile.example.md),
    else the starter set above. Every check below reads the taxonomy through this."""
    return set(domain_glosses(vault, dict.fromkeys(DOMAIN_NAMES, "")))

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


def _build_llm_prompt(names: set[str]) -> str:
    domain_list = "\n".join(f"- {name}" for name in sorted(names))
    return (
        "You are a domain classifier for an Obsidian knowledge vault.\n"
        "Given a note's title and content, identify which topic(s) it belongs to.\n\n"
        f"Valid domains (pick 1-3, ranked by relevance):\n{domain_list}\n\n"
        "Respond with ONLY a JSON object, no markdown fences, no explanation:\n"
        '{"domains": ["<primary>", "<secondary>"]}'
    )



# Constrains generation so the model cannot emit prose, markdown fences, or malformed
# JSON — without it, small local models emit unparseable output at a high rate and the
# check silently produces nothing while looking like it ran (verified in v1: 86-93% of
# notes got no tags from an unconstrained call over 14 notes on gemma4:12b/26b).
def _domain_schema(names: set[str]) -> dict:
    return {
        "type": "object",
        "properties": {"domains": {"type": "array", "items": {"type": "string", "enum": sorted(names)}, "maxItems": MAX_DOMAINS}},
        "required": ["domains"],
    }


def _strip_code_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_llm_response(raw: str, names: set[str] | None = None) -> list[str]:
    names = DOMAIN_NAMES if names is None else names
    try:
        data = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, ValueError):
        return []
    domains = data.get("domains", [])
    if not isinstance(domains, list):
        return []
    result = []
    for d in domains:
        if isinstance(d, str) and d in names and len(result) < MAX_DOMAINS:
            result.append(f"domain/{d}")
    return result


def _migrate_legacy_tags(tags: list[str], canonical: set[str] | None = None) -> list[str]:
    """Map legacy free-form tags onto canonical domain tags. With a vault taxonomy
    (`canonical`), a legacy tag whose starter target is not in it is left alone rather than
    turned into a tag the vault does not use."""
    result: list[str] = []
    domains_added: set[str] = set()
    for tag in tags:
        if tag in LEGACY_MIGRATION and (canonical is None or LEGACY_MIGRATION[tag] in canonical):
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
    canonical = {f"domain/{n}" for n in domain_names(vault)}
    for t in domain_tags:
        if t not in canonical:
            issues.append(Issue(note_path, "tags", "warning", f"Non-canonical domain tag: {t}", f"Replace with one of: {', '.join(sorted(canonical))}"))
    if len(domain_tags) > MAX_DOMAINS:
        issues.append(Issue(note_path, "tags", "info", f"Domain tag count ({len(domain_tags)}) exceeds max ({MAX_DOMAINS})", "Reduce to most relevant 1-3 domains"))
    for t in tags:
        # Matches _migrate_legacy_tags()'s own guard: a legacy tag whose starter-taxonomy
        # target the vault's own `domains` taxonomy doesn't carry is not something --fix will
        # touch, so don't tell the user it will.
        if t in LEGACY_MIGRATION and LEGACY_MIGRATION[t] in canonical:
            issues.append(Issue(note_path, "tags", "info", f"Legacy tag '{t}' should migrate to '{LEGACY_MIGRATION[t]}'", "Run --fix to auto-migrate"))
    return issues


def fix(
    note_path: Path, frontmatter: dict, body: str, vault: Path, config: Any = None,
) -> tuple[dict, str, list[FixResult]]:
    fm = dict(frontmatter)
    existing_tags: list[str] = list(fm.get("tags", []))
    results: list[FixResult] = []

    names = domain_names(vault)
    canonical = {f"domain/{n}" for n in names}
    migrated = _migrate_legacy_tags(existing_tags, canonical)
    if migrated != existing_tags:
        removed = set(existing_tags) - set(migrated)
        added = set(migrated) - set(existing_tags)
        fm["tags"] = migrated
        existing_tags = migrated
        results.append(FixResult(note_path, "tags", True, f"Migrated legacy tags: removed {removed}, added {added}"))

    if any(t in canonical for t in existing_tags):
        return fm, body, results

    title = note_path.stem
    user_content = f"Title: {title}\nDescription: {fm.get('description', '')}\n\nContent:\n{body[:CONTENT_TRUNCATE]}"

    try:
        raw = llm_chat(_build_llm_prompt(names), user_content, vault=vault, max_tokens=100, response_schema=_domain_schema(names))
        new_domains = _parse_llm_response(raw, names)
    except NoModelConfigured:
        results.append(FixResult(note_path, "tags", False, "SKIPPED — no inference_model configured (see profile.example.md)"))
        return fm, body, results
    except (RuntimeError, ValueError) as exc:
        results.append(FixResult(note_path, "tags", False, f"LLM classification failed: {exc}"))
        return fm, body, results

    if new_domains:
        # Every existing_tags entry here failed the canonical check above, so any domain/*
        # among them is stale (predates the vault's current taxonomy) — drop it rather than
        # pile the fresh classification on top: keeping it both left an unrecognized tag in
        # place and let the note's domain-tag count grow past MAX_DOMAINS on every re-run.
        kept = [t for t in existing_tags if not t.startswith("domain/")]
        fm["tags"] = kept + [d for d in new_domains if d not in kept]
        results.append(FixResult(note_path, "tags", True, f"LLM classified: {', '.join(new_domains)}"))
    else:
        results.append(FixResult(note_path, "tags", False, "LLM returned no valid domains"))

    return fm, body, results
