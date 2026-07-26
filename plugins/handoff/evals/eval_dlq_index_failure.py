"""Eval: an index-append failure against a resolvable-but-unwritable index path writes a
DLQ note, while the handoff save itself still succeeds — the primary artifact is never
lost just because the secondary cross-project index couldn't be updated.
"""
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
    name = "dlq_index_append_failure"
    repo = None
    vault_sandbox = None
    try:
        repo = _sandbox.make_repo_sandbox()
        vault_sandbox = _sandbox.make_vault_sandbox(vault)

        # Make the index's parent directory unwritable in a way that's portable and
        # root-proof: put a plain FILE where the directory needs to be, so
        # mkdir(parents=True, exist_ok=True) reliably raises regardless of permission
        # bits (which running as root, e.g. in some CI containers, would ignore).
        blocker = vault_sandbox / "00_Memory" / "handoffs"
        blocker.parent.mkdir(parents=True, exist_ok=True)
        blocker.write_text("blocking file, not a directory\n", encoding="utf-8")

        hf = _load_handoff_module("handoff_under_test_dlq")

        old_toolkit_vault = os.environ.get("TOOLKIT_VAULT")
        old_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["TOOLKIT_VAULT"] = str(vault_sandbox)
        os.environ["CLAUDE_PROJECT_DIR"] = str(repo)
        try:
            draft = repo / "_handoff" / ".draft.md"
            draft.parent.mkdir(exist_ok=True)
            draft.write_text("## Goal\n\nDLQ eval.\n", encoding="utf-8")

            out = StringIO()
            with redirect_stdout(out):
                hf.cmd_save(Namespace(stream="dlq-eval", title="DLQ eval", body_file=str(draft)))
            save_text = out.getvalue()

            handoff_file = repo / "_handoff" / "HANDOFF-dlq-eval-01.md"
            if not handoff_file.is_file():
                return {"eval": name, "pass": False, "detail": "handoff save should still succeed even when the index append fails"}
            if "Vault index:   FAILED" not in save_text:
                return {"eval": name, "pass": False, "detail": f"save output did not report the index-append failure: {save_text!r}"}

            dlq_dir = vault_sandbox / "00_Memory" / "dlq"
            dlq_notes = list(dlq_dir.glob("*handoff-index-append-failure*.md")) if dlq_dir.is_dir() else []
            if not dlq_notes:
                return {"eval": name, "pass": False, "detail": f"no DLQ note written to {dlq_dir} for the index-append failure"}

            return {
                "eval": name,
                "pass": True,
                "detail": "index-append failure against a resolvable vault was recorded to the DLQ; "
                "the handoff save itself still succeeded",
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
