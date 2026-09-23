"""Policy for the radar judgments: thresholds per backend and run limits.
Numbers live here and nowhere else; question wording lives in questions.py."""
from __future__ import annotations

import judge

# Priors from the R10 plan (2026-09-22), moved only after an acceptance run and a human accepting
# the result. T_WORTH 0.60 -> 0.70 on 2026-09-23: in the blind audit of the full 30-day replay
# (1,200 item x interest pairs) only 23% of the 0.60-0.80 band held up as worth reading, while
# the strong band held at 69%. Mike accepted the raise.
THRESHOLDS: dict[str, dict[str, float]] = {
    "jev": {
        "T_WORTH": 0.70,   # worth_reading at or above: listed for that interest
        "T_STRONG": 0.80,  # at or above: strong, the only band --promote ever acts on
        "T_FEED": 0.75,    # feed_worth at or above, for any interest: the feed is proposed
    },
}

ITEMS_PER_REQUEST = 8           # every interest is asked about every item in one request
MAX_REQUESTS_PER_RUN = 300      # a daily scan needs ~10; the 30-day replay ~220
# An item published this long before --since is a newly subscribed feed's back catalogue, not
# news: recorded as seen, never judged. [earned: 2026-09-22 smoke run, a new feed's archive
# arrived as that day's items]
BACKLOG_GRACE_DAYS = 7


def thresholds(backend: str) -> dict[str, float]:
    return judge.policy_for(THRESHOLDS, backend)

# discover
QUERIES_PER_INTEREST = 2        # Kagi searches per interest per discover run ($0.025 each)
PAGES_PER_QUERY = 8             # result pages fetched for feed autodiscovery
FEED_MIN_ITEMS = 3
FEED_MAX_SILENCE_DAYS = 45      # a feed whose latest item is older than this is dormant
