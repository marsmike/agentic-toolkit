"""Eval: distill_check fails the notes it must fail. The unattended pipeline retires a capture only
when distill_check passes, so every hard gate is shown to catch a note broken in exactly one way.
[earned: 2026-09-23 — the pipeline's own distilled notes pointed out that the check had never
been run against a deliberately broken note]

One correct note passes every hard gate; each broken variant fails exactly its gate and no other:

  frontmatter   no source · source "unknown" · status draft · no description
  source-line   no *Source:* line · a Source line naming another address (frontmatter correct)
  attachment    the capture's stored document not linked
  links         a link into 01_Capture/ · a link into 05_Archive/ · a dangling wikilink
  index         no Index.md line

Offline: judgment keys are removed, so only the hard gates run.
"""
from __future__ import annotations

import os
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "distill_check_negative"
KEY_ENV = ("TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
SOURCE = "https://example.org/eval-article"
CAPTURE = f"""---
source: {SOURCE}?utm_source=feed
origin: readwise
via: clip
attachment: 04_Resources/Attachments/eval-doc.pdf
---

# An article about eval gates

*Source: [{SOURCE}]({SOURCE})*

## Full Text

A claim with a number: gates catch 100% of what they are shown to catch.
"""
GOOD_FM = {"description": "A note that passes every hard gate.", "status": "distilled",
           "source": SOURCE, "processed_date": "2026-09-23"}
GOOD_BODY = f"""# Eval good note

*Source: [An article about eval gates]({SOURCE})*

The document: [[04_Resources/Attachments/eval-doc.pdf]]. Related: [[Typed-Judgments]].
"""


def _note(fm: dict, body: str) -> str:
    lines = ["---", *(f"{k}: {v}" for k, v in fm.items()), "---", ""]
    return "\n".join(lines) + body


VARIANTS: dict[str, tuple[str, dict, str]] = {
    # name: (the gate that must fail, frontmatter, body)
    "good": ("", GOOD_FM, GOOD_BODY),
    # an existing note enriched by the capture: its own Source line first, the capture's beside it
    "enriched": ("", {**GOOD_FM, "source": "https://earlier.example.org/first"},
                 "*Source: [The note's first source](https://earlier.example.org/first)*\n\n" + GOOD_BODY),
    "no-source": ("frontmatter", {k: v for k, v in GOOD_FM.items() if k != "source"}, GOOD_BODY),
    "unknown-source": ("frontmatter", {**GOOD_FM, "source": "unknown"}, GOOD_BODY),
    "draft": ("frontmatter", {**GOOD_FM, "status": "draft"}, GOOD_BODY),
    "no-description": ("frontmatter", {k: v for k, v in GOOD_FM.items() if k != "description"}, GOOD_BODY),
    "no-source-line": ("source-line", GOOD_FM, GOOD_BODY.replace(f"*Source: [An article about eval gates]({SOURCE})*\n", "")),
    "wrong-source-line": ("source-line", GOOD_FM, GOOD_BODY.replace(f"({SOURCE})", "(https://other.example.org/elsewhere)")),
    "no-attachment": ("attachment", GOOD_FM, GOOD_BODY.replace("[[04_Resources/Attachments/eval-doc.pdf]]", "the PDF")),
    "capture-link": ("links", GOOD_FM, GOOD_BODY + "\nSee [[01_Capture/Eval-Check-Capture]].\n"),
    "archive-link": ("links", GOOD_FM, GOOD_BODY + "\nSee [[05_Archive/Old-Thing]].\n"),
    "dangling": ("links", GOOD_FM, GOOD_BODY + "\nSee [[No-Such-Note-Anywhere-In-The-Vault]].\n"),
    "no-index": ("index", GOOD_FM, GOOD_BODY),
}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import distill_check

    problems: list[str] = []
    saved = {k: os.environ.pop(k, None) for k in KEY_ENV}
    sandbox = None
    try:
        sandbox = make_sandbox(vault)
        capture = sandbox / "01_Capture" / "Eval-Check-Capture.md"
        capture.write_text(CAPTURE, encoding="utf-8")
        (sandbox / "04_Resources" / "Attachments").mkdir(parents=True, exist_ok=True)
        (sandbox / "04_Resources" / "Attachments" / "eval-doc.pdf").write_bytes(b"%PDF-1.4 eval\n")
        (sandbox / "05_Archive").mkdir(exist_ok=True)
        (sandbox / "05_Archive" / "Old-Thing.md").write_text("---\nstatus: archived\n---\n# old\n", encoding="utf-8")
        index = sandbox / "Index.md"
        lines = []
        for name, (_, fm, body) in VARIANTS.items():
            (sandbox / "04_Resources" / f"Eval-Check-{name}.md").write_text(_note(fm, body), encoding="utf-8")
            if name != "no-index":
                lines.append(f"- [[04_Resources/Eval-Check-{name}|Eval {name}]] — fixture")
        index.write_text(index.read_text(encoding="utf-8") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

        for name, (must_fail, _, _) in VARIANTS.items():
            report = distill_check.check(sandbox / "04_Resources" / f"Eval-Check-{name}.md", capture, sandbox, asks=[])
            failed = sorted(g for g, (ok, _) in report["hard"].items() if not ok)
            expected = [must_fail] if must_fail else []
            if failed != expected:
                why = {g: report["hard"][g][1] for g in failed}
                problems.append(f"{name}: expected {expected or 'a pass'}, failed {failed} {why}")
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else f"{len(VARIANTS) - 2} broken notes each fail exactly their gate; the good and the enriched note pass"}
