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
(contract/templates/VAULT_AGENTS.md, earned by the 2026-07-26 X-Bookmark/Readwise
double-distill collision) — cross-origin dedup is distill's job; not re-emitting duplicate
raw captures on every ingest run is this plugin's job.

A `pdf` clipping's file is never written into the vault: it is downloaded to a temp dir and
converted to page-anchored Markdown by `pdf_extract.extract_pdf()`, and only the conversion
(plus `pdf_pages`/`pdf_sha256`/`extractor`) lands in the capture. [earned: 2026-09-24, owner's
request — the vault's own .gitignore excludes *.pdf, so the old `store_attachment()` path
bloated the git repo on every real run and the stored file vanished from a cloud container
the moment it exited, leaving a note that linked nowhere]
"""
from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from typing import Any

import pdf_extract
import tweet_enrich
from vault_utils import find_capture_by_doc_id, unique_path, write_dlq_note, write_frontmatter

STUB_CHARS = 200        # less real text than this is not the article (a short X post via RSS has ~270)
STUB_CEILING = 1500     # a known wall phrase in a text shorter than this marks a stub
STUB_PHRASES = re.compile(
    r"(?i)(page (does not|doesn't) exist|\bnot found\b|\b404\b|create a (free )?account|sign up to|"
    r"log ?in to (continue|read)|enable javascript|subscribe to (continue|read)|access denied|just a moment)")


def is_stub(text: str, category: str) -> bool:
    """Reader saved a wall, not the content: a sign-up page, a 404, a bot check. A tweet is short
    by nature and never a stub. [earned: 2026-09-24 — two clips held "Create a free account" and
    "This page does not exist"; the dossier rated both discard-candidate ~1.0]"""
    if category == "tweet":
        return False
    body = text.strip()
    return len(body) < STUB_CHARS or (len(body) < STUB_CEILING and bool(STUB_PHRASES.search(body)))


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


# Avatars and emoji glyphs in Reader's tweet HTML are chrome, not content.
MEDIA_SKIP = re.compile(r"profile_images|/emoji/|abs\.twimg\.com")


def _media(match: re.Match) -> str:
    src = match.group(1)
    return "" if MEDIA_SKIP.search(src) or src.startswith("data:") else f" ![]({src}) "


def _html_to_md_basic(html: str, keep_media: bool = False) -> str:
    """Last-resort HTML→MD when no richer cleanup tool is available. Deliberately tiny —
    a full readability pipeline is out of scope; see README's dropped-components table.

    `keep_media` (tweets) keeps images as `![](src)` and a video as its poster plus a marker,
    since a tweet's point often sits in a screenshot. [earned: 2026-09-25 — a prompt shared as a
    screenshot reached the capture as nothing, and ~16 September tweet captures read "Your
    browser does not support the video tag."]"""
    if not html:
        return ""
    h = re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S | re.I)
    if keep_media:
        h = re.sub(r'<video[^>]*?poster="([^"]+)"[^>]*>.*?</video>',
                   lambda m: _media(m) + "*(video: watch it at the source)*\n", h, flags=re.S | re.I)
        h = re.sub(r"<video.*?</video>", "\n*(video: watch it at the source)*\n", h, flags=re.S | re.I)
        h = re.sub(r'<img[^>]*?src="([^"]+)"[^>]*>', _media, h, flags=re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    h = re.sub(r"</p>", "\n\n", h, flags=re.I)
    h = re.sub(r"<li[^>]*>", "- ", h, flags=re.I)
    h = re.sub(r"</li>", "\n", h, flags=re.I)
    h = re.sub(r"<h[1-6][^>]*>", "\n## ", h, flags=re.I)
    h = re.sub(r"</h[1-6]>", "\n", h, flags=re.I)
    h = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", h, flags=re.S | re.I)
    h = re.sub(r"<[^>]+>", "", h)
    h = unescape(h)
    h = h.replace("Your browser does not support the video tag.", "*(video: watch it at the source)*")
    # A quoted tweet arrives as a link with no text: say what it is.
    h = re.sub(r"\[\s*\]\((https?://[^)]+/status/[^)]+)\)", r"Quoted post: <\1>", h)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", h).strip()


def write_capture(vault: Path, item: dict[str, Any], provenance: dict[str, Any] | None = None) -> tuple[Path | None, str]:
    """Write one Reader v3 clipping as a capture note. Returns (path, status).

    `provenance` is how the item reached the library: `{"via": "clip"}` (the owner saved it),
    `{"via": "newsletter"}` (delivered), or `{"via": "radar", "radar_interests": [...]}` (the
    radar promoted it). It lands in frontmatter; distill may drop a non-clip capture, never a clip.

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

    # A `pdf` item's file is never written into the vault (see module docstring): only the
    # conversion, its page count and hash reach the capture. `extract_pdf()` itself degrades to
    # `extractor: "reader"` on a bad/missing URL, so it is always safe to call for this category.
    pdf_info = pdf_extract.extract_pdf(source_url) if category == "pdf" else None
    text = pdf_info["text"] if pdf_info and pdf_info["text"] else _html_to_md_basic(html, keep_media=category == "tweet")
    enriched = tweet_enrich.enrich(summary, text, _html_to_md_basic) if category == "tweet" and tweet_enrich.enabled() else None
    media: list[str] = []
    if enriched:
        summary, text = enriched["summary"], enriched["text"]
        text, media, lost = tweet_enrich.save_media(text, vault, doc_id)
        if lost and enriched["status"] != "partial":
            enriched["status"] = "partial"
        elif media and enriched["status"] == "none":
            enriched["status"] = "full"
    stub = is_stub(text, category)
    fm = {
        "source": source_url,
        "origin": "readwise",
        "readwise_doc_id": doc_id,
        "category": category,
        "author": author or None,
        "saved_at": saved_at or None,
        "created": saved_at or None,
        "pdf_pages": pdf_info.get("pages") if pdf_info else None,
        "pdf_sha256": pdf_info.get("sha256") if pdf_info else None,
        "extractor": pdf_info.get("extractor") if pdf_info else None,
        "content": "stub" if stub else None,
        "links": (enriched["links"] or None) if enriched else None,
        "media": media or None,
        "enrichment": enriched["status"] if enriched and enriched["status"] != "none" else None,
        **(provenance or {}),
        "tags": ["readwise", category, *(["radar"] if (provenance or {}).get("via") == "radar" else [])],
    }
    fm = {k: v for k, v in fm.items() if v is not None}

    body_lines = [f"# {title}", "", f"*Source: [{source_url}]({source_url})*"]
    if author:
        body_lines[-1] += f" — {author}"
    if pdf_info and pdf_info.get("pages"):
        body_lines += ["", f"*PDF: {pdf_info['pages']} pages, converted by {pdf_info['extractor']} "
                           f"(sha256 {pdf_info['sha256'][:12]}…). The file itself is not stored here — "
                           "only at the Source link above; cite page ranges (`<!-- page N -->` anchors below) "
                           "instead of linking a document.*"]
    elif pdf_info:
        body_lines += ["", "*PDF: conversion did not run for this item (see `extractor: reader` in frontmatter); "
                           "the text below is Reader's own extraction, and the file itself is not stored here — "
                           "only at the Source link above.*"]
    body_lines.append("")
    if summary:
        body_lines += ["## Readwise summary", "", summary, ""]
    if pdf_info and pdf_info.get("outline"):
        body_lines += [pdf_info["outline"]]
    body_lines.append("## Full Text")
    body_lines.append("")
    if stub:
        body_lines += ["> [!warning] Stub: Reader saved no real content (a wall, a 404 or an empty page). "
                       "Fetch the source before distilling.", ""]
    body_lines.append(text if text else "_(no body content returned by the API for this item)_")
    body_lines.append("")
    if enriched:
        body_lines += tweet_enrich.linked_section(enriched["linked"])
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
