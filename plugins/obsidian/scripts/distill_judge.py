#!/usr/bin/env python3
"""Advisory judgments for a distill run — one block per capture, nothing applied.

    uv run scripts/distill_judge.py 01_Capture/Some-Capture.md --json
    uv run scripts/distill_judge.py 01_Capture/*.md                    # batch: adds pairwise uniqueness
    uv run scripts/distill_judge.py --calibrate GOLDEN.json            # agreement against labelled rows
    uv run scripts/distill_judge.py 01_Capture/*.md --emit-golden-skeleton

For each capture this asks a typed-judgment backend (judge.py) one request's worth of
narrow questions over shared state: what kind of material it is, which found notes are
really related and how, whether an existing note already covers the same source, which
domains it is about, and where it belongs. A batch adds one request of pairwise "does A
add anything B lacks".

Everything printed is advisory input to the distill skill's Phase 1 handoff
(skills/distill/references/workflow.md). This script writes nothing to the vault except a
dead-letter note when a configured backend fails outright. No backend or no key is the
normal pre-adoption state: the block says SKIPPED and the skill proceeds as before.

Question wording lives in judgments/questions.py. Policy (thresholds and what they lead
to) lives here, keyed by backend because only a calibrated backend's numbers transfer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import judge
from judge import Answer, JudgmentFailed, JudgmentUnavailable, Question
from judgments import questions as Q
from judgments.state import domain_glosses, in_chunks, note_payload
from search import search
from search_judge import expand
from vault_utils import discover_notes, read_frontmatter, require_vault, write_dlq_note

CAPTURE_CHARS = 6000
BATCH_CAPTURE_CHARS = 2000
MAX_BATCH = 12  # captures per full pairwise request; above that, pairs are blocked first
PAIR_BLOCK_JACCARD = 0.34  # title-token overlap at or above: a pair worth judging
NEAR_IDENTICAL = 0.85      # body similarity at or above (difflib, first 6000 chars): a duplicate, decided without a model
QUERY_BODY_CHARS = 600
MAX_LISTED_FOLDERS = 60
NOTES_PER_REQUEST = 8  # candidate notes per request; the capture rides along in each. A real
# vault's capture plus 40 widened candidates exceeded the backend's input limit (2026-09-22).
MAX_CANDIDATES = 24
# Requests per capture; an even number also asks with the candidate notes in reverse order and
# averages. Left at 1: measured 2026-09-22, an identical rerun moves a noul by 0.008 on average
# (max 0.09) and two views by 0.006, with golden agreement unchanged (54/60 vs 55/60). Unlike
# the pairwise link question there is no order effect worth paying a second request for.
VIEWS = 1

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
    },
}

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
MAX_PASSAGES = 200        # a 300 KB report is about 200 paragraphs; judged in chunks of 12
MIN_PASSAGE_CHARS = 60
PASSAGE_CHARS = 1200      # per passage on the wire
SOURCE_TEXT_CHARS = 12000  # of the article itself, for the summary-faithfulness check
FULL_CAPTURE_CHARS = 400000
SUMMARY_HEADINGS = ("synthesis", "readwise summary", "summary", "tl;dr")
LEVEL_BY_RELATION = {"strengthens-passage": "L2", "contradicts-claim": "L3", "adjacent": "L1", "unrelated": None}


# ---------------------------------------------------------------------------
# Reading captures and notes
# ---------------------------------------------------------------------------


TRACKING_PARAMS = {"is", "si", "feature", "t", "ref", "source", "fbclid", "gclid", "igshid", "s", "mc_cid", "mc_eid"}


def _canonical(url: str) -> str:
    """Same address, same key: lower-cased host, no scheme/www, tracking parameters dropped
    (utm_*, share ids), fragment dropped, trailing slash dropped. [earned: 2026-09-22 — Reader
    held one video twice under URLs differing only by `&is=`]"""
    u = url.strip().rstrip("/.,;")
    u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I)
    u, _, _ = u.partition("#")
    path, _, query = u.partition("?")
    keep = []
    for part in query.split("&"):
        key = part.split("=", 1)[0].lower()
        if part and key not in TRACKING_PARAMS and not key.startswith("utm_"):
            keep.append(part)
    return (path.lower().rstrip("/") + ("?" + "&".join(sorted(keep)) if keep else ""))


def _h1_or_stem(body: str, path: Path) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


HEADER_LINE_RE = re.compile(r"^\s*\*\*(Source|Author|Saved|Captured|Origin|Published|URL)\s*:?\*\*\s*:?", re.I)


def query_text(capture: dict) -> str:
    """What search sees for a capture: title, description, and the first content lines with
    the capture pipeline's own header (**Source:** … **Saved:** …) and bare URLs stripped.
    [earned: 2026-09-22 replay — a Readwise capture's first 400 chars were all header, and the
    note that mattered ranked #2 on a clean query and nowhere on the boilerplate one]"""
    lines = [ln for ln in capture["body"].splitlines() if ln.strip() and not HEADER_LINE_RE.match(ln) and not ln.startswith("# ")]
    content = URL_RE.sub(" ", " ".join(lines))
    return " ".join([capture["title"], capture["description"], content[:QUERY_BODY_CHARS]])


def read_capture(path: Path) -> dict[str, Any]:
    fm, body = read_frontmatter(path)
    urls = [str(fm["source"])] if str(fm.get("source") or "").startswith("http") else []
    urls += [u for u in URL_RE.findall(body) if u not in urls]
    return {
        "title": _h1_or_stem(body, path),
        "description": str(fm.get("description") or ""),
        "own_source": str(fm["source"]) if str(fm.get("source") or "").startswith("http") else "",
        "source_urls": urls[:20],
        "body": body.strip()[:CAPTURE_CHARS],
    }


def url_hits(capture: dict, vault: Path, exclude: list[str]) -> dict[str, str]:
    """workflow.md step 2, in Python: {note rel path: origin} for every active note that
    mentions one of the capture's URLs. Only a note whose `source:` is the capture's *own*
    source (its frontmatter URL) is "frontmatter", i.e. provenance; a note whose source is a
    URL the capture merely links in its body is "body-cited", and a note that mentions a
    capture URL in prose is "body". [earned: 2026-09-22 acceptance run — a capture linking
    an example tool made that tool's note read as the capture's canonical distillation]"""
    own = {_canonical(capture["own_source"])} if capture.get("own_source") else set()
    cited = {_canonical(u) for u in capture["source_urls"]} - own
    hits: dict[str, str] = {}
    if not own and not cited:
        return hits
    for path in discover_notes(vault, exclude=exclude):
        fm, body = read_frontmatter(path)
        rel = path.relative_to(vault).as_posix()
        src = _canonical(str(fm.get("source") or ""))
        if src and src in own:
            hits[rel] = "frontmatter"
        elif src and src in cited:
            hits[rel] = "body-cited"
        elif any(_canonical(u) in own | cited for u in URL_RE.findall(body)):
            hits[rel] = "body"
    return hits


def _subfolders(vault: Path, para: str) -> list[str]:
    root = vault / para
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))[:MAX_LISTED_FOLDERS]


def _excluded(rel: str, exclude: list[str]) -> bool:
    return any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in exclude)


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")


def cited_notes(capture: dict, vault: Path) -> list[str]:
    """Notes the capture itself names with a wikilink (a Readwise capture often carries the
    pipeline's own cross-references). [earned: 2026-09-22 replay on a real vault — the strongest
    L2 target for one capture was reachable only through the capture's in-text citations]"""
    by_stem: dict[str, str] = {}
    for path in discover_notes(vault):
        by_stem.setdefault(path.stem, path.relative_to(vault).as_posix())
    return [by_stem[t.strip().split("/")[-1]] for t in WIKILINK_RE.findall(capture["body"]) if t.strip().split("/")[-1] in by_stem]


def candidates(capture: dict, vault: Path, top: int, exclude: list[str], force: list[str]) -> tuple[list[dict], dict]:
    """Search results widened by their neighbours, the notes the capture cites, every URL hit,
    and any path the caller forces in (calibration). On a large vault the right note is often
    at search rank 8-12, so `top` is the *judged* count and search runs a little deeper."""
    found = search(query_text(capture), vault, top=max(top, 12))
    hits = url_hits(capture, vault, exclude)
    for rel in cited_notes(capture, vault):
        hits.setdefault(rel, "cited")
    rows: dict[str, dict] = {}
    # Search hits, then the notes those hits link to (deterministic, free): the answer to
    # "which existing note is this capture really about" is often one link away from the
    # note the keywords land on. Judged the same way; only the origin differs.
    for r in expand(found["results"], vault):
        rows[r["path"]] = {"search_score": r.get("score"), "above_enrichment_gate": r.get("above_enrichment_gate"),
                           "via": r.get("via")}
    for rel in [*hits, *force]:
        rows.setdefault(rel, {"search_score": None, "above_enrichment_gate": None, "via": None})
    out = []
    for rel, extra in rows.items():
        path = vault / rel
        if _excluded(rel, exclude) or not path.is_file():
            continue
        out.append({**note_payload(path, vault), **extra, "url_hit": hits.get(rel)})
    meta = {"score_gate": found.get("score_gate"), "note": found.get("note", "")}
    return out, meta


# ---------------------------------------------------------------------------
# Questions + policy for one capture
# ---------------------------------------------------------------------------


def build_request(capture: dict, notes: list[dict], vault: Path, first: int = 0,
                  capture_questions: bool = True) -> tuple[dict, dict[str, Question], dict[str, str]]:
    """(state, questions, qid -> stable key) for `notes`, numbered from `first + 1`. Stable
    keys name notes by path, not by the per-run N01.. ids, so a golden file survives a change
    in search order. Capture-level questions (triage, placement, domains) go in one request
    only; the per-note questions are asked in chunks that each carry the capture again."""
    note_ids = {f"N{first + i:02d}": n for i, n in enumerate(notes, start=1)}
    state = {
        "capture": capture,
        "vault_map": Q.VAULT_MAP,
        "projects": _subfolders(vault, "02_Projects"),
        "areas": _subfolders(vault, "03_Areas"),
        "domains": domain_glosses(vault, Q.DOMAIN_GLOSS),
        "notes": {nid: {k: n[k] for k in ("title", "path", "description", "source", "body_head")} for nid, n in note_ids.items()},
    }
    questions: dict[str, Question] = {}
    stable: dict[str, str] = {}
    if capture_questions:
        questions.update({"triage": Q.triage(), "para": Q.para(), "concept_vs_root": Q.concept_vs_root()})
        stable.update({"triage": "triage", "para": "para", "concept_vs_root": "concept_vs_root"})
        for name in state["domains"]:
            questions[f"dom_{name}"] = Q.domain(name)
            stable[f"dom_{name}"] = f"dom|{name}"
    for nid, n in note_ids.items():
        for family, make in (("rel", Q.relevant), ("prin", Q.same_principle), ("relation", Q.relation), ("covers", Q.covers)):
            questions[f"{family}_{nid}"] = make(nid)
            stable[f"{family}_{nid}"] = f"{family}|{n['path']}"
    return state, questions, stable


def _probs(a: Answer | None) -> dict[str, float]:
    return {k: round(v, 3) for k, v in sorted(a.probs.items(), key=lambda kv: -kv[1])} if a else {}


def apply_policy(notes: list[dict], answers: dict[str, Answer], t: dict[str, float]) -> dict[str, Any]:
    """Turn probabilities into advisory suggestions. The only place thresholds are read."""
    triage = answers.get("triage")
    triage_top = triage.top if triage and triage.top != "unclear" and triage.probs[triage.top] >= t["T_TRIAGE"] else None

    related = []
    for i, n in enumerate(notes, start=1):
        nid = f"N{i:02d}"
        rel, relation, covers = answers.get(f"rel_{nid}"), answers.get(f"relation_{nid}"), answers.get(f"covers_{nid}")
        prin = answers.get(f"prin_{nid}")
        by_topic = rel is not None and rel.p >= t["T_RELEVANT"]
        by_principle = prin is not None and prin.p >= t["T_PRINCIPLE"]
        judged = by_topic or by_principle
        level = None
        if judged and relation is not None:
            sure = relation.probs.get(relation.top, 0.0) >= t["T_UPGRADE"]
            level = LEVEL_BY_RELATION.get(relation.top) if sure else "L1"
            level = level or "L1"  # judged relevant but "unrelated" on top: still only a backlink
        related.append({
            "path": n["path"], "title": n["title"], "search_score": n["search_score"], "via": n.get("via"),
            "above_enrichment_gate": n["above_enrichment_gate"], "url_hit": n["url_hit"],
            "p_relevant": round(rel.p, 3) if rel else None, "p_principle": round(prin.p, 3) if prin else None,
            "judged_relevant": judged, "bridge": by_principle and not by_topic,
            "relation": relation.top if relation else None, "relation_probs": _probs(relation),
            "suggested_level": level,
            "p_covers": round(covers.p, 3) if covers else None,
        })
    related.sort(key=lambda r: -max(r["p_relevant"] or 0.0, r["p_principle"] or 0.0))

    canonical = [r["path"] for r in related if r["url_hit"] == "frontmatter"]  # "cited" and "body" are not provenance
    covering = [r["path"] for r in related if (r["p_covers"] or 0.0) >= t["T_COVERS"] and r["path"] not in canonical]
    body_hit = [r["path"] for r in related if r["url_hit"] in ("body", "body-cited")]
    if canonical:
        mode = "enrich-only"  # deterministic: the source URL is already a note's provenance
    elif covering:
        mode = "hybrid?" if body_hit else "enrich-only?"
    else:
        mode = "new-note"

    domains = sorted(
        ((qid[4:], a.p) for qid, a in answers.items() if qid.startswith("dom_")), key=lambda kv: -kv[1],
    )
    picked = [(n, p) for n, p in domains if p >= t["T_DOMAIN"]][:3]

    para, concept = answers.get("para"), answers.get("concept_vs_root")
    ambiguous = para is None or para.top == "no-clear-home" or para.margin() < t["T_PLACEMENT_MARGIN"]
    folder = None if ambiguous else para.top
    if folder == "04_Resources" and concept is not None and concept.p >= 0.5:
        folder = "04_Resources/Concepts"
    # Soft placement: a runner-up that holds real mass is not noise, it is a second home the
    # note may deserve a link from (the "block on the distribution, not the label" lesson).
    alternatives = [
        {"folder": label, "p": round(p, 3)} for label, p in sorted(para.probs.items(), key=lambda kv: -kv[1])[1:]
        if label != "no-clear-home" and p >= t["T_SECOND_HOME"]
    ] if para is not None else []

    return {
        "triage": {"recommendation": triage_top, "probs": _probs(triage),
                   "note": "discard-candidate is never applied automatically" if triage_top == "discard-candidate" else ""},
        "related": related,
        "already_distilled": {"suggested_mode": mode, "canonical_by_url": canonical, "covers": covering, "url_in_body": body_hit},
        "domains": {"picked": [{"domain": n, "p": round(p, 3)} for n, p in picked],
                    "low_confidence_top": None if picked or not domains else {"domain": domains[0][0], "p": round(domains[0][1], 3)}},
        "placement": {"folder": folder, "ambiguous": ambiguous, "alternatives": alternatives, "probs": _probs(para),
                      "p_single_concept": round(concept.p, 3) if concept else None,
                      "note": "ambiguous: follow rules.md and record a DLQ note if it stays 50/50" if ambiguous else ""},
    }


def _average(views: list[dict[str, Answer]]) -> dict[str, Answer]:
    """Mean of several answers to the same stable-keyed questions (noul p; choice probs per label)."""
    merged: dict[str, Answer] = {}
    for key in {k for view in views for k in view}:
        seen = [view[key] for view in views if key in view]
        if seen[0].kind == "noul":
            merged[key] = Answer("noul", p=sum(a.p for a in seen) / len(seen))
        else:
            labels = {label for a in seen for label in a.probs}
            probs = {label: sum(a.probs.get(label, 0.0) for a in seen) / len(seen) for label in labels}
            merged[key] = Answer("choice", probs=probs, top=max(probs, key=probs.get))
    return merged


def judge_capture(path: Path, vault: Path, top: int, exclude: list[str], force: list[str] | None = None,
                  views: int = VIEWS) -> dict[str, Any]:
    capture = read_capture(path)
    notes, search_meta = candidates(capture, vault, top, exclude, force or [])
    # Forced and URL-hit notes are never dropped by the cap; search rows after them are.
    pinned = [n for n in notes if n.get("url_hit") or n["path"] in (force or [])]
    notes = (pinned + [n for n in notes if n not in pinned])[:MAX_CANDIDATES]
    per_view, usages = [], []
    for view in range(views):
        ordered = notes if view % 2 == 0 else notes[::-1]
        def ask(chunk, start):
            state, questions, stable = build_request(capture, chunk, vault, first=start, capture_questions=(start == 0))
            raw, used = judge.judge(vault, state, questions)
            usages.append(used)
            return {stable[qid]: a for qid, a in raw.items()}

        per_view.append(in_chunks(ordered, NOTES_PER_REQUEST, ask) if ordered else ask([], 0))
    by_key = _average(per_view)
    # apply_policy() reads per-run ids in the order of `notes`; rebuild that view from the averages.
    stable = {}
    for c in range(0, len(notes), NOTES_PER_REQUEST):
        stable.update(build_request(capture, notes[c:c + NOTES_PER_REQUEST], vault, first=c, capture_questions=(c == 0))[2])
    answers = {qid: by_key[key] for qid, key in stable.items() if key in by_key}
    usage = usages[0]
    for extra in usages[1:]:
        usage.requests += extra.requests
        usage.input_tokens += extra.input_tokens
        usage.usd += extra.usd
        usage.splits += extra.splits
        usage.skipped.extend(extra.skipped)
    block = {"capture": path.relative_to(vault).as_posix() if path.is_relative_to(vault) else str(path), "advisory": True,
             "questions_version": Q.QUESTIONS_VERSION, "search": search_meta}
    block.update(apply_policy(notes, answers, thresholds(usage.backend)))
    block["judgment"] = {**usage.as_dict(), "views": views}
    block["answers"] = {stable[qid]: (round(a.p, 4) if a.kind == "noul" else _probs(a)) for qid, a in answers.items()}
    return block


def thresholds(backend: str) -> dict[str, float]:
    if backend not in THRESHOLDS:
        raise SystemExit(f"no threshold table for judgment backend {backend!r}; calibrate one before using it")
    return THRESHOLDS[backend]


# ---------------------------------------------------------------------------
# Batch: pairwise uniqueness (rules.md, cluster uniqueness gate)
# ---------------------------------------------------------------------------


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
        return {"capture": path.name, "passages": [], "essence_chars": 0, "total_chars": len(capture["body"])}
    usages = []

    def ask(chunk, start):
        sub_state = {k: v for k, v in state.items() if k != "passages"}
        sub_state["passages"] = {pid: state["passages"][pid] for pid in chunk}
        sub_q = {qid: qq for qid, qq in questions.items() if qid[5:] in chunk or (qid in ("relation", "reverses") and start == 0)}
        raw, used = judge.judge(vault, sub_state, sub_q)
        usages.append(used)
        return raw

    answers = in_chunks(list(state["passages"]), 12, ask)
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
    return {"capture": path.name, "passages": rows, "essence_chars": essence, "total_chars": sum(len(p) for p in state["passages"].values()),
            "summary_relation": relation.top if relation else None, "p_reverses": round(reverses.p, 3) if reverses else None,
            "summary_warning": warning,
            "essence_text": "\n\n".join(state["passages"][r["id"]] for r in rows if r["keep"]),
            "judgment": usage.as_dict()}


def _title_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in ("the", "and", "for", "with", "how", "why", "what")}


def candidate_pairs(caps: dict[str, dict]) -> list[tuple[str, str]]:
    """Which capture pairs are worth a uniqueness judgment. Up to MAX_BATCH captures, all of
    them. Above that, cheap blocking: the same own source, a shared URL, or title-token
    overlap at or above PAIR_BLOCK_JACCARD. [earned: 2026-09-22 acceptance run — the batch
    judged only the first twelve of 81 captures and missed a video Reader held twice]"""
    ids = list(caps)
    if len(ids) <= MAX_BATCH:
        return [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ca, cb = caps[a], caps[b]
            same_source = ca["own_source"] and _canonical(ca["own_source"]) == _canonical(cb["own_source"])
            shared_url = bool(set(map(_canonical, ca["source_urls"])) & set(map(_canonical, cb["source_urls"])))
            ta, tb = _title_tokens(ca["title"]), _title_tokens(cb["title"])
            jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
            if same_source or shared_url or jac >= PAIR_BLOCK_JACCARD:
                out.append((a, b))
    return out


def judge_batch(paths: list[Path], vault: Path, refs: list[str] | None = None) -> dict[str, Any]:
    """Pairwise uniqueness over a batch. `refs` name the captures in the output (default: file
    names); golden files pass their own. Pairs are asked in both directions, in chunks that
    carry only the captures they need."""
    ids = {f"C{i:02d}": p for i, p in enumerate(paths, start=1)}
    caps = {cid: read_capture(p) for cid, p in ids.items()}
    names = {cid: (refs[i] if refs else p.name) for i, (cid, p) in enumerate(ids.items())}
    pairs_to_ask = candidate_pairs(caps)
    usages: list = []

    def ask(chunk, start):
        members = sorted({c for pair in chunk for c in pair})
        state = {"captures": {c: {"title": caps[c]["title"], "description": caps[c]["description"],
                                  "body": caps[c]["body"][:BATCH_CAPTURE_CHARS]} for c in members}}
        questions = {}
        for a, b in chunk:
            questions[f"adds_{a}_{b}"] = Q.adds(a, b)
            questions[f"adds_{b}_{a}"] = Q.adds(b, a)
        got, used = judge.judge(vault, state, questions)
        usages.append(used)
        return got

    # Reader holding one item twice is a fact, not a judgment: the same own source address, or
    # near-identical text, settles the pair without a model call.
    identical = {}
    for a, b in pairs_to_ask:
        same_source = caps[a]["own_source"] and _canonical(caps[a]["own_source"]) == _canonical(caps[b]["own_source"])
        if same_source:
            identical[(a, b)] = "same source"
            continue
        ratio = SequenceMatcher(None, caps[a]["body"][:6000], caps[b]["body"][:6000]).quick_ratio()
        if ratio >= NEAR_IDENTICAL and SequenceMatcher(None, caps[a]["body"][:6000], caps[b]["body"][:6000]).ratio() >= NEAR_IDENTICAL:
            identical[(a, b)] = round(ratio, 3)
    pairs_to_ask = [pr for pr in pairs_to_ask if pr not in identical]
    answers = in_chunks(pairs_to_ask, 6, ask) if pairs_to_ask else {}
    dup_rows = [{"a": names[a], "b": names[b], "a_adds": None, "b_adds": None, "verdict": "duplicate",
                 "adds_nothing": [names[b]], "similarity": r} for (a, b), r in identical.items()]
    if not usages:
        return {"cluster": dup_rows, "judgment": {}, "answers": {}, "pairs_considered": len(identical), "captures": len(paths),
                "blocked": len(paths) > MAX_BATCH}
    usage = usages[0]
    for extra in usages[1:]:
        usage.requests += extra.requests
        usage.input_tokens += extra.input_tokens
        usage.usd += extra.usd
    t = thresholds(usage.backend)
    pairs, raw = list(dup_rows), {}
    for a, b in pairs_to_ask:
        ab, ba = answers.get(f"adds_{a}_{b}"), answers.get(f"adds_{b}_{a}")
        if ab is None or ba is None:
            continue
        raw[f"adds|{names[a]}|{names[b]}"] = round(ab.p, 4)
        raw[f"adds|{names[b]}|{names[a]}"] = round(ba.p, 4)
        redundant = [names[x] for x, ans in ((a, ab), (b, ba)) if 1 - ans.p >= t["T_REDUNDANT"]]
        pairs.append({"a": names[a], "b": names[b], "a_adds": round(ab.p, 3), "b_adds": round(ba.p, 3),
                      "verdict": "merge-candidate" if redundant else "distinct", "adds_nothing": redundant})
    return {"cluster": pairs, "judgment": usage.as_dict(), "answers": raw,
            "pairs_considered": len(pairs_to_ask) + len(identical), "captures": len(paths),
            "blocked": len(paths) > MAX_BATCH}


# ---------------------------------------------------------------------------
# Preservation check: does a note carry the substance of a capture's kept passages?
# ---------------------------------------------------------------------------


def check_note(note: Path, capture: Path, vault: Path) -> dict[str, Any]:
    ps = judge_passages(capture, vault)
    kept = [r for r in ps["passages"] if r["keep"]]
    _, body = read_frontmatter(note)
    _, full_body = read_frontmatter(capture)
    passages, _, _ = split_passages(full_body.strip()[:FULL_CAPTURE_CHARS])
    text_of = {f"P{i:02d}": p[:PASSAGE_CHARS] for i, p in enumerate(passages, start=1)}
    usages = [judge.Usage(backend=ps["judgment"]["backend"], model=ps["judgment"]["model"], requests=ps["judgment"]["requests"],
                          input_tokens=ps["judgment"]["input_tokens"], usd=ps["judgment"]["usd"])]

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
    return {"note": note.as_posix(), "capture": capture.name, "kept_passages": len(kept), "carried": len(kept) - len(misses),
            "misses": misses, "judgment": usage.as_dict()}


# ---------------------------------------------------------------------------
# Golden file: calibration and skeleton
# ---------------------------------------------------------------------------


def _decide(key: str, value: Any, t: dict[str, float]) -> Any:
    """The hard label policy would read off one raw answer."""
    family = key.split("|", 1)[0]
    if isinstance(value, dict):
        return max(value, key=value.get) if value else None
    cut = {"rel": t["T_RELEVANT"], "prin": t["T_PRINCIPLE"], "covers": t["T_COVERS"], "dom": t["T_DOMAIN"], "adds": 1 - t["T_REDUNDANT"]}.get(family, 0.5)
    return value >= cut


def _resolve_capture(ref: str, vault: Path, base: Path | None) -> Path:
    """A golden row names a capture in the vault (`01_Capture/X.md`, or a bare file name
    under 01_Capture) or a fixture next to the golden file (`fixtures/captures/X.md`)."""
    for candidate in (vault / ref, vault / "01_Capture" / ref, *([base / ref] if base else [])):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"golden file names a capture that does not exist: {ref}")


def run_golden(golden: dict, vault: Path, top: int, exclude: list[str], base: Path | None = None) -> dict[str, Any]:
    """Ask the backend everything the golden file labels and collect raw answers per capture.
    `base` is the directory fixture paths are relative to (the evals/ directory)."""
    rows = golden["rows"]
    by_capture: dict[str, list[dict]] = {}
    for row in rows:
        by_capture.setdefault(row["capture"], []).append(row)
    raw: dict[str, dict] = {}
    usages = []
    for capture, crows in by_capture.items():
        if capture == "*batch*":
            continue
        force = sorted({r["qid"].split("|", 1)[1] for r in crows if r["qid"].split("|", 1)[0] in ("rel", "relation", "covers")})
        block = judge_capture(_resolve_capture(capture, vault, base), vault, top, exclude, force)
        raw[capture] = block["answers"]
        usages.append(block["judgment"])
    if "*batch*" in by_capture:
        refs = sorted({n for r in by_capture["*batch*"] for n in r["qid"].split("|")[1:]})
        batch = judge_batch([_resolve_capture(n, vault, base) for n in refs], vault, refs)
        raw["*batch*"] = batch["answers"]
        usages.append(batch["judgment"])
    return {"raw": raw, "usages": usages}


def calibrate(golden: dict, raw: dict[str, dict], backend: str, show_holdout: bool) -> dict[str, Any]:
    t = thresholds(backend)
    report: dict[str, Any] = {"questions_version": Q.QUESTIONS_VERSION, "splits": {}, "disagreements": [], "missing": []}
    sweeps: dict[str, list[tuple[float, bool]]] = {}
    for row in golden["rows"]:
        # Rows labelled with the backend's answer in view cannot measure the backend; they are
        # reported apart and never sweep a threshold (Copilot review, PR #12).
        split = "anchored" if row.get("labelled_by") == "claude-anchored" else row.get("split", "tune")
        value = raw.get(row["capture"], {}).get(row["qid"])
        if value is None:
            report["missing"].append({"capture": row["capture"], "qid": row["qid"]})
            continue
        got = _decide(row["qid"], value, t)
        ok = got == row["expect"]
        family = row["qid"].split("|", 1)[0]
        s = report["splits"].setdefault(split, {}).setdefault(family, {"n": 0, "agree": 0, "must_failed": 0})
        s["n"] += 1
        s["agree"] += ok
        s["must_failed"] += (not ok) and row.get("strength") == "must"
        if isinstance(value, float) and isinstance(row["expect"], bool) and split == "tune":
            sweeps.setdefault(family, []).append((value, row["expect"]))
        if not ok and (split == "tune" or (show_holdout and split != "anchored")):
            report["disagreements"].append({**row, "got": got, "answer": value})
    report["threshold_sweep"] = {
        family: [
            {"cut": cut, "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn)}
            for cut in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
            for tp, fp, fn in [_confusion(points, cut)]
        ]
        for family, points in sweeps.items()
    }
    return report


def _confusion(points: list[tuple[float, bool]], cut: float) -> tuple[int, int, int]:
    tp = sum(1 for p, y in points if p >= cut and y)
    fp = sum(1 for p, y in points if p >= cut and not y)
    fn = sum(1 for p, y in points if p < cut and y)
    return tp, fp, fn


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 3) if b else None


def golden_skeleton(blocks: list[dict], batch: dict | None, backend: str) -> dict[str, Any]:
    """Rows with the backend's own answer as a *proposal*. A human sets `expect`,
    `strength` and `rationale`; a backend's answer is never accepted as a label unreviewed."""
    t = thresholds(backend)
    rows = []
    for block in blocks:
        for key, value in block.get("answers", {}).items():
            rows.append({"capture": block["capture"], "qid": key, "expect": None, "proposed": _decide(key, value, t),
                         "strength": "should", "labelled_by": None, "split": "tune", "rationale": ""})
    for key, value in (batch or {}).get("answers", {}).items():
        rows.append({"capture": "*batch*", "qid": key, "expect": None, "proposed": _decide(key, value, t),
                     "strength": "should", "labelled_by": None, "split": "tune", "rationale": ""})
    return {"questions_version": Q.QUESTIONS_VERSION, "rows": rows}


def run_captures(vault: Path, paths: list[Path], top: int, exclude: list[str]) -> dict[str, Any]:
    """Judge every capture (plus the batch request for two or more). A configured backend
    that answers nothing is recorded in the dead-letter queue, never silently skipped."""
    try:
        blocks = [judge_capture(p, vault, top, exclude) for p in paths]
        batch = judge_batch(paths, vault) if len(paths) > 1 else None
    except JudgmentFailed as e:
        dlq = write_dlq_note(
            vault, slug="judgment-backend-failed", title="typed-judgment backend answered nothing",
            what_happened=f"`distill_judge.py` reached a configured judgment backend but every request failed: {e}",
            why_recorded="A configured backend that fails is not the normal 'no backend' skip path; the distill run "
                         "continued without advisory judgments and someone should check the key, quota or endpoint.",
            confidence="low",
        )
        return {"failed": str(e), "dlq": dlq.relative_to(vault).as_posix()}
    usages = [b["judgment"] for b in blocks] + ([batch["judgment"]] if batch else [])
    return {"captures": blocks, "batch": batch, "usd": round(sum(u["usd"] for u in usages), 6),
            "requests": sum(u["requests"] for u in usages)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_text(result: dict) -> None:
    for b in result["captures"]:
        print(f"\n## {b['capture']}  (advisory; {b['judgment']['backend']}/{b['judgment']['model']}, questions {b['questions_version']})")
        if "skipped" in b:
            print(f"SKIPPED — judgment backend unavailable ({b['skipped']})")
            continue
        print(f"triage: {b['triage']['recommendation'] or 'no recommendation'}  {b['triage']['probs']}")
        print(f"mode:   {b['already_distilled']['suggested_mode']}  {b['already_distilled']}")
        print(f"place:  {b['placement']['folder'] or 'AMBIGUOUS'}  {b['placement']['probs']}")
        print(f"domains: {b['domains']}")
        if b.get("passages"):
            ps = b["passages"]
            warn = "  SUMMARY MAY MISSTATE THE SOURCE" if ps.get("summary_warning") else ""
            print(f"essence: {ps['essence_chars']}/{ps['total_chars']} chars in {sum(r['keep'] for r in ps['passages'])}/{len(ps['passages'])} passages; "
                  f"summary={ps.get('summary_relation')} reverses={ps.get('p_reverses')}{warn}")
        for r in b["related"]:
            flag = "b" if r.get("bridge") else "*" if r["judged_relevant"] else " "
            print(f" {flag} {r['p_relevant']} {r.get('p_principle')}  {r['suggested_level'] or '--'}  {r['relation'] or '':<20} {r['path']}")
    if result.get("batch"):
        for p in result["batch"].get("cluster", []):
            print(f"pair: {p['verdict']:<16} {p['a']} ({p['a_adds']}) <-> {p['b']} ({p['b_adds']})")
    print(f"\ncost: ${result['usd']:.6f} over {result['requests']} request(s)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("captures", nargs="*", help="capture notes (vault-relative or absolute)")
    ap.add_argument("--top", type=int, default=12, help="search results judged per capture (before widening)")
    ap.add_argument("--exclude", action="append", default=[], help="vault-relative prefix never sent to the backend (repeatable)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--calibrate", metavar="GOLDEN", help="score the backend against a golden file instead of judging captures")
    ap.add_argument("--show-holdout", action="store_true", help="with --calibrate: also list held-out disagreements")
    ap.add_argument("--emit-golden-skeleton", action="store_true", help="print unlabelled golden rows for these captures")
    ap.add_argument("--passages", action="store_true", help="also judge which passages carry the capture's substance, and whether its summary is faithful")
    ap.add_argument("--check-note", metavar="NOTE", help="preservation check: list the capture's kept passages this note does not carry")
    args = ap.parse_args()
    vault = require_vault()

    reason = judge.unavailable_reason(vault)
    if reason:
        skipped = {"captures": [{"capture": c, "advisory": True, "skipped": reason, "questions_version": Q.QUESTIONS_VERSION,
                                 "judgment": judge.load_config(vault)} for c in args.captures] or [],
                   "skipped": reason, "usd": 0.0, "requests": 0}
        print(json.dumps(skipped, indent=2) if args.json else f"SKIPPED — judgment backend unavailable ({reason})")
        return 0

    try:
        if args.calibrate:
            golden_path = Path(args.calibrate).resolve()
            golden = json.loads(golden_path.read_text(encoding="utf-8"))
            golden["rows"] = [r for r in golden["rows"] if r.get("expect") is not None]
            run = run_golden(golden, vault, args.top, args.exclude, base=golden_path.parent.parent)
            backend = run["usages"][0]["backend"] if run["usages"] else judge.load_config(vault)["backend"]
            report = calibrate(golden, run["raw"], backend, args.show_holdout)
            report["usd"] = round(sum(u["usd"] for u in run["usages"]), 6)
            report["model"] = run["usages"][0]["model"] if run["usages"] else ""
            print(json.dumps(report, indent=2))
            return 0

        if args.check_note:
            if len(args.captures) != 1:
                ap.error("--check-note takes exactly one capture")
            note = Path(args.check_note) if Path(args.check_note).is_absolute() else vault / args.check_note
            cap = Path(args.captures[0]) if Path(args.captures[0]).is_absolute() else vault / args.captures[0]
            report = check_note(note, cap, vault)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"{report['carried']}/{report['kept_passages']} kept passages carried by {report['note']}  (${report['judgment']['usd']})")
                for m in report["misses"]:
                    print(f"  MISSING p={m['p_carried']}  {m['text'][:160]}")
            return 0
        if not args.captures:
            ap.error("name at least one capture, or use --calibrate")
        paths = [p if p.is_absolute() else vault / p for p in map(Path, args.captures)]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            ap.error(f"not a file: {', '.join(missing)}")
        result = run_captures(vault, paths, args.top, args.exclude)
        if args.passages and "failed" not in result:
            for block, path in zip(result["captures"], paths, strict=True):
                block["passages"] = judge_passages(path, vault)
                result["usd"] = round(result["usd"] + block["passages"].get("judgment", {}).get("usd", 0.0), 6)
    except JudgmentUnavailable as e:  # key vanished between the check and the call
        print(f"SKIPPED — judgment backend unavailable ({e.reason})")
        return 0
    if "failed" in result:
        print(f"judgment backend failed ({result['failed']}); recorded {result['dlq']}", file=sys.stderr)
        return 1

    blocks, batch = result["captures"], result["batch"]
    if args.emit_golden_skeleton:
        print(json.dumps(golden_skeleton(blocks, batch, blocks[0]["judgment"]["backend"]), indent=2))
    elif args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
