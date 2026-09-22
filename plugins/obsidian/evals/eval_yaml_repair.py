"""Eval: vault_yaml_repair.py makes broken frontmatter parse with the smallest edit.

In a sandbox: a description with an unquoted `: `, an `author: @handle`, a Templater
`created: {{date}}`, a corrupted opening delimiter, and one block no rule can repair. After
--apply the first four parse, their bodies are byte-identical, only frontmatter lines changed,
the archive copy is untouched without --include-archive, and the unrepairable note is reported,
not written.
"""
from __future__ import annotations

import os
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "yaml_repair"
BODY = "\n# Title\n\nBody text: with a colon, kept as is.\n"
CASES = {
    "04_Resources/Eval-Yaml-Colon.md": "---\nstatus: distilled\ndescription: The claim: it works in three of four cases\n---" + BODY,
    "04_Resources/Eval-Yaml-Handle.md": "---\nstatus: active\nauthor: @someone\n---" + BODY,
    "04_Resources/Eval-Yaml-Template.md": "---\nstatus: draft\ncreated: {{date}}\n---" + BODY,
    "04_Resources/Eval-Yaml-Delimiter.md": "x---\nstatus: active\ndescription: fine\n---" + BODY,
}
BROKEN = ("04_Resources/Eval-Yaml-Hopeless.md", "---\nstatus: [active\ndescription: fine\n---" + BODY)
ARCHIVED = ("05_Archive/Eval-Yaml-Archived.md", "---\nauthor: @frozen\n---" + BODY)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import vault_yaml_repair
    from vault_utils import UnparseableFrontmatter, read_frontmatter

    problems: list[str] = []
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        for rel, text in {**CASES, BROKEN[0]: BROKEN[1], ARCHIVED[0]: ARCHIVED[1]}.items():
            (sandbox / rel).parent.mkdir(parents=True, exist_ok=True)
            (sandbox / rel).write_text(text, encoding="utf-8")

        vault_yaml_repair.main(["--apply"])

        for rel, original in CASES.items():
            p = sandbox / rel
            try:
                fm, body = read_frontmatter(p, strict=True)
            except UnparseableFrontmatter:
                problems.append(f"{rel}: still does not parse")
                continue
            if body != BODY.lstrip("\n") and body != BODY:
                problems.append(f"{rel}: body changed")
            before, after = original.split("\n"), p.read_text(encoding="utf-8").split("\n")
            if len(before) != len(after) or sum(a != b for a, b in zip(before, after, strict=True)) != 1:
                problems.append(f"{rel}: expected exactly one changed line")
        if read_frontmatter(sandbox / "04_Resources/Eval-Yaml-Colon.md")[0].get("description") != "The claim: it works in three of four cases":
            problems.append("the repaired description does not read back as written")
        if (sandbox / BROKEN[0]).read_text(encoding="utf-8") != BROKEN[1]:
            problems.append("an unrepairable note was written")
        if (sandbox / ARCHIVED[0]).read_text(encoding="utf-8") != ARCHIVED[1]:
            problems.append("the archive was touched without --include-archive")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "4 repairs, one line each, bodies intact; archive and unrepairable untouched"}
