"""Eval: the owner's Reader highlights reach the vault (offline, stubbed Reader).

1. capture  — highlights on a document already in the vault become one highlights capture that
              names where the document went, `via: clip`, every highlight quoted with its note
2. new doc  — highlights on a document the vault has never seen (fetched by id) get their own capture
3. known    — a highlight whose text is already in the vault is recorded, not captured
4. ledger   — every highlight id is a ledger row; a rerun captures nothing twice
5. archive  — archive_settled never archives a highlight
6. note     — a Reader note on a document is rendered as the owner's note
7. prefix   — a highlight whose first words are in the vault but not the whole text is captured
8. retry    — a parent that can't be fetched records nothing, so the next run retries it
9. same run — a parent captured in the same run is named as where the highlights go
11. gone    — a parent Reader no longer has (404) still gets its highlights captured, marked as all
              that is left, with the highlight's Reader link as source
10. crash   — a highlights capture a crashed run left without ledger rows is recorded, not written twice
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
                             _hl("h4", "P", "Already quoted in a vault note, word for word"),
                             {**_hl("h5", "P", "Already quoted in a vault note, word for word, and then much more"),
                              "highlight_location": "7"},  # Reader mixes numbers and strings
                             _hl("h6", "R", "On a document Reader can't return right now")],
               "note": [{"id": "n7", "parent_id": "P", "category": "note", "content": "",
                         "notes": "Try this on the M5 Max", "created_at": "2026-09-12T08:00:00+00:00"}]}
    parents = {"Q": {"id": "Q", "title": "Unseen Doc", "author": "Someone", "source_url": "https://example.org/q"}}
    saved = (rw.reader_list_all, ingest.fetch_full, ingest.GET_DELAY_S, rw.reader_archive, ingest._pushed_paths)
    archived: list[str] = []
    sandbox = make_sandbox(vault)
    try:
        rw.reader_list_all = lambda category=None, **_: listing.get(category, [])
        def fetch(doc_id: str) -> dict:
            if doc_id not in parents:
                raise rw.ReadwiseAPIError("gone", status=404) if doc_id == "G" else rw.ReadwiseAPIError("unavailable", status=503)
            return parents[doc_id]
        ingest.fetch_full = fetch
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
            if fm.get("via") != "clip" or fm.get("readwise_highlight_ids") != ["h1", "h2", "h5", "n7"] or \
                    "`01_Capture/Readwise-Tweet-p-2026-09-11.md`" not in body or \
                    "> Sustained fifty tokens a second for code" not in body or "*my note:* check this on the M5" not in body \
                    or "*Note (2026-09-12):* Try this on the M5 Max" not in body:
                problems.append(f"capture/note: content of {p_cap}")
            if "h5" not in (fm.get("readwise_highlight_ids") or []) and not any(r["doc_id"] == "h5" and r.get("capture") for r in rows):
                problems.append("prefix: a highlight matched only by its first words was not captured")
        if not any("Unseen-Doc" in c for c in caps):
            problems.append("new doc: no capture for the unseen document")
        known = [r for r in rows if r["doc_id"] == "h4"]
        if not known or known[0].get("found") != "text in the vault" or known[0].get("capture"):
            problems.append(f"known: {known}")
        if sorted(r["doc_id"] for r in rows) != ["h1", "h2", "h3", "h4", "h5", "n7"] or summary.get("parent_failed") != 1:
            problems.append(f"ledger/retry: {[r['doc_id'] for r in rows]}, {summary}")

        ledger.update({r["doc_id"]: r for r in rows})
        parents["R"] = {"id": "R", "title": "Back Again", "source_url": "https://example.org/r"}
        ledger["R"] = {"doc_id": "R", "capture": "01_Capture/Readwise-Article-r-2026-09-25.md", "via": "clip"}  # same run
        rows2, _ = ingest.ingest_highlights(sandbox, items, ledger, {}, {}, NOW)
        if [r["doc_id"] for r in rows2] != ["h6"]:
            problems.append(f"retry/rerun: {rows2}")
        else:
            _, body6 = read_frontmatter(sandbox / rows2[0]["capture"])
            if "`01_Capture/Readwise-Article-r-2026-09-25.md`" not in body6:
                problems.append("same run: the parent's new capture is not named")
            ledger.update({r["doc_id"]: r for r in rows2})
            caps += [rows2[0]["capture"]]

        (sandbox / ingest.LEDGER).write_text("".join(json.dumps(r) + "\n" for r in ledger.values()), encoding="utf-8")
        rw.reader_archive = lambda doc_id, token=None: archived.append(doc_id) or {}
        ingest._pushed_paths = lambda v: {p for p in caps}  # everything "pushed"
        ingest.archive_settled(sandbox, NOW)
        if any(a.startswith("h") for a in archived):
            problems.append(f"archive: highlights archived {archived}")
        # --- 10. crash: the ledger lost every highlight row, the captures are still there ---
        fresh = {k: v for k, v in ledger.items() if "highlight_of" not in v}
        before = sorted(p.name for p in (sandbox / "01_Capture").glob("Readwise-Highlights-*.md"))
        rows3, s3 = ingest.ingest_highlights(sandbox, items, fresh, {}, {}, NOW)
        after = sorted(p.name for p in (sandbox / "01_Capture").glob("Readwise-Highlights-*.md"))
        if before != after or s3.get("recovered") != 6:
            problems.append(f"crash: files {len(before)}->{len(after)}, {s3}")
        # --- 11. gone: the parent was deleted in Reader ---
        listing["highlight"].append({**_hl("h8", "G", "The last trace of a deleted page"), "url": "https://read.readwise.io/read/h8"})
        rows4, s4 = ingest.ingest_highlights(sandbox, items, {**ledger, **{r["doc_id"]: r for r in rows3}}, {}, {}, NOW)
        g = [r for r in rows4 if r["doc_id"] == "h8" and r.get("capture")]
        if not g or s4.get("parent_gone") != 1:
            problems.append(f"gone: {rows4}, {s4}")
        else:
            fm8, body8 = read_frontmatter(sandbox / g[0]["capture"])
            if fm8.get("source") != "https://read.readwise.io/read/h8" or "all that is left of it" not in body8:
                problems.append(f"gone: capture {fm8.get('source')}")
    finally:
        rw.reader_list_all, ingest.fetch_full, ingest.GET_DELAY_S, rw.reader_archive, ingest._pushed_paths = saved
        teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "highlights captured once, known ones recorded, never archived"}
