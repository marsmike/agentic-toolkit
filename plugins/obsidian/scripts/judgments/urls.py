"""One address, one key: URL canonicalisation shared by every caller that compares sources.

Copied byte-identical to plugins/radar/scripts/judgments/urls.py (no cross-plugin imports,
contract/KNOWLEDGE_API.md); core/tests/test_contract.py fails if the two copies drift."""
from __future__ import annotations

import re

TRACKING_PARAMS = {"is", "si", "feature", "t", "ref", "source", "fbclid", "gclid", "igshid", "s", "mc_cid", "mc_eid",
                   "rw_tt_thread", "ref_src", "ref_url"}

# A repository's front page under its other spellings: `.git` clone URL, default-branch tree.
# Deeper paths (issues, files, releases) stay distinct: they are different documents.
GITHUB_REPO_RE = re.compile(r"^github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/(?:main|master))?$")

# One paper under every arXiv spelling: abs/pdf/html, any version, `.pdf` suffix, export host.
ARXIV_RE = re.compile(r"^(?:export\.)?arxiv\.org/(?:abs|pdf|html)/(.+?)(?:v\d+)?(?:\.pdf)?$")


def _canonical(url: str) -> str:
    """Same address, same key: lower-cased host, no scheme/www, tracking parameters dropped
    (utm_*, share ids), fragment dropped, trailing slash dropped; GitHub repo roots and arXiv
    papers collapsed to one form each. [earned: 2026-09-22 — Reader held one video twice under
    URLs differing only by `&is=`]"""
    u = url.strip().rstrip("/.,;")
    u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I)
    u, _, _ = u.partition("#")
    path, _, query = u.partition("?")
    keep = []
    for part in query.split("&"):
        key = part.split("=", 1)[0].lower()
        if part and key not in TRACKING_PARAMS and not key.startswith("utm_"):
            keep.append(part)
    path = path.lower().rstrip("/")
    if m := GITHUB_REPO_RE.match(path):
        path = f"github.com/{m.group(1)}/{m.group(2)}"
    elif m := ARXIV_RE.match(path):
        path = f"arxiv.org/abs/{m.group(1)}"
    return path + ("?" + "&".join(sorted(keep)) if keep else "")
