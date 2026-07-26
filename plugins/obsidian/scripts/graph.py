"""Thin client for the gaiafield binary — deterministic graph consumption over the
vault's wikilink graph (`contract/KNOWLEDGE_API.md`'s `neighbors`/`context` surface).

Mirrors `search.py`'s farsight preference chain: resolve a binary via
`TOOLKIT_GAIAFIELD_BIN` env var, else `gaiafield` on PATH, else absent. Absence is a
normal, expected state (pre-adoption, no release binaries yet) and every function here
degrades to a `GraphUnavailable` outcome rather than raising. A binary that IS present
but fails on a real invocation is a different, abnormal state — that failure is logged to
the vault's dead-letter queue (`vault_utils.write_dlq_note`) before degrading, per
`contract/KNOWLEDGE_API.md`'s dead-letter rule.

R3 scope only: deterministic graph consumption — index/neighbors/stats, and the
`graph_context` helper the distill skill uses for phase-1 backlink/bridge candidates. No
inferred edges, no LLM calls; see `crates/gaiafield/README.md` (v1 scope) and
`vault/04_Resources/Concepts/Deterministic-vs-Inferred-Graph-Edges.md`. Surprise scoring
and inferred edges are gaiafield v2/R4+, not this module.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vault_utils import write_dlq_note

GAIAFIELD_BIN_ENV = "TOOLKIT_GAIAFIELD_BIN"
DEFAULT_TIMEOUT = 30
INDEX_TIMEOUT = 60


@dataclass(frozen=True)
class GraphUnavailable:
    """Returned instead of raising whenever a call in this module can't produce graph data.

    reason:
      "no-binary"   — no gaiafield binary found. Normal pre-adoption state; never logged
                      to the DLQ (mirrors search.py's farsight-absent path).
      "no-index"    — binary present but no graph database exists yet at the expected
                      path. Normal before the first `ensure_index()` call; never logged.
      "call-failed" — the binary was invoked and it (or the parse of its output) failed.
                      Abnormal — the caller that detected it has already written a DLQ
                      note under `00_Memory/dlq/` before returning this.
    """
    reason: str
    detail: str


def gaiafield_binary() -> str | None:
    """`TOOLKIT_GAIAFIELD_BIN` env var wins; otherwise a `gaiafield` binary on PATH, if any."""
    return os.environ.get(GAIAFIELD_BIN_ENV) or shutil.which("gaiafield")


def available() -> bool:
    return gaiafield_binary() is not None


def default_db_path(vault: Path) -> Path:
    """Mirrors `gaiafield::default_db_path` — `<vault>/.gaiafield/graph.db`."""
    return Path(vault) / ".gaiafield" / "graph.db"


def _run_json(binary: str, args: list[str], timeout: int = DEFAULT_TIMEOUT) -> tuple[Any, str | None]:
    """Shell out to gaiafield with `--json` appended. Returns (parsed_json, None) on
    success, (None, detail) on any failure — never raises."""
    try:
        proc = subprocess.run(
            [binary, *args, "--json"], capture_output=True, text=True, timeout=timeout, check=True,
        )
        return json.loads(proc.stdout), None
    except subprocess.CalledProcessError as exc:
        return None, (exc.stderr or str(exc)).strip()
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _dlq_on_call_failure(vault: Path, operation: str, detail: str) -> None:
    write_dlq_note(
        vault,
        slug=f"gaiafield-{operation}-failed",
        title=f"gaiafield {operation} invocation failed",
        what_happened=f"`gaiafield {operation}` was invoked but failed: {detail}",
        why_recorded=(
            "A gaiafield binary is present but a call to it failed — this is not the "
            "normal 'binary absent' degrade path, so it's worth a human look rather than "
            "a silently-skipped graph feature."
        ),
        confidence="low",
    )


def ensure_index(vault: Path, full: bool = False) -> dict | GraphUnavailable:
    """Run `gaiafield index` (incremental by default). The gate every other call in this
    module depends on — call this once per skill/CLI run before `neighbors()`/
    `graph_stats()`/`graph_context()` so the database reflects the vault's current state."""
    binary = gaiafield_binary()
    if binary is None:
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")

    args = ["index", "--vault", str(vault)]
    if full:
        args.append("--full")
    result, error = _run_json(binary, args, timeout=INDEX_TIMEOUT)
    if error is not None:
        _dlq_on_call_failure(vault, "index", error)
        return GraphUnavailable("call-failed", f"gaiafield index failed: {error}")
    return result


def neighbors(vault: Path, note: str, depth: int = 1, direction: str = "both") -> list[dict] | GraphUnavailable:
    """Depth-N neighbors of `note` (a vault-relative path or bare note name, wikilink
    semantics). Requires an existing database — call `ensure_index()` first; a missing
    database is reported as `GraphUnavailable("no-index", ...)`, not a call failure."""
    binary = gaiafield_binary()
    if binary is None:
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")
    if not default_db_path(vault).is_file():
        return GraphUnavailable("no-index", "no graph database yet — call ensure_index() first")

    args = ["neighbors", note, "--vault", str(vault), "--depth", str(depth), "--direction", direction]
    result, error = _run_json(binary, args)
    if error is not None:
        _dlq_on_call_failure(vault, "neighbors", error)
        return GraphUnavailable("call-failed", f"gaiafield neighbors {note!r} failed: {error}")
    return result


def graph_stats(vault: Path) -> dict | GraphUnavailable:
    """Node/edge counts, dangling-edge and boundary-violation counts, top-linked notes."""
    binary = gaiafield_binary()
    if binary is None:
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")
    if not default_db_path(vault).is_file():
        return GraphUnavailable("no-index", "no graph database yet — call ensure_index() first")

    result, error = _run_json(binary, ["stats", "--vault", str(vault)])
    if error is not None:
        _dlq_on_call_failure(vault, "stats", error)
        return GraphUnavailable("call-failed", f"gaiafield stats failed: {error}")
    return result


# ---------------------------------------------------------------------------
# graph_context — distill phase-1's deterministic backlink/bridge helper
# ---------------------------------------------------------------------------


def _top_level(path: str) -> str:
    """The first path segment: a PARA folder name for anything under 02/03/04, or the
    bare filename for a root-level note (e.g. `Alex-Vega.md`) — which can never equal a
    PARA folder name, so a root note always reads as a different top-level cluster from
    any 02_Projects/03_Areas/04_Resources placement."""
    return path.split("/", 1)[0]


def graph_context(vault: Path, matched_paths: list[str], k: int = 1) -> dict | GraphUnavailable:
    """Depth-`k` neighbors of every note in `matched_paths` (the top text-search matches),
    split into:

    - `backlink_candidates` — neighbors not already present in `matched_paths`: notes a
      pure keyword/BM25 search missed but the graph says are directly connected. These
      are Level-1 backlink candidates for the distill workflow's enrichment step.
    - `bridge_opportunities` — the subset of `backlink_candidates` whose top-level PARA
      subtree differs from `matched_paths[0]`'s (the same folder
      `search.propose_placement()` would propose, since it is the top-ranked match). This
      is the deterministic precursor of surprise scoring (gaiafield v2, R4+,
      `crates/gaiafield/README.md`): a same-cluster neighbor is an ordinary backlink; a
      different-cluster one is a bridge worth a human's attention, without any scoring or
      inference involved.

    Returns `GraphUnavailable` if the graph isn't available, no index exists yet, or the
    neighbor lookup fails for every matched path. A lookup failure for a subset of
    `matched_paths` is skipped rather than failing the whole call (its own DLQ note, if
    any, is already written by `neighbors()`).
    """
    if not matched_paths:
        return {"matched_paths": [], "placement_folder": None, "backlink_candidates": [], "bridge_opportunities": []}

    if not available():
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")
    if not default_db_path(vault).is_file():
        return GraphUnavailable("no-index", "no graph database yet — call ensure_index() first")

    matched_set = set(matched_paths)
    placement_folder = _top_level(matched_paths[0])

    candidates: dict[str, dict] = {}
    any_success = False
    for note in matched_paths:
        result = neighbors(vault, note, depth=k, direction="both")
        if isinstance(result, GraphUnavailable):
            continue
        any_success = True
        for n in result:
            if n["path"] in matched_set:
                continue
            candidates.setdefault(n["path"], n)

    if not any_success:
        return GraphUnavailable("call-failed", "neighbors lookup failed for every matched path")

    backlink_candidates = sorted(candidates.values(), key=lambda n: n["path"])
    bridge_opportunities = [n for n in backlink_candidates if _top_level(n["path"]) != placement_folder]

    return {
        "matched_paths": matched_paths,
        "placement_folder": placement_folder,
        "backlink_candidates": backlink_candidates,
        "bridge_opportunities": bridge_opportunities,
    }
