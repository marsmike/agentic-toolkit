"""Links check — broken wikilink audit and fuzzy/LLM-assisted fix."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vault_utils import EXCLUDE_DIRS, NoModelConfigured, llm_chat

from checks import FixResult, Issue

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

IGNORE_PATTERNS = [
    re.compile(r"\.png$|\.jpg$|\.jpeg$|\.gif$|\.svg$|\.webp$|\.pdf$", re.IGNORECASE),
    re.compile(r"/$"),           # folder links like [[02_Projects/]]
    re.compile(r"^[a-z]+$"),     # bare lowercase words like [[orange]], [[blue]]
]

CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```|`[^`\n]+`", re.MULTILINE)

CONTENT_TRUNCATE = 4000

LINK_RESOLVE_PROMPT = """You resolve broken wikilinks in a knowledge vault.
Given a broken link and its surrounding context, pick the best matching note from the candidate list.

Rules:
- If a candidate clearly matches the broken link's intent, return ONLY the exact candidate name.
- If no candidate is a good match, return exactly: none
- No explanation, no markdown, just the candidate name or "none"."""


def _should_ignore(target: str) -> bool:
    return any(p.search(target) for p in IGNORE_PATTERNS)


def _strip_code_blocks(text: str) -> str:
    return CODE_BLOCK_RE.sub("", text)


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


_NEVER_LINK_TARGETS = {"00_Memory", "01_Capture", "05_Archive"}


def _build_note_index(vault: Path) -> set[str]:
    """Every note stem a wikilink could validly resolve to.

    Deliberately broader than discover_notes()'s active-content-only scope: a wikilink
    check asks "does this target exist anywhere a link is allowed to point", which
    includes root-level and Config/ notes (e.g. a persona note, a profile note) — not
    just 02_Projects/03_Areas/04_Resources. contract/VAULT_SCHEMA.md's active-content
    filter governs search/enrichment/generated-index scope, not link-target existence.
    Still excludes 00_Memory/01_Capture/05_Archive: active content must never link there
    (contract/VAULT_SCHEMA.md), so a target that only exists in one of those folders is
    not a valid resolution target either.
    """
    stems: set[str] = set()
    for md in vault.rglob("*.md"):
        rel = md.relative_to(vault)
        if rel.parts and rel.parts[0] in _NEVER_LINK_TARGETS:
            continue
        if any(part in EXCLUDE_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        stems.add(md.stem)
    return stems


def _get_context_around(body: str, target: str, window: int = 200) -> str:
    pos = body.find(f"[[{target}]]")
    if pos == -1:
        pos = body.find(target)
    if pos == -1:
        return body[:window]
    start = max(0, pos - window)
    end = min(len(body), pos + len(target) + window)
    return body[start:end]


def _llm_resolve(target: str, context: str, candidates: list[str], vault: Path) -> str | None:
    """Ask the configured LLM to pick the best match from candidates. Returns name or None."""
    target_words = set(target.lower().replace("-", " ").replace("_", " ").split())
    scored = sorted(
        candidates,
        key=lambda c: -len(target_words & set(c.lower().replace("-", " ").replace("_", " ").split())),
    )
    top_candidates = scored[:30]
    if not top_candidates:
        return None

    candidate_list = "\n".join(f"- {c}" for c in top_candidates)
    user_msg = f"Broken link: [[{target}]]\n\nContext:\n{context}\n\nCandidate notes:\n{candidate_list}"

    try:
        result = llm_chat(LINK_RESOLVE_PROMPT, user_msg, vault=vault, temperature=0.1, max_tokens=100)
    except (NoModelConfigured, RuntimeError):
        return None

    result = result.strip().strip("[]")
    if result.lower() == "none":
        return None
    if result in top_candidates:
        return result
    for c in top_candidates:
        if c.lower() == result.lower():
            return c
    return None


def audit(note_path: Path, frontmatter: dict, body: str, vault: Path) -> list[Issue]:
    """Find broken wikilinks and suggest corrections via fuzzy matching."""
    issues: list[Issue] = []
    index = _build_note_index(vault)
    prose = _strip_code_blocks(body)

    for match in WIKILINK_RE.finditer(prose):
        target = match.group(1).strip()
        if _should_ignore(target):
            continue
        stem = target.rsplit("/", 1)[-1]
        if stem in index:
            continue

        best_match, best_dist = None, float("inf")
        for candidate in sorted(index):
            d = _levenshtein(stem, candidate)
            if d < best_dist:
                best_dist, best_match = d, candidate

        proposed = (
            f"Replace [[{target}]] with [[{best_match}]] (distance {best_dist})"
            if best_dist <= 2 and best_match is not None
            else "No close match found in vault"
        )
        issues.append(Issue(
            note=note_path, check="links", severity="warning" if best_dist <= 2 else "error",
            description=f"Broken wikilink [[{target}]]", proposed_fix=proposed,
        ))
    return issues


def fix(
    note_path: Path, frontmatter: dict, body: str, vault: Path, config: Any = None,
) -> tuple[dict, str, list[FixResult]]:
    """Fix broken links: Levenshtein for typos, LLM for semantic resolution."""
    results: list[FixResult] = []
    index_list = sorted(_build_note_index(vault))
    new_body = body
    prose = _strip_code_blocks(body)

    for match in WIKILINK_RE.finditer(prose):
        target = match.group(1).strip()
        if _should_ignore(target):
            continue
        stem = target.rsplit("/", 1)[-1]
        if stem in index_list:
            continue

        best_match, best_dist = None, float("inf")
        for candidate in index_list:
            d = _levenshtein(stem, candidate)
            if d < best_dist:
                best_dist, best_match = d, candidate

        resolved, method = None, ""
        if best_dist <= 1 and best_match is not None:
            resolved, method = best_match, f"Levenshtein distance {best_dist}"
        else:
            context = _get_context_around(body, target)
            llm_pick = _llm_resolve(target, context, index_list, vault)
            if llm_pick:
                resolved, method = llm_pick, "LLM"

        if resolved:
            old_link = match.group(0)
            alias_match = re.match(r"\[\[([^\]|]+)\|([^\]]+)\]\]", old_link)
            new_link = f"[[{resolved}|{alias_match.group(2)}]]" if alias_match else f"[[{resolved}]]"
            new_body = new_body.replace(old_link, new_link)
            results.append(FixResult(note_path, "links", True, f"Replaced [[{target}]] with [[{resolved}]] ({method})"))
        else:
            results.append(FixResult(note_path, "links", False, f"No match for [[{target}]]"))

    return frontmatter, new_body, results
