#!/usr/bin/env python3
"""Vault quality suggestions from typed judgments — report-only.

    uv run scripts/vault_judge.py --json
    uv run scripts/vault_judge.py --scope 04_Resources --exclude 03_Areas/Personal

Two questions per active note, ten notes per request:

- **descriptions** — does the description say specifically what the note is about? The
  description is what search weights twice and what Index.md shows, so a vague or padded
  one costs retrieval (the BM25-dilution lesson). Notes with no description are listed
  without asking anyone.
- **domains** — which domains of the vault's taxonomy is the note mainly about? Listed only
  where the backend is confident about a domain the note's tags do not carry.

Nothing is written. `vault_normalize.py --fix` remains the only thing that edits notes;
this script produces the reading list a human (or the vault-lint skill) works through.
"""
from __future__ import annotations

import argparse
import json

import judge
from judgments import questions as Q
from judgments.state import domain_glosses, in_chunks, note_payload
from vault_utils import discover_notes, read_frontmatter, require_vault

NOTES_PER_REQUEST = 10
BODY_CHARS = 1500
# Policy, per backend. Deliberately strict: this is a suggestion list, a short one is useful.
# T_DESCRIPTION_WEAK, 2026-09-22, jev-1.13 on the bundled vault: the two planted description
# specimens score 0.70 and 0.75 and are the two lowest of 63; every curated description is at
# 0.85 or above. The cut sits in that gap. It is a prior from one well-kept vault: on a real
# vault read the ranking first and recalibrate the cut.
THRESHOLDS = {"jev": {"T_DESCRIPTION_WEAK": 0.78, "T_DOMAIN_SUGGEST": 0.80}}


def review(vault, scope: str | None, exclude: list[str]) -> dict:
    notes = discover_notes(vault, scope=scope, exclude=exclude)
    domains = domain_glosses(vault, Q.DOMAIN_GLOSS)
    # Computed once, up front: whether a note has a description does not depend on
    # judge.judge() succeeding, so it must not live inside the retryable ask() closure below
    # (in_chunks()/_ask_split() re-invokes ask() on smaller sub-chunks of the same notes after
    # a judge.StateTooLarge split, which would otherwise re-append the same paths).
    payloads = {path: note_payload(path, vault, BODY_CHARS) for path in notes}
    missing = [p["path"] for p in payloads.values() if not p["description"]]
    weak, suggestions = [], []
    usage_total = {"backend": "", "model": "", "requests": 0, "input_tokens": 0, "usd": 0.0, "splits": 0, "skipped": []}
    def ask(chunk, start):
        state = {"domains": domains, "notes": {}}
        questions, tags_of = {}, {}
        for i, path in enumerate(chunk, start=1):
            nid = f"N{i:02d}"
            payload = payloads[path]
            fm, _ = read_frontmatter(path)
            tags_of[nid] = {str(t) for t in (fm.get("tags") or []) if isinstance(t, str)}
            state["notes"][nid] = payload
            if payload["description"]:
                questions[f"desc_{nid}"] = Q.description_specific(nid)
            for name in domains:
                questions[f"dom_{nid}_{name}"] = Q.domain(name, f"notes.{nid}")
        answers, usage = judge.judge(vault, state, questions)
        t = judge.policy_for(THRESHOLDS, usage.backend)
        usage_total["backend"], usage_total["model"] = usage.backend, usage.model
        for key in ("requests", "input_tokens", "usd", "splits"):
            usage_total[key] += getattr(usage, key)
        usage_total["skipped"].extend(usage.skipped)
        for nid, payload in state["notes"].items():
            desc = answers.get(f"desc_{nid}")
            if desc is not None and desc.p <= t["T_DESCRIPTION_WEAK"]:
                weak.append({"path": payload["path"], "p_specific": round(desc.p, 3), "description": payload["description"]})
            for name in domains:
                a = answers.get(f"dom_{nid}_{name}")
                if a is not None and a.p >= t["T_DOMAIN_SUGGEST"] and f"domain/{name}" not in tags_of[nid]:
                    suggestions.append({"path": payload["path"], "suggest": f"domain/{name}", "p": round(a.p, 3)})
        return {}

    in_chunks(notes, NOTES_PER_REQUEST, ask)
    usage_total["usd"] = round(usage_total["usd"], 6)
    return {
        "advisory": True, "questions_version": Q.QUESTIONS_VERSION, "notes_reviewed": len(notes),
        "missing_description": missing, "weak_descriptions": sorted(weak, key=lambda r: r["p_specific"]),
        "domain_suggestions": sorted(suggestions, key=lambda r: -r["p"]), "judgment": usage_total,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scope", help="one PARA folder, e.g. 04_Resources")
    ap.add_argument("--exclude", action="append", default=[], help="vault-relative prefix never sent to the backend (repeatable)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    vault = require_vault()
    reason = judge.unavailable_reason(vault)
    if reason:
        print(json.dumps({"skipped": reason}) if args.json else f"SKIPPED — judgment backend unavailable ({reason})")
        return 0
    try:
        report = review(vault, args.scope, args.exclude)
    except judge.JudgmentFailed as e:
        print(f"judgment backend failed: {e}")
        return 1
    except judge.JudgmentUnavailable as e:  # key vanished between the check above and a later chunk
        print(f"SKIPPED — judgment backend unavailable ({e.reason})")
        return 0
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{report['notes_reviewed']} notes reviewed (advisory; {report['judgment']['backend']}/{report['judgment']['model']}, "
          f"${report['judgment']['usd']})")
    print(f"\nno description ({len(report['missing_description'])}):")
    for path in report["missing_description"]:
        print(f"  {path}")
    print(f"\nweak descriptions ({len(report['weak_descriptions'])}):")
    for row in report["weak_descriptions"]:
        print(f"  {row['p_specific']:<5} {row['path']}")
    print(f"\ndomain suggestions ({len(report['domain_suggestions'])}):")
    for row in report["domain_suggestions"]:
        print(f"  {row['p']:<5} {row['suggest']:<28} {row['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
