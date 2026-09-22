"""Links check — broken wikilink audit and fuzzy/LLM-assisted fix."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import judge
from judgments import questions as Q
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


# Policy for the typed-judgment path, per backend: apply only above `apply`, propose above `propose`.
LINK_POLICY = {"jev": {"apply": 0.80, "propose": 0.50, "min_margin": 0.30}}
CANDIDATES_PER_LINK = 30


def _shortlist(target: str, candidates: list[str]) -> list[str]:
    """Cheap blocking: name-token overlap first, then edit distance, so the judge sees a
    list the author's note is likely on."""
    target_words = set(target.lower().replace("-", " ").replace("_", " ").split())
    scored = sorted(
        candidates,
        key=lambda c: (-len(target_words & set(c.lower().replace("-", " ").replace("_", " ").split())), _levenshtein(target[:40], c[:40])),
    )
    return scored[:CANDIDATES_PER_LINK]


def judge_resolve(links: list[dict], candidates: list[str], vault: Path) -> list[dict | None]:
    """One request per note: for each broken link {target, context} a Choice over its shortlist
    plus `none`. Returns per link {pick, p, margin, label: apply|propose|none} or None."""
    if not links or not judge.available(vault):
        return [None] * len(links)
    state, questions = {"links": {}}, {}
    for i, link in enumerate(links, start=1):
        lid = f"L{i:02d}"
        # A candidate literally named "none" would collide with the sentinel "no match" key
        # below (the dict-literal's own "none" wins the merge) and become unreachable as a
        # pick; excluded here rather than risk that — the Levenshtein/LLM paths still cover it.
        short = [c for c in _shortlist(link["target"], candidates) if c != "none"]
        if not short:
            continue
        state["links"][lid] = {"text": link["target"], "context": link["context"][:500], "candidates": short}
        q = Q.link_target(lid)
        questions[f"link_{lid}"] = judge.Question("choice", q.instructions, {**{c: None for c in short}, "none": "no candidate is the note the author meant"})
    if not questions:
        return [None] * len(links)
    try:
        answers, usage = judge.judge(vault, state, questions)
        policy = judge.policy_for(LINK_POLICY, usage.backend)
    except (judge.JudgmentUnavailable, judge.JudgmentFailed):
        return [None] * len(links)
    out: list[dict | None] = []
    for i in range(1, len(links) + 1):
        a = answers.get(f"link_L{i:02d}")
        if a is None:
            # The backend answered other links in this batch but skipped this one (a malformed
            # per-question response) — not the same as it confidently saying "none of these"
            # matched. Leave it unresolved here, not "resolved to no match", so fix() still
            # falls back to _llm_resolve() for it instead of silently giving up.
            out.append(None)
            continue
        if a.top == "none":
            out.append({"pick": None, "p": round(a.probs.get("none", 0.0), 3), "label": "none"})
            continue
        p, margin = a.probs[a.top], a.margin()
        label = "apply" if p >= policy["apply"] and margin >= policy["min_margin"] else "propose" if p >= policy["propose"] else "none"
        out.append({"pick": a.top if label != "none" else None, "p": round(p, 3), "margin": round(margin, 3), "label": label})
    return out


def _llm_resolve(target: str, context: str, candidates: list[str], vault: Path) -> str | None:
    """Ask the configured LLM to pick the best match from candidates. Returns name or None."""
    top_candidates = _shortlist(target, candidates)
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
    """Find broken wikilinks and suggest corrections: fuzzy matching, plus a typed judgment
    over each link's shortlist when a judgment backend is configured (report-only here)."""
    issues = _audit_plain(note_path, frontmatter, body, vault)
    broken = [i for i in issues if i.description.startswith("Broken wikilink")]
    if not broken or not judge.available(vault):
        return issues
    index_list = sorted(_build_note_index(vault))
    targets = [i.description.split("[[", 1)[1].rsplit("]]", 1)[0] for i in broken]
    links = [{"target": t, "context": _get_context_around(body, t)} for t in targets]
    for issue, verdict in zip(broken, judge_resolve(links, index_list, vault), strict=True):
        if verdict and verdict.get("pick"):
            issue.proposed_fix = f"{verdict['label']}: [[{verdict['pick']}]] (p={verdict['p']}, judged)"
    return issues


def _audit_plain(note_path: Path, frontmatter: dict, body: str, vault: Path) -> list[Issue]:
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

    broken = []
    for match in WIKILINK_RE.finditer(prose):
        target = match.group(1).strip()
        if not _should_ignore(target) and target.rsplit("/", 1)[-1] not in index_list:
            broken.append({"match": match, "target": target, "context": _get_context_around(body, target)})
    verdicts = judge_resolve(broken, index_list, vault) if judge.available(vault) else [None] * len(broken)

    for link, verdict in zip(broken, verdicts, strict=True):
        match, target = link["match"], link["target"]
        stem = target.rsplit("/", 1)[-1]

        best_match, best_dist = None, float("inf")
        for candidate in index_list:
            d = _levenshtein(stem, candidate)
            if d < best_dist:
                best_dist, best_match = d, candidate

        resolved, method = None, ""
        if best_dist <= 1 and best_match is not None:
            resolved, method = best_match, f"Levenshtein distance {best_dist}"
        elif verdict is not None:
            if verdict.get("label") == "apply":
                resolved, method = verdict["pick"], f"judged p={verdict['p']}"
            elif verdict.get("pick"):
                results.append(FixResult(note_path, "links", False, f"Proposed for [[{target}]]: [[{verdict['pick']}]] (p={verdict['p']}, below the apply cut)"))
                continue
        else:
            llm_pick = _llm_resolve(target, link["context"], index_list, vault)
            if llm_pick:
                resolved, method = llm_pick, "LLM"

        if resolved:
            old_link = match.group(0)
            if old_link not in new_body:
                # str.replace() below has no notion of "just this occurrence": an earlier
                # identical broken-link text in this same note already rewrote every instance
                # of it. Nothing is left to change for this one — say so rather than claim a
                # (possibly different) resolution was applied here too.
                results.append(FixResult(note_path, "links", True,
                                          f"[[{target}]] already replaced by an earlier identical occurrence in this note"))
                continue
            alias_match = re.match(r"\[\[([^\]|]+)\|([^\]]+)\]\]", old_link)
            new_link = f"[[{resolved}|{alias_match.group(2)}]]" if alias_match else f"[[{resolved}]]"
            new_body = new_body.replace(old_link, new_link)
            results.append(FixResult(note_path, "links", True, f"Replaced [[{target}]] with [[{resolved}]] ({method})"))
        else:
            results.append(FixResult(note_path, "links", False, f"No match for [[{target}]]"))

    return frontmatter, new_body, results
