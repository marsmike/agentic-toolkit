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
        "T_SCOUT_VALUE": 0.65,  # scout_value at or above: the candidate makes the week's capture
    },
}

ITEMS_PER_REQUEST = 8           # every interest is asked about every item in one request
MAX_REQUESTS_PER_RUN = 300      # a daily scan needs ~10; the 30-day replay ~220
# A promoted item becomes a capture and, through the pipeline, a note: at most this many a run
# (one `scan --promote`, one `gaps --promote`), strongest first. [Mike, 2026-09-23: one pipeline
# for clips and radar; the 8-day backlog held 52 strong items, 36 of them arXiv] Per run, not per
# day: a daily cap spent by a morning burst archived every strong item after it. [earned:
# 2026-09-30 — 50 a day were gone by 07:11 UTC; the next three scans promoted none of 60]
PROMOTE_PER_RUN = 5
# Sensor items (Hacker News, Kagi News, the sensor RSS feeds) become captures too, not only
# momentum: the Signal Radar held OpenAI's own GPT-6.1 Sol post (805 HN points) and DevDay recap
# for two days and nothing ever promoted them, since only Reader feed items could be.
# [earned: 2026-09-30, DevDay 2026 missing from the vault]
SENSOR_PROMOTE_SOURCES = ("hn", "kagi_news", "rss")  # hf/github trending and Reddit have their own feed path
SENSOR_PROMOTE_WINDOW_DAYS = 3   # sensor day files read back; an item first seen earlier is old news
SENSOR_HN_MOMENTUM = 300         # HN points at which T_WORTH is enough: the judge sees a title only
# A paywalled outlet is the last choice of a story told by several: the capture holds a headline,
# and distill drops it (both FT stories of 2026-09-30 were dropped, NPR had the Astra story whole).
PAYWALLED = ("ft.com", "nytimes.com", "wsj.com", "bloomberg.com", "theinformation.com", "economist.com",
             "washingtonpost.com", "theathletic.com", "barrons.com")
SENSOR_SAME_STORY = 0.5          # title-word Jaccard at or above: another outlet's copy of a promoted story
# One watched name (Muse, OpenAI, …) may take this many of a run's sensor promotions, and this many
# a day; a lab's own announcement is never held back but counts. Outlets retell one story in words
# the title overlap cannot match: 14 of 20 promotions in one run were Meta Muse coverage, and
# distill merges them into one note anyway. [earned: 2026-09-30, 19:11 run]
SENSOR_PER_NAME_PER_RUN = 2
SENSOR_PER_NAME_PER_DAY = 6
# A lab's own announcement is promoted whatever the judge says from its title alone ("DevDay 2026
# Recap" scored 0.31). Host -> path prefixes that are announcements, not docs or careers pages.
LAB_ANNOUNCEMENTS: dict[str, tuple[str, ...]] = {
    "openai.com": ("/index/", "/news/", "/blog/"),
    "anthropic.com": ("/news/", "/engineering/", "/research/", "/claude-"),
    "claude.com": ("/blog/",),
    "blog.google": ("/technology/ai/", "/technology/google-deepmind/", "/products/gemini/"),
    "deepmind.google": ("/discover/blog/", "/blog/"),
    "developers.googleblog.com": ("/",),
    "ai.meta.com": ("/blog/",),
    "mistral.ai": ("/news/",),
    "x.ai": ("/news/",),
    "qwenlm.github.io": ("/blog/",),
    "huggingface.co": ("/blog/",),
}
# A lab's own feed also carries customer stories ("Proaction boosts sales 60% with Codex"): an
# announcement that arrives by RSS, without Hacker News or Kagi News having picked it up, needs
# this much from the judge, who sees its feed summary there, not a title alone.
LAB_RSS_MIN_P = 0.5
# One release stream (github.com/<owner>/<repo>/releases) is promoted at most once in this many
# days: each patch release is its own feed item, and four Claude Code patch releases in a day
# became four captures titled only "v2.1.27x". [earned: 2026-09-24 pipeline run]
RELEASE_STREAM_DAYS = 7
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

# scout: new sources (feeds, APIs, services, tools, datasets) the owner does not know about yet
SCOUT_WINDOW_DAYS = 28          # candidates come from state.jsonl and clips over the last four weeks
SCOUT_QUERIES_PER_INTEREST = 1  # one Kagi *news* query per interest per run ($0.002 each) — cheap
                                 # on purpose: launches are rare, and gaps.py already covers content
SCOUT_MAX_JUDGED = 20           # candidates judged per run, ranked by mention count first: kind +
                                 # value + actionable, 3 questions each — the cap on cost, not a
                                 # mention-count floor, since one clip can be evidence enough
SCOUT_TOP_N = 8                 # candidates kept in the week's capture
# A news hit names the outlet that reported a launch, not the thing launched; a web search returns
# the product page or repo itself. The owner's strongest interests (most strong items in the window)
# get one web search each ($0.025), and half the judged slots go to candidates only the web found:
# ranked by mentions alone, what the owner already reads always won. [earned: 2026-09-24 dry run —
# 20 judged, all mined from his own clips and feeds; the one proposal was a site he clips from daily]
SCOUT_SEARCH_INTERESTS = 5
SCOUT_EXTERNAL_SHARE = 0.5
