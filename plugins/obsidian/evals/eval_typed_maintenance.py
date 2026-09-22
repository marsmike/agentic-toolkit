"""Eval: the three maintenance judgments, offline against a stubbed transport.

1. passages   — distill_judge.judge_passages() splits a capture into passages, keeps what the
                stub scores high, drops the pipeline header, and raises the summary warning
                on `misstates`; the essence is a subset of the capture's own text
2. sweep      — vault_sweep.sweep() takes same-source pairs as candidates (never verdicts),
                ignores a shared address held by many notes, flags a pair only above the
                cut, and writes nothing
3. batch      — above MAX_BATCH captures pairs are blocked; a same-source pair (tracking
                parameters stripped) or near-identical text is a duplicate with no call
4. check-note — a note that drops a kept passage is told which one
5. links      — checks.links.judge_resolve() asks one Choice per broken link over a
                shortlist plus `none`, and the fix path applies only at the `apply` label
                while a `propose` verdict is reported, not written
No key → every path degrades: SKIPPED / plain audit / no request.
"""
from __future__ import annotations

import os
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "typed_maintenance"
KEY_ENVS = ("TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
CAPTURE = """---
captured: 2026-09-22
origin: readwise
source: https://example.org/article
---

# A test article

**Source:** https://example.org/article
**Author:** example.org

## Synthesis

The pipeline's own reading of the article, which says the effect is large and reliable across the board.

## Article content

The effect was measured at 0.42 in three of four settings, and did not appear in the fourth; the authors call it moderate.

Subscribe to our newsletter for more articles like this one and follow us on every platform.

A second finding: response time fell by 30 percent when the cache was warm, a mechanism the authors attribute to prefix reuse.
"""


def _snapshot(vault: Path):
    return {p.relative_to(vault).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in vault.rglob("*") if p.is_file() and ".gaiafield" not in p.parts}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import distill_judge as dj
    import judge
    import vault_sweep
    from checks import links
    from vault_utils import read_frontmatter, write_frontmatter

    problems = []
    saved = {k: os.environ.pop(k, None) for k in (*KEY_ENVS, "TOOLKIT_OBSIDIAN_JUDGMENT_BACKEND")}
    real_post = judge._post
    sandbox = None  # set inside try: below, so a failed make_sandbox() still restores saved
    calls = []

    def stub(url, payload, headers):
        calls.append(payload)
        answers = {}
        for qid, q in payload["questions"].items():
            if q["type"] == "choice":
                labels = list(q["criteria"])
                # summary relation -> misstates; link targets -> the first candidate, confidently
                top = "misstates" if "misstates" in labels else labels[0]
                probs = {lab: (0.9 if lab == top else 0.1 / max(1, len(labels) - 1)) for lab in labels}
                answers[qid] = {"type": "choice", "choice": top, "confidence": 0.9, "probabilities": probs}
            else:
                text = payload["state"].get("passages", {}).get(qid[5:], "") if qid.startswith(("keep_", "pipe_")) else ""
                if qid.startswith("keep_"):
                    p = 0.1 if "newsletter" in text else 0.9
                elif qid.startswith("pipe_"):
                    p = 0.9 if "pipeline" in text else 0.1
                elif qid.startswith("same_"):
                    p = 0.95
                elif qid.startswith("carried_"):
                    ptext = payload["state"]["passages"][qid[8:]]
                    p = 0.9 if ptext[:40] in payload["state"]["note"] else 0.1
                elif qid.startswith("adds_"):
                    p = 0.9
                else:
                    p = 0.2
                answers[qid] = {"type": "noul", "noul": p}
        return {"model": "stub-1", "usage": {"input_tokens": 100}, "answers": answers}

    try:
        sandbox = make_sandbox(vault)
        cap = sandbox / "01_Capture" / "Readwise-Eval-Test-Article.md"
        cap.write_text(CAPTURE, encoding="utf-8")
        # no key: passages skip cleanly, sweep skips, links audit is the plain audit
        try:
            dj.judge_passages(cap, sandbox)
            problems.append("no-key: judge_passages ran without a backend")
        except judge.JudgmentUnavailable:
            pass
        os.environ[KEY_ENVS[0]] = "stub-key-not-a-secret"
        judge._post = stub
        before = _snapshot(sandbox)

        ps = dj.judge_passages(cap, sandbox)
        kept = [r for r in ps["passages"] if r["keep"]]
        if not kept or any("newsletter" in r["head"] for r in kept):
            problems.append("passages: the promotional passage was kept or nothing was")
        if ps["essence_text"] and ps["essence_text"] not in CAPTURE.replace("\r", "") and any(part not in CAPTURE for part in ps["essence_text"].split("\n\n")):
            problems.append("passages: essence contains text not in the capture")
        if not ps["summary_warning"] or ps["summary_relation"] != "misstates":
            problems.append(f"passages: a misstating summary should warn, got {ps['summary_relation']!r}")
        if any(r["head"].startswith("**Source:**") for r in ps["passages"]):
            problems.append("passages: the pipeline header line was judged as a passage")

        # sweep: two notes with one source, plus seven notes sharing a repo root
        for i in range(2):
            write_frontmatter(sandbox / "04_Resources" / f"Eval-Dup-{i}.md", {"description": "d", "status": "distilled", "source": "https://example.org/same-work"}, "\n# Dup\n\nThe same work.\n")
        for i in range(7):
            write_frontmatter(sandbox / "04_Resources" / f"Eval-Coll-{i}.md", {"description": "d", "status": "distilled", "source": "https://github.com/x/repo"}, f"\n# Coll {i}\n\nPart {i} of a collection.\n")
        report = vault_sweep.sweep(sandbox, max_pairs=50, exclude=[], include_graph=False)
        if report["pairs_from_same_source"] != 1:
            problems.append(f"sweep: expected 1 same-source pair (collection of 7 ignored), got {report['pairs_from_same_source']}")
        if len(report["duplicates"]) != 1 or report["duplicates"][0]["p_same_work"] is None:
            problems.append("sweep: the same-source pair must be judged, not assumed")
        if report["contradictions"]:
            problems.append("sweep: no contradiction should be flagged at p=0.2")

        # batch: above MAX_BATCH captures, pairs are blocked; same-source and near-identical pairs are duplicates without a call
        caps_dir = sandbox / "01_Capture"
        words = ["harbour", "granite", "violin", "compost", "lantern", "ferry", "orchid", "kettle", "meadow", "anvil", "saffron", "tundra", "quartz", "pelican"]
        for i in range(14):
            w = words[i]
            (caps_dir / f"Readwise-Eval-Batch-{i:02d}.md").write_text(
                f"---\nsource: https://example.org/item/{i % 13}?utm_source=x\norigin: readwise\n---\n\n# Notes on the {w}\n\n"
                f"Everything here is about the {w}: how a {w} is made, why the {w} matters, and what a {w} costs in {2000 + i}.\n", encoding="utf-8")
        batch = dj.judge_batch(sorted(caps_dir.glob("Readwise-Eval-Batch-*.md")), sandbox)
        dups = [r for r in batch["cluster"] if r["verdict"] == "duplicate"]
        if not batch.get("blocked") or len(dups) != 1 or dups[0].get("similarity") != "same source":
            problems.append(f"batch: expected blocking with one same-source duplicate (items 0 and 13), got blocked={batch.get('blocked')} dups={dups}")
        if batch["pairs_considered"] >= 14 * 13 // 2:
            problems.append("batch: blocking did not reduce the pair count")

        # check-note: a note that drops a kept passage is told so
        note_ok = sandbox / "04_Resources" / "Eval-Check.md"
        write_frontmatter(note_ok, {"description": "d", "status": "distilled", "source": "https://example.org/article"},
                          "\n# Check\n\nThe effect was measured at 0.42 in three of four settings; the authors call it moderate.\n")
        chk = dj.check_note(note_ok, cap, sandbox)
        if chk["kept_passages"] < 2 or chk["carried"] >= chk["kept_passages"]:
            problems.append(f"check-note: expected at least one miss for a note that omits the cache finding, got {chk['carried']}/{chk['kept_passages']}")

        # links: a note with a broken link whose shortlist holds the right note
        note = sandbox / "04_Resources" / "Eval-Linker.md"
        write_frontmatter(note, {"description": "d", "status": "distilled"}, "\n# Linker\n\nSee [[Fusion Of Keyword And Vector Search]] for the fusion idea.\n")
        fm, body = read_frontmatter(note)
        issues = links.audit(note, fm, body, sandbox)
        judged = [i for i in issues if "judged" in (i.proposed_fix or "")]
        if not judged:
            problems.append("links: audit produced no judged proposal")
        elif not judged[0].proposed_fix.startswith("apply:"):
            problems.append(f"links: a 0.9 pick should be labelled apply, got {judged[0].proposed_fix}")
        if _snapshot(sandbox) != {**before, **{k: v for k, v in _snapshot(sandbox).items() if k.startswith(("04_Resources/Eval-", "01_Capture/Readwise-Eval"))}}:
            problems.append("read-only: a judgment changed a pre-existing file")
        _, new_body, results = links.fix(note, fm, body, sandbox)
        if "[[Fusion Of Keyword And Vector Search]]" in new_body or not any(r.applied and "judged" in r.description for r in results):
            problems.append("links: fix did not apply an `apply`-labelled pick")

        # a low-confidence pick is proposed, never written
        def stub_unsure(url, payload, headers):
            out = stub(url, payload, headers)
            for a in out["answers"].values():
                if a["type"] == "choice" and "misstates" not in a["probabilities"]:
                    labels = list(a["probabilities"])
                    a["probabilities"] = {lab: (0.6 if lab == labels[0] else 0.4 / max(1, len(labels) - 1)) for lab in labels}
            return out
        judge._post = stub_unsure
        _, body2, results2 = links.fix(note, fm, body, sandbox)
        if "[[Fusion Of Keyword And Vector Search]]" not in body2 or not any("Proposed" in r.description for r in results2):
            problems.append("links: a 0.6 pick must be proposed, not applied")

        # links: heading, block and table-escaped alias forms of a valid link are not broken, and a
        # repaired typo keeps its anchor and its escaped alias
        judge._post = stub
        forms = sandbox / "04_Resources" / "Eval-Link-Forms.md"
        write_frontmatter(forms, {"description": "d", "status": "distilled"},
                          "\n# Forms\n\n[[Eval-Check#Check]] and [[Eval-Check^abc]] and [[#Forms]].\n\n"
                          "| a | b |\n|---|---|\n| [[04_Resources/Eval-Check\\|the check]] | [[Eval-Chek#Check\\|typo]] |\n")
        fm, body = read_frontmatter(forms)
        broken = [i.description for i in links.audit(forms, fm, body, sandbox) if i.description.startswith("Broken")]
        if broken != ["Broken wikilink [[Eval-Chek#Check\\]]"]:
            problems.append(f"links: only the typo should be broken, got {broken}")
        _, body3, _ = links.fix(forms, fm, body, sandbox)
        if "[[Eval-Check#Check\\|typo]]" not in body3 or "[[04_Resources/Eval-Check\\|the check]]" not in body3:
            problems.append("links: a repair must keep the anchor and the table-escaped alias")
    finally:
        judge._post = real_post
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)
    if problems:
        return {"eval": NAME, "pass": False, "detail": "; ".join(problems)}
    return {"eval": NAME, "pass": True, "detail": f"passages, sweep and links ok ({len(calls)} stubbed requests)"}
