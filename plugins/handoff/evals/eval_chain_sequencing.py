"""Eval: a second save on the same stream tag gets seq 2 and a `prev:`/follows link back
to the first — the chain-sequencing behavior ported from v1's `next_seq()`."""
from __future__ import annotations

import importlib.util
import os
import sys
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sandbox  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_handoff_module(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / "handoff.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(vault: Path) -> dict:
    name = "chain_sequencing"
    repo = None
    vault_sandbox = None
    try:
        repo = _sandbox.make_repo_sandbox()
        vault_sandbox = _sandbox.make_vault_sandbox(vault)
        hf = _load_handoff_module("handoff_under_test_chain")

        old_toolkit_vault = os.environ.get("TOOLKIT_VAULT")
        old_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["TOOLKIT_VAULT"] = str(vault_sandbox)
        os.environ["CLAUDE_PROJECT_DIR"] = str(repo)
        try:
            draft = repo / "_handoff" / ".draft.md"
            draft.parent.mkdir(exist_ok=True)
            draft.write_text("## Goal\n\nFirst save.\n", encoding="utf-8")
            with redirect_stdout(StringIO()):
                hf.cmd_save(Namespace(stream="chain-eval", title="First", body_file=str(draft)))

            first = repo / "_handoff" / "HANDOFF-chain-eval-01.md"
            if not first.is_file():
                return {"eval": name, "pass": False, "detail": f"expected {first} after first save"}

            draft.write_text("## Goal\n\nSecond save.\n", encoding="utf-8")
            with redirect_stdout(StringIO()):
                hf.cmd_save(Namespace(stream="chain-eval", title="Second", body_file=str(draft)))

            second = repo / "_handoff" / "HANDOFF-chain-eval-02.md"
            if not second.is_file():
                return {"eval": name, "pass": False, "detail": f"expected {second} after second save (seq should be 2)"}

            text = second.read_text(encoding="utf-8")
            if "prev: HANDOFF-chain-eval-01.md" not in text:
                return {"eval": name, "pass": False, "detail": "second handoff's frontmatter did not set prev: to the first"}
            if "follows [HANDOFF-chain-eval-01.md]" not in text:
                return {"eval": name, "pass": False, "detail": "second handoff's rendered header did not include a follows link"}

            return {
                "eval": name,
                "pass": True,
                "detail": "second save on the same stream got seq 2 with prev:/follows pointing at seq 1",
            }
        finally:
            if old_toolkit_vault is None:
                os.environ.pop("TOOLKIT_VAULT", None)
            else:
                os.environ["TOOLKIT_VAULT"] = old_toolkit_vault
            if old_project_dir is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_project_dir
    except Exception as exc:
        return {"eval": name, "pass": False, "detail": f"eval raised {type(exc).__name__}: {exc}"}
    finally:
        if repo is not None:
            _sandbox.teardown_sandbox(repo)
        if vault_sandbox is not None:
            _sandbox.teardown_sandbox(vault_sandbox)
