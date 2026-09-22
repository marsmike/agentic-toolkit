"""Passages of a capture: which carry its substance, how the pipeline's synthesis relates to
the article, and whether a written note carries what was kept (the preservation check)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import judge
from judge import JudgmentFailed, Question
from vault_utils import read_frontmatter

from judgments import questions as Q
from judgments.capture import HEADER_LINE_RE, read_capture
from judgments.policy import thresholds
from judgments.state import in_chunks

MAX_PASSAGES = 200        # a 300 KB report is about 200 paragraphs; judged in chunks of 12

MIN_PASSAGE_CHARS = 60

PASSAGE_CHARS = 1200      # per passage on the wire

SOURCE_TEXT_CHARS = 12000  # of the article itself, for the summary-faithfulness check

FULL_CAPTURE_CHARS = 400000

SUMMARY_HEADINGS = ("synthesis", "readwise summary", "summary", "tl;dr")

def split_passages(body: str) -> tuple[list[str], str | None, str]:
    """(passages, summary section text or None, source text). Paragraphs are blank-line
    separated; the capture pipeline's header lines are dropped; a section headed Synthesis /
    Summary is returned separately so its faithfulness can be checked against the rest."""
    passages, summary, source_parts = [], [], []
    section = None
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            section = block.lstrip("# ").strip().lower()
            continue
        if HEADER_LINE_RE.match(block) or len(block) < MIN_PASSAGE_CHARS:
            continue
        is_summary = section is not None and any(section.startswith(h) for h in SUMMARY_HEADINGS)
        (summary if is_summary else source_parts).append(block)
        passages.append(block)
    return passages[:MAX_PASSAGES], ("\n\n".join(summary) or None), "\n\n".join(source_parts)[:SOURCE_TEXT_CHARS]

def judge_passages(path: Path, vault: Path) -> dict[str, Any]:
    """Which passages of a capture carry its substance, and is its summary faithful to the source.
    The essence is what a distilling agent reads first; the rest is there if it wants it."""
    capture = read_capture(path)
    _, full_body = read_frontmatter(path)  # the whole capture, not the judged-candidate cap
    passages, summary, source = split_passages(full_body.strip()[:FULL_CAPTURE_CHARS])
    state: dict[str, Any] = {"capture_title": capture["title"], "passages": {f"P{i:02d}": p[:PASSAGE_CHARS] for i, p in enumerate(passages, start=1)}}
    questions: dict[str, Question] = {}
    for pid in state["passages"]:
        questions[f"keep_{pid}"] = Q.passage_keep(pid)
        questions[f"pipe_{pid}"] = Q.passage_pipeline(pid)
    if summary and source:
        state["summary"], state["source_text"] = summary[:3000], source
        questions["relation"] = Q.summary_relation()
        questions["reverses"] = Q.summary_reverses()
    if not questions:
        cfg = judge.load_config(vault)
        empty_usage = judge.Usage(backend=cfg["backend"], model=cfg["model"])
        return {"capture": path.name, "passages": [], "essence_chars": 0, "total_chars": len(capture["body"]),
                "judgment": empty_usage.as_dict()}
    usages = []

    def ask(chunk, start):
        sub_state = {k: v for k, v in state.items() if k != "passages"}
        sub_state["passages"] = {pid: state["passages"][pid] for pid in chunk}
        sub_q = {qid: qq for qid, qq in questions.items() if qid[5:] in chunk or (qid in ("relation", "reverses") and start == 0)}
        raw, used = judge.judge(vault, sub_state, sub_q)
        usages.append(used)
        return raw

    answers = in_chunks(list(state["passages"]), 12, ask)
    if not usages:
        # Every chunk hit judge.StateTooLarge all the way down to a single passage and still
        # failed: in_chunks() degrades that to {} rather than raising, so nothing here ever
        # called judge.judge() successfully.
        raise JudgmentFailed("passage state exceeded the backend's size limit, even alone")
    t = thresholds(usages[0].backend)
    rows, essence = [], 0
    for pid, text in state["passages"].items():
        keep, pipe = answers.get(f"keep_{pid}"), answers.get(f"pipe_{pid}")
        kept = keep is not None and keep.p >= t["T_KEEP"]
        essence += len(text) if kept else 0
        rows.append({"id": pid, "keep": kept, "p_keep": round(keep.p, 3) if keep else None,
                     "p_pipeline": round(pipe.p, 3) if pipe else None, "head": text[:100]})
    relation, reverses = answers.get("relation"), answers.get("reverses")
    warning = (reverses is not None and reverses.p >= t["T_REVERSES"]) or (relation is not None and relation.top in ("misstates", "overstates"))
    usage = usages[0]
    for extra in usages[1:]:
        usage.requests += extra.requests
        usage.input_tokens += extra.input_tokens
        usage.usd += extra.usd
        usage.splits += extra.splits
        usage.skipped.extend(extra.skipped)
    return {"capture": path.name, "passages": rows, "essence_chars": essence, "total_chars": sum(len(p) for p in state["passages"].values()),
            "summary_relation": relation.top if relation else None, "p_reverses": round(reverses.p, 3) if reverses else None,
            "summary_warning": warning,
            "essence_text": "\n\n".join(state["passages"][r["id"]] for r in rows if r["keep"]),
            "judgment": usage.as_dict()}

def check_note(note: Path, capture: Path, vault: Path) -> dict[str, Any]:
    ps = judge_passages(capture, vault)
    kept = [r for r in ps["passages"] if r["keep"]]
    _, body = read_frontmatter(note)
    _, full_body = read_frontmatter(capture)
    passages, _, _ = split_passages(full_body.strip()[:FULL_CAPTURE_CHARS])
    text_of = {f"P{i:02d}": p[:PASSAGE_CHARS] for i, p in enumerate(passages, start=1)}
    usages = [judge.Usage(backend=ps["judgment"]["backend"], model=ps["judgment"]["model"], requests=ps["judgment"]["requests"],
                          input_tokens=ps["judgment"]["input_tokens"], usd=ps["judgment"]["usd"],
                          splits=ps["judgment"]["splits"], skipped=list(ps["judgment"]["skipped"]))]

    def ask(chunk, start):
        state = {"note": body[:30000], "passages": {r["id"]: text_of[r["id"]] for r in chunk}}
        questions = {f"carried_{r['id']}": judge.Question(
            "noul", f"Does `note` carry the substance of `passages.{r['id']}`: the same claim, number, mechanism or example, in any wording?",
            {"true": "a reader of the note would learn what that passage says, including its specific",
             "false": "the passage's specific is absent from the note, or only a vaguer version is there"}) for r in chunk}
        got, used = judge.judge(vault, state, questions)
        usages.append(used)
        return got

    answers = in_chunks(kept, 12, ask) if kept else {}
    t = thresholds(usages[0].backend)
    misses = [{"id": r["id"], "p_carried": round(answers[f"carried_{r['id']}"].p, 3), "text": text_of[r["id"]][:300]}
              for r in kept if f"carried_{r['id']}" in answers and answers[f"carried_{r['id']}"].p < t["T_KEEP"]]
    usage = usages[0]
    for extra in usages[1:]:
        usage.requests += extra.requests
        usage.input_tokens += extra.input_tokens
        usage.usd += extra.usd
        usage.splits += extra.splits
        usage.skipped.extend(extra.skipped)
    return {"note": note.as_posix(), "capture": capture.name, "kept_passages": len(kept), "carried": len(kept) - len(misses),
            "misses": misses, "judgment": usage.as_dict()}
