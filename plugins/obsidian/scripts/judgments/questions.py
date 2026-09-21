"""Every question the distill judgments ask: wording only, no policy.

This file is data. Thresholds, gates, and what a probability leads to live in
`distill_judge.py` and `graph.py`; nothing here may mention a number, a threshold, or an
action to take. The `judgment-calibration` skill edits this file (and only this file)
when a disagreement traces back to wording, and bumps QUESTIONS_VERSION when it does.

Rules the wording follows (TypeSafe primitive docs):
- one narrow judgment per question; a high noul always means "yes, the condition holds";
- criteria describe concrete situations that separate the answers, not degrees;
- every choice has a way to say "none of these";
- state is referenced by backticked path; the eval checks each path exists.
"""
from __future__ import annotations

from judge import Question

QUESTIONS_VERSION = "2026-09-22.1"

# One-line meaning of each placement target, sent as `vault_map` so `para` can point at it.
VAULT_MAP = {
    "02_Projects": "active efforts with a specific outcome and an end; one subfolder per project, listed in `projects`",
    "03_Areas": "ongoing responsibilities with no end date, listed in `areas`",
    "04_Resources": "reference knowledge kept for future use, tied to no project or responsibility",
}

# Gloss per domain of the starter taxonomy in checks/tags.py. A vault with its own
# taxonomy replaces both together.
DOMAIN_GLOSS = {
    "ai-ml": "machine learning and language models themselves: training, inference, embeddings, retrieval quality, evaluation",
    "agent-systems": "software agents that plan and act: orchestration, tool use, memory, multi-agent coordination",
    "software-engineering": "building and running software: architecture, languages, testing, infrastructure, operations",
    "knowledge-management": "capturing, organizing and finding notes: vault structure, linking, search over personal knowledge",
    "productivity": "how a person plans and does work: routines, reviews, focus, task systems",
    "toolkit-meta": "this toolkit's own design, conventions, evals and maintenance",
}


def triage() -> Question:
    return Question(
        kind="choice",
        instructions="What kind of material is `capture`, judged by what a personal knowledge vault could keep from it?",
        criteria={
            "distill": "contains a transferable mechanism, argument or finding that is worth restating in the owner's own words",
            "quick-file": "reference material to look up later, such as a link list, spec, how-to or data table, with no idea of its own to restate",
            "discard-candidate": "an empty stub, a broken or truncated clip, pure promotion, or news that loses its value within weeks",
            "unclear": "none of the other descriptions fits, or the text is too short to tell",
        },
    )


def relevant(nid: str) -> Question:
    return Question(
        kind="noul",
        instructions=(
            f"Would a reader of a note written from the subject matter of `capture` be materially helped by a link to `notes.{nid}`? "
            "Judge what `capture` is about, not the collector's remarks in it about how it was gathered or should be processed."
        ),
        criteria={
            "true": f"`notes.{nid}` discusses the same mechanism, system or decision as the subject matter of `capture`",
            "false": (
                f"`notes.{nid}` only shares vocabulary, a broad topic area, or a folder with `capture`, "
                "or relates only to how captures are collected, named or processed"
            ),
        },
    )


def relation(nid: str) -> Question:
    return Question(
        kind="choice",
        instructions=(
            f"How does the subject matter of `capture` bear on what `notes.{nid}` already says? "
            "Ignore the collector's remarks in `capture` about how it was gathered or should be processed."
        ),
        criteria={
            "strengthens-passage": f"`notes.{nid}` contains a specific sentence or section that `capture` extends with new evidence, detail or an example",
            "contradicts-claim": f"`notes.{nid}` states a specific claim that `capture` says is false, outdated or overstated",
            "adjacent": "the two are about related subjects, but no single passage is extended or contradicted",
            "unrelated": "the two are about different subjects",
        },
    )


def covers(nid: str) -> Question:
    return Question(
        kind="noul",
        instructions=(
            f"Is `notes.{nid}` already a write-up of the same original work that `capture` was taken from, "
            f"even if the addresses in `notes.{nid}.source` and `capture.source_urls` differ?"
        ),
        criteria={
            "true": "the same article, talk, paper or thread: same author and title, or a mirror, repost or newsletter copy of it",
            "false": "a different work, even one on the same topic or by the same author",
        },
    )


def domain(name: str, subject: str = "capture") -> Question:
    """`subject` is the state path being classified: `capture` in a distill run, `note` in vault-lint."""
    return Question(
        kind="noul",
        instructions=f"Is `domains.{name}` a primary subject of `{subject}`, one the owner would look for it under?",
        criteria={
            "true": "it is mainly about this subject",
            "false": "the subject is absent, or only mentioned in passing as background or an example",
        },
    )


def para() -> Question:
    return Question(
        kind="choice",
        instructions="Where in the vault described by `vault_map` does a note written from `capture` belong?",
        criteria={
            "02_Projects": "it directly serves one of the named efforts in `projects`",
            "03_Areas": "it informs one of the ongoing responsibilities in `areas`",
            "04_Resources": "it is general reference knowledge that serves no listed project or responsibility in particular",
            "no-clear-home": "two of the other answers fit about equally well, or none fits",
        },
    )


def concept_vs_root() -> Question:
    return Question(
        kind="noul",
        instructions="Is `capture` about one named, reusable concept or mechanism that other notes could link to as a building block?",
        criteria={
            "true": "a single idea with one thesis, drawn from one primary source",
            "false": "a survey, digest, thread with several voices, tool write-up, or a paper-specific summary",
        },
    )


def adds(a: str, b: str) -> Question:
    """Pairwise uniqueness, asked in both directions. High = `a` has something `b` lacks."""
    return Question(
        kind="noul",
        instructions=f"Does `captures.{a}` contribute at least one mechanism, finding or example that `captures.{b}` does not contain?",
        criteria={
            "true": f"there is a nameable idea that appears only in `captures.{a}`",
            "false": f"everything substantive in `captures.{a}` also appears in `captures.{b}`",
        },
    )


def should_link(pid: str) -> Question:
    """gaiafield adjudication: would a link between two notes help a reader?

    Worded after the vault's own human-made links, not after "same mechanism": on the bundled
    vault that narrower wording scored real, author-made links at a mean of 0.24 and rejected
    most of them (calibration log, 2026-09-22)."""
    return Question(
        kind="noul",
        instructions=(
            f"Would a link between `pairs.{pid}.a` and `pairs.{pid}.b` help a reader, because understanding "
            "or using one of them genuinely draws on the other?"
        ),
        criteria={
            "true": (
                "one explains, implements, applies, extends or is a worked example of something the other "
                "discusses, or someone working from one would need the other"
            ),
            "false": "they only share vocabulary, a broad subject area, a document type or a folder, and neither draws on the other",
        },
    )


def same_mechanism(pid: str) -> Question:
    """The narrower companion of should_link(): are the two notes about the same idea? Asked
    in the same request. Its absolute values run low (real matches average about 0.25), so
    it is read as a ranking and against its own low cut, never against should_link()'s."""
    return Question(
        kind="noul",
        instructions=(
            f"Do `pairs.{pid}.a` and `pairs.{pid}.b` describe the same underlying mechanism, skill or decision, "
            "so that a reader of one should be pointed to the other?"
        ),
        criteria={
            "true": "both notes explain or apply the same idea, even in different subject areas",
            "false": "they share vocabulary, a domain or a document style, but explain different things",
        },
    )


def description_specific(nid: str) -> Question:
    """vault quality: does a note's description earn its place in search and in Index.md?"""
    return Question(
        kind="noul",
        instructions=(
            f"Does `notes.{nid}.description` tell a reader specifically what `notes.{nid}.body_head` is about, "
            "well enough to pick this note out from others on nearby subjects?"
        ),
        criteria={
            "true": "it names the note's actual subject and its main point in plain terms",
            "false": (
                "it is missing, generic enough to fit many notes, about something the body does not cover, "
                "or so long and padded that the subject is buried"
            ),
        },
    )
