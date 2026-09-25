"""Eval: report_build.py writes the last run's ingestion report as an Artifact page.

1. contract — a <title> first, no doctype/html/head/body tags, no script
2. items    — the run's imported item is listed with its source link, its expanded links and the
              note it became (found by its source even when the manifest names it in prose)
3. safe     — a title holding markup is escaped; a `javascript:` link in a capture never becomes a link
4. quiet    — a run that imported nothing says so and shows the last run that did
5. notes    — a note added in the working tree since HEAD is listed as written this run
6. vitals   — the vault's note count and the distilled-per-day chart are on the page
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "report_build"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import imports_log
    import report_build

    problems: list[str] = []
    sandbox, saved = make_sandbox(vault), os.environ.get("TOOLKIT_VAULT")
    try:
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        arch = sandbox / "05_Archive" / "Readwise-Captures-2026-09"
        arch.mkdir(parents=True, exist_ok=True)
        (arch / "Readwise-Tweet-x--FULLCAPTURE.md").write_text(
            "---\nsource: https://x.com/a/status/42?s=12\ncategory: tweet\nvia: clip\nlinks:\n- https://github.com/acme/widget\n- javascript:alert(1)\n"
            "media:\n- 04_Resources/Attachments/Tweets/t-1.jpg\n---\n\n# <b>Bold</b> & widgets\n", encoding="utf-8")
        (arch / "README.md").write_text("- `Readwise-Tweet-x--FULLCAPTURE.md` — new note on the widget. Distilled 2026-09-25.\n",
                                        encoding="utf-8")
        (sandbox / "04_Resources" / "Eval-Report-Widget.md").write_text(
            "---\nstatus: distilled\nsource: https://twitter.com/a/status/42\n---\n# W\n", encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.email", "e@x.org"), ("config", "user.name", "e"), ("add", "-A"),
                     ("commit", "-q", "-m", "base")):
            _git(sandbox, *args)
        imports_log.record(sandbox, "2026-09-25 13:06", [{"doc_id": "d", "capture": "01_Capture/Readwise-Tweet-x.md", "via": "clip"}])
        imports_log.record(sandbox, "2026-09-25 16:03", [])
        (sandbox / "04_Resources" / "Eval-Report-New.md").write_text("---\nstatus: distilled\n---\n# N\n", encoding="utf-8")

        page = report_build.render(sandbox)
        import re
        if not page.startswith("<title>") or re.search(r"<(!doctype|html|head|body|script)[\s>]", page, re.I):
            problems.append("contract: page must start with <title> and carry no document tags or script")
        for want in ('href="https://x.com/a/status/42?s=12"', 'href="https://github.com/acme/widget"', "Eval Report Widget", "1 image kept"):
            if want not in page:
                problems.append(f"items: missing {want!r}")
        if "<b>Bold</b>" in page or "&lt;b&gt;Bold&lt;/b&gt; &amp; widgets" not in page:
            problems.append("safe: title not escaped")
        if "javascript:" in page:
            problems.append("safe: a javascript: link reached the page")
        if "Quiet run" not in page or "What came in on 2026-09-25 13:06" not in page:
            problems.append("quiet: the empty run does not fall back to the last run that imported")
        if "Eval Report New" not in page:
            problems.append("notes: the note written this run is not listed")
        if "notes in the vault" not in page or 'aria-label="Notes distilled per day' not in page:
            problems.append("vitals: note count or chart missing")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "contract, items, escaping, quiet run, notes"}
