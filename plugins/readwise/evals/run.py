#!/usr/bin/env python3
"""Run all R0 capability evals for the readwise plugin.

    uv run --project scripts python3 evals/run.py [--json]

Per contract/PROFILE.md, evals always target ./vault, never a TOOLKIT_VAULT-resolved real
vault — this script resolves the vault itself rather than importing
vault_utils.resolve_vault(), so it can never accidentally honor TOOLKIT_VAULT.

Exit codes:
  0 — every eval ran and passed.
  1 — the vault was found but at least one eval failed.
  2 — corpus not present: ./vault does not exist yet. Not a real failure.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

EVAL_MODULES = (
    "eval_capture_note_formatting",
    "eval_dedup_guard",
    "eval_book_capture_dedup",
    "eval_hook_silent_noop",
)


def resolve_repo_vault() -> Path:
    """./vault relative to this repo's root — deliberately ignores TOOLKIT_VAULT."""
    here = Path(__file__).resolve().parent  # plugins/readwise/evals/
    return here.parent.parent.parent / "vault"


def main() -> int:
    as_json = "--json" in sys.argv
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
    for name in EVAL_MODULES:
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
