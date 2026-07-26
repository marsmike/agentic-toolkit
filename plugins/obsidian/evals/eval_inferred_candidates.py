"""Eval: gaiafield v2 inferred-edge consumption (`graph.py`'s `ensure_inferred()` /
`inferred_candidates()` / `surprise_candidates()`), stub-binary-driven for phases 1-3, plus
one real-binary phase (4) when a v2-capable binary is actually available.

crates/gaiafield v2 was originally built in parallel with no release binary, so phases 1-3
run against fabricated stub scripts emitting JSON shaped to what the CLI spec *claimed*
(`contract/KNOWLEDGE_API.md`'s v2 section) — never a real gaiafield invocation. That spec
was wrong for `surprise` (R5 engine observer, 2026-07-26): it had no `label` field and no
`--include-ambiguous` flag, which the fixed `gaiafield::surprise` (Fix 2) both now carries.
`V2_STUB`'s `surprise` case below is written to the corrected, contract-conformant shape —
pair-shaped (`a`/`b`, not `path`), carrying `label`/`model`. Phase 4 closes the gap this
stub-only design otherwise leaves: a stub can be *wrong* about the real binary's shape and
every stub-driven assertion would still happily pass, insulating this eval from ever
noticing gaiafield itself drifted from the contract (the finding this rewrite fixes 2026-07-26).

Four phases, phases 1-3 all against a sandbox copy (`_sandbox.py`) since `ensure_inferred()`
can write to `.gaiafield/`:

1. **v2-stub phase**: a stub whose `--help` output advertises `infer`/`candidates`/
   `surprise` (what `graph._supports_inference()` probes for) and whose `candidates` and
   `surprise` subcommands always return one INFERRED row and one AMBIGUOUS row,
   unconditionally — regardless of `--include-ambiguous`. Asserts:
   (a) the default call's rows carry `kind="inferred"` and a `label` — a shape
       `graph_context()`'s deterministic backlink dicts never carry (extracted edges
       never carry a score, per the v2 contract) — proving inferred candidates are
       structurally labeled and separated from deterministic ones.
   (b) the AMBIGUOUS row is absent from the default (`include_ambiguous=False`) result
       even though the stub returns it unconditionally — proving `graph.py` enforces the
       "surfaced only on request" rule client-side, not merely by trusting the binary's
       own `--include-ambiguous` flag.
   (c) report-only, structurally: a snapshot of every vault file's (size, mtime) — except
       `.gaiafield/`, which is engine-internal state, not vault content — taken before and
       after running `ensure_inferred()`, `inferred_candidates()`, and
       `surprise_candidates()` is identical. No automation in this module writes vault
       content from an inferred edge, ever.
   (d) `surprise_candidates()`'s default call excludes the AMBIGUOUS row too — the "surfaced
       only on request" rule applies at the edge-label level, regardless of which
       subcommand produced the row, not just to `candidates`/`inferred_candidates()`.

2. **v1-stub phase**: a stub whose `--help` output never mentions `infer`/`candidates`/
   `surprise` (mimicking a pre-v2 release binary). Asserts (e) `ensure_inferred()` and
   `inferred_candidates()` both degrade to `GraphUnavailable("no-inference", ...)`
   *without* writing a DLQ note — the same silent-degradation contract as
   `"no-binary"`/`"no-index"`, since a binary that predates inference is a normal, expected
   state, not a call failure.

3. **v1-prose-stub phase**: the exact reproduced false-positive from finding 1 — a stub
   whose `--help` output never lists `infer`/`candidates`/`surprise` as subcommands but
   *does* contain the word "inference" in ordinary prose (e.g. "statistical inference is
   not yet supported in this build"). The pre-fix `"infer" in proc.stdout` bare-substring
   check would probe this as supporting inference (since "infer" is a substring of
   "inference"), then fail the real `infer` call against a stub that doesn't implement it
   and wrongly write a DLQ note — for what should have been a silent, normal
   "no-inference" degrade, identical to phase 2. Asserts (f)
   `graph._supports_inference()` called directly against this stub returns `False` (the
   cleanest place to pin the token-boundary fix), and (g) `ensure_inferred()` degrades to
   `GraphUnavailable("no-inference", ...)` with *no* new DLQ note, same as phase 2.

4. **real-binary phase** (Fix 2's stub-false-confidence closer): if `TOOLKIT_GAIAFIELD_BIN`
   points at a real binary AND it probes v2-capable (`graph._supports_inference()`, the same
   probe `ensure_inferred()`/`surprise_candidates()` use internally), run the real pipeline
   — `ensure_index()` then `ensure_inferred()` — against a scratch-copied, indexed+inferred
   vault, then call `surprise_candidates()` for real and assert (h) every row is pair-shaped
   (carries `a`/`b`, not `path`), (i) every row carries a `label`, and (j) the default call
   (`include_ambiguous=False`) excludes every `AMBIGUOUS` row even though the real db may
   contain some. No real binary, or one that isn't v2-capable: skip with a detail string
   rather than failing — this is the one phase that can't run in every environment (no
   release binary as of R5, `docs/PLAN.md`), same presence-gate style as `eval_search_parity`
   / `eval_graph_context`.
"""
from __future__ import annotations

import stat
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NOTE = "04_Resources/Guides/Test-Corpus-Map.md"

V2_STUB = """#!/bin/sh
case "$1" in
  --help)
    echo "USAGE: gaiafield <index|neighbors|stats|infer|candidates|surprise> [--json]"
    ;;
  infer)
    echo '{"embedded": 42, "inferred_edges": 7, "ambiguous_edges": 2, "model": "stub-embed-v1", "high_gate": 0.82, "low_gate": 0.68, "elapsed_ms": 5}'
    ;;
  candidates)
    echo '[{"path": "04_Resources/Guides/Vault-Maintenance-and-Linting.md", "score": 0.91, "label": "INFERRED", "kind": "inferred", "det_distance": null, "surprise": 0.12}, {"path": "03_Areas/Birding.md", "score": 0.71, "label": "AMBIGUOUS", "kind": "inferred", "det_distance": 3, "surprise": 0.4}]'
    ;;
  surprise)
    echo '[{"a": "02_Projects/field-guide/Field-Guide-Project.md", "b": "04_Resources/Guides/Vault-Maintenance-and-Linting.md", "score": 0.88, "surprise": 0.31, "det_distance": null, "same_subtree": false, "label": "INFERRED", "model": "stub-embed-v1"}, {"a": "02_Projects/field-guide/Field-Guide-Project.md", "b": "03_Areas/Birding.md", "score": 0.66, "surprise": 0.52, "det_distance": 4, "same_subtree": false, "label": "AMBIGUOUS", "model": "stub-embed-v1"}]'
    ;;
  *)
    echo "unrecognized subcommand: $1" >&2
    exit 2
    ;;
esac
"""

V1_STUB = """#!/bin/sh
case "$1" in
  --help)
    echo "USAGE: gaiafield <index|neighbors|stats> [--json]"
    ;;
  *)
    echo "unrecognized subcommand: $1" >&2
    exit 2
    ;;
esac
"""

# Finding 1's exact reproduction: a pre-v2 binary whose --help prose merely *mentions*
# "inference" without listing infer/candidates/surprise as actual subcommands. The
# pre-fix bare-substring probe (`"infer" in proc.stdout`) misread this as a v2 binary,
# then let the resulting real `infer` call fail against a stub that (correctly, for a v1
# binary) doesn't implement it.
V1_PROSE_STUB = """#!/bin/sh
case "$1" in
  --help)
    echo "USAGE: gaiafield <index|neighbors|stats> [--json]"
    echo "Note: statistical inference is not yet supported in this build."
    ;;
  *)
    echo "unrecognized subcommand: $1" >&2
    exit 2
    ;;
esac
"""


def _write_stub(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _seed_fake_index(vault: Path) -> None:
    """`inferred_candidates()`/`surprise_candidates()` require an existing graph.db
    before they'll even shell out — write an empty placeholder rather than running a real
    `gaiafield index` (this eval never depends on the real crate)."""
    gaiafield_dir = vault / ".gaiafield"
    gaiafield_dir.mkdir(parents=True, exist_ok=True)
    (gaiafield_dir / "graph.db").write_bytes(b"")


def _vault_snapshot(vault: Path) -> dict[str, tuple[int, float]]:
    """(size, mtime) for every file under `vault` except `.gaiafield/` — engine-internal
    state that inference is expected to touch, not vault content, which it must not."""
    snap = {}
    for p in vault.rglob("*"):
        if not p.is_file() or ".gaiafield" in p.relative_to(vault).parts:
            continue
        st = p.stat()
        snap[str(p.relative_to(vault))] = (st.st_size, st.st_mtime)
    return snap


def _run_v2_phase(vault: Path, graph_mod) -> dict | None:
    sandbox_vault = make_sandbox(vault)
    try:
        _seed_fake_index(sandbox_vault)
        stub = sandbox_vault.parent / "gaiafield-stub-v2"
        _write_stub(stub, V2_STUB)

        import os
        old_env = os.environ.get(graph_mod.GAIAFIELD_BIN_ENV)
        os.environ[graph_mod.GAIAFIELD_BIN_ENV] = str(stub)
        try:
            before = _vault_snapshot(sandbox_vault)

            infer_result = graph_mod.ensure_inferred(sandbox_vault)
            if isinstance(infer_result, graph_mod.GraphUnavailable):
                return {"eval": "inferred_candidates", "pass": False, "detail": f"ensure_inferred failed: {infer_result}"}

            default_result = graph_mod.inferred_candidates(sandbox_vault, NOTE, k=5)
            if isinstance(default_result, graph_mod.GraphUnavailable):
                return {"eval": "inferred_candidates", "pass": False, "detail": f"inferred_candidates failed: {default_result}"}

            # include_ambiguous=True must still surface it — proves the filter is
            # selective, not a bug that drops everything.
            with_ambiguous = graph_mod.inferred_candidates(sandbox_vault, NOTE, k=5, include_ambiguous=True)

            # (d) the same client-side AMBIGUOUS filter applies to surprise_candidates(),
            # not just candidates()/inferred_candidates() — the rule is per-edge-label,
            # not per-subcommand.
            surprise_default = graph_mod.surprise_candidates(sandbox_vault, top=10)

            after = _vault_snapshot(sandbox_vault)
        finally:
            if old_env is None:
                os.environ.pop(graph_mod.GAIAFIELD_BIN_ENV, None)
            else:
                os.environ[graph_mod.GAIAFIELD_BIN_ENV] = old_env

        problems = []

        # (a) labeled and structurally separated from deterministic edges: every row
        # carries kind="inferred" plus a label — deterministic backlink dicts never do.
        if not default_result:
            problems.append("default inferred_candidates() call returned no rows at all")
        elif not all(row.get("kind") == "inferred" and "label" in row for row in default_result):
            problems.append(f"expected every row to carry kind='inferred' and a label, got {default_result}")

        # (b) AMBIGUOUS excluded by default, even though the stub returns it unconditionally.
        labels = {row.get("label") for row in default_result}
        if "AMBIGUOUS" in labels:
            problems.append(f"default call (include_ambiguous=False) leaked an AMBIGUOUS row: {default_result}")
        if "INFERRED" not in labels:
            problems.append(f"expected an INFERRED row in the default result, got labels {labels}")

        if isinstance(with_ambiguous, graph_mod.GraphUnavailable) or "AMBIGUOUS" not in {
            row.get("label") for row in with_ambiguous
        }:
            problems.append(f"include_ambiguous=True unexpectedly dropped the AMBIGUOUS row: {with_ambiguous!r}")

        # (d) surprise_candidates() default excludes AMBIGUOUS too, even though the stub
        # returns it unconditionally — same client-side rule as (b), different subcommand.
        if isinstance(surprise_default, graph_mod.GraphUnavailable):
            problems.append(f"surprise_candidates() failed: {surprise_default}")
        elif "AMBIGUOUS" in {row.get("label") for row in surprise_default}:
            problems.append(
                f"surprise_candidates() default (include_ambiguous=False) leaked an AMBIGUOUS row: {surprise_default}"
            )

        # (c) report-only: zero vault-content modifications from any of the calls above.
        if before != after:
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            problems.append(f"vault content changed during inference consumption (report-only violation): {changed}")

        if problems:
            return {"eval": "inferred_candidates", "pass": False, "detail": "; ".join(problems)}
        return None
    finally:
        teardown_sandbox(sandbox_vault)


def _run_v1_phase(vault: Path, graph_mod) -> dict | None:
    sandbox_vault = make_sandbox(vault)
    try:
        _seed_fake_index(sandbox_vault)
        stub = sandbox_vault.parent / "gaiafield-stub-v1"
        _write_stub(stub, V1_STUB)

        import os
        old_env = os.environ.get(graph_mod.GAIAFIELD_BIN_ENV)
        os.environ[graph_mod.GAIAFIELD_BIN_ENV] = str(stub)
        try:
            dlq_dir = sandbox_vault / "00_Memory" / "dlq"
            before_dlq = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()

            infer_result = graph_mod.ensure_inferred(sandbox_vault)
            candidates_result = graph_mod.inferred_candidates(sandbox_vault, NOTE, k=5)

            after_dlq = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()
        finally:
            if old_env is None:
                os.environ.pop(graph_mod.GAIAFIELD_BIN_ENV, None)
            else:
                os.environ[graph_mod.GAIAFIELD_BIN_ENV] = old_env

        problems = []
        for label, result in (("ensure_inferred", infer_result), ("inferred_candidates", candidates_result)):
            if not isinstance(result, graph_mod.GraphUnavailable):
                problems.append(f"{label}() against a v1 (pre-infer) stub should degrade, got {result!r}")
            elif result.reason != "no-inference":
                problems.append(f"{label}() expected reason='no-inference', got {result.reason!r}")

        if after_dlq != before_dlq:
            problems.append(
                f"v1-binary degradation must be silent — unexpected new DLQ note(s): {after_dlq - before_dlq}"
            )

        if problems:
            return {"eval": "inferred_candidates", "pass": False, "detail": "; ".join(problems)}
        return None
    finally:
        teardown_sandbox(sandbox_vault)


def _run_v1_prose_phase(vault: Path, graph_mod) -> dict | None:
    """Finding 1's exact reproduction: a v1 stub whose `--help` prose contains the word
    "inference" without listing infer/candidates/surprise as actual subcommands. Pins
    both the direct probe result and the end-to-end silent-degradation behavior."""
    sandbox_vault = make_sandbox(vault)
    try:
        _seed_fake_index(sandbox_vault)
        stub = sandbox_vault.parent / "gaiafield-stub-v1-prose"
        _write_stub(stub, V1_PROSE_STUB)

        problems = []

        # (f) the cleanest place to pin the token-boundary fix directly: the bare
        # substring check this replaces (`"infer" in proc.stdout`) would return True
        # here, since "infer" is a substring of "inference".
        if graph_mod._supports_inference(str(stub)):
            problems.append(
                "_supports_inference() returned True for a stub whose --help only "
                "mentions 'inference' in prose — the word-boundary fix regressed"
            )

        import os
        old_env = os.environ.get(graph_mod.GAIAFIELD_BIN_ENV)
        os.environ[graph_mod.GAIAFIELD_BIN_ENV] = str(stub)
        try:
            dlq_dir = sandbox_vault / "00_Memory" / "dlq"
            before_dlq = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()

            infer_result = graph_mod.ensure_inferred(sandbox_vault)

            after_dlq = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()
        finally:
            if old_env is None:
                os.environ.pop(graph_mod.GAIAFIELD_BIN_ENV, None)
            else:
                os.environ[graph_mod.GAIAFIELD_BIN_ENV] = old_env

        # (g) silent no-inference degradation — not a call-failed DLQ note from a real
        # `infer` invocation against a stub that (correctly, for a v1 binary) rejects it.
        if not isinstance(infer_result, graph_mod.GraphUnavailable):
            problems.append(f"ensure_inferred() against the prose-only stub should degrade, got {infer_result!r}")
        elif infer_result.reason != "no-inference":
            problems.append(f"ensure_inferred() expected reason='no-inference', got {infer_result.reason!r}")

        if after_dlq != before_dlq:
            problems.append(
                "the reproduced false-positive: an 'inference'-in-prose v1 stub must degrade silently, but got "
                f"new DLQ note(s): {after_dlq - before_dlq}"
            )

        if problems:
            return {"eval": "inferred_candidates", "pass": False, "detail": "; ".join(problems)}
        return None
    finally:
        teardown_sandbox(sandbox_vault)


def _run_real_binary_phase(vault: Path, graph_mod) -> dict:
    """Phase 4 — the stub-false-confidence closer (Fix 2). Mirrors `eval_graph_context`'s/
    `eval_search_parity`'s presence-gate style: this eval does not build the crate itself,
    it only uses a binary that's already there. Skips cleanly (still `pass: True`) when no
    real, v2-capable binary is configured — real coverage of this phase requires `cargo
    build -p gaiafield` plus `TOOLKIT_GAIAFIELD_BIN` pointed at the resulting binary, both
    outside this script's job."""
    binary = graph_mod.gaiafield_binary()
    if binary is None:
        return {
            "eval": "inferred_candidates", "pass": True,
            "detail": "real-binary phase skipped: no TOOLKIT_GAIAFIELD_BIN / gaiafield on PATH",
        }
    if not graph_mod._supports_inference(binary):
        return {
            "eval": "inferred_candidates", "pass": True,
            "detail": f"real-binary phase skipped: {binary} does not probe v2-capable (no infer/candidates/surprise)",
        }

    sandbox_vault = make_sandbox(vault)
    try:
        index_result = graph_mod.ensure_index(sandbox_vault, full=True)
        if isinstance(index_result, graph_mod.GraphUnavailable):
            return {
                "eval": "inferred_candidates", "pass": False,
                "detail": f"real-binary phase: ensure_index failed: {index_result.detail}",
            }

        infer_result = graph_mod.ensure_inferred(sandbox_vault)
        if isinstance(infer_result, graph_mod.GraphUnavailable):
            return {
                "eval": "inferred_candidates", "pass": False,
                "detail": f"real-binary phase: ensure_inferred failed: {infer_result.detail}",
            }

        default_surprise = graph_mod.surprise_candidates(sandbox_vault, top=50)
        if isinstance(default_surprise, graph_mod.GraphUnavailable):
            return {
                "eval": "inferred_candidates", "pass": False,
                "detail": f"real-binary phase: surprise_candidates failed: {default_surprise.detail}",
            }

        problems = []
        if not default_surprise:
            problems.append(
                "real-binary phase: surprise_candidates() returned no rows at all against a "
                "freshly indexed+inferred vault — nothing to assert pair-shape/label against"
            )
        for row in default_surprise:
            if "a" not in row or "b" not in row:
                problems.append(f"real-binary phase: expected a pair-shaped row (a/b), got {row}")
                break
            if "path" in row:
                problems.append(
                    f"real-binary phase: surprise row unexpectedly carries a single-note 'path' "
                    f"key — it should be pair-shaped (a/b) instead, got {row}"
                )
                break
            if "label" not in row:
                problems.append(f"real-binary phase: expected every row to carry a label, got {row}")
                break
        if any(row.get("label") == "AMBIGUOUS" for row in default_surprise):
            problems.append(
                f"real-binary phase: default surprise_candidates() (include_ambiguous=False) "
                f"leaked an AMBIGUOUS row: {default_surprise}"
            )

        if problems:
            return {"eval": "inferred_candidates", "pass": False, "detail": "; ".join(problems)}
        return {
            "eval": "inferred_candidates", "pass": True,
            "detail": f"real-binary phase: {len(default_surprise)} pair-shaped, labeled, non-ambiguous surprise row(s)",
        }
    finally:
        teardown_sandbox(sandbox_vault)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import graph as graph_mod

    if not (vault / NOTE).is_file():
        return {"eval": "inferred_candidates", "pass": False, "detail": f"fixture not present: {NOTE}"}

    v2_problem = _run_v2_phase(vault, graph_mod)
    if v2_problem is not None:
        return v2_problem

    v1_problem = _run_v1_phase(vault, graph_mod)
    if v1_problem is not None:
        return v1_problem

    v1_prose_problem = _run_v1_prose_phase(vault, graph_mod)
    if v1_prose_problem is not None:
        return v1_prose_problem

    real_binary_result = _run_real_binary_phase(vault, graph_mod)
    if not real_binary_result["pass"]:
        return real_binary_result

    return {
        "eval": "inferred_candidates", "pass": True,
        "detail": (
            "v2 stub: labeled+separated, AMBIGUOUS excluded by default (candidates and surprise), "
            "zero vault mutation; v1 stub: silent no-inference degradation; v1-prose stub "
            "('inference' in --help prose): _supports_inference() correctly returns False, "
            "silent no-inference degradation, no DLQ note; " + real_binary_result["detail"]
        ),
    }
