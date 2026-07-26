#!/usr/bin/env python3
"""Fetch GitHub repo metadata for enrichment — stars, language, activity status.

Optional enrichment: shells out to the `gh` CLI. Degrades cleanly (returns an "error" key,
never raises or crashes the caller) when `gh` isn't installed or the repo can't be fetched
— GitHub enrichment is a nice-to-have on top of a capture, never a gate on writing one.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

_REPO_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
_NOT_REPOS = {"features", "about", "pricing", "topics", "collections", "sponsors",
              "orgs", "settings", "login", "marketplace", "trending", "explore"}


def extract_repo_slugs(*texts: str) -> set[str]:
    """Find owner/repo slugs in text. Strips a trailing `.git` by suffix, never by
    `str.rstrip(".git")` — that strips any trailing '.', 'g', 'i', 't' character, silently
    mangling names like `microsoft/graphrag` into `microsoft/graphra` (observed in v1)."""
    slugs = set()
    for text in texts:
        if not text:
            continue
        for owner, name in _REPO_RE.findall(text):
            if owner.lower() in _NOT_REPOS:
                continue
            name = re.sub(r"\.git$", "", name).rstrip(".")
            if name:
                slugs.add(f"{owner}/{name}")
    return slugs


def gh_available() -> bool:
    return shutil.which("gh") is not None


def fetch_repo_meta(owner_repo: str, timeout: int = 20) -> dict:
    """`{owner}/{repo}` -> metadata dict, or `{"error": "..."}` on any failure."""
    if not gh_available():
        return {"error": "gh CLI not on PATH — install: brew install gh"}
    jq_filter = (
        "{full_name: .full_name, description: .description, language: .language, "
        "stars: .stargazers_count, forks: .forks_count, open_issues: .open_issues_count, "
        "created_at: .created_at, pushed_at: .pushed_at, topics: .topics, "
        "license: .license.spdx_id, archived: .archived}"
    )
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{owner_repo}", "--jq", jq_filter],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"gh api call failed: {e}"}
    if result.returncode != 0:
        return {"error": (result.stderr or "gh api returned a non-zero exit code").strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "gh api returned non-JSON output"}


def activity_status(meta: dict) -> str:
    if meta.get("archived"):
        return "Archived"
    pushed = (meta.get("pushed_at") or "")[:10]
    if pushed and pushed >= "2025-01-01":
        return "Active"
    return "Stale"


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: github_meta.py <owner/repo>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(fetch_repo_meta(sys.argv[1]), indent=2))
