"""Eval: the dossier's URL hits read a note's whole provenance. A note is the capture's
distillation ("frontmatter") when its `source:`, any `sources:` entry or its `arxiv_id:` names
the capture's own source; a link in the body is "body", and a note sourced from a URL the capture
only cites is "body-cited". [earned: 2026-10-02 — the RLM paper had two notes, one sourced from a
tweet with `arxiv_id: 2512.24601`, and a run backlinked both because only `source:` was read]

Offline: url_hits is pure Python over the vault.
"""
from __future__ import annotations

from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "url_hits"
NOTES = {
    "Eval-Hits-Arxiv": "---\nsource: https://x.com/someone/status/1\narxiv_id: '2512.24601'\n---\n# A\n",
    "Eval-Hits-Sources": "---\nsource: https://example.org/first\nsources:\n  - https://example.org/first\n"
                         "  - https://example.org/enriched-later?utm_source=x\n---\n# B\n",
    "Eval-Hits-Body": "---\nsource: https://example.org/other\n---\n# C\n\nSee https://example.org/in-body for more.\n",
    "Eval-Hits-Cited": "---\nsource: https://github.com/acme/tool\n---\n# D\n",
}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import distill_judge

    problems: list[str] = []
    sandbox = None
    try:
        sandbox = make_sandbox(vault)
        res = sandbox / "04_Resources"
        res.mkdir(exist_ok=True)
        for name, text in NOTES.items():
            (res / f"{name}.md").write_text(text, encoding="utf-8")
        cases = [  # (capture own source, cited URLs, note, expected origin)
            ("https://arxiv.org/abs/2512.24601v2", [], "Eval-Hits-Arxiv", "frontmatter"),
            ("https://example.org/enriched-later", [], "Eval-Hits-Sources", "frontmatter"),
            ("https://example.org/in-body", [], "Eval-Hits-Body", "body"),
            ("https://x.com/someone/status/9", ["https://github.com/acme/tool/tree/main"], "Eval-Hits-Cited", "body-cited"),
        ]
        for own, cited, note, want in cases:
            cap = {"own_source": own, "source_urls": [own, *cited], "body": ""}
            got = distill_judge.url_hits(cap, sandbox, exclude=[]).get(f"04_Resources/{note}.md")
            if got != want:
                problems.append(f"{note}: capture {own} should be a {want} hit, got {got}")
    finally:
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else
            "source, sources: and arxiv_id: are provenance; a body link and a cited source are not"}
