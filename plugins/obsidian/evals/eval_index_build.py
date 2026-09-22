"""Eval: index_build.py rebuilds Index.md from descriptions, and vault_lint then sees no drift.

In a sandbox copy of the example vault, the existing Index.md is given one entry for a deleted
note and one real entry carrying a retrieval-verification mark (✓); one note loses its
description. After the rebuild: no dangling and no missing entries per vault_lint, the note
without a description is marked ⚙ and keeps its previous summary, the ✓ carries over, every
other summary is the note's own description, and nothing but Index.md (and Log.md) changed.
"""
from __future__ import annotations

import os
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "index_build"
MARKED = "04_Resources/Concepts/Hybrid-Retrieval"
UNDESCRIBED = "04_Resources/Concepts/BM25-Dilution"


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import index_build
    import vault_lint
    from vault_utils import read_frontmatter, write_frontmatter

    problems: list[str] = []
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        index = sandbox / "Index.md"
        text = index.read_text(encoding="utf-8")
        lines =[ln + " ✓" if ln.startswith(f"- [[{MARKED}|") else ln for ln in text.splitlines()]
        lines.append("- [[04_Resources/Concepts/Deleted-Long-Ago|Deleted-Long-Ago]] — gone")
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")
        prev_summary = next((ln.split(" — ", 1)[1] for ln in lines if ln.startswith(f"- [[{UNDESCRIBED}|")), None)
        fm, body = read_frontmatter(sandbox / f"{UNDESCRIBED}.md")
        fm.pop("description", None)
        write_frontmatter(sandbox / f"{UNDESCRIBED}.md", fm, body)
        before = {p.relative_to(sandbox).as_posix(): p.stat().st_mtime_ns for p in sandbox.rglob("*") if p.is_file()}

        index_build.main([])

        notes, _, _ = vault_lint.scan_vault(sandbox)
        drift = vault_lint.find_index_drift(sandbox, notes)
        if drift["dangling"] or drift["missing"]:
            problems.append(f"drift after rebuild: {len(drift['dangling'])} dangling, {len(drift['missing'])} missing")
        built = {ln.split("|", 1)[0][4:]: ln for ln in index.read_text(encoding="utf-8").splitlines() if ln.startswith("- [[")}
        if not built.get(MARKED, "").endswith("✓"):
            problems.append("the ✓ mark did not carry over")
        und = built.get(UNDESCRIBED, "")
        if "⚙" not in und or (prev_summary and prev_summary.rstrip(" ⚙✓⚠") not in und):
            problems.append(f"a note without a description must keep its previous summary and be marked ⚙, got {und!r}")
        sample = "04_Resources/Concepts/Calibration-Bias"
        desc = read_frontmatter(sandbox / f"{sample}.md")[0].get("description", "")
        if " ".join(str(desc).split()) not in built.get(sample, ""):
            problems.append("a summary is not the note's own description")
        after = {p.relative_to(sandbox).as_posix(): p.stat().st_mtime_ns for p in sandbox.rglob("*") if p.is_file()}
        changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        if changed - {"Index.md", "Log.md"}:
            problems.append(f"rebuild touched more than Index.md/Log.md: {sorted(changed - {'Index.md', 'Log.md'})}")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "rebuild leaves no drift; ⚙ and ✓ handled; only Index.md changed"}
