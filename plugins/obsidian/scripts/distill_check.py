#!/usr/bin/env python3
"""Gates a distilled note has to pass before its capture is retired.

    uv run scripts/distill_check.py NOTE CAPTURE --ask "question one" --ask "question two"

One command, one verdict, no prose to interpret: every invariant the distill skill relies
on is checked here, so the skill can say what a good note is instead of how to make one.
Exit 0 when every hard gate passes; 1 otherwise, with each failure and what would fix it.

Hard gates (fail the check):
  frontmatter   source, status: distilled, processed_date, description present
  source-line   a `*Source: …*` body line naming the capture's own source
  attachment    a capture with `attachment:` is linked from the note
  links         no wikilink into 01_Capture/ or 05_Archive/; every wikilink resolves
  index         Index.md has a line for the note
Soft gates (reported, never fail): the capture's other URLs not carried by the note (a
thread's reply links are usually fine to drop; a paper or repo is not), findability of each
--ask question (top three by widened rerank, plain search without a backend), and the
preservation check against the capture's kept passages (needs a judgment backend).
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import judge
from judgments.capture import URL_RE, _canonical, read_capture
from judgments.passages import check_note
from search import search
from vault_utils import discover_notes, read_frontmatter, require_vault

NEVER_LINK = ("01_Capture/", "05_Archive/")
IMAGE_HOSTS = ("readwise-assets", "substackcdn", "pbs.twimg.com", "images.unsplash", "cdn-images", "gravatar")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def _substantive_urls(capture: dict) -> list[str]:
    return [u for u in capture["source_urls"] if not any(h in u for h in IMAGE_HOSTS) and not re.search(r"\.(png|jpe?g|gif|svg|webp)(\?|$)", u, re.I)]


def check(note: Path, capture: Path, vault: Path, asks: list[str]) -> dict:
    fm, body = read_frontmatter(note, strict=False)
    cap_fm, _ = read_frontmatter(capture)
    cap = read_capture(capture)
    hard: dict[str, tuple[bool, str]] = {}

    # A literal `unknown` is the skill's forbidden placeholder: absent is honest, "unknown" is a guess dressed up.
    missing = [k for k in ("source", "status", "processed_date", "description") if not fm.get(k) or str(fm.get(k)).strip().lower() == "unknown"]
    hard["frontmatter"] = (not missing and fm.get("status") == "distilled",
                           f"missing or 'unknown': {missing}" if missing else ("status must be distilled" if fm.get("status") != "distilled" else "ok"))
    src_line = re.search(r"^\*Source:.*\*", body, re.M)
    own = cap.get("own_source") or ""
    line_urls = {_canonical(u) for u in URL_RE.findall(src_line.group(0))} if src_line else set()
    names_own = not own or _canonical(own) in line_urls or _canonical(own) == _canonical(str(fm.get("source") or ""))
    hard["source-line"] = (bool(src_line) and names_own,
                           "add a `*Source: …*` line" if not src_line else ("the Source line must name the capture's own source" if not names_own else "ok"))
    note_text = body + "\n" + json.dumps(fm, default=str)
    note_urls = {_canonical(u) for u in URL_RE.findall(note_text)}
    lost = [u for u in _substantive_urls(cap) if _canonical(u) not in note_urls]
    att = str(cap_fm.get("attachment") or "")
    hard["attachment"] = (not att or att in body, f"link the stored document [[{att}]]" if att and att not in body else "ok")
    stems = {p.stem for p in discover_notes(vault)} | {p.stem for p in vault.rglob("*.pdf")}
    forbidden = [t for t in WIKILINK_RE.findall(body) if t.strip().startswith(NEVER_LINK)]
    dangling = [t for t in WIKILINK_RE.findall(body) if t.strip().split("/")[-1].removesuffix(".pdf") not in stems
                and not (vault / t.strip()).exists()]
    hard["links"] = (not forbidden and not dangling,
                     (f"links into {forbidden[:2]}; " if forbidden else "") + (f"dangling {dangling[:3]}" if dangling else "") or "ok")
    rel = note.relative_to(vault).with_suffix("").as_posix()
    index = (vault / "Index.md").read_text(encoding="utf-8", errors="replace") if (vault / "Index.md").is_file() else ""
    hard["index"] = (f"[[{rel}|" in index or f"[[{rel}]]" in index, "add an Index.md line" if f"[[{rel}" not in index else "ok")

    soft: dict[str, object] = {"urls_not_in_note": {"count": len(lost), "sample": lost[:5]}}
    if asks:
        target = note.relative_to(vault).as_posix()
        ranks = []
        for q in asks:
            rows = search(q, vault, top=10)["results"]
            if judge.available(vault):
                import search_judge
                try:
                    rows = search_judge.rerank(q, vault, 10, [], widen=True)["results"]
                except (judge.JudgmentUnavailable, judge.JudgmentFailed) as e:
                    soft["findability_note"] = f"plain search order used: {e}"
            ranks.append(next((i for i, r in enumerate(rows, 1) if r["path"] == target), None))
        soft["findability"] = {"questions": asks, "ranks": ranks, "top3": sum(1 for r in ranks if r and r <= 3)}
    if judge.available(vault):
        try:
            pres = check_note(note, capture, vault)
            soft["preservation"] = {"kept": pres["kept_passages"], "carried": pres["carried"],
                                    "misses": [m["text"][:160] for m in pres["misses"]], "usd": pres["judgment"]["usd"]}
        except (judge.JudgmentUnavailable, judge.JudgmentFailed) as e:
            soft["preservation"] = {"skipped": str(e)}
    return {"note": note.relative_to(vault).as_posix(), "capture": capture.name, "hard": hard, "soft": soft,
            "pass": all(ok for ok, _ in hard.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("note")
    ap.add_argument("capture")
    ap.add_argument("--ask", action="append", default=[], help="a question a reader might type a year from now (repeatable)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    vault = require_vault()
    note = Path(args.note) if Path(args.note).is_absolute() else vault / args.note
    capture = Path(args.capture) if Path(args.capture).is_absolute() else vault / args.capture
    t0 = time.time()
    report = check(note, capture, vault, args.ask)
    report["seconds"] = round(time.time() - t0, 1)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for gate, (ok, why) in report["hard"].items():
            print(f"  {'ok  ' if ok else 'FAIL'} {gate:<12} {why}")
        u = report["soft"]["urls_not_in_note"]
        if u["count"]:
            print(f"  soft urls: {u['count']} capture URL(s) not in the note, e.g. {u['sample'][:2]}")
        f = report["soft"].get("findability")
        if f:
            print(f"  soft findability: {f['top3']}/{len(f['questions'])} questions in the top three  ranks={f['ranks']}")
        p = report["soft"].get("preservation")
        if p and "kept" in p:
            print(f"  soft preservation: {p['carried']}/{p['kept']} kept passages carried" + (f"; {len(p['misses'])} missing" if p["misses"] else ""))
            for m in p["misses"][:5]:
                print(f"       - {m[:120]}")
        print("PASS" if report["pass"] else "FAIL: fix the gates above before retiring the capture")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
