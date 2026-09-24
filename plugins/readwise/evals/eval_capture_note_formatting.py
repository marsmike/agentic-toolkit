"""Eval: given a fixture Readwise Reader item (no network), build_captures.write_capture()
produces a schema-conformant capture note — origin-prefixed filename, flat under
01_Capture/, frontmatter carrying the fields the dedup guard and coverage check depend on.
A wall instead of content (a sign-up page, a 404) is marked `content: stub`; a short tweet and a
real article are not. Writes, so this runs against a sandbox copy of the vault.
"""
from __future__ import annotations

import json
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

REQUIRED_FRONTMATTER_FIELDS = ("source", "origin", "readwise_doc_id", "category", "tags")


def run(vault: Path) -> dict:
    import sys

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_captures as bc
    from vault_utils import read_frontmatter

    fixture = json.loads((Path(__file__).parent / "fixtures" / "reader_item.json").read_text())

    sandbox_vault = make_sandbox(vault)
    try:
        path, status = bc.write_capture(sandbox_vault, fixture)

        problems = []
        if status != "written":
            problems.append(f"expected status 'written' on first write, got {status!r}")
        if path is None:
            return {"eval": "capture_note_formatting", "pass": False, "detail": "; ".join(problems) or "no path returned"}

        if path.parent != sandbox_vault / "01_Capture":
            problems.append(f"capture not written flat under 01_Capture/: {path}")
        if not path.name.startswith("Readwise-"):
            problems.append(f"filename not origin-prefixed: {path.name}")

        fm, body = read_frontmatter(path)
        missing_fields = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in fm]
        if missing_fields:
            problems.append(f"missing frontmatter fields: {missing_fields}")
        if fm.get("readwise_doc_id") != fixture["id"]:
            problems.append(f"readwise_doc_id mismatch: {fm.get('readwise_doc_id')!r} != {fixture['id']!r}")
        if not isinstance(fm.get("tags"), list):
            problems.append(f"tags is not a list: {fm.get('tags')!r}")
        if fixture["title"] not in body:
            problems.append("capture body does not contain the fixture's title")
        if "## Full Text" not in body:
            problems.append("capture body is missing the '## Full Text' section")

        walls = {"wall1": ("article", "<p>Explore the Resource Hub.</p><p><a href='/sign-up'>Create a free account</a></p>"),
                 "gone1": ("article", "<p>DeveloPassion</p><p>Not found</p><p>This page does not exist</p>" + "<p>menu</p>" * 40),
                 "twt1": ("tweet", "<p>This is actually insane.</p>"),
                 "real1": ("article", "<p>" + "A paragraph with a claim and a number, 42 percent. " * 12 + "</p>")}
        for doc_id, (category, html) in walls.items():
            wp, _ = bc.write_capture(sandbox_vault, {**fixture, "id": doc_id, "title": f"Wall test {doc_id}",
                                                     "category": category, "html_content": html})
            got = read_frontmatter(wp)[0].get("content") == "stub" if wp else None
            if got != doc_id.startswith(("wall", "gone")):
                problems.append(f"{doc_id} ({category}): stub={got}")

        if problems:
            return {"eval": "capture_note_formatting", "pass": False, "detail": "; ".join(problems)}
        return {"eval": "capture_note_formatting", "pass": True, "detail": f"wrote {path.name} with conformant frontmatter"}
    finally:
        teardown_sandbox(sandbox_vault)
