"""Policy for the distill judgments: thresholds per backend and what a relation maps to.
Numbers live here and nowhere else; question wording lives in questions.py."""
from __future__ import annotations

# Initial priors, 2026-09-21, jev-latest, not yet calibrated against a labelled set.
# Change only from `--calibrate` output a human accepted; record date + model here.
THRESHOLDS: dict[str, dict[str, float]] = {
    "jev": {
        "T_TRIAGE": 0.60,            # below this top probability: no triage recommendation
        "T_RELEVANT": 0.50,          # rel_* at or above: enrichment candidate
        "T_PRINCIPLE": 0.55,         # prin_* at or above: a cross-domain bridge, also a candidate
        "T_UPGRADE": 0.75,           # relation must be this sure before suggesting L2/L3 over L1
        "T_COVERS": 0.80,            # covers_* at or above: probably the same original work
        "T_DOMAIN": 0.50,
        "T_PLACEMENT_MARGIN": 0.20,  # top-two gap below this: placement is ambiguous
        "T_REDUNDANT": 0.70,         # 1 - adds(a, b) at or above: a adds nothing over b
        "T_SECOND_HOME": 0.25,       # a runner-up folder holding this much mass is worth naming (soft placement)
        "T_KEEP": 0.60,              # passage_keep at or above: part of the capture's essence
        "T_REVERSES": 0.40,          # summary_reverses at or above, or relation misstates/overstates on top: read the source, not the summary
        "T_CONCEPT_UPGRADE": 0.50,   # concept_vs_root at or above: 04_Resources -> 04_Resources/Concepts
    },
}

LEVEL_BY_RELATION = {"strengthens-passage": "L2", "contradicts-claim": "L3", "adjacent": "L1", "unrelated": None}

def thresholds(backend: str) -> dict[str, float]:
    if backend not in THRESHOLDS:
        raise SystemExit(f"no threshold table for judgment backend {backend!r}; calibrate one before using it")
    return THRESHOLDS[backend]
