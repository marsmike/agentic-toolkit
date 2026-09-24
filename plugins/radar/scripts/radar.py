#!/usr/bin/env python3
"""Radar: judge every Reader feed item against the owner's interests.

    uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py scan --since 1d [--json]
    uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py replay --since 30d --out DIR
    uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py discover [--interest ID ...]
    uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py feeds|trend|weekly

`scan` fetches feed items saved since `--since`, drops those already seen (canonical URL, or the
same title from the same feed: a repost under a new address) and a new feed's back catalogue
(published more than BACKLOG_GRACE_DAYS before `--since`; recorded as seen, not judged), asks
the judgment backend `worth_reading` per item x interest and `kind` per item, applies the
policy, appends one row per item to `00_Memory/radar/state.jsonl`, renders that day's note
`00_Memory/radar/YYYY-MM-DD.md` from the day's rows, and settles every fetched item it has now
recorded as seen (judged, repost or back catalogue) in Reader: with `--promote`, a strong one moves
to Later (profile `promote_location`) tagged `radar` and `radar/<interest>`, with a note when it
has none; every other one is archived (`--keep-in-feed` skips archiving). An item that could not
be judged, or whose promotion failed, stays in the feed for the next scan. Nothing is deleted; no
active content is written. With `--todoist`, each Portfolio epic (an interest from Todoist) that
got a strong item this run gets one dated comment listing them, at most one per epic and day;
never a new task, never a completed one. Without a key it prints SKIPPED and sends nothing; a backend that
answers nothing at all is recorded once in the dead-letter queue.

`replay` is the acceptance run (replay.py): own clips vs. feed items, Jev vs. BM25 vs. recency.
`discover` (discover.py) finds feeds for the interests via Kagi and writes an OPML to import.
`feeds`, `trend` and `weekly` (reports.py) read state.jsonl only: feed yield, rising interests,
and the weekly capture `01_Capture/Radar-Week-YYYY-WW.md`. `gaps` (gaps.py) is the weekly search
for what the feeds missed; `kagi search|news|answer|summarize` is the kagi skill's entry point.

What leaves the machine: item titles, summaries and site names, and interest names and glosses,
to the judgment backend (OpenRouter by default).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import discover as discover_mod
import gaps as gaps_mod
import interests as interests_mod
import judge
import kagi
import reader
import replay
import reports
from interests import Interest
from judgments import policy
from judgments import questions as Q
from judgments.state import in_chunks
from judgments.urls import _canonical
from reader import Item
from vault_utils import atomic_write, profile_value, read_frontmatter, require_vault, write_dlq_note

RADAR_DIR = Path("00_Memory") / "radar"
DEFAULT_PROMOTE_LOCATION = "later"
NOT_CONTENT = {"00_Memory", ".obsidian", ".trash", ".smart-env", "Templates", "Config"}


def parse_since(text: str, now: datetime) -> datetime:
    """`1d`, `36h`, `30d`, or a date `YYYY-MM-DD` (midnight UTC)."""
    if m := re.fullmatch(r"(\d+)([dh])", text.strip()):
        n = int(m.group(1))
        return now - (timedelta(days=n) if m.group(2) == "d" else timedelta(hours=n))
    try:
        return datetime.fromisoformat(text.strip()).replace(tzinfo=UTC)
    except ValueError:
        raise SystemExit(f"--since: expected like 1d, 36h or YYYY-MM-DD, got {text!r}") from None


def item_key(item: Item) -> str:
    return item.canonical or f"reader:{item.id}"


def keys_of(item: Item) -> set[str]:
    return {item_key(item), title_key(item)} - {""}


def title_key(item: Item) -> str:
    """feed + normalised title: a repost under a different URL. Empty for an untitled item."""
    words = re.sub(r"[^\w]+", " ", item.title.casefold()).split()
    return f"{item.feed.casefold()}|{' '.join(words)}" if words else ""


_RELEASE = re.compile(r"^(github\.com/[^/]+/[^/]+/releases)(/|$)")


def release_stream(canonical: str) -> str | None:
    """`github.com/<owner>/<repo>/releases` for a release page, else None."""
    m = _RELEASE.match(canonical)
    return m.group(1) if m else None


def is_backlog(item: Item, since: datetime) -> bool:
    """Published well before the window it was saved in: a newly subscribed feed's archive."""
    try:
        published = datetime.fromisoformat(item.published).replace(tzinfo=UTC)
    except ValueError:
        return False
    return published < since - timedelta(days=policy.BACKLOG_GRACE_DAYS)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def vault_sources(vault: Path) -> dict[str, str]:
    """canonical source URL -> vault-relative path, for every note with a `source`, captures
    included (a clipped item is covered). Built once per run."""
    index: dict[str, str] = {}
    for path in vault.rglob("*.md"):
        rel = path.relative_to(vault)
        if rel.parts and rel.parts[0] in NOT_CONTENT:
            continue
        try:
            fm, _ = read_frontmatter(path)
        except OSError:
            continue
        sources = fm.get("source")
        for src in sources if isinstance(sources, list) else [sources]:
            if isinstance(src, str) and src.startswith("http"):
                index.setdefault(_canonical(src), rel.as_posix())
    return index


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------


@dataclass
class RunUsage:
    backend: str = ""
    model: str = ""
    requests: int = 0
    input_tokens: int = 0
    usd: float = 0.0
    splits: int = 0
    skipped: int = 0
    failed_chunks: int = 0
    capped: bool = False
    errors: list[str] = field(default_factory=list)

    def add(self, u: judge.Usage) -> None:
        self.backend, self.model = u.backend, u.model or self.model
        self.requests += u.requests
        self.input_tokens += u.input_tokens
        self.usd += u.usd
        self.splits += u.splits
        self.skipped += len(u.skipped)

    def as_dict(self) -> dict[str, Any]:
        return {"backend": self.backend, "model": self.model, "requests": self.requests,
                "input_tokens": self.input_tokens, "usd": round(self.usd, 6), "splits": self.splits,
                "skipped_questions": self.skipped, "failed_chunks": self.failed_chunks, "capped": self.capped}


def judge_items(vault: Path, items: list[Item], interests: list[Interest], run: RunUsage,
                max_requests: int = policy.MAX_REQUESTS_PER_RUN) -> dict[int, dict]:
    """index into `items` -> {"p": {interest id: P(worth reading)}, "kind": label or None}.
    An item missing from the result was not judged (failed chunk, request cap) and stays unseen."""
    interest_state = {it.id: it.state() for it in interests}

    def ask(chunk: list[Item], offset: int) -> dict[int, dict]:
        if run.requests >= max_requests:
            run.capped = True
            return {}
        keys = [f"i{offset + j}" for j in range(len(chunk))]
        state = {"interests": interest_state, "items": {k: it.state() for k, it in zip(keys, chunk, strict=True)}}
        questions: dict[str, judge.Question] = {}
        for k in keys:
            questions[f"kind_{k}"] = Q.kind(k)
            for n, it in enumerate(interests):
                questions[f"w_{k}_{n}"] = Q.worth_reading(k, it.id)
        try:
            answers, usage = judge.judge(vault, state, questions)
        except judge.StateTooLarge:
            raise  # in_chunks halves the chunk
        except judge.JudgmentFailed as e:
            run.failed_chunks += 1
            run.errors.append(str(e)[:200])
            return {}
        run.add(usage)
        out: dict[int, dict] = {}
        for j, k in enumerate(keys):
            p = {it.id: round(answers[f"w_{k}_{n}"].p, 4) for n, it in enumerate(interests)
                 if f"w_{k}_{n}" in answers and answers[f"w_{k}_{n}"].p is not None}
            if p:
                kind = answers.get(f"kind_{k}")
                out[offset + j] = {"p": p, "kind": kind.top if kind else None}
        return out

    return in_chunks(items, policy.ITEMS_PER_REQUEST, ask)


def to_row(item: Item, judged: dict, run_date: str, run: RunUsage, t: dict[str, float], in_vault: str | None) -> dict:
    p = judged["p"]
    return {
        "run": run_date, "id": item.id, "canonical": item_key(item), "url": item.url, "title": item.title,
        "feed": item.feed, "category": item.category, "published": item.published, "saved_at": item.saved_at,
        "kind": judged["kind"], "p": p,
        "worth": sorted(i for i, v in p.items() if v >= t["T_WORTH"]),
        "strong": sorted(i for i, v in p.items() if v >= t["T_STRONG"]),
        "in_vault": in_vault,
        "backend": run.backend, "model": run.model, "questions_version": Q.QUESTIONS_VERSION,
    }


# ---------------------------------------------------------------------------
# The daily note
# ---------------------------------------------------------------------------


def _md_link(row: dict) -> str:
    title = (row.get("title") or row.get("url") or "untitled").replace("[", "(").replace("]", ")")
    return f"[{title}]({row['url']})" if row.get("url") else title


def render_daily(run_date: str, rows: list[dict], interests: list[Interest], usage: dict) -> str:
    names = {it.id: it.name for it in interests}
    strong_n = sum(1 for r in rows if r["strong"])
    worth_n = sum(1 for r in rows if r["worth"])
    models = sorted({f"{r['backend']}/{r['model']}" for r in rows})
    qv = sorted({r["questions_version"] for r in rows})
    lines = [
        "---",
        f"description: Radar {run_date} — {len(rows)} feed items judged, {strong_n} strong, {worth_n} worth reading",
        "status: active",
        f"created: {run_date}",
        "tags:",
        "  - domain/toolkit-meta",
        "---",
        "",
        f"# Radar {run_date}",
        "",
        f"{len(rows)} feed items judged against {len(interests)} interests ({', '.join(models) or 'no backend'}; "
        f"questions {', '.join(qv) or '-'}). **{strong_n} strong, {worth_n} worth reading.** "
        f"This run: {usage.get('requests', 0)} requests, ${usage.get('usd', 0):.4f}.",
        "",
    ]
    quiet = []
    for iid, name in names.items():
        worth = sorted((r for r in rows if iid in r["worth"]), key=lambda r: -r["p"].get(iid, 0))
        if not worth:
            quiet.append(name)
            continue
        strong = [r for r in worth if iid in r["strong"]]
        lines += [f"## {name}", "", f"strong {len(strong)} · worth {len(worth)} · of {len(rows)}", ""]
        for r in worth:
            bits = [r["feed"] or "?", r["kind"] or "?", f"p={r['p'][iid]:.2f}"]
            if r.get("in_vault"):
                bits.append(f"already in vault: `{r['in_vault']}`")
            link = _md_link(r)
            lines.append(f"- {'**' + link + '**' if r in strong else link} — {' · '.join(bits)}")
        lines.append("")
    if quiet:
        lines += [f"Nothing worth reading for: {', '.join(quiet)}.", ""]

    kinds = Counter(r["kind"] or "unjudged" for r in rows)
    lines += ["## Kinds", "", " · ".join(f"{k} {n}" for k, n in kinds.most_common()), ""]

    feeds: dict[str, list[dict]] = {}
    for r in rows:
        feeds.setdefault(r["feed"] or "?", []).append(r)
    lines += ["## Feeds", "", "| Feed | scanned | worth | strong |", "|---|---:|---:|---:|"]
    for feed, fr in sorted(feeds.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"| {feed} | {len(fr)} | {sum(1 for r in fr if r['worth'])} | {sum(1 for r in fr if r['strong'])} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


def _apply(updates: list[dict], done_key: str) -> dict[str, Any]:
    """`archived` -> archived / archive_error / archive_failed; `promoted` likewise."""
    if not updates:
        return {}
    stem = done_key.removesuffix("d")
    try:
        done, failed = reader.bulk_update(updates)
    except reader.ReaderError as e:
        return {done_key: 0, f"{stem}_error": str(e)[:200]}
    return {done_key: len(done), **({f"{stem}_failed": len(failed)} if failed else {})}


def settle(fetched: list[Item], recorded: set[str], state_rows: list[dict], names: dict[str, str],
           run_date: str, archive: bool, promote: bool, location: str, out: Path | None = None) -> dict[str, Any]:
    """Move every fetched feed item the radar has recorded (a repost shares a key with its
    original) out of the feed. With `promote`, the strongest not yet promoted, up to
    PROMOTE_PER_DAY a day counted in `promoted.jsonl`, go to `location`; a promoted item
    becomes a capture and a note, so the bar is deliberate. Every other recorded item is
    archived (the daily note still lists it). A failed promotion is neither recorded nor
    archived: it stays in the feed and competes again next scan. A Reader failure here never
    fails the scan."""
    strong: dict[str, dict[str, float]] = {}
    ledger = (out / "promoted.jsonl") if out else None
    done_before = read_jsonl(ledger) if ledger else []
    if promote:
        promoted_keys = {r["canonical"] for r in done_before}
        for r in state_rows:
            s = reports.bands(r)[1]
            if s and r["canonical"] not in promoted_keys:
                strong[r["canonical"]] = {i: r["p"][i] for i in s}
    budget = max(0, policy.PROMOTE_PER_DAY - sum(1 for r in done_before if r.get("date") == run_date))
    settled = [it for it in fetched if keys_of(it) & recorded]
    candidates = sorted((it for it in settled if item_key(it) in strong), key=lambda it: -max(strong[item_key(it)].values()))
    since = (date.fromisoformat(run_date) - timedelta(days=policy.RELEASE_STREAM_DAYS)).isoformat()
    streams = {release_stream(r["canonical"]) for r in done_before if str(r.get("date", "")) > since} - {None}
    chosen: set[str] = set()
    for it in candidates:
        if len(chosen) >= budget:
            break
        stream = release_stream(item_key(it))
        if stream in streams:
            continue  # this repo's release already came in this week; the daily note still lists it
        if stream:
            streams.add(stream)
        chosen.add(it.id)
    promotions, archive_ids = [], []
    for it in settled:
        if it.id in chosen:
            p = strong[item_key(it)]
            u: dict[str, Any] = {"id": it.id, "location": location, "tags": ["radar", *(f"radar/{i}" for i in sorted(p))]}
            if not it.notes.strip():
                u["notes"] = f"[radar {run_date}] " + "; ".join(f"{names.get(i, i)} p={v:.2f}" for i, v in sorted(p.items()))
            promotions.append(u)
        elif archive:
            archive_ids.append({"id": it.id, "location": "archive"})
    result: dict[str, Any] = {}
    if promotions:
        try:
            done, failed = reader.bulk_update(promotions)
        except reader.ReaderError as e:
            done, failed = [], []
            result["promote_error"] = str(e)[:200]
        by_id = {it.id: it for it in settled}
        if ledger and done:
            append_jsonl(ledger, [{"canonical": item_key(by_id[i]), "id": i, "date": run_date} for i in done])
        result["promoted"] = len(done)
        if failed:
            result["promote_failed"] = len(failed)
    return {**result, **_apply(archive_ids, "archived")}


TODOIST_ITEMS_PER_COMMENT = 5


def _td_comment(task_id: str, text: str) -> None:
    """The one write to Todoist. Evals replace it with a stub."""
    if not shutil.which("td"):
        raise FileNotFoundError("td")
    subprocess.run(["td", "comment", "add", f"id:{task_id}", "--content", text, "--no-notify"],
                   capture_output=True, text=True, timeout=60, check=True)


def comment_epics(out: Path, rows: list[dict], interests: list[Interest], run_date: str) -> dict[str, Any]:
    """One comment per epic with strong items in `rows`, idempotent per (task, date) through
    `todoist.jsonl`. Without `td` or epics it does nothing and says nothing."""
    epics = {i.id: i for i in interests if i.todoist_task_id}
    if not epics:
        return {}
    ledger = out / "todoist.jsonl"
    done = {(r.get("task"), r.get("date")) for r in read_jsonl(ledger)}
    by_epic: dict[str, list[dict]] = {}
    for r in rows:
        for iid in reports.bands(r)[1] & epics.keys():
            by_epic.setdefault(iid, []).append(r)
    posted = 0
    for iid, rs in sorted(by_epic.items()):
        task = str(epics[iid].todoist_task_id)
        if (task, run_date) in done:
            continue
        top = sorted(rs, key=lambda r: -r["p"][iid])[:TODOIST_ITEMS_PER_COMMENT]
        text = "\n".join([f"[radar {run_date}] {len(rs)} strong feed item(s) for this epic:",
                          *(f"- {_md_link(r)} (p={r['p'][iid]:.2f})" for r in top)])
        try:
            _td_comment(task, text)
        except FileNotFoundError:
            return {}
        except (subprocess.SubprocessError, OSError) as e:
            return {"todoist_comments": posted, "todoist_error": str(e)[:200]}
        append_jsonl(ledger, [{"task": task, "date": run_date, "interest": iid, "items": len(rs)}])
        posted += 1
    return {"todoist_comments": posted}


def scan(vault: Path, out: Path, since: datetime, now: datetime, limit: int | None = None,
         max_requests: int = policy.MAX_REQUESTS_PER_RUN, archive: bool = True, promote: bool = False,
         todoist: bool = False) -> dict[str, Any]:
    run_date = now.date().isoformat()
    interests = interests_mod.load(vault)
    if not interests:
        return {"status": "no-interests", "detail": "no interests: set `interests_note` in Config/toolkit/radar.md"}
    reason = judge.unavailable_reason(vault)
    if reason:
        return {"status": "SKIPPED", "detail": f"judgment backend unavailable ({reason}); nothing sent"}
    try:
        fetched = reader.list_feed(since)
    except reader.NoToken:
        return {"status": "SKIPPED", "detail": "READWISE_TOKEN is not set; nothing fetched"}
    except reader.ReaderError as e:
        return {"status": "failed", "detail": f"Reader: {e}"}

    seen_rows = read_jsonl(out / "seen.jsonl")
    seen = {r["canonical"] for r in seen_rows} | {r["title_key"] for r in seen_rows if r.get("title_key")}
    items: list[Item] = []
    backlog: list[Item] = []
    for it in fetched:
        if keys_of(it) & seen:
            continue
        seen |= keys_of(it)
        (backlog if is_backlog(it, since) else items).append(it)
    items = items[:limit] if limit else items
    recorded = {r["canonical"] for r in seen_rows} | {r["title_key"] for r in seen_rows if r.get("title_key")}
    recorded |= {k for it in backlog for k in keys_of(it)}

    def archived() -> dict[str, Any]:
        names = {i.id: i.name for i in interests}
        location = str(profile_value(vault, "promote_location", DEFAULT_PROMOTE_LOCATION))
        return settle(fetched, recorded, read_jsonl(out / "state.jsonl"), names, run_date, archive, promote, location, out)
    append_jsonl(out / "seen.jsonl", [{"canonical": item_key(it), "title_key": title_key(it),
                                        "first_seen": run_date, "backlog": True} for it in backlog])
    result: dict[str, Any] = {"since": since.isoformat(), "fetched": len(fetched), "new": len(items),
                              "backlog": len(backlog), "interests": len(interests)}
    if not items:
        return {**result, **archived(), "status": "empty"}

    run = RunUsage()
    judged = judge_items(vault, items, interests, run, max_requests)
    result["usage"] = run.as_dict()
    if not judged:
        if run.failed_chunks:
            dlq = write_dlq_note(
                vault, "radar-scan-no-answers", "Radar scan got no judgments",
                what_happened=f"{run.failed_chunks} request(s) for {len(items)} feed items returned nothing: "
                              f"{'; '.join(run.errors[:3])}",
                why_recorded="A configured backend that answers nothing is not the no-key case; every item stays "
                             "unseen and is retried next run.",
            )
            return {**result, **archived(), "status": "failed", "dlq": dlq.relative_to(vault).as_posix()}
        return {**result, "status": "capped" if run.capped else "failed"}

    t = policy.thresholds(run.backend)
    sources = vault_sources(vault)
    rows = [to_row(items[i], j, run_date, run, t, sources.get(items[i].canonical)) for i, j in sorted(judged.items())]
    append_jsonl(out / "state.jsonl", rows)
    append_jsonl(out / "seen.jsonl", [{"canonical": item_key(items[i]), "title_key": title_key(items[i]),
                                        "first_seen": run_date} for i in sorted(judged)])

    day_rows = [r for r in read_jsonl(out / "state.jsonl") if r.get("run") == run_date]
    note = out / f"{run_date}.md"
    atomic_write(note, render_daily(run_date, day_rows, interests, run.as_dict()))
    recorded |= {k for i in judged for k in keys_of(items[i])}
    commented = comment_epics(out, rows, interests, run_date) if todoist else {}
    return {**result, **archived(), **commented, "status": "ok", "judged": len(rows), "unjudged": len(items) - len(rows),
            "strong": sum(1 for r in rows if r["strong"]), "worth": sum(1 for r in rows if r["worth"]),
            "note": str(note)}


def report(vault: Path, out: Path, cmd: str, now: datetime, week: str | None, force: bool = False) -> dict[str, Any]:
    rows = read_jsonl(out / "state.jsonl")
    if not rows:
        return {"status": "empty", "detail": f"no radar state in {out}; run `scan` first"}
    if cmd == "feeds":
        return {"status": "ok", "feeds": reports.feeds(rows, now)}
    if cmd == "trend":
        wk = week or reports.week_of(now.date().isoformat())
        return {"status": "ok", "week": wk, "interests": reports.trend(rows, wk), "terms": reports.emerging_terms(rows, wk)}
    wk = week or reports.last_complete_week(now.date())
    if not any(reports.week_of(r["run"]) == wk for r in rows):
        # A week the radar did not scan has no digest; writing one would hand distill an empty
        # capture. [earned: 2026-09-23, first live week: the last complete week predates the radar]
        return {"status": "empty", "week": wk, "detail": f"no scans in {wk}; nothing to digest"}
    text = reports.render_weekly(wk, rows, interests_mod.load(vault), now, gaps=gaps_mod.load_week(out, wk))
    try:
        path = reports.write_weekly(vault, wk, text, force, out / "weekly.jsonl")
    except FileExistsError as e:
        return {"status": "exists", "detail": str(e)}
    return {"status": "ok", "week": wk, "capture": path.relative_to(vault).as_posix()}


def kagi_cmd(vault: Path, out: Path, mode: str, text: str) -> dict[str, Any]:
    """The kagi skill's entry point: one call, under the same ledger and weekly budget as discovery."""
    ledger = kagi.Ledger(out / "kagi-ledger.jsonl",
                         float(profile_value(vault, "kagi_weekly_budget_usd", kagi.DEFAULT_WEEKLY_BUDGET_USD)))
    call = {"search": kagi.search, "news": kagi.news, "answer": kagi.fastgpt, "summarize": kagi.summarize}[mode]
    try:
        answer = call(text, ledger)
    except kagi.NoKey:
        return {"status": "SKIPPED", "detail": "KAGI_API_KEY is not set; nothing sent"}
    except kagi.OverBudget as e:
        return {"status": "over-budget", "detail": str(e)}
    except kagi.KagiError as e:
        return {"status": "failed", "detail": str(e)}
    last = ledger.rows()[-1]
    return {"status": "ok", "mode": mode, "result": answer, "usd": last["usd"],
            "spent_this_week": round(ledger.spent_this_week(datetime.now(UTC)), 4)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("scan", help="judge feed items saved since --since")
    sp.add_argument("--since", default="1d")
    sp.add_argument("--limit", type=int, default=None, help="judge at most this many new items")
    sp.add_argument("--max-requests", type=int, default=policy.MAX_REQUESTS_PER_RUN)
    sp.add_argument("--out", type=Path, default=None, help="radar state dir (default: $VAULT/00_Memory/radar)")
    sp.add_argument("--keep-in-feed", action="store_true", help="do not archive recorded items in Reader")
    sp.add_argument("--promote", action="store_true", help="move strong items to Later, tagged radar/<interest>")
    sp.add_argument("--todoist", action="store_true", help="comment strong items on the Portfolio epic they serve")
    sp.add_argument("--json", action="store_true")
    rp = sub.add_parser("replay", help="acceptance: own clips vs. feed items, judgment vs. BM25 vs. recency")
    rp.add_argument("--since", default="30d")
    rp.add_argument("--exclude-last-days", type=int, default=7, help="keep the most recent days out of the labels")
    rp.add_argument("--feed-sample", type=int, default=300, help="feed items to judge as negatives; 0 = all")
    rp.add_argument("--max-requests", type=int, default=policy.MAX_REQUESTS_PER_RUN)
    rp.add_argument("--out", type=Path, required=True, help="report dir; never the vault")
    rp.add_argument("--json", action="store_true")
    dp = sub.add_parser("discover", help="find feeds for the interests (Kagi) and write an OPML for Reader")
    dp.add_argument("--interest", action="append", default=None, help="interest id; repeat; default all")
    dp.add_argument("--seed", action="append", default=None, help="a page or feed URL to validate and judge too")
    dp.add_argument("--queries", type=int, default=policy.QUERIES_PER_INTEREST, help="Kagi searches per interest; 0 = none")
    dp.add_argument("--out", type=Path, default=None, help="default: $VAULT/00_Memory/radar")
    dp.add_argument("--json", action="store_true")
    for name, text in (("feeds", "per-feed yield and unsubscribe advice"), ("trend", "rising interests this week")):
        rp_ = sub.add_parser(name, help=text)
        rp_.add_argument("--week", default=None, help="ISO week YYYY-Www (trend; default: this week)")
        rp_.add_argument("--out", type=Path, default=None)
        rp_.add_argument("--json", action="store_true")
    wp = sub.add_parser("weekly", help="write 01_Capture/Radar-Week-YYYY-WW.md from state.jsonl")
    wp.add_argument("--week", default=None, help="ISO week YYYY-Www (default: the last complete week)")
    wp.add_argument("--force", action="store_true", help="rewrite an existing weekly capture")
    wp.add_argument("--out", type=Path, default=None)
    wp.add_argument("--json", action="store_true")
    gp = sub.add_parser("gaps", help="once a week: recent posts per interest the feeds missed (Kagi news), judged")
    gp.add_argument("--promote", action="store_true", help="save the strongest to Reader Later, within the daily budget")
    gp.add_argument("--out", type=Path, default=None)
    gp.add_argument("--json", action="store_true")
    kp = sub.add_parser("kagi", help="Kagi on demand: search, news, answer (FastGPT), summarize (a URL)")
    kp.add_argument("mode", choices=("search", "news", "answer", "summarize"))
    kp.add_argument("text", help="the query, or for summarize the URL")
    kp.add_argument("--out", type=Path, default=None)
    kp.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    vault = require_vault()
    now = datetime.now(UTC)
    if args.cmd == "kagi":
        result = kagi_cmd(vault, args.out or vault / RADAR_DIR, args.mode, args.text)
    elif args.cmd == "gaps":
        result = gaps_mod.gaps(vault, args.out or vault / RADAR_DIR, now, args.promote)
    elif args.cmd in ("feeds", "trend", "weekly"):
        result = report(vault, args.out or vault / RADAR_DIR, args.cmd, now, args.week, getattr(args, "force", False))
    elif args.cmd == "discover":
        result = discover_mod.discover(vault, args.out or vault / RADAR_DIR, now, args.interest, args.seed, args.queries)
    elif args.cmd == "replay":
        result = replay.replay(vault, args.out, parse_since(args.since, now),
                               now - timedelta(days=args.exclude_last_days), args.feed_sample, args.max_requests)
    else:
        result = scan(vault, args.out or vault / RADAR_DIR, parse_since(args.since, now), now, args.limit,
                      args.max_requests, archive=not args.keep_in_feed, promote=args.promote, todoist=args.todoist)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        hide = ("status", "usage", "per_interest", "thresholds")
        detail = result.get("detail") or ", ".join(f"{k}={v}" for k, v in result.items() if k not in hide)
        print(f"{result['status'].upper()}  {detail}")
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
