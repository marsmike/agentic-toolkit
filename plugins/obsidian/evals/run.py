#!/usr/bin/env python3
"""Run all R0 capability evals for the obsidian plugin.

    uv run evals/run.py [--json]

Per contract/PROFILE.md, evals always target ./vault, never a TOOLKIT_VAULT-resolved
real vault — this script resolves the vault itself rather than importing
vault_utils.resolve_vault(), so it can never accidentally honor TOOLKIT_VAULT.

Exit codes:
  0 — every eval ran and passed.
  1 — the vault was found but at least one eval failed.
  2 — corpus not present: ./vault does not exist yet (a parallel example-vault build
      hasn't landed). Not a real failure — re-run once the vault exists.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

EVAL_MODULES = (
    "eval_vault_lint_broken_link",
    "eval_distill_placement",
    "eval_retrieval_verification_report",
    "eval_dlq_on_missing_scores",
    "eval_search_parity",
    "eval_graph_context",
    "eval_inferred_candidates",
    "eval_distill_judge",
    "eval_link_adjudication",
    "eval_search_judge",
    "eval_typed_maintenance",
    "eval_index_build",
    "eval_yaml_repair",
    "eval_status_aliases",
    "eval_provenance",
    "eval_pipeline_run",
    "eval_distill_check_negative",
    "eval_map_build",
    "eval_now_build",
    "eval_dashboard_build",
    "eval_retire_capture",
    "eval_search_heading_weight",
)


def resolve_repo_vault() -> Path:
    """./vault relative to this repo's root — deliberately ignores TOOLKIT_VAULT."""
    here = Path(__file__).resolve().parent  # plugins/obsidian/evals/
    return here.parent.parent.parent / "vault"


@contextlib.contextmanager
def _stdout_to_stderr():
    """Evals call builders in-process (`index_build.main([])`) and those spawn subprocesses, all
    printing progress to stdout; stdout is the results' alone, so `--json` parses. Redirected at
    the file descriptor, which catches the subprocesses too. [earned: 2026-09-24 review GLM-9 —
    `run.py --json | jq .` failed; CI only passed because it greps rather than parses]"""
    sys.stdout.flush()
    saved = os.dup(1)
    os.dup2(2, 1)
    try:
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)


def main() -> int:
    as_json = "--json" in sys.argv
    # Keys come from the environment only, as before: the key-file fallback (vault_utils.secret)
    # would hand a "no key" case the developer's real ~/.env.
    os.environ["TOOLKIT_KEYS_FILE"] = os.devnull
    evals_dir = Path(__file__).resolve().parent
    if str(evals_dir) not in sys.path:
        sys.path.insert(0, str(evals_dir))

    vault = resolve_repo_vault()
    if not vault.is_dir():
        results = [
            {"eval": name.removeprefix("eval_"), "pass": False, "detail": f"corpus not present: {vault} does not exist"}
            for name in EVAL_MODULES
        ]
        print(json.dumps(results, indent=2) if as_json else "\n".join(f"CORPUS-NOT-PRESENT  {r['eval']}" for r in results))
        return 2

    results = []
    with _stdout_to_stderr():
        for name in EVAL_MODULES:
            import importlib
            try:
                mod = importlib.import_module(name)
                result = mod.run(vault)
            except Exception as exc:  # an eval crashing is itself a failure to report, not to propagate
                result = {"eval": name.removeprefix("eval_"), "pass": False, "detail": f"eval raised {type(exc).__name__}: {exc}"}
            results.append(result)

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['eval']} — {r['detail']}")
        passed = sum(1 for r in results if r["pass"])
        print(f"\n{passed}/{len(results)} passed")

    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
