"""Eval: the typed-judgment layer (judge.py + distill_judge.py) behaves, offline.

No network and no credential: `judge._post`, the module's single network call, is
replaced with a stub that answers in the backend's wire format. What the stub cannot
prove (that the real service accepts this shape and judges the bundled captures
sensibly) is covered by an opt-in live phase, the same split eval_inferred_candidates
uses for stub-vs-real-binary: set TOOLKIT_EVAL_LIVE_JEV=1 with a key in the environment
and the real CLI path runs in a sandbox and is scored against
golden/distill_judge.golden.json. The live phase never runs in CI.

Offline phases:
1. wire shape      — URL, bearer header, state/model/questions, one typed object per question
2. state paths     — every backticked path in every question resolves in the state sent
3. policy          — thresholds map probabilities to suggestions (L3 only when sure, never
                     auto-discard, no-clear-home -> ambiguous, URL provenance beats the model)
4. no key          — SKIPPED, no request, no DLQ note
5. partial failure — a request that fails is halved and the answers still arrive
6. total failure   — exactly one DLQ note
7. read-only       — judging changes no note in the vault (the graph index may be built)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "distill_judge"
CAPTURES = ("01_Capture/Readwise-Hybrid-Search-Landscape.md", "01_Capture/X-Bookmark-Retrieval-Debate.md")
KEY_ENVS = ("TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
GOLDEN = Path(__file__).resolve().parent / "golden" / "distill_judge.golden.json"
PATH_RE = re.compile(r"`([A-Za-z_][\w.]*)`")


def _resolves(state: dict, dotted: str) -> bool:
    node = state
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _canned(question: dict) -> dict:
    if question["type"] == "noul":
        return {"type": "noul", "noul": 0.9}
    labels = list(question["criteria"])
    probs = {label: (0.85 if i == 0 else 0.15 / (len(labels) - 1)) for i, label in enumerate(labels)}
    return {"type": "choice", "choice": labels[0], "confidence": 0.8, "probabilities": probs}


def _snapshot(vault: Path) -> dict[str, tuple[int, int]]:
    # `.gaiafield/` is the graph engine's own index, which candidate widening may build; it is
    # not vault content, and the read-only claim is about notes.
    return {p.relative_to(vault).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in vault.rglob("*") if p.is_file() and ".gaiafield" not in p.parts}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import distill_judge as dj
    import judge

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in (*KEY_ENVS, "TOOLKIT_OBSIDIAN_JUDGMENT_BACKEND")}
    real_post = judge._post
    sandbox = None  # set inside try: below, so a failed make_sandbox() still restores saved_env
    calls: list[dict] = []

    def stub_ok(url, payload, headers):
        calls.append({"url": url, "payload": payload, "headers": headers})
        return {"model": "stub-1", "usage": {"input_tokens": 1000},
                "answers": {qid: _canned(q) for qid, q in payload["questions"].items()}}

    def stub_fails_when_large(url, payload, headers):
        if len(payload["questions"]) > 4:
            raise judge._CallError("HTTP 500: stub", retryable_by_split=True)
        return stub_ok(url, payload, headers)

    def stub_always_fails(url, payload, headers):
        raise judge._CallError("HTTP 500: stub", retryable_by_split=True)

    try:
        sandbox = make_sandbox(vault)
        paths = [sandbox / c for c in CAPTURES]
        dlq_dir = sandbox / "00_Memory" / "dlq"

        # Phase 4 first, while no key is set.
        judge._post = stub_ok
        if judge.unavailable_reason(sandbox) != "no-key":
            problems.append(f"phase 4: expected 'no-key', got {judge.unavailable_reason(sandbox)!r}")
        try:
            judge.judge(sandbox, {"x": 1}, {"q": judge.Question("noul", "Is `x` set?")})
            problems.append("phase 4: judge() answered without a key")
        except judge.JudgmentUnavailable:
            pass
        if calls:
            problems.append("phase 4: a request was sent without a key")

        os.environ[KEY_ENVS[0]] = "stub-key-not-a-secret"
        before = _snapshot(sandbox)

        # Phases 1, 2, 7.
        result = dj.run_captures(sandbox, paths, top=5, exclude=[])
        if "failed" in result or len(result["captures"]) != 2 or not result["batch"]:
            problems.append(f"phase 1: unexpected run result keys {sorted(result)}")
        for call in calls:
            payload = call["payload"]
            if not call["url"].endswith("/v1/systemone"):
                problems.append(f"phase 1: wrong endpoint {call['url']}")
            if call["headers"].get("Authorization") != "Bearer stub-key-not-a-secret":
                problems.append("phase 1: bearer header missing or wrong")
            if set(payload) != {"state", "model", "questions"} or not payload["model"]:
                problems.append(f"phase 1: body keys {sorted(payload)}")
            for qid, q in payload["questions"].items():
                if q.get("type") not in ("noul", "choice") or not q.get("instructions"):
                    problems.append(f"phase 1: malformed question {qid}")
                if q["type"] == "choice" and "criteria" not in q:
                    problems.append(f"phase 1: choice {qid} has no criteria")
                text = json.dumps(q)
                for dotted in PATH_RE.findall(text):
                    if not _resolves(payload["state"], dotted):
                        problems.append(f"phase 2: {qid} references `{dotted}`, absent from the state")
        if _snapshot(sandbox) != before:
            problems.append("phase 7: judging changed files in the vault")
        block = result["captures"][0] if "captures" in result else {}
        if block.get("advisory") is not True or "questions_version" not in block:
            problems.append("phase 1: block is not labelled advisory with a questions_version")
        # The bundled profile pins [[Alex-Vega]] (a root-level `status: active` note) in
        # `enrichment_targets`: it must reach the backend as a candidate for every capture,
        # whether or not search ranks it for this one.
        judged = {n["path"] for c in calls for n in c["payload"]["state"].get("notes", {}).values()}
        if "Alex-Vega.md" not in judged:
            problems.append("phase 1: profile enrichment_targets note was not among the judged candidates")

        # Phase 3: policy, on synthetic answers.
        t = dj.THRESHOLDS["jev"]
        note = {"path": "04_Resources/X.md", "title": "X", "search_score": 1.0, "above_enrichment_gate": False, "url_hit": None}

        def policy(relation_probs, triage_probs=None, para_probs=None, url_hit=None, covers=0.1):
            top = max(relation_probs, key=relation_probs.get)
            answers = {
                "rel_N01": judge.Answer("noul", p=0.9),
                "relation_N01": judge.Answer("choice", probs=relation_probs, top=top),
                "covers_N01": judge.Answer("noul", p=covers),
            }
            if triage_probs:
                answers["triage"] = judge.Answer("choice", probs=triage_probs, top=max(triage_probs, key=triage_probs.get))
            if para_probs:
                answers["para"] = judge.Answer("choice", probs=para_probs, top=max(para_probs, key=para_probs.get))
            return dj.apply_policy([{**note, "url_hit": url_hit}], answers, t)

        sure = policy({"contradicts-claim": 0.9, "adjacent": 0.1})
        unsure = policy({"contradicts-claim": 0.6, "adjacent": 0.4})
        if sure["related"][0]["suggested_level"] != "L3":
            problems.append(f"phase 3: contradicts at 0.9 should suggest L3, got {sure['related'][0]['suggested_level']}")
        if unsure["related"][0]["suggested_level"] != "L1":
            problems.append(f"phase 3: contradicts at 0.6 should fall back to L1, got {unsure['related'][0]['suggested_level']}")
        discard = policy({"adjacent": 1.0}, triage_probs={"discard-candidate": 0.95, "distill": 0.05})
        if discard["triage"]["recommendation"] != "discard-candidate" or "never applied" not in discard["triage"]["note"]:
            problems.append("phase 3: a discard recommendation must carry the never-applied note")
        homeless = policy({"adjacent": 1.0}, para_probs={"no-clear-home": 0.6, "04_Resources": 0.4})
        close = policy({"adjacent": 1.0}, para_probs={"04_Resources": 0.5, "02_Projects": 0.45, "no-clear-home": 0.05})
        if not homeless["placement"]["ambiguous"] or not close["placement"]["ambiguous"]:
            problems.append("phase 3: no-clear-home or a thin margin must mark placement ambiguous")
        provenance = policy({"adjacent": 1.0}, url_hit="frontmatter", covers=0.05)
        if provenance["already_distilled"]["suggested_mode"] != "enrich-only":
            problems.append("phase 3: a frontmatter URL hit decides enrich-only regardless of the model")
        if policy({"adjacent": 1.0}, covers=0.95)["already_distilled"]["suggested_mode"] != "enrich-only?":
            problems.append("phase 3: a confident covers_* with no URL hit should suggest 'enrich-only?'")

        # Phase 5: halving.
        judge._post = stub_fails_when_large
        answers, usage = judge.judge(sandbox, {"x": 1}, {f"q{i}": judge.Question("noul", "Is `x` set?") for i in range(10)})
        if len(answers) != 10 or usage.splits == 0:
            problems.append(f"phase 5: expected 10 answers after splitting, got {len(answers)} (splits={usage.splits})")

        # Phase 6: total failure -> exactly one DLQ note.
        judge._post = stub_always_fails
        dlq_before = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()
        failed = dj.run_captures(sandbox, paths, top=5, exclude=[])
        new_dlq = (set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()) - dlq_before
        if "failed" not in failed or len(new_dlq) != 1:
            problems.append(f"phase 6: expected one DLQ note on total failure, got {len(new_dlq)} (result keys {sorted(failed)})")

        live_detail = "live phase skipped (set TOOLKIT_EVAL_LIVE_JEV=1 with a key to run it)"
        if os.environ.get("TOOLKIT_EVAL_LIVE_JEV") == "1":
            judge._post = real_post
            live_detail = _live_phase(dj, sandbox, saved_env, problems)
    finally:
        judge._post = real_post
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    if problems:
        return {"eval": NAME, "pass": False, "detail": "; ".join(problems)}
    return {"eval": NAME, "pass": True, "detail": f"7 offline phases ok ({len(calls)} stubbed requests); {live_detail}"}


def _live_phase(dj, sandbox: Path, saved_env: dict, problems: list[str]) -> str:
    """Real backend, sandbox vault, scored against human-reviewed golden rows."""
    key = next((saved_env[k] for k in KEY_ENVS if saved_env.get(k)), None)
    if not key:
        return "live phase requested but no key in the environment"
    if not GOLDEN.is_file():
        return f"live phase requested but {GOLDEN.name} is missing"
    os.environ[KEY_ENVS[0]] = key
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    golden["rows"] = [r for r in golden["rows"] if r.get("expect") is not None]
    run = dj.run_golden(golden, sandbox, top=8, exclude=[], base=GOLDEN.parent.parent)
    report = dj.calibrate(golden, run["raw"], run["usages"][0]["backend"], show_holdout=True)
    scored = {k: v for k, v in report["splits"].items() if k != "anchored"}
    n = sum(f["n"] for split in scored.values() for f in split.values())
    agree = sum(f["agree"] for split in scored.values() for f in split.values())
    must_failed = sum(f["must_failed"] for split in scored.values() for f in split.values())
    anchored = report["splits"].get("anchored", {})
    an = sum(f["n"] for f in anchored.values())
    aa = sum(f["agree"] for f in anchored.values())
    if must_failed:
        problems.append(f"live: {must_failed} 'must' row(s) disagreed: " +
                        ", ".join(f"{d['capture']}::{d['qid']}" for d in report["disagreements"] if d.get("strength") == "must"))
    if n and agree / n < 0.85:
        problems.append(f"live: agreement {agree}/{n} is below 0.85")
    return (f"live: {agree}/{n} agree on unanchored rows ({aa}/{an} anchored, informational), "
            f"model {run['usages'][0]['model']}, questions {report['questions_version']}")
