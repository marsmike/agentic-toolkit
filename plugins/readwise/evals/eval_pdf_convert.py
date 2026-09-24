"""Eval: `build_captures.write_capture()` for a `pdf` item never writes the file into the
vault — only the conversion (page anchors, `pdf_pages`, `pdf_sha256`, `extractor`) reaches the
capture. A failed conversion, and a failed download, both fall back to Reader's own
`html_content` with `extractor: reader` and no `attachment` field anywhere.

Offline: `pdf_extract._download` and `pdf_extract.convert` are both stubbed — no real network
call and no dependency on producing an actual parseable PDF for the fixture bytes.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "pdf_convert"
FAKE_PDF_BYTES = b"%PDF-1.4 fixture bytes, not a real document\n"
FAKE_SHA256 = hashlib.sha256(FAKE_PDF_BYTES).hexdigest()
CONVERTED_TEXT = "<!-- page 1 -->\n# Report\n\nFirst page body.\n\n<!-- page 2 -->\n## Section two\n\nSecond page body."


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_captures as bc
    import pdf_extract
    from vault_utils import read_frontmatter

    problems: list[str] = []
    real = (pdf_extract._download, pdf_extract.convert)
    sandbox = None
    try:
        sandbox = make_sandbox(vault)
        base_item = {"category": "pdf", "title": "placeholder", "author": "Someone",
                     "source_url": "https://example.org/report.pdf", "summary": "", "notes": "",
                     "saved_at": "2026-09-24T00:00:00Z"}

        # 1. a clean conversion: page anchors + pdf_pages/pdf_sha256/extractor, no file in the vault
        pdf_extract._download = lambda url: FAKE_PDF_BYTES
        pdf_extract.convert = lambda path: {"text": CONVERTED_TEXT, "outline": "", "pages": 2,
                                             "extractor": "liteparse 9.9.9", "truncated_at": None}
        before = {p.relative_to(sandbox).as_posix() for p in sandbox.rglob("*") if p.is_file()}
        path, status = bc.write_capture(sandbox, {**base_item, "id": "pdfeval1", "title": "A converted report",
                                                   "html_content": "<p>reader's own extraction, unused when conversion works</p>"})
        after = {p.relative_to(sandbox).as_posix() for p in sandbox.rglob("*") if p.is_file()}
        new_pdfs = [f for f in after - before if f.lower().endswith(".pdf")]
        if status != "written" or path is None:
            problems.append(f"phase 1: expected written, got {status!r}")
        else:
            fm, body = read_frontmatter(path)
            if fm.get("pdf_pages") != 2:
                problems.append(f"phase 1: pdf_pages should be 2, got {fm.get('pdf_pages')!r}")
            if fm.get("pdf_sha256") != FAKE_SHA256:
                problems.append("phase 1: pdf_sha256 does not match the downloaded bytes")
            if fm.get("extractor") != "liteparse 9.9.9":
                problems.append(f"phase 1: extractor should name liteparse, got {fm.get('extractor')!r}")
            if "attachment" in fm:
                problems.append("phase 1: a new PDF capture must not carry an attachment field")
            if "<!-- page 1 -->" not in body or "<!-- page 2 -->" not in body:
                problems.append("phase 1: capture body is missing page anchors")
        if new_pdfs:
            problems.append(f"phase 1: a PDF file was written into the vault: {new_pdfs}")

        # 2. the download succeeds but conversion raises: falls back to Reader's html_content,
        # extractor: reader, no pdf_pages — but the hash of the bytes we did fetch is kept.
        def _boom(_path):
            raise RuntimeError("simulated conversion failure")
        pdf_extract.convert = _boom
        path2, status2 = bc.write_capture(sandbox, {**base_item, "id": "pdfeval2", "title": "A conversion failure",
                                                     "html_content": "<p>" + "Reader's own extracted text. " * 15 + "</p>"})
        if status2 != "written" or path2 is None:
            problems.append(f"phase 2: expected written, got {status2!r}")
        else:
            fm2, body2 = read_frontmatter(path2)
            if fm2.get("extractor") != "reader":
                problems.append(f"phase 2: a failed conversion must record extractor: reader, got {fm2.get('extractor')!r}")
            if "pdf_pages" in fm2:
                problems.append("phase 2: a failed conversion has no known page count")
            if fm2.get("pdf_sha256") != FAKE_SHA256:
                problems.append("phase 2: the hash of the downloaded bytes should still be recorded")
            if "Reader's own extracted text" not in body2:
                problems.append("phase 2: the capture body must fall back to Reader's html_content")

        # 3. the download itself fails: same reader fallback, but no hash at all — nothing was ever fetched
        pdf_extract._download = lambda url: None
        path3, status3 = bc.write_capture(sandbox, {**base_item, "id": "pdfeval3", "title": "A broken download",
                                                     "html_content": "<p>" + "Reader saved this one directly. " * 15 + "</p>"})
        if status3 != "written" or path3 is None:
            problems.append(f"phase 3: expected written, got {status3!r}")
        else:
            fm3, body3 = read_frontmatter(path3)
            if fm3.get("extractor") != "reader" or "pdf_sha256" in fm3:
                problems.append(f"phase 3: a failed download has no hash and extractor: reader, got {fm3}")
            if "Reader saved this one directly" not in body3:
                problems.append("phase 3: the capture body must fall back to Reader's html_content")
    finally:
        pdf_extract._download, pdf_extract.convert = real
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "PDF conversion, both fallbacks, and no-vault-write all verified"}
