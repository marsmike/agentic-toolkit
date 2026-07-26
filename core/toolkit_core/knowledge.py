"""Graph status for `toolkit doctor`: gaiafield binary discovery + a `stats` call.

Same preference chain as `plugins/obsidian/scripts/graph.py` (`TOOLKIT_GAIAFIELD_BIN` env
var, else `gaiafield` on PATH, else the well-known `toolkit engines install` dir) —
deliberately reimplemented rather than imported, since `core` never depends on a plugin
(docs/PLAN.md's plugin-independence rule runs both directions: plugins depend on
core/contract only, and core stays plugin-agnostic too). The well-known-dir step lives
in `engines.py`; this module is allowed to import it since both are `core`.

R3 scope: report what already exists (db present, counts, freshness). This module never
runs `gaiafield index` itself — indexing is a plugin/skill's job; `doctor` only reports
state, per its existing "surfaces, never mutates" character (see `dlq_status` in
`vault.py`).

v2 addition (R5): the same `stats --json` call gains inference fields once the engine
supports them (`contract/KNOWLEDGE_API.md`'s v2 section) — model name, high/low gates,
inferred/ambiguous edge counts. Three states, distinguished the same way
`scripts/graph.py`'s `_supports_inference()` probes it: no `model` key at all means a v1
binary that predates inference; the key present but empty means a v2 binary that hasn't
run `gaiafield infer` yet; populated is the normal reporting case. `doctor` only ever
reports this — it never runs `infer` itself.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from toolkit_core import engines
from toolkit_core.vault import ACTIVE_CONTENT_FOLDERS

GAIAFIELD_BIN_ENV = "TOOLKIT_GAIAFIELD_BIN"
FARSIGHT_BIN_ENV = "TOOLKIT_FARSIGHT_BIN"
STATS_TIMEOUT = 30
INDEX_TIMEOUT = 60
QUERY_TIMEOUT = 30


def gaiafield_binary() -> str | None:
    """`TOOLKIT_GAIAFIELD_BIN` env var wins; then a `gaiafield` binary on PATH; then the
    well-known `toolkit engines install` dir (`engines.binary_path`) — the one added
    probe step that makes "clone + uv tool install + toolkit engines install" alone
    enough, no PATH/env wiring required."""
    env = os.environ.get(GAIAFIELD_BIN_ENV)
    if env:
        return env
    on_path = shutil.which("gaiafield")
    if on_path:
        return on_path
    installed = engines.binary_path("gaiafield")
    return str(installed) if installed.is_file() else None


def farsight_binary() -> str | None:
    """Same three-step discovery chain as `gaiafield_binary()`, for the other engine."""
    env = os.environ.get(FARSIGHT_BIN_ENV)
    if env:
        return env
    on_path = shutil.which("farsight")
    if on_path:
        return on_path
    installed = engines.binary_path("farsight")
    return str(installed) if installed.is_file() else None


def default_db_path(vault_path: Path) -> Path:
    """Mirrors `gaiafield::default_db_path` — `<vault>/.gaiafield/graph.db`."""
    return Path(vault_path) / ".gaiafield" / "graph.db"


def _newest_active_note_mtime(vault_path: Path) -> float | None:
    """Newest mtime across 02_Projects/03_Areas/04_Resources — the freshness signal
    doctor compares against the graph database's own mtime."""
    vault_path = Path(vault_path)
    newest: float | None = None
    for folder in ACTIVE_CONTENT_FOLDERS:
        folder_path = vault_path / folder
        if not folder_path.is_dir():
            continue
        for note in folder_path.rglob("*.md"):
            try:
                mtime = note.stat().st_mtime
            except OSError:
                continue
            if newest is None or mtime > newest:
                newest = mtime
    return newest


def _inference_status(stats: dict) -> dict:
    """The `inference` sub-section of `graph_status`'s report, derived from the same
    `stats` payload — see the module docstring's v2 addition for the three-state logic."""
    if "model" not in stats:
        return {"available": False, "note": "engine lacks inference (v1 binary — no inference fields in stats)"}

    model = stats.get("model")
    if not model:
        return {"available": False, "note": "not inferred — run `gaiafield infer` to compute inferred edges"}

    inferred_edges = stats.get("inferred_edges")
    ambiguous_edges = stats.get("ambiguous_edges")
    return {
        "available": True,
        "model": model,
        "high_gate": stats.get("high_gate"),
        "low_gate": stats.get("low_gate"),
        "inferred_edges": inferred_edges,
        "ambiguous_edges": ambiguous_edges,
        "note": f"{inferred_edges} inferred, {ambiguous_edges} ambiguous (model={model})",
    }


def graph_status(vault_path: Path) -> dict:
    """Graph section for `toolkit doctor`. Never raises: every failure mode collapses
    into a `present`/`note` pair the caller can render directly, matching the rest of
    doctor's report shape."""
    binary = gaiafield_binary()
    if binary is None:
        return {"present": False, "note": "gaiafield not present"}

    db_path = default_db_path(vault_path)
    if not db_path.is_file():
        return {
            "present": False,
            "note": f"gaiafield binary found ({binary}) but no graph database yet — run `gaiafield index`",
        }

    try:
        proc = subprocess.run(
            [binary, "stats", "--vault", str(vault_path), "--db", str(db_path), "--json"],
            capture_output=True, text=True, timeout=STATS_TIMEOUT, check=True,
        )
        stats = json.loads(proc.stdout)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or str(exc)).strip()
        return {"present": True, "note": f"gaiafield stats failed: {detail}"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"present": True, "note": f"gaiafield stats failed: {exc}"}

    db_mtime = db_path.stat().st_mtime
    newest_note = _newest_active_note_mtime(vault_path)
    stale = newest_note is not None and newest_note > db_mtime

    return {
        "present": True,
        "db_path": str(db_path),
        "nodes": stats.get("nodes"),
        "edges": stats.get("edges"),
        "dangling_edges": stats.get("dangling_edges"),
        "boundary_violations": stats.get("boundary_violations"),
        "stale": stale,
        "inference": _inference_status(stats),
        "note": (
            "index may be stale — a note changed since the last `gaiafield index`"
            if stale else "index is fresh"
        ),
    }


# ---------------------------------------------------------------------------
# `toolkit demo` support — real, best-effort calls to both engines. Every function here
# returns None (never raises) on any failure so demo.py can treat "engine call didn't
# work" as just another step to report honestly, not a crash. This deliberately
# duplicates a slice of plugins/obsidian/scripts/graph.py's shape (ensure_index /
# neighbors / infer / candidates) rather than importing it — same plugin-independence
# rule as gaiafield_binary() above.
# ---------------------------------------------------------------------------


def farsight_query(vault_path: Path, query: str, k: int = 5) -> dict:
    """Shell out to `farsight query --json`. Never raises: `{"available": False, ...}`
    when no binary is present, `{"available": True, "results": [...]}` on success, or
    `{"available": True, "note": ...}` if a present binary's call itself fails."""
    binary = farsight_binary()
    if binary is None:
        return {"available": False, "note": "farsight not present"}
    try:
        proc = subprocess.run(
            [binary, "query", query, "--vault", str(vault_path), "--k", str(k), "--json"],
            capture_output=True, text=True, timeout=QUERY_TIMEOUT, check=True,
        )
        results = json.loads(proc.stdout)
    except subprocess.CalledProcessError as exc:
        return {"available": True, "note": f"farsight query failed: {(exc.stderr or str(exc)).strip()}"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"available": True, "note": f"farsight query failed: {exc}"}
    return {"available": True, "binary": binary, "results": results}


def gaiafield_index(vault_path: Path) -> dict | None:
    """Run `gaiafield index` (incremental). `None` on any failure — a demo step treats
    that as "skip this step", never a crash."""
    binary = gaiafield_binary()
    if binary is None:
        return None
    try:
        proc = subprocess.run(
            [binary, "index", "--vault", str(vault_path), "--json"],
            capture_output=True, text=True, timeout=INDEX_TIMEOUT, check=True,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def gaiafield_neighbors(vault_path: Path, note: str, depth: int = 1) -> list | None:
    binary = gaiafield_binary()
    if binary is None:
        return None
    try:
        proc = subprocess.run(
            [binary, "neighbors", note, "--vault", str(vault_path), "--depth", str(depth), "--json"],
            capture_output=True, text=True, timeout=STATS_TIMEOUT, check=True,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def gaiafield_infer(vault_path: Path) -> dict | None:
    """Run `gaiafield infer` — the embedding pass gating `gaiafield_candidates()`.
    Report-only per contract/KNOWLEDGE_API.md's v2 rule 1: this computes candidates for
    a human to look at, never writes vault content."""
    binary = gaiafield_binary()
    if binary is None:
        return None
    try:
        proc = subprocess.run(
            [binary, "infer", "--vault", str(vault_path), "--json"],
            capture_output=True, text=True, timeout=INDEX_TIMEOUT, check=True,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def gaiafield_candidates(vault_path: Path, note: str, k: int = 3) -> list | None:
    binary = gaiafield_binary()
    if binary is None:
        return None
    try:
        proc = subprocess.run(
            [binary, "candidates", note, "--vault", str(vault_path), "--k", str(k), "--json"],
            capture_output=True, text=True, timeout=STATS_TIMEOUT, check=True,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
