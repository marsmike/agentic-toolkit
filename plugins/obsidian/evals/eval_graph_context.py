"""Eval: `graph.py`'s `graph_context()` helper against a real gaiafield binary.

Mirrors `eval_search_parity`'s presence gate: this eval does not build the crate itself —
that's cargo's job, not CI's Python lane. If no gaiafield binary is available
(`TOOLKIT_GAIAFIELD_BIN` env var, else PATH — release binaries don't exist yet as of R3,
see docs/PLAN.md), it reports pass with detail "gaiafield not present".

Three phases:

0. **Call-failure phase** (runs unconditionally, regardless of whether a real gaiafield
   binary happens to be installed on this machine): points `TOOLKIT_GAIAFIELD_BIN` at a
   stub binary that always exits 1, then asserts `ensure_index()` degrades to
   `GraphUnavailable("call-failed", ...)` and that the DLQ note the module's docstring
   promises for this abnormal path (as opposed to the normal "binary absent" degrade) is
   actually written under a sandbox's `00_Memory/dlq/`, carrying the documented
   frontmatter keys (`vault_utils.write_dlq_note`'s convention). Runs against its own
   sandbox copy (`_sandbox.py`), never `./vault`.

When a binary is present, this runs against a sandbox copy (`_sandbox.py`) — indexing
writes a graph.db, so this must never touch the real `./vault` — for a capture planted in
the birding cluster, using the top-two matches `search.propose_placement()` would surface
for birding vocabulary (`Field-Guide-Project.md`, `Birding.md`; see
`vault/04_Resources/Guides/Test-Corpus-Map.md`'s cluster map) as `matched_paths`, and
asserts:

(a) at least one correct Level-1 backlink candidate from the planted field-guide cluster
    that isn't already one of the two matches — e.g. `Species-Accounts-Workflow.md`,
    `Illustration-Sourcing.md`, `Reference-Library.md`, `Publisher-Outreach-Log.md`, or
    the field-guide `Weekly-Review.md` — all of which both matches directly link to.
(b) a non-empty bridge-opportunity list, deterministically guaranteed regardless of which
    of the two matches `propose_placement()` would rank first (02_Projects or 03_Areas):
    both `Field-Guide-Project.md` and `Birding.md` link directly to `Alex-Vega.md`, the
    vault's root bridge note (Test-Corpus-Map.md: "root persona, links into all three
    clusters"), which — living at the vault root rather than in any 02/03/04 subtree —
    can never share a top-level folder with either placement candidate.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

MATCHED_PATHS = [
    "02_Projects/field-guide/Field-Guide-Project.md",
    "03_Areas/Birding.md",
]
EXPECTED_BACKLINK_STEMS = {
    "Species-Accounts-Workflow",
    "Illustration-Sourcing",
    "Reference-Library",
    "Publisher-Outreach-Log",
    "Weekly-Review",
}
BRIDGE_NOTE = "Alex-Vega.md"
DLQ_FRONTMATTER_KEYS = ("description", "status", "created", "tags", "confidence")


def _run_call_failure_phase(vault: Path, graph_mod, scripts_dir: Path) -> dict | None:
    """Point `TOOLKIT_GAIAFIELD_BIN` at a stub that exits 1 and assert `ensure_index()`
    degrades to `GraphUnavailable("call-failed")` with a DLQ note written to the sandbox's
    `00_Memory/dlq/`. Returns a failing eval dict on any problem, else None. Independent of
    whether a real gaiafield binary is installed — it fabricates its own."""
    import sys
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import vault_utils

    sandbox_vault = make_sandbox(vault)
    try:
        stub = sandbox_vault.parent / "gaiafield-stub-exit1"
        stub.write_text("#!/bin/sh\necho 'boom: simulated gaiafield failure' >&2\nexit 1\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

        old_env = os.environ.get(graph_mod.GAIAFIELD_BIN_ENV)
        os.environ[graph_mod.GAIAFIELD_BIN_ENV] = str(stub)
        try:
            result = graph_mod.ensure_index(sandbox_vault, full=True)
        finally:
            if old_env is None:
                os.environ.pop(graph_mod.GAIAFIELD_BIN_ENV, None)
            else:
                os.environ[graph_mod.GAIAFIELD_BIN_ENV] = old_env

        if not isinstance(result, graph_mod.GraphUnavailable):
            return {
                "eval": "graph_context", "pass": False,
                "detail": f"call-failure phase: expected GraphUnavailable for a failing binary, got {result!r}",
            }
        if result.reason != "call-failed":
            return {
                "eval": "graph_context", "pass": False,
                "detail": f"call-failure phase: expected reason='call-failed', got {result.reason!r}",
            }

        dlq_dir = sandbox_vault / "00_Memory" / "dlq"
        dlq_notes = sorted(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else []
        if not dlq_notes:
            return {
                "eval": "graph_context", "pass": False,
                "detail": "call-failure phase: expected a DLQ note under 00_Memory/dlq/, found none",
            }

        fm, _ = vault_utils.read_frontmatter(dlq_notes[-1])
        missing = [k for k in DLQ_FRONTMATTER_KEYS if k not in fm]
        if missing:
            return {
                "eval": "graph_context", "pass": False,
                "detail": f"call-failure phase: DLQ note {dlq_notes[-1].name} missing frontmatter keys {missing}",
            }
        return None
    finally:
        teardown_sandbox(sandbox_vault)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import graph as graph_mod

    call_failure_problem = _run_call_failure_phase(vault, graph_mod, scripts_dir)
    if call_failure_problem is not None:
        return call_failure_problem

    if not graph_mod.available():
        return {"eval": "graph_context", "pass": True, "detail": "gaiafield not present"}

    for rel in MATCHED_PATHS:
        if not (vault / rel).is_file():
            return {"eval": "graph_context", "pass": False, "detail": f"fixture not present: {rel}"}

    sandbox_vault = make_sandbox(vault)
    try:
        index_result = graph_mod.ensure_index(sandbox_vault, full=True)
        if isinstance(index_result, graph_mod.GraphUnavailable):
            return {"eval": "graph_context", "pass": False, "detail": f"ensure_index failed: {index_result.detail}"}

        context = graph_mod.graph_context(sandbox_vault, MATCHED_PATHS, k=1)
        if isinstance(context, graph_mod.GraphUnavailable):
            return {"eval": "graph_context", "pass": False, "detail": f"graph_context failed: {context.detail}"}

        backlink_stems = {Path(n["path"]).stem for n in context["backlink_candidates"]}
        bridge_paths = [n["path"] for n in context["bridge_opportunities"]]

        problems = []
        matched = backlink_stems & EXPECTED_BACKLINK_STEMS
        if not matched:
            problems.append(
                f"expected a backlink candidate among {sorted(EXPECTED_BACKLINK_STEMS)}, got {sorted(backlink_stems)}"
            )
        if not bridge_paths:
            problems.append("bridge_opportunities is empty")
        elif BRIDGE_NOTE not in bridge_paths:
            problems.append(f"expected {BRIDGE_NOTE!r} among bridge_opportunities, got {bridge_paths}")

        if problems:
            return {"eval": "graph_context", "pass": False, "detail": "; ".join(problems)}
        return {
            "eval": "graph_context", "pass": True,
            "detail": (
                f"placement_folder={context['placement_folder']!r}, "
                f"backlinks={sorted(backlink_stems)}, bridges={bridge_paths}"
            ),
        }
    finally:
        teardown_sandbox(sandbox_vault)
