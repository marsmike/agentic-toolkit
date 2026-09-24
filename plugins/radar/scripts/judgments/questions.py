"""Every question the radar asks: wording only, no policy.

This file is data. Thresholds and what a probability leads to live in `policy.py`; nothing here
may mention a number, a threshold, or an action. The `judgment-calibration` loop edits this
file (and only this file) when a disagreement traces back to wording, and bumps
QUESTIONS_VERSION when it does.

State shape: `interests.<id>` = {name, gloss}; `items.<key>` = {title, summary, site, category};
`feeds.<key>` = {title, description, site, recent} (recent: the latest item titles, joined).
Interests enter as name and gloss only, never their search queries.
"""
from __future__ import annotations

from judge import Question

QUESTIONS_VERSION = "2026-09-23.1"

KINDS = {
    "paper": "a research paper or preprint, or a write-up of one",
    "release-or-tool": "a software release, a new tool or library, or a changelog",
    "news": "a report of something that happened: an announcement, a launch, an event, a deal",
    "opinion": "an essay, commentary or argument, where the author's view is the content",
    "promo": "an advertisement, sponsored post, sale or product pitch",
    "other": "none of the other descriptions fits, or the text is too short to tell",
}


def worth_reading(key: str, iid: str) -> Question:
    return Question(
        kind="noul",
        instructions=(
            f"Would someone actively working on `interests.{iid}` want to read `items.{key}` this week, "
            "because it carries new information for that work?"
        ),
        criteria={
            "true": f"`items.{key}` reports a result, release, method or decision that bears directly on `interests.{iid}`",
            "false": (
                f"`items.{key}` only shares vocabulary or a broad field with `interests.{iid}`, "
                "or is about something else"
            ),
        },
    )


def kind(key: str) -> Question:
    return Question(kind="choice", instructions=f"What kind of text is `items.{key}`?", criteria=dict(KINDS))


FEED_KINDS = {
    "research": "mostly research papers or preprints",
    "releases": "mostly software releases, changelogs or new tools",
    "practice": "mostly hands-on posts: how someone built, used or evaluated something",
    "news": "mostly news and announcements",
    "discussion": "mostly community discussion or link aggregation",
    "promo": "mostly marketing, sponsored posts or product pitches",
    "other": "none of the other descriptions fits",
}


def feed_worth(key: str, iid: str) -> Question:
    return Question(
        kind="noul",
        instructions=(
            f"Judging by its recent items, would `feeds.{key}` bring someone actively working on "
            f"`interests.{iid}` something new worth reading most weeks?"
        ),
        criteria={
            "true": f"several recent items in `feeds.{key}` bear directly on `interests.{iid}`",
            "false": f"`feeds.{key}` only touches `interests.{iid}` occasionally, or through shared vocabulary",
        },
    )


def feed_kind(key: str) -> Question:
    return Question(kind="choice", instructions=f"What does `feeds.{key}` mostly carry?", criteria=dict(FEED_KINDS))


SCOUT_KINDS = {
    "feed": "a blog, newsletter, changelog or other subscribable feed of posts",
    "api": "a programmable API or SDK meant to be integrated into other software",
    "service": "a hosted product or service someone would sign up for and use directly",
    "tool": "a downloadable tool, library or app run or installed directly, not called as an API",
    "dataset": "a dataset or corpus for training, evaluation or reference",
    "community": "a forum, Discord, subreddit or other place people gather to discuss it",
    "other": "none of the other descriptions fits, or there is too little to tell",
}


def scout_kind(key: str) -> Question:
    return Question(kind="choice", instructions=f"What is `candidates.{key}`?", criteria=dict(SCOUT_KINDS))


def scout_value(key: str) -> Question:
    return Question(
        kind="noul",
        instructions=(
            f"Judging `candidates.{key}` against everything in `interests`, would it have real value for "
            "someone actively working on those interests — something worth knowing exists?"
        ),
        criteria={
            "true": f"`candidates.{key}` does something none of the owner's existing tools or sources "
                    "already cover, for at least one interest",
            "false": f"`candidates.{key}` only restates what is already common knowledge for these "
                     "interests, or serves something unrelated to all of them",
        },
    )


def scout_actionable(key: str) -> Question:
    return Question(
        kind="noul",
        instructions=(
            f"Could the owner act on `candidates.{key}` directly this week — sign up, subscribe, call it, "
            "or install it — without more research first?"
        ),
        criteria={
            "true": "signing up, subscribing or installing needs no more than an account or a URL",
            "false": "it needs approval, a waitlist, missing documentation, or is not usable yet",
        },
    )
