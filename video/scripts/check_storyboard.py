#!/usr/bin/env python3
"""Check that the video renders the locked storyboard exactly.

Usage: check_storyboard.py STORYBOARD.md

STORYBOARD.md is the locked slice 01 storyboard (it lives in the mission
workspace, not in this repo). Checks, against src/storyboard.json and the
capture it names:
  - the same scenes, in order, with the same start/end seconds and source,
    and each scene's composed text cell byte for byte;
  - scene times are contiguous and total 90-120 s;
  - each terminal block (T4-T9) equals the session.txt lines the scene
    shows, with T7's declared crop applied.
Exits 1 with every difference listed.
"""
import json
import re
import sys
from pathlib import Path

VIDEO = Path(__file__).resolve().parent.parent


def table(storyboard: str) -> list[dict]:
    scenes = []
    for line in storyboard.splitlines():
        if not re.match(r"^\| \d+ \|", line):
            continue
        n, span, dur, _on, text, src = [c.strip() for c in line.strip().strip("|").split(" | ")]
        start, end = (int(x) for x in span.split("–"))
        scenes.append({"n": int(n), "start": start, "end": end, "dur": int(dur), "text": text, "source": src})
    return scenes


def blocks(storyboard: str) -> dict[str, list[str]]:
    return {
        m.group(1): m.group(2).rstrip("\n").split("\n")
        for m in re.finditer(r"\*\*(T\d): .*?```\n(.*?)```", storyboard, re.S)
    }


def shown_lines(session: list[str], terminal: dict) -> list[str]:
    first, last = terminal["lines"]
    lines = session[first - 1 : last]
    crop = terminal.get("crop")
    if crop:
        i = crop["line"] - first
        cut = lines[i].index(crop["endsWith"]) + len(crop["endsWith"])
        lines[i] = lines[i][:cut]
    return lines


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    storyboard = Path(sys.argv[1]).read_text(encoding="utf-8")
    ours = json.loads((VIDEO / "src" / "storyboard.json").read_text(encoding="utf-8"))
    session = (VIDEO / ours["capture"]).with_suffix(".txt").read_text(encoding="utf-8").split("\n")
    problems = []

    if not re.search(r"^locked: ", storyboard, re.M):
        problems.append("storyboard has no `locked:` line")
    theirs = table(storyboard)
    if len(theirs) != len(ours["scenes"]):
        problems.append(f"scene count: storyboard {len(theirs)}, video {len(ours['scenes'])}")
    for want, got in zip(theirs, ours["scenes"]):
        for key in ("n", "start", "end", "text", "source"):
            if want[key] != got[key]:
                problems.append(f"scene {want['n']} {key}:\n  storyboard: {want[key]!r}\n  video:      {got[key]!r}")
        if want["end"] - want["start"] != want["dur"]:
            problems.append(f"scene {want['n']}: storyboard duration {want['dur']} != end - start")
    scenes = ours["scenes"]
    for a, b in zip(scenes, scenes[1:]):
        if a["end"] != b["start"]:
            problems.append(f"gap or overlap between scenes {a['n']} and {b['n']}")
    total = scenes[-1]["end"] - scenes[0]["start"]
    if not 90 <= total <= 120:
        problems.append(f"total {total} s is outside 90-120 s")

    expected = blocks(storyboard)
    for scene in scenes:
        terminal = scene.get("terminal")
        if not terminal:
            continue
        name = terminal["block"]
        got = shown_lines(session, terminal)
        if expected.get(name) != got:
            problems.append(f"scene {scene['n']} {name}: terminal lines differ from the storyboard block")
            for i, (w, g) in enumerate(zip(expected.get(name, []), got)):
                if w != g:
                    problems.append(f"  line {i + 1}:\n    storyboard: {w!r}\n    capture:    {g!r}")

    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(scenes)} scenes, {total} s, captions and terminal blocks match the locked storyboard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
