"""Eval: search.py's BM25 ranking sees a note's own headings, not just its first BODY_HEAD
(2000) characters of body.

Real failure (2026-09-24): `--ask "how were contrails solved"` against the real vault ranked a
note whose *title* happened to contain "solved" above
`04_Resources/John-Platt-Google-ERA-AI-for-Science-Latent-Space-2026.md`, whose only match —
the heading `## Result: contrails solved (the counterfactual problem ERA cracked)` — sits at
character 3512 of an 8341-character body, past the 2000-character window `Doc.__init__` used to
build the ranked text. `search.py` now also pulls every `#`-heading out of the *whole* body
(cheap: the file is already fully read for the BODY_HEAD slice) and weights it like the title.

Two phases:
1. mechanism — `Doc(...).text` (what BM25 actually scores) contains a term that appears only
   in a heading placed past BODY_HEAD, and not otherwise in the truncated body.
2. ranking   — reproduces the real shape: a long note whose only match is a late heading beats
   a short, otherwise-unrelated note whose title happens to contain the query terms. Skipped
   (not failed) if a `farsight` binary shadows the Python BM25 path for `search()`'s callers —
   this eval targets `search.py`'s own scorer, not the Rust engine's compiled binary.

Sandboxed: writes fixture notes under 04_Resources, so it runs against a throwaway copy.
"""
from __future__ import annotations

from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "search_heading_weight"

LATE_HEADING_NOTE = (
    "Filler introduction paragraph with no query terms at all, padding this note out past the "
    "old two-thousand-character truncation window so the heading below used to be invisible "
    "to the ranker entirely. " * 11 +
    "\n\n## Result: zzyzxquark solved (the counterfactual problem cracked)\n\n"
    "This section is what the note is actually about, and the only place the term appears."
)

# Mirrors the real distractor exactly: its title/heading carries the *common* query word
# ("solved") but never the rare, decisive one ("contrails" there, "zzyzxquark" here) — the
# target must win on the rare term's much higher idf, not merely on raw term count.
TITLE_MATCH_NOTE_BODY = (
    "A short, otherwise unrelated note about a completely different problem that was also "
    "solved a different way, with no connection to the target note's own subject at all."
)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import search

    problems: list[str] = []
    sandbox = None
    try:
        sandbox = make_sandbox(vault)
        target = sandbox / "04_Resources" / "Eval-Heading-Weight-Target.md"
        distractor = sandbox / "04_Resources" / "Eval-Heading-Weight-Solved-Distractor.md"
        target.write_text(f"# Eval Heading Weight Target\n\n{LATE_HEADING_NOTE}\n", encoding="utf-8")
        distractor.write_text(f"# Eval Heading Weight Solved Distractor\n\n{TITLE_MATCH_NOTE_BODY}\n", encoding="utf-8")

        # Phase 1: mechanism. The heading's term must be past BODY_HEAD in the raw body, and
        # must still show up in what Doc actually builds for scoring.
        body_only = target.read_text(encoding="utf-8")
        offset = body_only.lower().find("zzyzxquark")
        if offset < search.BODY_HEAD:
            problems.append(f"phase 1 fixture is wrong: 'zzyzxquark' appears at {offset}, not past BODY_HEAD={search.BODY_HEAD}")
        doc = search.Doc(target, sandbox, {})
        if "zzyzxquark" not in doc.text:
            problems.append("phase 1: a term that appears only in a late heading is absent from Doc.text — heading weighting is not wired up")

        # Phase 2: ranking, via search.py's own BM25 (bypasses any farsight binary, which has
        # its own compiled copy of this same fix in crates/farsight and is not rebuilt by this
        # eval — see eval_search_parity.py for the same convention).
        corpus = search.build_corpus(sandbox)
        scores = search.bm25_scores("how was zzyzxquark solved", corpus)
        t_score, d_score = scores.get(target.relative_to(sandbox).as_posix()), scores.get(distractor.relative_to(sandbox).as_posix())
        if t_score is None or d_score is None:
            problems.append(f"phase 2: expected both fixtures to score, got target={t_score} distractor={d_score}")
        elif t_score <= d_score:
            problems.append(f"phase 2: the note whose only match is a late heading ({t_score}) did not outrank "
                            f"the note matching only by title ({d_score})")
    finally:
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else
            "a late heading's terms reach Doc.text and outrank a title-only match, as the real contrails query needed"}
