"""Eval: checks.frontmatter.fix() maps lifecycle words onto the contract without a model call and
keeps the original word in `stage:`; an unknown word falls back to active, labelled as a default.
In-memory only: fix() returns the new frontmatter, nothing is written."""
from __future__ import annotations

from pathlib import Path

NAME = "status_aliases"
CASES = {"shipped": "archived", "Ready-To-Paste": "review", "living": "active", "inbox": "draft"}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from checks import frontmatter

    problems = []
    for word, expected in CASES.items():
        fm, _, results = frontmatter.fix(Path("x.md"), {"status": word, "tags": [], "description": "d"}, "", vault)
        if fm["status"] != expected or fm.get("stage") != word or "(alias)" not in results[0].description:
            problems.append(f"{word!r}: got status={fm['status']!r} stage={fm.get('stage')!r} ({results[0].description})")
    fm, _, results = frontmatter.fix(Path("x.md"), {"status": "active", "stage": "live", "tags": [], "description": "d"}, "", vault)
    if results or fm.get("stage") != "live":
        problems.append("a valid status with an existing stage must be left alone")
    fm, _, results = frontmatter.fix(Path("x.md"), {"status": "zzz", "tags": [], "description": "d"}, "", vault)
    if fm["status"] != "active" or fm.get("stage") != "zzz" or "(default)" not in results[0].description:
        problems.append(f"unknown word: {results[0].description}")
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"{len(CASES)} aliases mapped, stage kept, unknown word labelled default"}
