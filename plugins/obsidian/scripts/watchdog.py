#!/usr/bin/env python3
"""Watchdog: is the pipeline alive and well? Reads the vault, prints a verdict, changes nothing.

    uv run scripts/watchdog.py [--json] [--max-age-hours 4] [--now ISO]

The pipeline routine can only report what goes wrong inside a run. This says what it cannot: that
no run has committed for too long, that a run died holding the lock, that the last run's summary
carries a failure, that captures are parked or piling up, that a DLQ note appeared. A second
routine runs it between pipeline runs and sends one notification only when `ok` is false.
[earned: 2026-09-25, owner's request — "alert me if something is not working"]

Exit 1 when there is a problem, so a shell can branch on it. Every check is deterministic: no
model, no network, only git and files. `health()` is the importable one-word verdict (healthy,
late, stuck, failing) from the vault's files alone, no git; the week's run counts come from the
ledger's run rows (`imports_log.runs`), not from `git log`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import imports_log
import radar_ledger
from vault_utils import contained, example_vault, git_output, read_frontmatter, require_vault, shallow_history

LOCK = Path("00_Memory") / "pipeline.lock"
STATE = Path("00_Memory") / "pipeline-state.json"
DLQ = Path("00_Memory") / "dlq"
SIGNAL = Path("00_Memory") / "radar" / "signal.json"  # the Signal Radar's own file; `generated` is its UTC time
MAX_AGE_HOURS = 4.0        # the routine runs every 3 h; one missed run is a problem
LOCK_STALE_HOURS = 6.0     # pipeline_run's own stale-lock horizon; the lock is never committed, so in a fresh
                           # clone (the cloud routine) a hung run shows up as `stale`, not `hung`
NEW_DLQ_HOURS = 24.0       # a DLQ note this recent is news; older open ones are listed, not alerted
INBOX_LIMIT = 25           # pipeline_run.DEFAULT_BATCH: more than one batch waiting means runs are not keeping up
NOTIFY_CHARS = 600         # a push notification's budget; the text is cut here, never by the routine
STATS_DAYS = 7             # the rolling window of `facts.week`
RUNS_PER_DAY = 8           # the pipeline's cadence (every 3 h): what a full week of runs looks like
DIGEST_WEEKDAY, DIGEST_HOUR, DIGEST_MINUTE = 6, 20, 50  # Sunday, the 20:58 UTC check (20:50–20:59, allowing for
                                                        # start-up); the 23:58 check runs too and must not repeat it
FAIL_WORDS = ("failed", "build failed", "git-ignored", "missing", "not attempted", "refused")


def last_pipeline_commit(vault: Path, grep: str = "^pipeline") -> tuple[datetime | None, str]:
    """(commit time, subject) of the newest commit whose subject matches `grep` (`pipeline …` by
    default), or (None, "")."""
    out = git_output(vault, "log", "-1", f"--grep={grep}", "--format=%cI%x09%s").strip()
    if not out:
        return None, ""
    when, _, subject = out.partition("\t")
    try:
        return datetime.fromisoformat(when), subject
    except ValueError:
        return None, subject


def _counts(summary: str) -> dict[str, int]:
    m = re.search(r"(\d+) distilled, (\d+) dropped, (\d+) failed", summary)
    return {"distilled": int(m.group(1)), "dropped": int(m.group(2)), "failed": int(m.group(3))} if m else {}


def check(vault: Path, now: datetime, max_age_hours: float = MAX_AGE_HOURS) -> dict:
    problems: list[dict[str, str]] = []
    facts: dict[str, object] = {}

    when, subject = last_pipeline_commit(vault)
    facts["last_run"] = when.isoformat() if when else None
    facts["last_summary"] = subject.split(": ", 1)[-1] if subject else ""
    if when is None:
        problems.append({"kind": "no-run", "detail": "no `pipeline …` commit in this checkout's history"})
    else:
        age = (now - when.astimezone(UTC)).total_seconds() / 3600
        facts["age_hours"] = round(age, 1)
        if age > max_age_hours:
            problems.append({"kind": "stale", "detail": f"no pipeline run committed for {age:.1f} h (last: {when.strftime('%Y-%m-%d %H:%M')} UTC)"})
        summary = facts["last_summary"]
        counts = _counts(summary)
        flagged = [w for w in FAIL_WORDS if w in summary and not (w == "failed" and counts.get("failed", 1) == 0)]
        if flagged:
            problems.append({"kind": "failed", "detail": f"last run reported: {summary}"})

    # The Signal Radar routine commits `signal radar …` every 3 h; checked only once this vault has
    # one, so a vault without the routine is not alarmed. [earned: 2026-09-27, the routine went live
    # and nothing would have noticed it stop]
    sig_when, sig_subject = last_pipeline_commit(vault, "^signal radar")
    if sig_when is not None:
        sig_age = (now - sig_when.astimezone(UTC)).total_seconds() / 3600
        facts["signal_last"] = sig_subject.split(": ", 1)[-1]
        facts["signal_age_hours"] = round(sig_age, 1)
        if sig_age > max_age_hours:
            problems.append({"kind": "signal-stale", "detail": f"no Signal Radar run committed for {sig_age:.1f} h "
                                                               f"(last: {sig_when.strftime('%Y-%m-%d %H:%M')} UTC)"})

    lock = vault / LOCK
    if lock.is_file():
        held = (now - datetime.fromtimestamp(lock.stat().st_mtime, tz=UTC)).total_seconds() / 3600
        facts["lock_hours"] = round(held, 1)
        if held > LOCK_STALE_HOURS:
            problems.append({"kind": "hung", "detail": f"pipeline.lock has been held for {held:.1f} h: a run died or hangs"})

    try:
        state = json.loads((vault / STATE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    parked = state.get("parked") or []
    facts["parked"] = len(parked)
    if parked:
        problems.append({"kind": "parked", "detail": f"{len(parked)} capture(s) parked after repeated failures: {', '.join(str(p) for p in parked[:5])}"})

    inbox = [p for p in contained((vault / "01_Capture").glob("*.md"), vault) if p.is_file()]
    facts["inbox"] = len(inbox)
    if len(inbox) > INBOX_LIMIT:
        problems.append({"kind": "backlog", "detail": f"{len(inbox)} captures waiting, more than one batch ({INBOX_LIMIT}): runs are not keeping up"})

    open_notes, new_notes = [], []
    for p in sorted(contained((vault / DLQ).glob("*.md"), vault)):
        fm, _ = read_frontmatter(p)
        if str(fm.get("status") or "") != "active":
            continue
        open_notes.append(p.name)
        created = str(fm.get("created") or "")[:10]
        try:
            fresh = now - datetime.fromisoformat(created).replace(tzinfo=UTC) <= timedelta(hours=NEW_DLQ_HOURS)
        except ValueError:
            fresh = False
        if fresh:
            new_notes.append(f"{p.stem}: {str(fm.get('description') or '')[:120]}")
    facts["dlq_open"] = open_notes
    if new_notes:
        problems.append({"kind": "dlq", "detail": f"{len(new_notes)} new DLQ note(s): " + "; ".join(new_notes[:5])})

    facts["week"] = week_stats(vault, now)
    digest = (weekly_digest(facts["week"], now)
              if now.weekday() == DIGEST_WEEKDAY and now.hour == DIGEST_HOUR and now.minute >= DIGEST_MINUTE else "")
    return {"ok": not problems, "checked_at": now.isoformat(timespec="minutes"), "problems": problems, "facts": facts,
            "notification": notification(problems), "weekly_digest": digest}


def health(vault: Path, now: datetime | None = None, max_age_hours: float = MAX_AGE_HOURS) -> dict:
    """The pipeline in one word, from the vault's own files (no git, so a shallow or missing
    history changes nothing), for Now.md's health line:

        late      no run in the ledger, or the last one more than `max_age_hours` ago
        failing   the last run reported a capture that failed
        stuck     an active DLQ note, or a capture parked after repeated failures
        healthy   none of these (checked in this order; the first that applies is the word)

    {"ok", "word", "detail", "pipeline_at" (the last run row's UTC time, or None), "radar_at"
    (00_Memory/radar/signal.json's `generated`, or None)}."""
    now = now or datetime.now(UTC)
    last = next(iter(imports_log.load(vault)), None)
    pipeline_at = str(last.get("at") or f"{last['run'].replace(' ', 'T')}:00Z") if last else None
    try:
        radar_at = json.loads((vault / SIGNAL).read_text(encoding="utf-8")).get("generated") or None
    except (OSError, json.JSONDecodeError, AttributeError):
        radar_at = None
    try:
        parked = json.loads((vault / STATE).read_text(encoding="utf-8")).get("parked") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        parked = []
    dlq = sum(1 for p in contained((vault / DLQ).glob("*.md"), vault)
              if str(read_frontmatter(p)[0].get("status", "active")) == "active")
    try:
        age = (now - datetime.fromisoformat(pipeline_at).astimezone(UTC)).total_seconds() / 3600 if pipeline_at else None
    except ValueError:
        age = None
    if age is None or age > max_age_hours:
        word, detail = "late", "no pipeline run recorded" if age is None else f"last run {age:.1f} h ago"
    elif int((last or {}).get("failed") or 0):
        word, detail = "failing", f"the last run failed {int(last['failed'])} capture(s)"
    elif dlq or parked:
        word, detail = "stuck", ", ".join(x for x in (f"{dlq} open DLQ note(s)" if dlq else "",
                                                      f"{len(parked)} parked capture(s)" if parked else "") if x)
    else:
        word, detail = "healthy", f"last run {age:.1f} h ago"
    return {"ok": word == "healthy", "word": word, "detail": detail, "pipeline_at": pipeline_at, "radar_at": radar_at}


def week_stats(vault: Path, now: datetime) -> dict:
    """The last STATS_DAYS calendar days (today and the six before it, one boundary for every
    source) as numbers: runs and what they distilled (the ledger's run rows, `imports_log.runs`),
    what came in (the imports log), what the feeds brought (the radar ledgers). Derived every time
    from the vault; nothing is persisted, so the watchdog stays a reader. [earned: 2026-09-25,
    owner's request — "the monitoring job can collect stats too"] Only a vault whose ledger has no
    run row yet counts `pipeline …` commits instead, and `shallow` says when that history is cut
    short. [earned: 2026-09-29 — a shallow checkout's `git log` undercounts]"""
    first_day = now.date() - timedelta(days=STATS_DAYS - 1)  # today and the six dates before it, for every source
    ledger = imports_log.runs(vault)
    shallow = False
    if ledger:
        runs = [r for r in ledger if first_day.isoformat() <= r["run"][:10] <= now.date().isoformat()]
        counts = [{k: int(r[k]) for k in ("distilled", "failed")} for r in runs if r["counted"]]
    else:
        since = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)
        log = git_output(vault, "log", f"--since={since.isoformat()}", "--grep=^pipeline", "--format=%s")
        runs = [s for s in log.splitlines() if s.strip()]
        counts = [_counts(s) for s in runs]
        shallow = bool(runs) and shallow_history(vault)
    distilled = sum(c.get("distilled", 0) for c in counts)
    failed = sum(c.get("failed", 0) for c in counts)
    imported = sum(len(r["items"]) for r in imports_log.load(vault) if r["run"][:10] >= first_day.isoformat())
    radar = radar_ledger.load(vault, first_day.isoformat(), now.date())
    top = next(iter(radar["interests"]), "")
    return {"days": STATS_DAYS, "runs": len(runs), "runs_expected": STATS_DAYS * RUNS_PER_DAY, "distilled": distilled,
            "source": "ledger" if ledger else "git", "shallow": shallow,
            "failed": failed, "imported": imported, "radar_judged": radar["counts"].get("judged", 0),
            "radar_strong": radar["counts"].get("strong", 0), "radar_promoted": radar["counts"].get("promoted", 0),
            "rising": [radar["interests"].get(i, {}).get("name", i) for i in radar["rising"][:3]],
            "top_interest": radar["interests"].get(top, {}).get("name", top) if top else ""}


def weekly_digest(week: dict, now: datetime) -> str:
    """One push notification a week with the numbers, cut to NOTIFY_CHARS."""
    parts = [f"TheVoid, week to {now.date().isoformat()} ({now.strftime('%H:%M')} UTC):",
             f"{week['runs']} of ~{week['runs_expected']} runs, {week['distilled']} distilled, {week['imported']} imported"
             + (f", {week['failed']} failed" if week["failed"] else "")
             + (" (from a shallow git history: at least this many)" if week.get("shallow") else ""),
             f"radar: {week['radar_judged']} judged, {week['radar_strong']} strong, {week['radar_promoted']} promoted"
             + (f"; top: {week['top_interest']}" if week["top_interest"] else "")
             + (f"; rising: {', '.join(week['rising'])}" if week["rising"] else "")]
    text = "\n".join(parts)
    return text if len(text) <= NOTIFY_CHARS else text[:NOTIFY_CHARS - 1].rstrip() + "…"


def notification(problems: list[dict[str, str]]) -> str:
    """The push notification's text, ready to send: every problem, cut to NOTIFY_CHARS so the routine
    never has to. [Copilot review of PR #45]"""
    if not problems:
        return ""
    text = "TheVoid pipeline:\n" + "\n".join(f"[{p['kind']}] {p['detail']}" for p in problems)
    return text if len(text) <= NOTIFY_CHARS else text[:NOTIFY_CHARS - 1].rstrip() + "…"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-age-hours", type=float, default=MAX_AGE_HOURS)
    ap.add_argument("--now", help="ISO time to check against (default: now, UTC)")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now).astimezone(UTC) if args.now else datetime.now(UTC)
    vault = require_vault()
    if example_vault(vault):
        problems = [{"kind": "wrong-vault", "detail": f"{vault} is the toolkit's example vault, not the "
                     "owner's: set TOOLKIT_VAULT to the real vault (/home/user/TheVoid in the routine)"}]
        result = {"ok": False, "checked_at": now.strftime("%Y-%m-%dT%H:%M+00:00"), "problems": problems,
                  "facts": {}, "notification": notification(problems), "weekly_digest": ""}
    else:
        result = check(vault, now, args.max_age_hours)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["ok"]:
        print(f"OK  last run {result['facts'].get('last_run')}: {result['facts'].get('last_summary')}")
    else:
        print("PROBLEM\n" + "\n".join(f"- [{p['kind']}] {p['detail']}" for p in result["problems"]))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
