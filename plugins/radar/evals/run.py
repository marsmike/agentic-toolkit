#!/usr/bin/env python3
"""Run the radar plugin's evals against ./vault (never a TOOLKIT_VAULT-resolved vault).

    uv run --project plugins/radar/scripts python3 plugins/radar/evals/run.py [--json]

Exit codes: 0 all passed, 1 at least one failed, 2 ./vault not present.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

EVAL_MODULES = (
    "eval_scan",
    "eval_replay",
)


def main() -> int:
    as_json = "--json" in sys.argv
    evals_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(evals_dir))
    sys.path.insert(0, str(evals_dir.parent / "scripts"))
    vault = evals_dir.parent.parent.parent / "vault"
    if not vault.is_dir():
        print(f"CORPUS-NOT-PRESENT  {vault}")
        return 2

    results = []
    for name in EVAL_MODULES:
        try:
            result = importlib.import_module(name).run(vault)
        except Exception as exc:  # an eval crashing is itself a failure to report
            result = {"eval": name.removeprefix("eval_"), "pass": False, "detail": f"eval raised {type(exc).__name__}: {exc}"}
        results.append(result)

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['eval']} — {r['detail']}")
        print(f"\n{sum(r['pass'] for r in results)}/{len(results)} passed")
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
