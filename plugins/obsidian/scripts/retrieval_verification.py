#!/usr/bin/env python3
"""Sampling and reporting scaffold for the retrieval-verification skill.

The predict-then-score step is done by the calling agent, not this script — it reads
only a note's title+description (never the body), writes down what it expects the note
to contain, then compares against the real body and scores 1-5. That reasoning step
can't be scripted; this file provides the two mechanical halves around it:

    uv run scripts/retrieval_verification.py sample --n 15 --json
        -> title + description only for N active notes, body withheld

    uv run scripts/retrieval_verification.py report --scores scores.json
        -> JSON report + a summary note appended to 01_Capture/

`scores.json` shape: {"<rel-path>": {"score": 1-5, "predicted": "...", "note": "..."}}
one entry per path returned by `sample`. `note` is optional free text (why it scored low).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from vault_utils import (
    append_capture_note,
    discover_notes,
    read_frontmatter,
    require_vault,
    write_dlq_note,
)

FLAG_THRESHOLD = 3  # score strictly below this is flagged for rewrite


def sample_notes(vault: Path, n: int, scope: str | None = None, seed: int | None = 42) -> list[dict]:
    """Pick min(n, available) active notes; deterministic by default (seed=42) so evals
    and repeated runs are reproducible unless the caller explicitly wants a fresh draw."""
    notes = discover_notes(vault, scope=scope)
    if not notes:
        return []
    rng = random.Random(seed)
    chosen = rng.sample(notes, min(n, len(notes)))

    samples = []
    for path in chosen:
        fm, _ = read_frontmatter(path)
        rel = path.relative_to(vault).as_posix()
        description = fm.get("description", "")
        samples.append({
            "path": rel, "title": path.stem, "description": description,
            "has_description": bool(description),
        })
    return sorted(samples, key=lambda s: s["path"])


def build_report(samples: list[dict], scores: dict, vault: Path) -> dict:
    entries = []
    missing_scores = []
    for s in samples:
        score_entry = scores.get(s["path"])
        if score_entry is None:
            missing_scores.append(s["path"])
            continue
        score = score_entry.get("score")
        entries.append({
            "path": s["path"], "title": s["title"], "description": s["description"],
            "score": score, "predicted": score_entry.get("predicted", ""),
            "note": score_entry.get("note", ""),
            "flagged": (not s["has_description"]) or (isinstance(score, (int, float)) and score < FLAG_THRESHOLD),
        })

    numeric_scores = [e["score"] for e in entries if isinstance(e["score"], (int, float))]
    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sampled": len(samples),
        "scored": len(entries),
        "missing_scores": missing_scores,
        "average_score": round(sum(numeric_scores) / len(numeric_scores), 2) if numeric_scores else None,
        "flagged": [e for e in entries if e["flagged"]],
        "entries": entries,
    }

    if missing_scores:
        write_dlq_note(
            vault, slug="retrieval-verification-missing-scores",
            title="retrieval-verification: sampled notes never got a score",
            what_happened=f"{len(missing_scores)} of {len(samples)} sampled notes have no entry in the scores map passed to `report`: {missing_scores}",
            why_recorded="A silently incomplete run would look identical to a clean pass in the JSON report's top-level counts if the gap weren't called out explicitly.",
            resolution="Re-run the predict/score step for the listed paths and re-invoke `report` with the completed scores map.",
            confidence="high",
        )
    return report


def write_report(report: dict, vault: Path) -> Path:
    out_dir = vault / "00_Memory" / "retrieval-verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{time.strftime('%Y-%m-%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out_path


def append_inbox_summary(report: dict, vault: Path, report_path: Path) -> Path:
    """Append a summary capture to 01_Capture/ so a low-scoring batch surfaces for triage,
    per contract/VAULT_SCHEMA.md's flat, origin-prefixed capture convention."""
    flagged = report["flagged"]
    lines = [
        (f"Sampled {report['sampled']} notes, scored {report['scored']}, "
        f"average {report['average_score']}, {len(flagged)} flagged (<{FLAG_THRESHOLD}) for a description rewrite."),
        "",
        f"Full report: `{report_path.relative_to(vault)}`",
        "",
    ]
    if flagged:
        lines.append("Flagged notes:")
        lines += [f"- [[{e['path'].rsplit('.md', 1)[0]}]] (score {e['score']}) — {e['note'] or 'no reason given'}" for e in flagged]
    else:
        lines.append("Nothing flagged this run.")

    content = (
        "---\n"
        f"description: Retrieval-verification run summary, {report['sampled']} notes sampled, {len(flagged)} flagged.\n"
        "status: draft\n"
        f"created: {time.strftime('%Y-%m-%d')}\n"
        "tags:\n  - domain/toolkit-meta\n"
        "---\n\n"
        f"# Retrieval verification — {time.strftime('%Y-%m-%d')}\n\n" + "\n".join(lines) + "\n"
    )
    return append_capture_note(vault, origin="RetrievalVerification", title=time.strftime("%Y-%m-%d-%H%M%S"), content=content)


def main() -> int:
    parser = argparse.ArgumentParser(description="retrieval-verification sampling/reporting scaffold")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser("sample", help="Sample N active notes, title+description only")
    p_sample.add_argument("--n", type=int, default=15)
    p_sample.add_argument("--scope", default=None)
    p_sample.add_argument("--seed", type=int, default=42)
    p_sample.add_argument("--json", action="store_true")

    p_report = sub.add_parser("report", help="Build the JSON report + inbox summary from a completed scores map")
    p_report.add_argument("--samples", required=True, help="Path to the sample() output JSON (from `sample --json`)")
    p_report.add_argument("--scores", required=True, help="Path to {path: {score, predicted, note}} JSON")

    args = parser.parse_args()
    vault = require_vault()

    if args.cmd == "sample":
        samples = sample_notes(vault, args.n, scope=args.scope, seed=args.seed)
        if args.json:
            print(json.dumps(samples, indent=2))
        else:
            for s in samples:
                marker = "" if s["has_description"] else "  [NO DESCRIPTION]"
                print(f"{s['path']}\n  title: {s['title']}\n  description: {s['description']}{marker}\n")
        return 0

    # report
    samples = json.loads(Path(args.samples).read_text(encoding="utf-8"))
    scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
    report = build_report(samples, scores, vault)
    report_path = write_report(report, vault)
    inbox_path = append_inbox_summary(report, vault, report_path)
    print(json.dumps({"report": str(report_path), "inbox_summary": str(inbox_path), **{k: v for k, v in report.items() if k != "entries"}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
