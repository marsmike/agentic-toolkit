"""Eval: the owner's Reader highlights reach the vault (offline, stubbed Reader).

1. capture  — highlights on a document already in the vault become one highlights capture that
              names where the document went, `via: clip`, every highlight quoted with its note
2. new doc  — highlights on a document the vault has never seen (fetched by id) get their own capture
3. known    — a highlight whose text is already in the vault is recorded, not captured
4. ledger   — every highlight id is a ledger row; a rerun captures nothing twice
5. archive  — archive_settled never archives a highlight
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "highlights"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def _hl(i: str, parent: str, text: str, note: str = "") -> dict:
    return {"id": i, "parent_id": parent, "category": "highlight", "content": text, "notes": note,
            "created_at": "2026-09-11T05:57:03+00:00", "highlight_location": int(i[-1])}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import ingest
    import readwise_api as rw
    from vault_utils import read_frontmatter

    problems: list[str] = []
    listing = {"highlight": [_hl("h1", "P", "Sustained fifty tokens a second for code"),
                             _hl("h2", "P", "The second highlight", note="check this on the M5"),
                             _hl("h3", "Q", "A highlight on an unseen doc"),
                             _hl("h4", "P", "Already quoted in a vault note, word for word")],
               "note": []}
    parents = {"Q": {"id": "Q", "title": "Unseen Doc", "author": "Someone", "source_url": "https://example.org/q"}}
    saved = (rw.reader_list_all, ingest.fetch_full, ingest.GET_DELAY_S, rw.reader_archive, ingest._pushed_paths)
    archived: list[str] = []
    sandbox = make_sandbox(vault)
    try:
        rw.reader_list_all = lambda category=None, **_: listing.get(category, [])
        ingest.fetch_full = lambda doc_id: parents[doc_id]
        ingest.GET_DELAY_S = 0
        (sandbox / "04_Resources" / "Eval-HL-Quote.md").write_text(
            "---\nstatus: distilled\n---\n# Q\n\n> Already quoted in a vault note, word for word\n", encoding="utf-8")
        ledger = {"P": {"doc_id": "P", "capture": "01_Capture/Readwise-Tweet-p-2026-09-11.md", "via": "clip"}}
        items = [{"id": "P", "title": "The Parent", "author": "Ivan", "source_url": "https://x.com/i/status/1", "category": "tweet"}]
        rows, summary = ingest.ingest_highlights(sandbox, items, ledger, {}, {}, NOW)
        caps = sorted({r["capture"] for r in rows if r.get("capture")})
        if len(caps) != 2 or summary.get("captures") != 2:
            problems.append(f"capture: {caps}, {summary}")
        p_cap = next((c for c in caps if "The-Parent" in c), None)
        if p_cap:
            fm, body = read_frontmatter(sandbox / p_cap)
            if fm.get("via") != "clip" or fm.get("readwise_highlight_ids") != ["h1", "h2"] or \
                    "`01_Capture/Readwise-Tweet-p-2026-09-11.md`" not in body or \
                    "> Sustained fifty tokens a second for code" not in body or "*my note:* check this on the M5" not in body:
                problems.append(f"capture: content of {p_cap}")
        if not any("Unseen-Doc" in c for c in caps):
            problems.append("new doc: no capture for the unseen document")
        known = [r for r in rows if r["doc_id"] == "h4"]
        if not known or known[0].get("found") != "text in the vault" or known[0].get("capture"):
            problems.append(f"known: {known}")
        if sorted(r["doc_id"] for r in rows) != ["h1", "h2", "h3", "h4"]:
            problems.append(f"ledger: {[r['doc_id'] for r in rows]}")

        ledger.update({r["doc_id"]: r for r in rows})
        rows2, _ = ingest.ingest_highlights(sandbox, items, ledger, {}, {}, NOW)
        if rows2:
            problems.append(f"rerun: captured again {rows2}")

        (sandbox / ingest.LEDGER).write_text("".join(json.dumps(r) + "\n" for r in ledger.values()), encoding="utf-8")
        rw.reader_archive = lambda doc_id, token=None: archived.append(doc_id) or {}
        ingest._pushed_paths = lambda v: {p for p in caps}  # everything "pushed"
        ingest.archive_settled(sandbox, NOW)
        if any(a.startswith("h") for a in archived):
            problems.append(f"archive: highlights archived {archived}")
    finally:
        rw.reader_list_all, ingest.fetch_full, ingest.GET_DELAY_S, rw.reader_archive, ingest._pushed_paths = saved
        teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "highlights captured once, known ones recorded, never archived"}
