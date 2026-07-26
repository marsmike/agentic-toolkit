"""Eval: the Classic v2 book-capture path — `write_book_capture()` — is schema-conformant
and dedup-safe, same as the singleton clipping path `eval_dedup_guard.py`/
`eval_capture_note_formatting.py` already cover. Books have no stable numeric id (Classic
v2 source objects carry none, see references/api.md), so `write_book_capture()` keys dedup
on a `book:<slug(author-title)>` `readwise_doc_id` instead — this eval is the acceptance
check that both the schema shape and that slug-keyed dedup actually hold, not just the
`readwise_doc_id`-keyed path the other two evals exercise. Writes, so this runs against a
sandbox copy of the vault.
"""
from __future__ import annotations

import json
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

REQUIRED_FRONTMATTER_FIELDS = ("source", "origin", "readwise_doc_id", "category", "tags")


def run(vault: Path) -> dict:
    import sys

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_captures as bc
    from vault_utils import iter_captures, read_frontmatter

    fixture = json.loads((Path(__file__).parent / "fixtures" / "reader_book.json").read_text())
    book, highlights = fixture["book"], fixture["highlights"]

    sandbox_vault = make_sandbox(vault)
    try:
        path1, status1 = bc.write_book_capture(sandbox_vault, book, highlights)
        path2, status2 = bc.write_book_capture(sandbox_vault, book, highlights)

        problems = []
        if status1 != "written":
            problems.append(f"first write: expected 'written', got {status1!r}")
        if path1 is None:
            return {"eval": "book_capture_dedup", "pass": False, "detail": "; ".join(problems) or "no path returned on first write"}

        fm, body = read_frontmatter(path1)
        missing_fields = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in fm]
        if missing_fields:
            problems.append(f"missing frontmatter fields: {missing_fields}")
        if fm.get("category") != "book":
            problems.append(f"expected category 'book', got {fm.get('category')!r}")
        if not isinstance(fm.get("tags"), list):
            problems.append(f"tags is not a list: {fm.get('tags')!r}")
        if path1.parent != sandbox_vault / "01_Capture":
            problems.append(f"capture not written flat under 01_Capture/: {path1}")
        if not path1.name.startswith("Readwise-"):
            problems.append(f"filename not origin-prefixed: {path1.name}")

        for h in highlights:
            if h["text"] not in body:
                problems.append(f"highlight text missing from body: {h['text']!r}")
        if f"Highlights ({len(highlights)})" not in body:
            problems.append("body is missing the highlight count heading")

        if status2 != "skipped-duplicate":
            problems.append(f"second write: expected 'skipped-duplicate', got {status2!r}")
        if path2 is not None:
            problems.append(f"second write returned a path when it should have returned None: {path2}")

        expected_doc_id = fm.get("readwise_doc_id", "")
        matching = [
            p for p in iter_captures(sandbox_vault)
            if expected_doc_id and expected_doc_id in p.read_text(encoding="utf-8", errors="replace")
        ]
        if len(matching) != 1:
            problems.append(f"expected exactly 1 capture file for {expected_doc_id!r}, found {len(matching)}: {[p.name for p in matching]}")

        if problems:
            return {"eval": "book_capture_dedup", "pass": False, "detail": "; ".join(problems)}
        return {"eval": "book_capture_dedup", "pass": True, "detail": f"wrote {path1.name} with conformant frontmatter; second write correctly deduped on title+author slug"}
    finally:
        teardown_sandbox(sandbox_vault)
