"""Does a capture's saved text actually carry the content its title and source promise?

Reader sometimes saves something else at the right address: a sign-up wall, a 404, or (real
example, 2026-09-24) 16 KB of an unrelated LinkedIn feed behind a treg.to docs link. Ingest
already marks a short wall `content: stub` before this ever reaches a model
(plugins/readwise/scripts/build_captures.py) — that shortcut is honoured here without a call.
What that miss can't catch is a *long* wrong page, and any capture ingested before the stub
fix existed; both need the model to actually read the text.

When the verdict isn't `ok`, the triage block's discard score judged this same wrong text, not
the article — distill_judge.judge_capture folds a note saying so into `triage.note`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import judge
from judgments import questions as Q
from judgments.capture import full_text_section, read_capture
from vault_utils import read_frontmatter

FULL_TEXT_CHARS = 4000


def judge_content(path: Path, vault: Path) -> tuple[dict[str, Any], judge.Usage | None]:
    """(content block, usage or None). `usage` is None exactly when no model call was made
    (the frontmatter shortcut, or nothing left to judge after the header) — the caller folds
    it into the capture's own usage total only when it isn't."""
    fm, body = read_frontmatter(path)
    if str(fm.get("content") or "").strip().lower() == "stub":
        return {"verdict": "stub", "p": 1.0, "source": "frontmatter",
                "note": "ingest marked this a stub (a sign-up wall, a 404 or an empty page): "
                        "the triage score above judged that page, not the article"}, None
    capture = read_capture(path)
    text = full_text_section(body)[:FULL_TEXT_CHARS]
    if not text:
        return {"verdict": "stub", "p": 1.0, "source": "empty",
                "note": "no text after the capture's own header: the triage score above judged an empty page"}, None
    state = {"capture": {"title": capture["title"], "own_source": capture["own_source"] or "(none)", "full_text": text}}
    answers, usage = judge.judge(vault, state, {"content": Q.content_match()})
    a = answers.get("content")
    if a is None:
        return {"verdict": None, "p": None, "source": "judged", "note": "backend answered nothing for this question"}, usage
    verdict, p = a.top, round(a.probs.get(a.top, 0.0), 3)
    note = "" if verdict == "ok" else (
        f"content judged {verdict} (p={p}): the triage score above judged what was actually saved, not the "
        "promised article — ignore it; fetch the source before distilling (SKILL.md, 'A stub is not the content')")
    return {"verdict": verdict, "p": p, "probs": {k: round(v, 3) for k, v in a.probs.items()},
            "source": "judged", "note": note}, usage
