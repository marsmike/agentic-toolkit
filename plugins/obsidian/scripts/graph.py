"""Thin client for the gaiafield binary — deterministic graph consumption over the
vault's wikilink graph (`contract/KNOWLEDGE_API.md`'s `neighbors`/`context` surface).

Mirrors `search.py`'s farsight preference chain: resolve a binary via
`TOOLKIT_GAIAFIELD_BIN` env var, else `gaiafield` on PATH, else absent. Absence is a
normal, expected state (pre-adoption, no release binaries yet) and every function here
degrades to a `GraphUnavailable` outcome rather than raising. A binary that IS present
but fails on a real invocation is a different, abnormal state — that failure is logged to
the vault's dead-letter queue (`vault_utils.write_dlq_note`) before degrading, per
`contract/KNOWLEDGE_API.md`'s dead-letter rule.

R3 scope: deterministic graph consumption — index/neighbors/stats, and the
`graph_context` helper the distill skill uses for phase-1 backlink/bridge candidates.

v2 addition (R5, `contract/KNOWLEDGE_API.md`'s v2 section): `ensure_inferred()`,
`inferred_candidates()`, and `surprise_candidates()` consume gaiafield's statistical
inferred-edge layer (`infer`/`candidates`/`surprise` subcommands). Rule 1 of that section
binds every caller of these functions, not just this module: inferred edges are
candidates for a human decision, never inputs to an autonomous write — this module only
ever *reads* them, and writes nothing to the vault. A binary that predates v2 (no
`infer` subcommand) is a normal, silent degradation (`GraphUnavailable("no-inference")`),
probed for rather than discovered by a crash — see `_supports_inference()`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import judge
from judgments import questions as Q
from judgments.state import note_payload
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
      "no-judgment"  — adjudicate_candidates() only: no typed-judgment backend or key
                       (normal pre-adoption state, silent)
      "no-inference" — binary present and index present, but it predates gaiafield v2
                      (no `infer` subcommand). Normal for any binary built before R5;
                      never logged, same as "no-binary"/"no-index".
    """
    reason: str
    detail: str


def _engines_install_dir() -> Path:
    """Mirrors `core/toolkit_core/engines.py::install_dir()` — plugin scripts are
    self-contained (no import of `core`, per this file's module docstring), so the
    well-known `toolkit engines install` dir is redefined here rather than imported.
    Keep both in sync. Invariant: suffix is `.exe` iff `os.name == "nt"` — identical
    expression to `engines.py::binary_path()` and to `search.py`'s own mirror; the
    three must never drift apart on this check."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    suffix = ".exe" if os.name == "nt" else ""
    return base / "agentic-toolkit" / "bin" / f"gaiafield{suffix}"


def gaiafield_binary() -> str | None:
    """`TOOLKIT_GAIAFIELD_BIN` env var wins; then a `gaiafield` binary on PATH; then the
    well-known `toolkit engines install` dir — the one added probe step, so
    `toolkit engines install` alone is enough with no PATH/env wiring."""
    env = os.environ.get(GAIAFIELD_BIN_ENV)
    if env:
        return env
    on_path = shutil.which("gaiafield")
    if on_path:
        return on_path
    installed = _engines_install_dir()
    return str(installed) if installed.is_file() else None


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


# ---------------------------------------------------------------------------
# v2 — inferred edges (R5). Report-only: every function below only reads gaiafield's
# statistical layer; nothing here writes vault content. contract/KNOWLEDGE_API.md's v2
# section, rule 1.
# ---------------------------------------------------------------------------

HELP_TIMEOUT = 10

# The v2 subcommand surface this probe checks for, as whole words — never substring
# matches (see `_supports_inference()`'s docstring for the false-positive this fixes).
_INFERENCE_SUBCOMMAND_TOKENS = ("infer", "candidates", "surprise")

# Per-binary-path cache for `_supports_inference()`. A binary's capability can't change
# mid-process, so every consumer in this module (`ensure_inferred()`,
# `inferred_candidates()`, `surprise_candidates()`) probing independently otherwise pays
# for a redundant `--help` subprocess each — up to three per skill/CLI run for the same
# binary.
_inference_probe_cache: dict[str, bool] = {}


def _supports_inference(binary: str) -> bool:
    """Capability probe for the v2 `infer`/`candidates`/`surprise` subcommands.

    Asks `--help` rather than invoking `infer` directly: a v1 binary would exit non-zero
    on an unrecognized subcommand, which is indistinguishable from a real call failure
    without fragile stderr-message matching, and would wrongly earn a DLQ note for a
    perfectly normal "not built with inference" state. `--help` is side-effect-free and
    works identically on both binary generations.

    Two bugs in the original bare-substring check, both fixed here:

    - `"infer" in proc.stdout` matches inside ordinary help *prose*, not just an actual
      `infer` subcommand token — a v1 binary whose `--help` says "statistical inference
      is not yet supported in this build" probed as supporting inference (since "infer"
      is a substring of "inference"), and the real `infer`/`candidates`/`surprise` call
      that followed then failed and wrongly earned a DLQ note for what should have been a
      silent, normal "no-inference" degrade. Fixed with `\\b<token>\\b` word-boundary
      matching: a regex boundary requires a word/non-word transition on each side, and
      there is no such transition between the "r" of "infer" and the "e" that follows in
      "inference" (both are word characters) — so `\\binfer\\b` does NOT match inside
      "inference", only a standalone "infer" token, e.g. one entry in a
      `<index|neighbors|stats|infer|candidates|surprise>` usage line (pipes and
      whitespace are non-word characters, so they count as boundaries).
    - No returncode check — a failing `--help` invocation could still emit matching text.
      `proc.returncode == 0` is now required alongside the token match.

    All three subcommand tokens must appear as whole words for this to return True: a
    binary advertising only a subset isn't the full v2 surface this module's three
    consumers collectively depend on.

    Result is cached per binary path (module-level dict) — see `_inference_probe_cache`.
    Any probe failure (missing binary, timeout, non-zero exit, missing token) reads as
    "no", the safe default, and is cached the same as a genuine "no"."""
    if binary in _inference_probe_cache:
        return _inference_probe_cache[binary]

    try:
        proc = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=HELP_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        result = False
    else:
        result = proc.returncode == 0 and all(
            re.search(rf"\b{token}\b", proc.stdout) for token in _INFERENCE_SUBCOMMAND_TOKENS
        )

    _inference_probe_cache[binary] = result
    return result


def ensure_inferred(vault: Path) -> dict | GraphUnavailable:
    """Run `gaiafield infer` — the embedding pass that computes the inferred-edge layer
    on top of whatever `ensure_index()` already built. Mirrors `ensure_index()`'s shape:
    call once per skill/CLI run before `inferred_candidates()`/`surprise_candidates()`.
    Returns the raw `{embedded, inferred_edges, ambiguous_edges, model, high_gate,
    low_gate, elapsed_ms}` object on success."""
    binary = gaiafield_binary()
    if binary is None:
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")
    if not _supports_inference(binary):
        return GraphUnavailable("no-inference", "gaiafield binary has no `infer` subcommand (pre-v2)")

    args = ["infer", "--vault", str(vault)]
    result, error = _run_json(binary, args, timeout=INDEX_TIMEOUT)
    if error is not None:
        _dlq_on_call_failure(vault, "infer", error)
        return GraphUnavailable("call-failed", f"gaiafield infer failed: {error}")
    return result


def inferred_candidates(
    vault: Path, note: str, k: int = 5, include_ambiguous: bool = False
) -> list[dict] | GraphUnavailable:
    """Statistical candidates for `note` — semantic-similarity neighbors gaiafield's
    embedding pass surfaced, never deterministic wikilinks. Every row carries `score` and
    a `label` of `"INFERRED"` or `"AMBIGUOUS"` (`contract/KNOWLEDGE_API.md`'s v2 gates).

    `include_ambiguous=False` (the default) filters AMBIGUOUS rows out client-side, even
    if the binary's own `--include-ambiguous` handling were to misbehave — the v2
    contract's "surfaced only when a caller explicitly asks" rule is enforced here, not
    just requested of the engine. Callers presenting these to a human must label them
    distinctly from any deterministic (`graph_context()`) result — they are candidates
    for a decision, never a fact about the vault's link graph."""
    binary = gaiafield_binary()
    if binary is None:
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")
    if not default_db_path(vault).is_file():
        return GraphUnavailable("no-index", "no graph database yet — call ensure_index() first")
    if not _supports_inference(binary):
        return GraphUnavailable("no-inference", "gaiafield binary has no `infer` subcommand (pre-v2)")

    args = ["candidates", note, "--vault", str(vault), "--k", str(k)]
    if include_ambiguous:
        args.append("--include-ambiguous")
    result, error = _run_json(binary, args)
    if error is not None:
        _dlq_on_call_failure(vault, "candidates", error)
        return GraphUnavailable("call-failed", f"gaiafield candidates {note!r} failed: {error}")

    if include_ambiguous:
        return result
    return [row for row in result if row.get("label") != "AMBIGUOUS"]


def surprise_candidates(
    vault: Path, top: int = 10, include_ambiguous: bool = False
) -> list[dict] | GraphUnavailable:
    """Cross-domain leads: inferred edges whose deterministic graph distance is large (or
    infinite, or across a different PARA subtree) — pairs a pure similarity search
    wouldn't flag as related through the link graph. Derived scoring, not stored magic
    (`contract/KNOWLEDGE_API.md`'s v2 section, rule 5); gaiafield computes it, this just
    reads the result. Report-only, same as `inferred_candidates()` — present as optional
    leads a human can request, never as a proactive recommendation.

    **Row shape differs from `inferred_candidates()` — pair-shaped, not single-note.**
    `candidates` rows describe one *other* note relative to the note you asked about
    (`path`/`score`/`label`/...); `surprise` has no "queried note" to be relative to, so
    each row is the pair itself: `a`/`b` (both vault-relative paths), `score`, `surprise`,
    `det_distance`, `same_subtree`, `label`, `model` (`crates/gaiafield/src/lib.rs`'s
    `SurpriseRow`). A caller presenting these must render both `a` and `b`, never assume a
    `row["path"]` key exists — this module's original CLI spec had rows carry no `label` at
    all and (per that same spec bug) `--include-ambiguous` didn't do anything server-side;
    both are fixed at the contract layer as of gaiafield v2's `surprise` (Fix 2, R5) and
    this function's filter below is real defense-in-depth against a live flag now, not
    dead code guarding a no-op.

    `include_ambiguous=False` (the default) filters AMBIGUOUS rows out client-side, same
    as `inferred_candidates()` — the v2 contract's "surfaced only when a caller explicitly
    asks" rule applies at the edge-label level, regardless of which subcommand produced
    the row, so this function enforces it independently rather than trusting the binary's
    own `--include-ambiguous` handling alone."""
    binary = gaiafield_binary()
    if binary is None:
        return GraphUnavailable("no-binary", "no gaiafield binary found (TOOLKIT_GAIAFIELD_BIN or PATH)")
    if not default_db_path(vault).is_file():
        return GraphUnavailable("no-index", "no graph database yet — call ensure_index() first")
    if not _supports_inference(binary):
        return GraphUnavailable("no-inference", "gaiafield binary has no `infer` subcommand (pre-v2)")

    args = ["surprise", "--vault", str(vault), "--top", str(top)]
    if include_ambiguous:
        args.append("--include-ambiguous")
    result, error = _run_json(binary, args)
    if error is not None:
        _dlq_on_call_failure(vault, "surprise", error)
        return GraphUnavailable("call-failed", f"gaiafield surprise failed: {error}")

    if include_ambiguous:
        return result
    return [row for row in result if row.get("label") != "AMBIGUOUS"]


# ---------------------------------------------------------------------------
# Adjudication — a typed judgment per suggested pair (advisory, report-only)
# ---------------------------------------------------------------------------

MAX_PAIRS_PER_REQUEST = 40
ADJUDICATION_CHARS = 1200

# Policy per judgment backend, so it lives here and not in question text (contract/ROUTING.md,
# "Typed-judgment models"). Two numbers per pair: `link` (would a link help a reader; runs on
# the scale of the vault's own hand-made links, mean 0.75) and `mech` (same underlying idea; the
# better ranker, AUC 0.95 against blind labels where gaiafield's cosine reaches 0.75, but on a
# compressed scale where real matches sit at 0.10-0.30). `mech` therefore only counts once
# `link` clears a floor. Priors, 2026-09-22, jev-1.13, fitted in-sample on 105 labelled pairs of
# the bundled vault: 11 of 70 gaiafield suggestions read LIKELY-LINK (8 real, base rate 16%),
# 16 read LIKELY-NOISE (0 real), 0 of 15 unlinked cross-cluster pairs read LIKELY-LINK.
# Recalibrate on any other vault before trusting the labels; the ranking transfers, the cuts may not.
LINK_POLICY: dict[str, dict[str, float]] = {
    "jev": {"link_high": 0.70, "mech_high": 0.15, "link_floor": 0.35, "link_low": 0.30, "mech_low": 0.10,
            "max_order_gap": 0.30},
}


def _link_label(link: float, mech: float | None, policy: dict[str, float], order_gap: float = 0.0) -> str:
    """`order_gap` is how far the two views of a pair (a,b and b,a) disagreed. A pair the
    backend cannot answer the same way twice is undecided, whatever the average says."""
    mech = 0.0 if mech is None else mech
    if order_gap >= policy["max_order_gap"]:
        return "UNDECIDED"
    if link >= policy["link_high"] or (mech >= policy["mech_high"] and link >= policy["link_floor"]):
        return "LIKELY-LINK"
    if link <= policy["link_low"] and mech < policy["mech_low"]:
        return "LIKELY-NOISE"
    return "UNDECIDED"


def _pair_of(row: dict, note: str | None) -> tuple[str, str] | None:
    """`surprise` rows are pair-shaped (a/b); `candidates` rows carry one `path` and are
    relative to the note they were asked for."""
    if "a" in row and "b" in row:
        return row["a"], row["b"]
    if note and "path" in row:
        return note, row["path"]
    return None


def _adjudicate_once(vault: Path, pairs: list[tuple[str, str]], cache: dict, usage_total: dict) -> list[dict | None]:
    """One pass: raw {link, mech} per pair, in order, None where a note is missing or skipped."""
    raw: list[dict | None] = [None] * len(pairs)

    def payload(rel: str) -> dict | None:
        if rel not in cache and (vault / rel).is_file():
            cache[rel] = note_payload(vault / rel, vault, ADJUDICATION_CHARS)
        return cache.get(rel)

    for start in range(0, len(pairs), MAX_PAIRS_PER_REQUEST):
        state, questions, index = {"pairs": {}}, {}, {}
        for offset, (a, b) in enumerate(pairs[start:start + MAX_PAIRS_PER_REQUEST]):
            pa, pb = payload(a), payload(b)
            if pa is None or pb is None:
                continue
            pid = f"P{offset + 1:02d}"
            state["pairs"][pid] = {"a": pa, "b": pb}
            questions[f"link_{pid}"] = Q.should_link(pid)
            questions[f"mech_{pid}"] = Q.same_mechanism(pid)
            index[pid] = start + offset
        if not questions:
            continue
        answers, usage = judge.judge(vault, state, questions)
        for pid, position in index.items():
            link, mech = answers.get(f"link_{pid}"), answers.get(f"mech_{pid}")
            if link is not None:
                raw[position] = {"link": link.p, "mech": mech.p if mech else None}
        usage_total["backend"], usage_total["model"] = usage.backend, usage.model
        for key in ("requests", "input_tokens", "usd"):
            usage_total[key] += getattr(usage, key)
    return raw


def adjudicate_pairs(vault: Path, pairs: list[tuple[str, str]], symmetric: bool = True) -> tuple[list[dict], dict]:
    """P(a link between them would help a reader) for each (a, b) of vault-relative note paths.

    Returns (adjudications aligned with `pairs`, usage). An entry is None where a note is
    missing or the backend skipped the question. Raises judge.JudgmentUnavailable /
    judge.JudgmentFailed like judge.judge(); callers decide how to degrade.

    `symmetric` (default) asks every pair twice, the second time with the two notes swapped,
    and averages; `order_gap` reports how far the two views disagreed. Measured 2026-09-22 on
    105 pairs: swapping which note is `a` moves the answer by 0.08-0.10 on average and up to
    0.4-0.5, enough to flip a third of the labels, while rerunning the identical request moves
    it by 0.02-0.04. It is an order effect, not batch cross-talk: one pair per request shows
    the same swing (0.08) as forty, and forty ranks at least as well, so the batch stays large
    and the second view is what makes a label worth reading.
    """
    usage_total = {"backend": "", "model": "", "requests": 0, "input_tokens": 0, "usd": 0.0}
    cache: dict[str, dict] = {}
    passes = [_adjudicate_once(vault, pairs, cache, usage_total)]
    if symmetric:
        mirrored = _adjudicate_once(vault, [(b, a) for a, b in reversed(pairs)], cache, usage_total)
        passes.append(mirrored[::-1])
    policy = LINK_POLICY.get(usage_total["backend"], {})
    results: list[dict | None] = []
    for views in zip(*passes, strict=True):
        seen = [v for v in views if v is not None]
        if not seen:
            results.append(None)
            continue
        link = sum(v["link"] for v in seen) / len(seen)
        gap = max(v["link"] for v in seen) - min(v["link"] for v in seen)
        mechs = [v["mech"] for v in seen if v["mech"] is not None]
        mech = sum(mechs) / len(mechs) if mechs else None
        results.append({"p": round(link, 3), "label": _link_label(link, mech, policy, gap),
                        "p_same_mechanism": round(mech, 3) if mech is not None else None,
                        "order_gap": round(gap, 3), "views": len(seen),
                        "backend": usage_total["backend"], "model": usage_total["model"],
                        "questions_version": Q.QUESTIONS_VERSION})
    usage_total["usd"] = round(usage_total["usd"], 6)
    return results, usage_total


def adjudicate_candidates(vault: Path, rows: list[dict], note: str | None = None) -> list[dict] | GraphUnavailable:
    """Attach an advisory `adjudication` to rows from inferred_candidates()/surprise_candidates().

    gaiafield's own `score`, `label` and order are never changed, and the contract is
    unchanged too: the rows stay report-only, AMBIGUOUS rows are still fetched only when a
    human asked for them. The adjudication helps that human; it is not a gate. No judgment
    backend is a normal, silent degradation (`GraphUnavailable("no-judgment")`).
    """
    pairs = [_pair_of(row, note) for row in rows]
    wanted = [(i, pair) for i, pair in enumerate(pairs) if pair is not None]
    if not wanted:
        return [dict(row) for row in rows]
    try:
        verdicts, _usage = adjudicate_pairs(vault, [pair for _, pair in wanted])
    except judge.JudgmentUnavailable as e:
        return GraphUnavailable("no-judgment", e.reason)
    except judge.JudgmentFailed as e:
        write_dlq_note(
            vault, slug="link-adjudication-failed", title="typed-judgment backend answered nothing",
            what_happened=f"`graph.adjudicate_candidates` reached a configured judgment backend but every request failed: {e}",
            why_recorded="A configured backend that fails is not the normal 'no backend' degrade path; the inferred "
                         "candidates were reported without adjudication and someone should check the key or endpoint.",
            confidence="low",
        )
        return GraphUnavailable("call-failed", str(e))
    out = [dict(row) for row in rows]
    for (i, _), verdict in zip(wanted, verdicts, strict=True):
        out[i]["adjudication"] = verdict
    return out
