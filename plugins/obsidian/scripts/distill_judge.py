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
from pathlib import Path
from typing import Any

import judge
from judge import Answer, JudgmentFailed, JudgmentUnavailable, Question
from judgments import questions as Q
from judgments.batch import judge_batch  # noqa: F401  (re-exported for the skill docs and evals)
from judgments.capture import CAPTURE_CHARS, URL_RE, WIKILINK_RE, query_text, read_capture  # noqa: F401
from judgments.content import judge_content
from judgments.passages import check_note, judge_passages, split_passages  # noqa: F401
from judgments.policy import LEVEL_BY_RELATION, THRESHOLDS, thresholds  # noqa: F401
from judgments.state import domain_glosses, in_chunks, note_payload
from judgments.urls import _canonical
from search import search
from search_judge import expand
from vault_utils import discover_notes, profile_value, read_frontmatter, require_vault, vault_file, write_dlq_note

MAX_LISTED_FOLDERS = 60


NOTES_PER_REQUEST = 8  # candidate notes per request; the capture rides along in each. A real


# vault's capture plus 40 widened candidates exceeded the backend's input limit (2026-09-22).
MAX_CANDIDATES = 24


# Requests per capture; an even number also asks with the candidate notes in reverse order and
# averages. Left at 1: measured 2026-09-22, an identical rerun moves a noul by 0.008 on average
# (max 0.09) and two views by 0.006, with golden agreement unchanged (54/60 vs 55/60). Unlike
# the pairwise link question there is no order effect worth paying a second request for.
VIEWS = 1


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
    if folder == "04_Resources" and concept is not None and concept.p >= t["T_CONCEPT_UPGRADE"]:
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
            # Sorted, not the raw set: a set of strings iterates in an order that depends on
            # the process's hash seed, and max()'s tie-break picks whichever label came first
            # in that order — an exact probability tie would then make `top` non-reproducible
            # from one run to the next for the same judgment data.
            labels = sorted({label for a in seen for label in a.probs})
            probs = {label: sum(a.probs.get(label, 0.0) for a in seen) / len(seen) for label in labels}
            merged[key] = Answer("choice", probs=probs, top=max(probs, key=probs.get))
    return merged


def enrichment_targets(vault: Path, exclude: list[str]) -> list[str]:
    """Profile `enrichment_targets`: notes the owner wants judged for every capture whatever
    search says (a personal profile note, a standing project). Wikilinks or vault-relative
    paths; anything that does not resolve, or sits under an excluded prefix, is dropped."""
    raw = profile_value(vault, "enrichment_targets", []) or []
    if isinstance(raw, str):
        raw = [t for t in re.split(r"[,\n]", raw) if t.strip()]
    # A profile note usually sits at the vault root; discover_notes returns it only when it
    # declares `status: active`, so every root note is looked up here.
    by_stem = {p.stem: p.relative_to(vault).as_posix() for p in discover_notes(vault, exclude=exclude)}
    by_stem.update({p.stem: p.name for p in vault.glob("*.md")})
    out = []
    for t in raw:
        name = str(t).strip().strip("[]").split("|", 1)[0].strip()
        rel = name if name.endswith(".md") else by_stem.get(name.rsplit("/", 1)[-1], "")
        if rel and (vault / rel).is_file() and not _excluded(rel, exclude) and rel not in out:
            out.append(rel)
    return out


OWNER_SOURCES = {"clip"}  # `via` values a person chose; anything else arrived on its own


def capture_provenance(path: Path) -> dict[str, Any]:
    """How the capture reached the inbox. `via` comes from the capture's frontmatter (the readwise
    plugin writes clip / newsletter / radar); a capture without it (research, bookmarks, older
    captures) was put there by the owner and counts as a clip."""
    try:
        fm, _ = read_frontmatter(path)
    except Exception:  # an unparseable capture is distill_check's problem, not triage's
        fm = {}
    via = str(fm.get("via") or "clip")
    prov: dict[str, Any] = {"via": via, "owner_chose_it": via in OWNER_SOURCES}
    if fm.get("radar_interests"):
        prov["radar_interests"] = list(fm["radar_interests"])
    return prov


def apply_provenance(triage: dict[str, Any], prov: dict[str, Any]) -> dict[str, Any]:
    """The one place provenance changes the pipeline: whether a capture may leave without a note.
    A clip never does [Mike, 2026-09-23: own clips never drop and get enhanced]; anything that
    arrived on its own (radar, newsletter) may be retired when triage says discard."""
    out = dict(triage)
    if out.get("recommendation") != "discard-candidate":
        return out
    if prov["owner_chose_it"]:
        out["recommendation"] = "quick-file"
        out["note"] = "the owner saved this: never discarded; file it at least"
    else:
        out["note"] = f"arrived via {prov['via']}, not chosen by the owner: may be retired without a note, with the reason in the archive manifest"
    return out


def judge_capture(path: Path, vault: Path, top: int, exclude: list[str], force: list[str] | None = None,
                  views: int = VIEWS) -> dict[str, Any]:
    capture = read_capture(path)
    force = [*(force or []), *[t for t in enrichment_targets(vault, exclude) if t not in (force or [])]]
    notes, search_meta = candidates(capture, vault, top, exclude, force)
    # Forced and URL-hit notes are never dropped by the cap; search rows after them are.
    pinned = [n for n in notes if n.get("url_hit") or n["path"] in (force or [])]
    rest = [n for n in notes if n not in pinned][:max(0, MAX_CANDIDATES - len(pinned))]
    notes = pinned + rest
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
    if not usages:
        # Every chunk hit judge.StateTooLarge all the way down to a single note (or the
        # capture-only state) and still failed: in_chunks() degrades that to {} rather than
        # raising, so nothing here ever called judge.judge() successfully.
        raise JudgmentFailed("capture state exceeded the backend's size limit, even alone")
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
    block["provenance"] = capture_provenance(path)
    block["triage"] = apply_provenance(block["triage"], block["provenance"])
    content, content_usage = judge_content(path, vault)
    if content_usage is not None:
        usage.requests += content_usage.requests
        usage.input_tokens += content_usage.input_tokens
        usage.usd += content_usage.usd
        usage.splits += content_usage.splits
        usage.skipped.extend(content_usage.skipped)
    block["content"] = content
    if content["verdict"] not in (None, "ok"):
        # The triage recommendation above was computed from this same wrong text; say so right
        # where a reader would see the score, not only in the new `content` block.
        block["triage"]["note"] = (block["triage"]["note"] + " " if block["triage"].get("note") else "") + (
            f"content judged {content['verdict']}: its triage score judged that text, not the article — see `content`.")
    block["judgment"] = {**usage.as_dict(), "views": views}
    block["answers"] = {stable[qid]: (round(a.p, 4) if a.kind == "noul" else _probs(a)) for qid, a in answers.items()}
    return block


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


def add_graph(block: dict, vault: Path) -> None:
    """Graph context for the top related notes and, when a judgment backend is present,
    adjudicated inferred candidates for the best one. Silent when no gaiafield binary."""
    import graph  # local: the seam must stay importable without the graph module's subprocess machinery

    top = [r["path"] for r in block.get("related", []) if r.get("judged_relevant")][:3]
    if not top or not graph.available():
        block["graph"] = {"available": False}
        return
    ctx = graph.graph_context(vault, top)
    if isinstance(ctx, graph.GraphUnavailable):
        block["graph"] = {"available": False, "reason": ctx.reason}
        return
    block["graph"] = {"available": True, "placement_folder": ctx.get("placement_folder"),
                      "backlink_candidates": [c.get("path") or c.get("title") for c in ctx.get("backlink_candidates", [])][:10],
                      "bridge_opportunities": [c.get("path") or c.get("title") for c in ctx.get("bridge_opportunities", [])][:5]}
    graph.ensure_inferred(vault)
    rows = graph.inferred_candidates(vault, top[0], k=8)
    if not isinstance(rows, graph.GraphUnavailable):
        judged = graph.adjudicate_candidates(vault, rows, note=top[0])
        block["graph"]["inferred"] = judged if not isinstance(judged, graph.GraphUnavailable) else rows


def _print_text(result: dict) -> None:
    for b in result["captures"]:
        print(f"\n## {b['capture']}  (advisory; {b['judgment']['backend']}/{b['judgment']['model']}, questions {b['questions_version']})")
        if "skipped" in b:
            print(f"SKIPPED — judgment backend unavailable ({b['skipped']})")
            continue
        c = b.get("content") or {}
        flag = "" if c.get("verdict") in (None, "ok") else f"  ** CONTENT {c['verdict'].upper()} (p={c['p']}) — {c.get('note', '')}"
        print(f"content: {c.get('verdict')}{flag}")
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
    ap.add_argument("--dossier", action="store_true", help="everything a distilling agent needs in one block: judgments, passages, graph context, adjudicated inferred candidates")
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
            note = vault_file(vault, args.check_note)
            cap = vault_file(vault, args.captures[0])
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
        paths = [vault_file(vault, c) for c in args.captures]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            ap.error(f"not a file: {', '.join(missing)}")
        result = run_captures(vault, paths, args.top, args.exclude)
        if (args.passages or args.dossier) and "failed" not in result:
            for block, path in zip(result["captures"], paths, strict=True):
                block["passages"] = judge_passages(path, vault)
                result["usd"] = round(result["usd"] + block["passages"].get("judgment", {}).get("usd", 0.0), 6)
                if args.dossier:
                    add_graph(block, vault)
    except JudgmentUnavailable as e:  # key vanished between the check and the call
        print(f"SKIPPED — judgment backend unavailable ({e.reason})")
        return 0
    except JudgmentFailed as e:  # --calibrate, --check-note and --passages reach the backend outside run_captures()
        print(f"judgment backend failed: {e}", file=sys.stderr)
        return 1
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
