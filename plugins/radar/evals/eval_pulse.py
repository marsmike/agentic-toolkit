"""Eval: `vault_pulse.pulse` on a hand-made vault of 30 notes + 1 clip, offline, no network.

1. rising/new/baseline — "rising-tag" (baseline 1/week, this week 5 notes + 1 clip) is rising;
   "steady-tag" (baseline 3/week, this week 4) grows but stays under the 2x+1 limit, not rising;
   "new-tag" (baseline 0, this week 2) is new but not rising (needs 3); a note's date decides
   which rolling week it lands in, not the order it was written
2. tag filtering — `domain/testing` never appears in a mention's `tags` (it becomes `domain`
   instead); `readwise/concept`, bare `readwise`, `W39-2026`, `area` and `source/github` are all
   dropped outright; the domains aggregate still sees "testing" rising; a plain tag on the same
   note (`vector-loom`) survives
3. auto document-frequency cut — "vault-generic", tagging 30 of 31 tagged mentions, never appears
   in the `tags` list at all even though its raw numbers would otherwise read as unremarkable-but-
   present, because the whole point is it is *everywhere*, not accelerating
4. clips counted — the clip's own tag and interest both land in the same aggregates as note tags;
   `week.clips` and the clips column of `daily` see it
5. interests — `radar_interests` tallies this week vs. the baseline the same way tags do
6. skipped — a note with unparseable frontmatter and one with neither `created` nor
   `processed_date` are both skipped and counted, never crash the run
7. symlink outside the vault — ignored, not counted, not skipped
8. shape — mentions carry family "vault", entities [], score/eng_pct/p None; origin falls back to
   the PARA folder when a note has no `kind`; `daily` covers exactly the last 28 days with zeros
   included
9. no writes — `pulse()` never touches the vault
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from _sandbox import make_sandbox, snapshot, teardown_sandbox

NAME = "pulse"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
TODAY = NOW.date()

# One representative date per rolling week (see _week_range: back=0 is this week, ending today).
THIS_WEEK_DATES = [TODAY - timedelta(days=d) for d in range(5, 0, -1)]  # 09-21 .. 09-25
BASELINE_DATES = [TODAY - timedelta(days=10), TODAY - timedelta(days=17),
                  TODAY - timedelta(days=24), TODAY - timedelta(days=31)]  # one per prior week


def _fm(lines: list[str]) -> str:
    return "---\n" + "\n".join(lines) + "\n---\n"


def _note(path: Path, tags: list[str], day: str | None, kind: str | None = None,
          radar_interests: list[str] | None = None, title: str = "") -> None:
    lines = [f"description: {path.stem}"]
    if day:
        lines.append(f"created: {day}")
    if kind:
        lines.append(f"kind: {kind}")
    lines.append("tags:")
    lines += [f"  - {t}" for t in tags]
    if radar_interests:
        lines.append("radar_interests:")
        lines += [f"  - {i}" for i in radar_interests]
    path.write_text(_fm(lines) + f"\n# {title or path.stem}\n\nBody.\n", encoding="utf-8")


def _build(vault: Path) -> None:
    res = vault / "04_Resources"
    res.mkdir(parents=True, exist_ok=True)
    n = 0

    def next_name(prefix: str) -> Path:
        nonlocal n
        n += 1
        return res / f"{prefix}-{n}.md"

    # 1. rising-tag: baseline 1/week x 4 weeks, this week 5 (+ vault-generic on all of them)
    for d in BASELINE_DATES:
        _note(next_name("rising-base"), ["rising-tag", "vault-generic"], d.isoformat(), kind="field-report")
    for i, d in enumerate(THIS_WEEK_DATES):
        interests = ["claude-code-anthropic-ecosystem"] if i < 2 else None
        _note(next_name("rising-this"), ["rising-tag", "vault-generic"], d.isoformat(),
              kind="field-report", radar_interests=interests, title=f"Rising Note {i}")

    # one baseline note also carries the interest (no topical tags, so it doesn't skew rising-tag's
    # own baseline), to give the interest a non-zero fractional baseline
    _note(next_name("rising-base-interest"), [], BASELINE_DATES[0].isoformat(),
          kind="field-report", radar_interests=["claude-code-anthropic-ecosystem"])

    # 2. steady-tag: baseline 2/week x 4 weeks, this week 4 (kept under the DF-stop's own
    # threshold of the tagged corpus, unlike vault-generic below, which is deliberately over it)
    for d in BASELINE_DATES:
        for _ in range(2):
            _note(next_name("steady-base"), ["steady-tag", "vault-generic"], d.isoformat(), kind="field-report")
    for d in THIS_WEEK_DATES[:4]:
        _note(next_name("steady-this"), ["steady-tag", "vault-generic"], d.isoformat(), kind="field-report")

    # 3. new-tag: no baseline, this week 2 — no `kind`, to check the folder-name origin fallback
    for d in THIS_WEEK_DATES[:2]:
        _note(next_name("new-this"), ["new-tag", "vault-generic"], d.isoformat())

    # 4. noise tags: domain/*, readwise/*, bare readwise, week tag, area, source/* — all this week
    _note(next_name("noise"), ["domain/testing", "readwise/concept", "vector-loom", "vault-generic"],
          THIS_WEEK_DATES[0].isoformat(), kind="field-report")
    _note(next_name("noise"), ["domain/testing", "readwise", "W39-2026", "vault-generic"],
          THIS_WEEK_DATES[1].isoformat(), kind="field-report")
    _note(next_name("noise"), ["domain/testing", "area", "source/github", "vault-generic"],
          THIS_WEEK_DATES[2].isoformat(), kind="field-report")

    # 5. skipped: unparseable frontmatter, and a note with neither created nor processed_date
    (res / "bad-frontmatter.md").write_text("---\ntags: [unterminated\n---\n# Bad\n", encoding="utf-8")
    _note(res / "no-date.md", ["rising-tag"], day=None)

    # 6. symlink outside the vault, disguised as a content note
    outside = vault.parent / "outside.md"
    outside.write_text("---\ncreated: 2026-09-24\ntags: [smuggled]\n---\n# Outside\n", encoding="utf-8")
    os.symlink(outside, res / "symlinked-outside.md")

    # 7. a clip, counted alongside notes
    capture = vault / "01_Capture"
    capture.mkdir(parents=True, exist_ok=True)
    (capture / "Clip-1.md").write_text(
        "---\nvia: clip\nsaved_at: " + THIS_WEEK_DATES[-1].isoformat() + "\nsource: https://example.org\n"
        "tags:\n  - rising-tag\nradar_interests:\n  - claude-code-anthropic-ecosystem\n---\n\n# A Clip\n",
        encoding="utf-8",
    )


def run(vault: Path) -> dict:
    import vault_pulse

    problems: list[str] = []
    sandbox = None
    try:
        sandbox = make_sandbox(vault)
        # start from an empty vault-shaped dir: the eval owns every note in the window
        for f in ("02_Projects", "03_Areas", "04_Resources", "01_Capture"):
            d = sandbox / f
            if d.is_dir():
                for p in d.rglob("*.md"):
                    p.unlink()
        _build(sandbox)
        before = snapshot(sandbox)

        result = vault_pulse.pulse(sandbox, NOW)

        if snapshot(sandbox) != before:
            problems.append("pulse() must not write anything to the vault")

        tags = {t["tag"]: t for t in result["tags"]}
        domains = {d["domain"]: d for d in result["domains"]}
        interests = {i["id"]: i for i in result["interests"]}

        # 1. rising / new / baseline math
        rt = tags.get("rising-tag")
        if not rt or rt["this_week"] != 6 or rt["baseline"] != 1.0 or not rt["rising"]:
            problems.append(f"phase 1: rising-tag should be this_week=6 baseline=1.0 rising=True, got {rt}")
        st = tags.get("steady-tag")
        if not st or st["this_week"] != 4 or st["baseline"] != 2.0 or st["rising"]:
            problems.append(f"phase 1: steady-tag should be this_week=4 baseline=2.0 rising=False, got {st}")
        nt = tags.get("new-tag")
        if not nt or nt["this_week"] != 2 or nt["baseline"] != 0.0 or nt["rising"] or not nt["new"]:
            problems.append(f"phase 1: new-tag should be this_week=2 baseline=0.0 new=True rising=False, got {nt}")
        if rt and not rt["examples"]:
            problems.append("phase 1: a rising tag with this-week notes should carry examples")

        # 2. tag filtering
        noise_mentions = [m for m in result["mentions"] if m.get("domain") == "testing"]
        if len(noise_mentions) != 3:
            problems.append(f"phase 2: expected 3 mentions with domain=testing, got {len(noise_mentions)}")
        for m in noise_mentions:
            leaked = set(m["tags"]) & {"domain/testing", "readwise/concept", "readwise", "W39-2026",
                                       "area", "source/github"}
            if leaked:
                problems.append(f"phase 2: noise tags leaked into a mention's tags: {leaked} ({m['url']})")
        if not any("vector-loom" in m["tags"] for m in noise_mentions):
            problems.append("phase 2: a plain tag alongside noise tags should survive filtering")
        if any(t in tags for t in ("domain/testing", "readwise/concept", "readwise", "W39-2026",
                                    "area", "source/github")):
            problems.append("phase 2: a noise tag must not appear in the tags aggregate at all")
        testing_domain = domains.get("testing")
        if not testing_domain or testing_domain["this_week"] != 3 or not testing_domain["rising"]:
            problems.append(f"phase 2: domain 'testing' should be this_week=3 rising=True, got {testing_domain}")

        # 3. auto document-frequency cut
        if "vault-generic" in tags:
            problems.append("phase 3: a tag on most of the tagged corpus must be auto-stoplisted out of tags")
        if any("vault-generic" in m["tags"] for m in result["mentions"]):
            problems.append("phase 3: the auto-stoplisted tag must not remain on any mention either")

        # 4. clips counted
        clip_mentions = [m for m in result["mentions"] if m["origin"] == "clip"]
        if len(clip_mentions) != 1:
            problems.append(f"phase 4: expected exactly 1 clip mention, got {len(clip_mentions)}")
        elif clip_mentions[0]["family"] != "vault" or "rising-tag" not in clip_mentions[0]["tags"]:
            problems.append(f"phase 4: clip mention shape wrong: {clip_mentions[0]}")
        if result["week"]["clips"] != 1 or result["week"]["baseline_clips"] != 0:
            problems.append(f"phase 4: week.clips should be 1 with baseline 0, got {result['week']}")
        if sum(d["clips"] for d in result["daily"]) != 1:
            problems.append("phase 4: the clip should show up exactly once in the daily clips column")

        # 5. interests
        ci = interests.get("claude-code-anthropic-ecosystem")
        if not ci or ci["this_week"] != 3 or ci["baseline"] != 0.25:
            problems.append(f"phase 5: interest should be this_week=3 baseline=0.25, got {ci}")

        # 6. skipped
        if result["skipped"] != 2:
            problems.append(f"phase 6: expected 2 skipped (bad frontmatter + no date), got {result['skipped']}")
        if any(m["url"].endswith("bad-frontmatter.md") or m["url"].endswith("no-date.md") for m in result["mentions"]):
            problems.append("phase 6: a skipped note must not appear as a mention")

        # 7. symlink outside the vault
        if any("symlinked-outside" in m["url"] or "smuggled" in m["tags"] for m in result["mentions"]):
            problems.append("phase 7: a symlink out of the vault must be ignored, not read")

        # 8. shape
        for m in result["mentions"]:
            if m["family"] != "vault" or m["entities"] != [] or m["score"] is not None \
                    or m["eng_pct"] is not None or m["p"] is not None:
                problems.append(f"phase 8: mention shape wrong: {m}")
                break
        new_note = next((m for m in result["mentions"] if "new-tag" in m["tags"] and m["origin"] != "clip"), None)
        if not new_note or new_note["origin"] != "note:04_Resources":
            problems.append(f"phase 8: a note with no kind should fall back to its folder, got {new_note}")
        kinded = next((m for m in result["mentions"] if m["origin"] == "note:field-report"), None)
        if not kinded:
            problems.append("phase 8: a note with a kind should use it as the origin")
        if len(result["daily"]) != vault_pulse.DAILY_DAYS:
            problems.append(f"phase 8: daily should cover exactly {vault_pulse.DAILY_DAYS} days, got {len(result['daily'])}")
        else:
            dates = [d["date"] for d in result["daily"]]
            if dates[-1] != TODAY.isoformat() or dates != sorted(dates):
                problems.append(f"phase 8: daily should be oldest-first ending today, got {dates[0]}..{dates[-1]}")
            if not any(d["notes"] == 0 and d["clips"] == 0 for d in result["daily"]):
                problems.append("phase 8: a day with no notes or clips should still appear with zeros")
    finally:
        if sandbox is not None:
            teardown_sandbox(sandbox)

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "rising/new/baseline, tag filtering, "
                      "the document-frequency cut, clips, interests, skips and shape all ok"}
