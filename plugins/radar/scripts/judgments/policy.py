"""Policy for the radar judgments: thresholds per backend and run limits.
Numbers live here and nowhere else; question wording lives in questions.py."""
from __future__ import annotations

import judge

# Initial priors, 2026-09-22, jev-latest, from the R10 plan; not yet calibrated. They move only
# after the acceptance replay (own clips vs. random feed items) and a human accepting the result.
THRESHOLDS: dict[str, dict[str, float]] = {
    "jev": {
        "T_WORTH": 0.60,   # worth_reading at or above: listed for that interest
        "T_STRONG": 0.80,  # at or above: strong, the only band --promote ever acts on
    },
}

ITEMS_PER_REQUEST = 8           # every interest is asked about every item in one request
MAX_REQUESTS_PER_RUN = 300      # a daily scan needs ~10; the 30-day replay ~220


def thresholds(backend: str) -> dict[str, float]:
    return judge.policy_for(THRESHOLDS, backend)
