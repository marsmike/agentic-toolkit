"""Eval: retrieval_verification.py produces scores for N notes — the JSON report and
inbox summary-note halves of the skill.

Uses the vault's own BM25-dilution specimen pair (Test-Corpus-Map.md's planted edge
case) as the N=2 sample: the long-description specimen is scored low (as its own
frontmatter says it's designed to be hard to predict from), the condensed one high.
Writes, so this runs against a sandbox copy, never the resolved vault directly.
"""
from __future__ import annotations

from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

LONG_SPECIMEN = "04_Resources/Concepts/Retrieval-Verification-Loop-Long-Description-Specimen.md"
CONDENSED_SPECIMEN = "04_Resources/Concepts/Retrieval-Verification-Loop-Condensed-Description-Specimen.md"


def run(vault: Path) -> dict:
    if not (vault / LONG_SPECIMEN).is_file() or not (vault / CONDENSED_SPECIMEN).is_file():
        return {"eval": "retrieval_verification_report", "pass": False, "detail": "BM25-dilution specimen pair not present"}

    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import retrieval_verification as rv

    sandbox_vault = make_sandbox(vault)
    try:
        samples = [
            {"path": LONG_SPECIMEN, "title": "Retrieval-Verification-Loop-Long-Description-Specimen", "description": "(long, diluted)", "has_description": True},
            {"path": CONDENSED_SPECIMEN, "title": "Retrieval-Verification-Loop-Condensed-Description-Specimen", "description": "(condensed)", "has_description": True},
        ]
        scores = {
            LONG_SPECIMEN: {"score": 2, "predicted": "something about search in general", "note": "description too diffuse to predict the specific content"},
            CONDENSED_SPECIMEN: {"score": 4, "predicted": "BM25 dilution test pair, condensed description", "note": "description matched the body closely"},
        }

        report = rv.build_report(samples, scores, sandbox_vault)
        report_path = rv.write_report(report, sandbox_vault)
        inbox_path = rv.append_inbox_summary(report, sandbox_vault, report_path)

        problems = []
        if report["sampled"] != 2 or report["scored"] != 2:
            problems.append(f"expected sampled=2 scored=2, got sampled={report['sampled']} scored={report['scored']}")
        flagged_paths = {e["path"] for e in report["flagged"]}
        if LONG_SPECIMEN not in flagged_paths:
            problems.append(f"expected {LONG_SPECIMEN} to be flagged (score 2 < 3), flagged={flagged_paths}")
        if CONDENSED_SPECIMEN in flagged_paths:
            problems.append(f"did not expect {CONDENSED_SPECIMEN} to be flagged (score 4)")
        if not report_path.is_file():
            problems.append(f"report file missing: {report_path}")
        if not inbox_path.is_file() or inbox_path.parent.name != "01_Capture":
            problems.append(f"inbox summary not written to 01_Capture/: {inbox_path}")

        if problems:
            return {"eval": "retrieval_verification_report", "pass": False, "detail": "; ".join(problems)}
        return {
            "eval": "retrieval_verification_report", "pass": True,
            "detail": f"report={report_path.name}, inbox={inbox_path.name}, flagged={sorted(flagged_paths)}",
        }
    finally:
        teardown_sandbox(sandbox_vault)
