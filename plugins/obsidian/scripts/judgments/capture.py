"""Reading a capture for judgment: title, description, its own source, the URLs it cites,
its body, and the search query built from it (with the capture pipeline's header lines
stripped)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vault_utils import read_frontmatter

CAPTURE_CHARS = 6000

QUERY_BODY_CHARS = 600

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")

def _h1_or_stem(body: str, path: Path) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem

HEADER_LINE_RE = re.compile(r"^\s*\*\*(Source|Author|Saved|Captured|Origin|Published|URL)\s*:?\*\*\s*:?", re.I)

def query_text(capture: dict) -> str:
    """What search sees for a capture: title, description, and the first content lines with
    the capture pipeline's own header (**Source:** … **Saved:** …) and bare URLs stripped.
    [earned: 2026-09-22 replay — a Readwise capture's first 400 chars were all header, and the
    note that mattered ranked #2 on a clean query and nowhere on the boilerplate one]"""
    lines = [ln for ln in capture["body"].splitlines() if ln.strip() and not HEADER_LINE_RE.match(ln) and not ln.startswith("# ")]
    content = URL_RE.sub(" ", " ".join(lines))
    return " ".join([capture["title"], capture["description"], content[:QUERY_BODY_CHARS]])

def read_capture(path: Path) -> dict[str, Any]:
    fm, body = read_frontmatter(path)
    urls = [str(fm["source"])] if str(fm.get("source") or "").startswith("http") else []
    urls += [u for u in URL_RE.findall(body) if u not in urls]
    return {
        "title": _h1_or_stem(body, path),
        "description": str(fm.get("description") or ""),
        "own_source": str(fm["source"]) if str(fm.get("source") or "").startswith("http") else "",
        "source_urls": urls[:20],
        "body": body.strip()[:CAPTURE_CHARS],
    }

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
