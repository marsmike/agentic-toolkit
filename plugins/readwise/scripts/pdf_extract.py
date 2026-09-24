#!/usr/bin/env python3
"""Convert a `pdf` clipping to page-anchored Markdown without ever writing the PDF into the
vault. [earned: 2026-09-24, owner's request — the vault's own .gitignore excludes *.pdf, so a
PDF downloaded into 04_Resources/Attachments/ (the old `build_captures.store_attachment()`
path) bloated the git repo on every real run and, worse, vanished from a cloud container the
moment it exited: the note kept linking a file that existed nowhere]

Extractor: LiteParse (run-llama, github.com/run-llama/liteparse) — a Rust core exposed via
PyO3, Apache-2.0, fully local (no LLM call, no network call, no GPU), with prebuilt wheels for
macOS arm64 and Linux x86_64/aarch64 (manylinux_2_28) at ~12-14MB each — small enough to be a
default dependency the cloud pipeline's `uv run` installs fresh on every run. Chosen over
pymupdf4llm (AGPL — licence excludes it) and marker/Chandra (revenue-capped licences — excluded
as a default); Docling (IBM, MIT) stays available as an explicit opt-in for table-heavy
documents that need its layout model instead — see plugins/readwise/README.md's Library note.

`extract_pdf()` is the one entry point `build_captures.write_capture()` calls: download to a
temp dir, hash, convert, discard the temp dir. A download failure or a conversion failure both
return `extractor: "reader"` with no page-specific fields — the caller then uses Reader's own
`html_content`, exactly as it always did for a pdf item before this module existed. The owner's
clips never drop over a conversion failure (distill SKILL.md invariant 8).
"""
from __future__ import annotations

import hashlib
import http.client
import re
import tempfile
import urllib.error
import urllib.request
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path
from typing import Any

DOWNLOAD_MAX_BYTES = 200 * 1024 * 1024  # the owner's 154-page/10MB report is typical; generous ceiling for a big report
DOWNLOAD_TIMEOUT = 180                   # bigger than the old attachment download's 120s: no longer racing a vault write
FULL_TEXT_MAX_CHARS = 400_000            # a sane cap so a giant PDF still leaves a readable capture note
OUTLINE_MIN_PAGES = 15                   # below this, an Outline section adds height without saving navigation time

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
PAGE_ANCHOR_RE = re.compile(r"^<!-- page (\d+) -->$", re.M)


def _download(url: str) -> bytes | None:
    """Fetch the PDF into memory. Same failure contract the old `store_attachment()` used: a
    bad scheme, a non-PDF response, a truncated or oversized body all return None rather than
    raise — a malformed `source_url` (seen from real API payloads: a stray space, a broken
    IPv6-literal host) makes urlopen() raise a bare ValueError instead of URLError, so that's
    caught here too."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agentic-toolkit-readwise/1.0"})
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            if "pdf" not in (resp.headers.get("Content-Type") or "").lower() and not url.lower().endswith(".pdf"):
                return None
            data = resp.read(DOWNLOAD_MAX_BYTES + 1)
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError):
        return None
    if len(data) > DOWNLOAD_MAX_BYTES or not data.startswith(b"%PDF"):
        return None
    return data


def liteparse_version() -> str:
    try:
        return _pkg_version("liteparse")
    except PackageNotFoundError:
        return "unknown"


def _outline(full_text: str) -> str:
    """`## Outline`: every Markdown heading in the conversion, next to the page anchor it falls
    under, so a big PDF can be navigated by page range instead of read start to finish."""
    events: list[tuple[int, str, str, str]] = []
    for m in PAGE_ANCHOR_RE.finditer(full_text):
        events.append((m.start(), "page", m.group(1), ""))
    for m in HEADING_RE.finditer(full_text):
        events.append((m.start(), "head", m.group(1), m.group(2).strip()))
    events.sort(key=lambda e: e[0])

    lines, page, found = ["## Outline", ""], 1, False
    for _, kind, a, b in events:
        if kind == "page":
            page = int(a)
        elif b:
            lines.append(f"{'  ' * (len(a) - 1)}- p.{page} {b}")
            found = True
    if not found:
        return ""
    lines.append("")
    return "\n".join(lines)


def _truncate(full_text: str, total_pages: int) -> tuple[str, int | None]:
    """Cap the conversion so a giant PDF still leaves a readable note, with a visible marker
    naming the page reached — the rest is one click away at the Source link."""
    if len(full_text) <= FULL_TEXT_MAX_CHARS:
        return full_text, None
    cut = full_text.rfind("<!-- page ", 0, FULL_TEXT_MAX_CHARS)
    head = (full_text[:cut] if cut > 0 else full_text[:FULL_TEXT_MAX_CHARS]).rstrip()
    reached = max((int(x) for x in PAGE_ANCHOR_RE.findall(head)), default=0)
    note = (f"\n\n> [!warning] Truncated at ~{FULL_TEXT_MAX_CHARS:,} chars (reached page {reached} of "
            f"{total_pages}); the rest is in the original PDF at the Source link above.")
    return head + note, reached


def convert(pdf_path: Path) -> dict[str, Any]:
    """Convert one on-disk PDF to page-anchored Markdown via LiteParse. Raises on any failure —
    `extract_pdf()` catches it and falls back to Reader's own text."""
    import liteparse  # imported lazily: a vault that never captures a PDF never pays for the wheel

    parser = liteparse.LiteParse(output_format="markdown", image_mode="placeholder", extract_links=True)
    result = parser.parse(str(pdf_path))
    total_pages = int(result.total_pages or len(result.pages))
    body = "\n\n".join(f"<!-- page {p.page_num} -->\n{(p.markdown or '').strip()}" for p in result.pages).strip()
    text, truncated_at = _truncate(body, total_pages)
    outline = _outline(text) if total_pages >= OUTLINE_MIN_PAGES else ""
    return {"text": text, "outline": outline, "pages": total_pages,
            "extractor": f"liteparse {liteparse_version()}", "truncated_at": truncated_at}


def extract_pdf(url: str) -> dict[str, Any]:
    """Download `url` to a temp dir (never the vault) and convert it. Always returns a dict;
    `text` is None exactly when there is nothing PDF-specific to show — the caller then falls
    back to Reader's own `html_content` with `extractor: "reader"` and no `pdf_pages`, same as
    any other item Reader captured but this plugin couldn't fetch itself. A conversion failure
    (after a successful download) still reports the hash — the bytes were real even if the
    parse wasn't."""
    if not url.startswith("http"):
        return {"sha256": None, "pages": None, "text": None, "outline": "", "extractor": "reader"}
    data = _download(url)
    if data is None:
        return {"sha256": None, "pages": None, "text": None, "outline": "", "extractor": "reader"}
    sha256 = hashlib.sha256(data).hexdigest()
    try:
        with tempfile.TemporaryDirectory(prefix="readwise-pdf-") as tmp:
            pdf_path = Path(tmp) / "capture.pdf"
            pdf_path.write_bytes(data)
            conv = convert(pdf_path)
    except Exception:
        # Any conversion failure (a missing native wheel, a corrupt or password-locked PDF, an
        # image-only scan LiteParse's built-in OCR can't read) falls back to Reader's own
        # extraction rather than losing the capture — the owner's clips never drop
        # (obsidian:distill SKILL.md invariant 8).
        return {"sha256": sha256, "pages": None, "text": None, "outline": "", "extractor": "reader"}
    return {"sha256": sha256, "pages": conv["pages"], "text": conv["text"], "outline": conv["outline"],
            "extractor": conv["extractor"]}
