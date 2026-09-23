"""Eval: capture provenance decides only one thing, whether a capture may leave without a note.

1. read     — `via` and `radar_interests` come from the capture's frontmatter; a capture without
              `via` (research, bookmarks, older captures) counts as the owner's clip
2. clip     — a discard-candidate clip becomes quick-file: the owner's clips never drop
3. arrived  — a discard-candidate radar or newsletter capture stays discard-candidate with the
              retire-with-reason note; every other recommendation passes through unchanged
4. address  — a twitter.com and an x.com source are one address, and so is one YouTube video under
              youtu.be, watch?v=, shorts or the mobile host
              (distill_check's source-line gate reads them through the same canonical form)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

NAME = "provenance"


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from distill_judge import apply_provenance, capture_provenance
    from judgments.urls import _canonical

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "radar.md").write_text("---\nvia: radar\nradar_interests: [claude-code]\n---\n# x\n", encoding="utf-8")
        (d / "news.md").write_text("---\nvia: newsletter\n---\n# x\n", encoding="utf-8")
        (d / "plain.md").write_text("---\norigin: research-session\n---\n# x\n", encoding="utf-8")
        radar, news, plain = (capture_provenance(d / f) for f in ("radar.md", "news.md", "plain.md"))

    # 1. read
    if radar != {"via": "radar", "owner_chose_it": False, "radar_interests": ["claude-code"]}:
        problems.append(f"phase 1: radar provenance read wrong: {radar}")
    if plain["via"] != "clip" or not plain["owner_chose_it"] or news["owner_chose_it"]:
        problems.append(f"phase 1: no `via` must count as a clip, a newsletter as arrived: {plain}, {news}")

    discard = {"recommendation": "discard-candidate", "probs": {"discard-candidate": 0.8}, "note": ""}
    # 2. clip
    if apply_provenance(discard, plain)["recommendation"] != "quick-file":
        problems.append("phase 2: a discard-candidate clip must become quick-file")
    # 3. arrived
    for prov in (radar, news):
        out = apply_provenance(discard, prov)
        if out["recommendation"] != "discard-candidate" or "retired" not in out["note"]:
            problems.append(f"phase 3: {prov['via']} may be retired with a reason, got {out}")
    for rec in ("distill", "quick-file", None):
        t = {"recommendation": rec, "probs": {}, "note": ""}
        if apply_provenance(t, radar) != t or apply_provenance(t, plain) != t:
            problems.append(f"phase 3: provenance must not change a {rec!r} recommendation")
    if discard["recommendation"] != "discard-candidate":
        problems.append("phase 3: apply_provenance mutated its input")

    # 4. address
    if _canonical("https://twitter.com/trq212/status/123?s=20") != _canonical("https://x.com/trq212/status/123"):
        problems.append("phase 4: twitter.com and x.com addresses of one tweet must canonicalise alike")
    video = {_canonical(u) for u in ("https://youtu.be/5NX_qkr4qRQ?si=a", "https://www.youtube.com/watch?v=5NX_qkr4qRQ&t=9",
                                     "https://m.youtube.com/watch?feature=share&v=5NX_qkr4qRQ", "https://youtube.com/shorts/5NX_qkr4qRQ")}
    if len(video) != 1:
        problems.append(f"phase 4: one YouTube video under four spellings must be one address, got {video}")

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "clips never discarded; radar and newsletter captures may be retired with a reason"}
