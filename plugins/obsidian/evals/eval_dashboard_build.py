"""Eval: dashboard_build.py writes a self-contained Dashboard.html from the vault, in a git sandbox.

1. notes    — a note distilled today is in, one outside the 84-day window is out, a backfilled
              `processed_date_estimated: true` note is out, `processed_date: unknown` is out, and a
              note never distilled (`status: review`, no `distilled_at`) is out
2. fields   — source type by address (x.com → tweet, arxiv → paper, none → own), domains from
              `domain/*` tags, kind (or `unsorted`)
3. runs     — every run row in the ledger is a run, newest first: its own counts and summary, or a
              legacy row's from its `pipeline …` commit, or "counts not recorded"; a hand commit is
              not a run
6. radar    — the radar ledgers reach the payload: worth-or-strong items with their fate, per-interest
              counts named from the interests note, today's counts, and a javascript: url never a link
5. imports  — a run's imported items reach its run row with their fate and notes, and a clipping
              in neither inbox nor archive is counted as missing
4. safe     — a description holding `</script><script>` cannot close the data element: the page
              has exactly two script elements and the payload parses back to the same data
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "dashboard_build"
NOTE = "---\ndescription: {d}\nstatus: distilled\nprocessed_date: {p}\n{extra}---\n\n# N\n"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import dashboard_build

    problems: list[str] = []
    today = date.today()
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        res = sandbox / "04_Resources"
        notes = {
            "Eval-Dash-Tweet": NOTE.format(d="Evil </script><script>alert(1)</script> tweet", p=today.isoformat(),
                                           extra="source: https://x.com/a/status/1\nkind: tool-landmark\ntags:\n- domain/ai-ml\n"),
            "Eval-Dash-Paper": NOTE.format(d="paper", p=(today - timedelta(days=3)).isoformat(),
                                           extra='source: https://arxiv.org/abs/2601.1\ningested_at: "2026-09-01T08:00:00Z"\n'
                                                 'distilled_at: "2026-09-25T13:00:00Z"\n'),
            "Eval-Dash-Old": NOTE.format(d="old", p=(today - timedelta(days=200)).isoformat(), extra=""),
            "Eval-Dash-Estimated": NOTE.format(d="est", p=today.isoformat(), extra="processed_date_estimated: true\n"),
            "Eval-Dash-Unknown": NOTE.format(d="unk", p="unknown", extra=""),
            # a real processed_date on a note never distilled: 75 such notes put 92 on a 17-note day
            "Eval-Dash-Review": NOTE.format(d="review", p=today.isoformat(), extra="").replace("status: distilled", "status: review"),
        }
        for name, text in notes.items():
            (res / f"{name}.md").write_text(text, encoding="utf-8")
        # title: a real title's punctuation ("5.5", a colon) never survives the filename slug
        # ("5-5"); the dashboard must read it from the H1, not derive it from the path.
        (res / "Eval-Dash-Punct-5-5-Title.md").write_text(
            f"---\ndescription: punct\nstatus: distilled\nprocessed_date: {today.isoformat()}\n---\n\n"
            "# Opus 5.5: a punctuated title, not a slug\n", encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.email", "eval@example.org"), ("config", "user.name", "eval"),
                     ("add", "-A"), ("commit", "-q", "-m", "hand edit"),
                     ("commit", "-q", "--allow-empty", "-m", "pipeline 2026-09-25 13:06: 7 distilled, 1 dropped, 2 failed; in: x")):
            _git(sandbox, *args)

        import imports_log
        (sandbox / "01_Capture").mkdir(exist_ok=True)
        (sandbox / "01_Capture" / "Readwise-Article-wait.md").write_text("---\nsource: https://e.org/w\n---\n# Wait\n", encoding="utf-8")
        imports_log.record(sandbox, "2026-09-25 13:06", [
            {"doc_id": "w", "capture": "01_Capture/Readwise-Article-wait.md", "via": "clip"},
            {"doc_id": "k", "found": "04_Resources/Eval-Dash-Paper.md"},
            {"doc_id": "m", "capture": "01_Capture/Readwise-Article-gone.md", "via": "clip"}])

        # radar ledgers: one strong item promoted today, one merely worth reading yesterday
        rd = sandbox / "00_Memory" / "radar"
        rd.mkdir(parents=True, exist_ok=True)
        (sandbox / "Config" / "toolkit").mkdir(parents=True, exist_ok=True)
        (sandbox / "Config" / "toolkit" / "radar.md").write_text("---\ninterests_note: 03_Areas/Eval-Interests.md\n---\n", encoding="utf-8")
        (sandbox / "03_Areas" / "Eval-Interests.md").write_text("---\ninterests:\n- name: Agent Memory\n  gloss: x\n---\n", encoding="utf-8")
        rows = [{"run": today.isoformat(), "canonical": "example.org/strong", "url": "https://example.org/strong", "title": "A strong <b>one</b>",
                 "feed": "arXiv.org", "kind": "paper", "p": {"agent-memory": 0.9, "epic-x": 0.2}, "worth": ["agent-memory"], "strong": ["agent-memory"], "in_vault": None},
                {"run": (today - timedelta(days=1)).isoformat(), "canonical": "example.org/worth", "url": "javascript:alert(1)", "title": "Worth",
                 "feed": "reddit.com", "kind": "opinion", "p": {"agent-memory": 0.72}, "worth": ["agent-memory"], "strong": [], "in_vault": None},
                {"run": today.isoformat(), "canonical": "example.org/no", "url": "https://example.org/no", "title": "No",
                 "feed": "LWN", "kind": "news", "p": {"agent-memory": 0.1}, "worth": [], "strong": [], "in_vault": None}]
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (rd / "promoted.jsonl").write_text(json.dumps({"canonical": "example.org/strong", "date": today.isoformat()}) + "\n", encoding="utf-8")
        import radar_ledger
        data = dashboard_build.build(sandbox, today)
        rad = data.get("radar") or {}
        if rad.get("counts") != {"judged": 3, "worth": 2, "strong": 1, "promoted": 1} or rad.get("today") != {"judged": 2, "strong": 1, "promoted": 1}:
            problems.append(f"radar: counts {rad.get('counts')}, today {rad.get('today')}")
        if [(i["title"], i["promoted"], i["url"]) for i in rad.get("items", [])] != [("A strong <b>one</b>", True, "https://example.org/strong"), ("Worth", False, "javascript:alert(1)")]:
            problems.append(f"radar: items {rad.get('items')}")
        if rad.get("interests", {}).get("agent-memory", {}).get("name") != "Agent Memory" or rad["interests"]["agent-memory"]["strong"] != 1:
            problems.append(f"radar: interests {rad.get('interests')}")
        wk = lambda d: "{}-W{:02d}".format(*d.isocalendar()[:2])  # noqa: E731
        # the quiet-week path: with no current-week rows at all, the week is still a (zero) column
        (rd / "state.jsonl").write_text(json.dumps({**rows[1], "run": (today - timedelta(days=21)).isoformat(), "strong": ["agent-memory"]}) + "\n", encoding="utf-8")
        quiet = radar_ledger.load(sandbox, (today - timedelta(days=83)).isoformat(), today)
        if wk(today) not in quiet.get("weeks", {}) or quiet["weeks"][wk(today)] != {} or list(quiet["weeks"])[-1] != wk(today):
            problems.append(f"radar: the current week must be the last, zero column when quiet, got {list(quiet.get('weeks', {}))}")
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        # rising: earlier weeks [2, 4] (median 3), this week 5 → rising; this week 4 → not (needs ≥ 1.5 × 3)
        hist = [(today - timedelta(weeks=3), 2), (today - timedelta(weeks=2), 4), (today - timedelta(weeks=1), 4)]
        extra = [{"run": (d - timedelta(days=d.weekday())).isoformat(), "canonical": f"e/{i}-{j}", "url": "", "title": "t", "feed": "f", "kind": "paper",
                  "p": {"agent-memory": 0.9}, "worth": ["agent-memory"], "strong": ["agent-memory"], "in_vault": None}
                 for i, (d, n) in enumerate(hist[:2]) for j in range(n)]
        this = [{**extra[0], "canonical": f"now/{j}", "run": today.isoformat()} for j in range(5)]
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in extra + this), encoding="utf-8")
        r2 = radar_ledger.load(sandbox, (today - timedelta(days=83)).isoformat(), today)
        if r2["rising"] != ["agent-memory"]:
            problems.append(f"radar: 5 strong against a median of 3 must be rising, got {r2['rising']}")
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in extra + this[:4]), encoding="utf-8")
        if radar_ledger.load(sandbox, (today - timedelta(days=83)).isoformat(), today)["rising"]:
            problems.append("radar: 4 strong against a median of 3 must not be rising")
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        # "Top feed items" from a GitHub release feed is often just the tag ("v2.1.275"), useless
        # without the repo: the title gets the repo name from the item's own URL prefixed.
        cases = [
            ("https://github.com/anthropics/claude-code/releases/tag/v2.1.275", "v2.1.275", "claude-code v2.1.275"),
            ("https://github.com/acme/widget/releases", "3.0", "widget 3.0"),
            ("https://github.com/acme/widget/releases", "Widget 3.0", "Widget 3.0"),
            ("https://example.org/not-github", "v2.1.275", "v2.1.275"),
            ("https://github.com/acme/widget/releases/tag/v2", "widget v2 release notes", "widget v2 release notes"),
        ]
        for url, title, want in cases:
            got = radar_ledger.release_title(url, title)
            if got != want:
                problems.append(f"release_title({url!r}, {title!r}): got {got!r}, want {want!r}")
        # retired interests: an id the owner has since renamed or dropped from the interests note
        # must not resurface as a second, stale-slug interest next to its current name.
        retired_row = {"run": today.isoformat(), "canonical": "example.org/retired", "url": "https://example.org/retired",
                       "title": "Old slug", "feed": "f", "kind": "paper", "p": {"agent-memory-old": 0.85},
                       "worth": ["agent-memory-old"], "strong": ["agent-memory-old"], "in_vault": None}
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [*rows, retired_row]), encoding="utf-8")
        r3 = radar_ledger.load(sandbox, (today - timedelta(days=83)).isoformat(), today)
        if "agent-memory-old" in r3["interests"]:
            problems.append(f"radar: a renamed/retired interest id must not appear as its own entry: {sorted(r3['interests'])}")
        if r3["interests"].get("retired", {}).get("name") != "Retired interests" or r3["interests"]["retired"]["strong"] < 1:
            problems.append(f"radar: a retired interest id must collapse into one 'Retired interests' bucket: {r3['interests'].get('retired')}")
        if any(iid == "agent-memory-old" for w in r3["weeks"].values() for iid in w):
            problems.append(f"radar: 'Strong per week' must not carry a raw retired id either: {r3['weeks']}")
        (rd / "state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        run = next((r for r in data["runs"] if r.get("run") == "2026-09-25 13:06"), {})
        fates = [(i["title"], i["status"], i["notes"]) for i in run.get("items", [])]
        if fates != [("Wait", "waiting", []), ("04_Resources/Eval-Dash-Paper.md", "known", ["04_Resources/Eval-Dash-Paper.md"]),
                     ("01_Capture/Readwise-Article-gone.md", "missing", [])] or data.get("missing") != 1:
            problems.append(f"imports: {fates}, missing={data.get('missing')}")
        got = {n["path"]: n for n in data["notes"]
              if n["path"] in ("04_Resources/Eval-Dash-Tweet.md", "04_Resources/Eval-Dash-Paper.md")}
        if set(got) != {"04_Resources/Eval-Dash-Tweet.md", "04_Resources/Eval-Dash-Paper.md"}:
            problems.append(f"notes: {sorted(got)}")
        t, p = got.get("04_Resources/Eval-Dash-Tweet.md", {}), got.get("04_Resources/Eval-Dash-Paper.md", {})
        # title: the note's own title (frontmatter `title`, else its `# H1`), never the filename
        # slug — a real title's dots and punctuation don't survive a filename ("5.5" -> "5-5").
        if t.get("title") != "N" or p.get("title") != "N":
            problems.append(f"title: both fixtures' body is '# N'; got tweet={t.get('title')!r} paper={p.get('title')!r}")
        punct = next((n for n in data["notes"] if n["path"] == "04_Resources/Eval-Dash-Punct-5-5-Title.md"), {})
        if punct.get("title") != "Opus 5.5: a punctuated title, not a slug":
            problems.append(f"title: must come from the H1, not the filename slug; got {punct.get('title')!r}")
        if (t.get("type"), t.get("kind"), t.get("domains")) != ("tweet", "tool-landmark", ["ai-ml"]):
            problems.append(f"fields: tweet {t.get('type')}, {t.get('kind')}, {t.get('domains')}")
        if (p.get("type"), p.get("kind")) != ("paper", "unsorted"):
            problems.append(f"fields: paper {p.get('type')}, {p.get('kind')}")
        if (p.get("ingested_at"), p.get("distilled_at")) != ("2026-09-01T08:00:00Z", "2026-09-25T13:00:00Z"):
            problems.append(f"fields: paper timestamps {p.get('ingested_at')}, {p.get('distilled_at')}")
        if dashboard_build.source_type("") != "own":
            problems.append("fields: no source is not 'own'")
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", str(data.get("built") or "")):
            problems.append(f"timestamps: data['built'] is not UTC-Z, got {data.get('built')!r}")
        if [(r["distilled"], r["dropped"], r["failed"]) for r in data["runs"]] != [(7, 1, 2)]:
            problems.append(f"runs: {data['runs']}")
        if any(n["path"] == "04_Resources/Eval-Dash-Review.md" for n in data["notes"]):
            problems.append("notes: a note never distilled (status: review, no distilled_at) counts on its processed_date")
        # runs come from the ledger's run rows: one with its own counts, one legacy row with neither
        # counts nor a commit (still a run), and the legacy row the commit above counts
        imports_log.record(sandbox, f"{today.isoformat()} 06:00", [], at=f"{today.isoformat()}T06:00:03Z", distilled=2,
                           dropped=0, failed=0, shallow=True, summary="2 distilled, 0 dropped, 0 failed; 4 in the inbox")
        imports_log.record(sandbox, f"{today.isoformat()} 03:00", [])
        got = [(r["run"][11:], r["distilled"], r["failed"], r["summary"], r["at"]) for r in dashboard_build.build(sandbox, today)["runs"]]
        if got != [("06:00", 2, 0, "2 distilled, 0 dropped, 0 failed; 4 in the inbox", f"{today.isoformat()}T06:00:03Z"),
                   ("03:00", 0, 0, "counts not recorded", f"{today.isoformat()}T03:00:00Z"),
                   ("13:06", 7, 2, "7 distilled, 1 dropped, 2 failed; in: x", "2026-09-25T13:06:00Z")]:
            problems.append(f"runs: from the ledger, newest first, got {got}")

        page = dashboard_build.render(data)
        if len(re.findall(r"<script\b", page)) != 2:
            problems.append("safe: a description opened a script element")
        m = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
        if not m or json.loads(m.group(1)) != json.loads(json.dumps(data)):
            problems.append("safe: embedded data does not round-trip")
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "notes, fields, runs and escaping as expected"}
