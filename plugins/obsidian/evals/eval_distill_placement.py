"""Eval: distill's placement heuristic (search.propose_placement) picks the right folder.

A synthetic capture drawn from the home-lab-migration project's own vocabulary should
route to that project's folder, not the generic 04_Resources default — proving the
keyword-scan fallback (the one this plugin ships in R0, ahead of farsight) actually
discriminates between clusters rather than always landing on the same answer.
Read-only: search() never writes, so this runs directly against the resolved vault.
"""
from __future__ import annotations

from pathlib import Path

SYNTHETIC_CAPTURE = (
    "Notes on VLAN segmentation and network topology for the home lab migration, covering "
    "hardware inventory, the backup strategy, and the migration runbook steps for cutover weekend."
)
EXPECTED_FOLDER_PREFIX = "02_Projects/home-lab-migration"


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from search import propose_placement

    if not (vault / "02_Projects" / "home-lab-migration").is_dir():
        return {"eval": "distill_placement", "pass": False, "detail": "fixture project not present: 02_Projects/home-lab-migration"}

    result = propose_placement(SYNTHETIC_CAPTURE, vault)
    top_paths = [m["path"] for m in result["top_matches"]]
    matched = any(p.startswith(EXPECTED_FOLDER_PREFIX) for p in top_paths)

    if not matched:
        return {
            "eval": "distill_placement", "pass": False,
            "detail": f"expected a top match under {EXPECTED_FOLDER_PREFIX}, got: {top_paths}",
        }
    return {"eval": "distill_placement", "pass": True, "detail": f"reason={result['reason']!r}, top_matches={top_paths}"}
