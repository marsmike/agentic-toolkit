#!/usr/bin/env python3
"""Write Readwise clippings into `$VAULT/01_Capture/` as origin-prefixed capture notes.

Singleton layout only (one capture per clipping) — v1 shipped a "concept cluster" mode too,
dropped here; v1's own skill already named singleton as "the default... on every run since
2026-06-29" and the cluster path as something to reach for only on explicit request. See
plugins/readwise/README.md's dropped-components table.

Two entry points:
  - `write_capture()`     — Reader v3 categories: tweet, article, video, email, pdf, epub.
  - `write_book_capture()` — Classic v2 books (a source + its highlights).

Both are dedup-safe: re-running ingest over the same clipping is a no-op rather than a
second file, which is the readwise plugin's own share of the dedup-before-distill rule
(contract/templates/VAULT_CLAUDE.md, earned by the 2026-07-26 X-Bookmark/Readwise
double-distill collision) — cross-origin dedup is distill's job; not re-emitting duplicate
raw captures on every ingest run is this plugin's job.
"""
from __future__ import annotations

import http.client
import re
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

from vault_utils import find_capture_by_doc_id, profile_value, unique_path, write_dlq_note, write_frontmatter

ATTACHMENT_MAX_BYTES = 50 * 1024 * 1024
ATTACHMENT_TIMEOUT = 120


def store_attachment(vault: Path, item: dict[str, Any], slug: str) -> Path | None:
    """For a `pdf` clipping, download the original file into the vault's attachment folder
    (profile key `attachments_folder`, default `04_Resources/Attachments`) and return its
    vault-relative path. The capture and later the distilled note link the file; the
    extracted text stays in the capture. A file that is already there is reused; a failed
    download returns None and the capture is written without an attachment.
    [earned: 2026-09-22 acceptance run — a 300 KB extracted-text capture of a 150-page
    report became one 10 KB note; the reader needs the document itself one click away]"""
    if item.get("category") != "pdf":
        return None
    url = str(item.get("source_url") or "")
    if not url.startswith("http"):
        return None
    folder = vault / str(profile_value(vault, "attachments_folder", "04_Resources/Attachments"))
    folder.mkdir(parents=True, exist_ok=True)
    # Keyed on the item's own doc_id, not the title-derived slug alone: two different PDF
    # items can slugify to the same (or, both title-less, an identical "untitled") string, and
    # unlike the capture note's own unique_path() call, this name must also stay stable across
    # a re-run of the *same* item (an ingest interrupted after the download but before the
    # capture note was written must not re-fetch it) -- the doc_id gives both at once.
    doc_id = str(item.get("id") or "")
    stem = f"{slug}-{_slugify(doc_id, maxlen=24)}" if doc_id else slug
    dest = folder / f"{stem}.pdf"
    if dest.is_file():
        return dest.relative_to(vault)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agentic-toolkit-readwise/1.0"})
        with urllib.request.urlopen(req, timeout=ATTACHMENT_TIMEOUT) as resp:
            if "pdf" not in (resp.headers.get("Content-Type") or "").lower() and not url.lower().endswith(".pdf"):
                return None
            data = resp.read(ATTACHMENT_MAX_BYTES + 1)
    # A malformed source_url (a bad scheme, a stray space or control character, a broken
    # IPv6-literal host — all seen from real API payloads) makes urlopen() raise a bare
    # ValueError or http.client.InvalidURL instead of URLError; this function's contract is
    # "a failed download returns None", not "crashes the whole capture write", so those must
    # degrade the same way as a network failure.
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError):
        return None
    if len(data) > ATTACHMENT_MAX_BYTES or not data.startswith(b"%PDF"):
        return None
    dest.write_bytes(data)
    return dest.relative_to(vault)

CATEGORY_LABEL = {
    "tweet": "Tweet",
    "article": "Article",
    "video": "Video",
    "email": "Newsletter",
    "pdf": "PDF",
    "epub": "EPUB",
}


def _slugify(text: str, maxlen: int = 70) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-")
    return (slug or "untitled")[:maxlen].rstrip("-")


def _html_to_md_basic(html: str) -> str:
    """Last-resort HTML→MD when no richer cleanup tool is available. Deliberately tiny —
    a full readability pipeline is out of scope; see README's dropped-components table."""
    if not html:
        return ""
    h = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</p>", "\n\n", h, flags=re.I)
    h = re.sub(r"<li[^>]*>", "- ", h, flags=re.I)
    h = re.sub(r"</li>", "\n", h, flags=re.I)
    h = re.sub(r"<h[1-6][^>]*>", "\n## ", h, flags=re.I)
    h = re.sub(r"</h[1-6]>", "\n", h, flags=re.I)
    h = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", h, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", "", h)
    h = unescape(h)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", h).strip()


def write_capture(vault: Path, item: dict[str, Any]) -> tuple[Path | None, str]:
    """Write one Reader v3 clipping as a capture note. Returns (path, status).

    `status` is one of: "written", "skipped-duplicate". `path` is None only when skipped.
    `item` is a Reader v3 list/get-response entry: id, category, title, author,
    source_url, summary, saved_at, notes, html_content (optional, from reader_get()).
    """
    doc_id = str(item.get("id") or "")
    if not doc_id:
        raise ValueError("item is missing 'id' — cannot dedup or write a coverage-checkable capture")

    existing = find_capture_by_doc_id(vault, doc_id)
    if existing is not None:
        return None, "skipped-duplicate"

    category = item.get("category") or "article"
    label = CATEGORY_LABEL.get(category, category.capitalize())
    title_raw = (item.get("title") or "").strip()
    title = title_raw or "(untitled)"
    author = (item.get("author") or "").strip()
    source_url = item.get("source_url") or item.get("url") or ""
    summary = (item.get("summary") or "").strip()
    saved_at = (item.get("saved_at") or item.get("created_at") or "")[:10]
    notes = (item.get("notes") or "").strip()
    html = item.get("html_content") or ""

    if not source_url or not title_raw:
        missing = ", ".join(
            name for name, present in (("source_url", bool(source_url)), ("title", bool(title_raw)))
            if not present
        )
        write_dlq_note(
            vault,
            slug=f"readwise-ambiguous-payload-{doc_id}",
            title=f"Readwise item {doc_id} missing {missing}",
            what_happened=(
                f"Reader v3 item {doc_id} (category: {category}) reached write_capture() without a usable "
                f"{missing} — the API returned it blank/absent, so the capture below was written with a "
                "guessed fallback rather than the real value."
            ),
            why_recorded=(
                "A doc_id with no source_url (or no title) is exactly the ambiguous case README's "
                "dead-letter-queue convention calls out — proceeding silently would hide a payload gap "
                "that the coverage check can't detect on its own."
            ),
            resolution="Check the item in Readwise directly and backfill the missing field by hand if needed.",
            confidence="low",
        )

    slug_base = f"{author}-{title}" if author else title
    slug = _slugify(slug_base)
    capture_dir = vault / "01_Capture"
    capture_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(capture_dir, f"Readwise-{label}-{slug}-{saved_at or 'undated'}")

    attachment = store_attachment(vault, item, slug)
    fm = {
        "source": source_url,
        "origin": "readwise",
        "readwise_doc_id": doc_id,
        "category": category,
        "author": author or None,
        "saved_at": saved_at or None,
        "created": saved_at or None,
        "attachment": attachment.as_posix() if attachment else None,
        "tags": ["readwise", category],
    }
    fm = {k: v for k, v in fm.items() if v is not None}

    body_lines = [f"# {title}", "", f"*Source: [{source_url}]({source_url})*"]
    if author:
        body_lines[-1] += f" — {author}"
    if attachment:
        body_lines += ["", f"**Document:** [[{attachment.as_posix()}]] (stored in the vault; the text below is the extraction)"]
    body_lines.append("")
    if summary:
        body_lines += ["## Readwise summary", "", summary, ""]
    body_lines.append("## Full Text")
    body_lines.append("")
    text = _html_to_md_basic(html)
    body_lines.append(text if text else "_(no body content returned by the API for this item)_")
    body_lines.append("")
    if notes:
        body_lines += ["## My notes", "", notes, ""]
    body_lines += [
        "## Processing Notes", "",
        f"- Ingested via readwise plugin ({category})",
        "- Status: awaiting distillation — see the obsidian:distill skill",
        "",
    ]

    write_frontmatter(dest, fm, "\n".join(body_lines))
    return dest, "written"


def write_book_capture(vault: Path, book: dict[str, Any], highlights: list[dict[str, Any]]) -> tuple[Path | None, str]:
    """Write one Classic v2 book/source (Kindle, Apple Books, …) as a single capture note
    listing its highlights. Dedup keyed on the source's title+author, since Classic v2
    source objects carry no stable numeric id (see references/api.md)."""
    title = (book.get("title") or book.get("readable_title") or "").strip() or "(untitled)"
    author = (book.get("author") or "").strip()
    doc_id = f"book:{_slugify(f'{author}-{title}', 100)}"

    existing = find_capture_by_doc_id(vault, doc_id)
    if existing is not None:
        return None, "skipped-duplicate"

    capture_dir = vault / "01_Capture"
    capture_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(f"{author}-{title}" if author else title)
    dest = unique_path(capture_dir, f"Readwise-Book-{slug}")

    fm = {
        "source": book.get("source_url") or book.get("readwise_url") or "",
        "origin": "readwise",
        "readwise_doc_id": doc_id,
        "category": "book",
        "author": author or None,
        "tags": ["readwise", "book"],
    }
    fm = {k: v for k, v in fm.items() if v is not None}

    body_lines = [f"# {title}", ""]
    if author:
        body_lines.append(f"*Author: {author}*")
        body_lines.append("")
    body_lines.append(f"## Highlights ({len(highlights)})")
    body_lines.append("")
    for h in highlights:
        text = (h.get("text") or "").strip()
        if not text:
            continue
        loc = h.get("location")
        suffix = f"  (loc {loc})" if loc else ""
        body_lines.append(f"> {text}{suffix}")
        note = (h.get("note") or "").strip()
        if note:
            body_lines.append(f">\n> **My note:** {note}")
        body_lines.append("")
    body_lines += ["## Processing Notes", "", "- Status: awaiting distillation — see the obsidian:distill skill", ""]

    write_frontmatter(dest, fm, "\n".join(body_lines))
    return dest, "written"
