"""Scout: new sources the owner does not know about yet — feeds, APIs, services, tools, datasets.

    radar.py scout [--week YYYY-Www] [--force] [--dry-run] [--out DIR] [--json]

Once a week, cost-capped (`judgments/policy.py`, "scout"): candidates come from what the owner
already reads and saves over the last `SCOUT_WINDOW_DAYS` — the URL of every worth/strong item in
`00_Memory/radar/state.jsonl` (scan's own record; no extra fetch) and every link in the owner's own
clips (`clips.py`; a clip's body, not just its title) — plus one Kagi *news* query per interest
aimed at a launch ("new API", "new service launch", "open-source release" or "new dataset",
rotated by ISO week so the same interest is not asked the same way every time), under the same
ledger and weekly budget as `discover.py` and `gaps.py`. A candidate the vault already knows (a
note's `source`, a name in `Index.md`, or a feed Reader already carries) is dropped before it
costs a judgment; so is a well-known content host (x.com, youtube.com, reddit.com, arxiv.org, …)
— it carries other people's sources, it is not one itself.

The survivors are ranked by how many independent things mentioned them (a feed item, a clip, a
Kagi hit — several is stronger evidence than one), and the top `SCOUT_MAX_JUDGED` are judged once
each: `kind` (feed/api/service/tool/dataset/community/other), `value` against everything in the
owner's interests, and whether he could act on it this week without more research. The
`SCOUT_TOP_N` strongest by value become the week's capture `01_Capture/Radar-Scout-YYYY-Www.md`
(`via: radar`, written once — like `weekly`, through the same `reports.write_weekly`); a
`feed`-kind survivor is also handed to `discover.discover` as a seed, so it goes through the same
fetch/parse/judge path and lands in the same OPML Reader-import flow. `--dry-run` prints the
capture instead of writing it, for a check against a real vault that leaves no mark; Kagi and the
judgment backend are still called, at their usual cost.

What leaves the machine: one query per interest to Kagi (a recent small-web/news search, not the
candidates themselves); candidate urls, titles and a short "seen in" list of titles to the
judgment backend, alongside interest names and glosses. Reader is only read (which feeds are
already subscribed); nothing is ever promoted or saved there.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import clips as clips_mod
import discover as discover_mod
import interests as interests_mod
import judge
import kagi
import reader
import reports
from interests import Interest
from judgments import policy
from judgments import questions as Q
from judgments.state import in_chunks
from judgments.urls import _canonical
from vault_utils import profile_value

LAUNCH_ANGLES = ("new API", "new service launch", "open-source release", "new dataset")
CANDIDATES_PER_REQUEST = 8

# Hosts that carry other people's sources rather than being one themselves: a candidate here is
# never "a new source", however often it is mentioned. [earned: 2026-09-24 design]
NOT_A_SOURCE_HOST = {
    "x.com", "twitter.com", "mobile.twitter.com", "youtube.com", "youtu.be", "m.youtube.com",
    "music.youtube.com", "reddit.com", "old.reddit.com", "news.ycombinator.com", "arxiv.org",
    "export.arxiv.org", "medium.com", "readwise.io", "read.readwise.io", "hnrss.org", "kagi.com",
    "openrouter.ai", "google.com", "wikipedia.org", "en.wikipedia.org", "github.com",
}
_GH_REPO = re.compile(r"^github\.com/([^/]+)/([^/]+)")
_GH_NOT_REPO = {"orgs", "topics", "sponsors", "marketplace", "settings", "about", "features", "trending", "search"}
_URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+")
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^\s)]+)\)")
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
# An invite-shortener domain is not itself the source: the code after it is. [earned: 2026-09-24
# live run against the real vault — a bare "discord.gg" candidate lost which server it was]
_INVITE_HOSTS = {"discord.gg", "t.me", "chat.whatsapp.com"}


def _is_public_site(domain: str) -> bool:
    """False for a dev/local address that leaked into a clip or article body — `localhost:3000`,
    a bare IP, a host with no TLD at all — none of which is a source anyone else could visit.
    [earned: 2026-09-24 live run — a tutorial screenshot's `localhost:3000` link surfaced as the
    week's top candidate]"""
    host = domain.split(":", 1)[0]
    return bool(host) and host != "localhost" and "." in host and not _IPV4.match(host)


@dataclass
class Candidate:
    key: str  # "github.com/owner/repo", or a bare domain
    urls: set[str] = field(default_factory=set)
    feed_hits: int = 0
    feeds: set[str] = field(default_factory=set)
    clip_hits: int = 0
    clip_paths: set[str] = field(default_factory=set)
    kagi_hits: int = 0
    examples: list[str] = field(default_factory=list)

    def mentions(self) -> int:
        return self.feed_hits + self.clip_hits + self.kagi_hits

    def link(self) -> str:
        return f"https://{self.key}"

    def state(self) -> dict[str, str]:
        return {"url": self.link(), "seen_in": " | ".join(self.examples[:5])}


def candidate_key(url: str) -> str | None:
    """A GitHub repo (`owner/repo`, from any URL under it) or else the bare domain — the unit a
    scout candidate is judged at. None for a well-known content host."""
    c = _canonical(url)
    if m := _GH_REPO.match(c):
        owner, repo = m.group(1), m.group(2).removesuffix(".git")
        return None if owner in _GH_NOT_REPO else f"github.com/{owner}/{repo}"
    domain = c.split("/", 1)[0]
    if not domain or domain in NOT_A_SOURCE_HOST or not _is_public_site(domain):
        return None
    if domain in _INVITE_HOSTS:
        rest = c[len(domain):].lstrip("/")
        code = rest.split("/", 1)[0]
        return f"{domain}/{code}" if code else None  # the bare shortener names nothing on its own
    return domain


def _links_in(text: str) -> set[str]:
    if not text:
        return set()
    return set(_MD_LINK_RE.findall(text)) | set(_URL_RE.findall(text))


def _add(cands: dict[str, Candidate], url: str, title: str, feed: str | None = None,
        clip: str | None = None, kagi_hit: bool = False) -> None:
    key = candidate_key(url)
    if key is None:
        return
    c = cands.setdefault(key, Candidate(key=key))
    c.urls.add(url)
    if title and title not in c.examples and len(c.examples) < 5:
        c.examples.append(title)
    if feed is not None:
        c.feed_hits += 1
        c.feeds.add(feed)
    if clip is not None:
        c.clip_hits += 1
        c.clip_paths.add(clip)
    if kagi_hit:
        c.kagi_hits += 1


def _from_state(cands: dict[str, Candidate], rows: list[dict], since: str) -> None:
    """Every worth/strong item's own URL, over the last SCOUT_WINDOW_DAYS (`arrived`, same rule
    trend/emerging_terms use)."""
    for r in rows:
        if reports.arrived(r) < since or not r.get("url"):
            continue
        worth, _ = reports.bands(r)
        if worth:
            _add(cands, r["url"], r.get("title") or "", feed=r.get("feed") or "?")


def _from_clips(cands: dict[str, Candidate], the_clips: list[clips_mod.Clip]) -> None:
    """A clip's own source, and every link its body carries (an article's citations, a session
    note's `sources:`, a video's description) — not just its title."""
    for c in the_clips:
        urls = ({c.source} if c.source else set()) | _links_in(c.body)
        for url in sorted(urls):
            _add(cands, url, c.title, clip=c.path)


def _from_kagi(cands: dict[str, Candidate], now: datetime, interests: list[Interest],
              ledger: kagi.Ledger) -> tuple[int, list[str]]:
    """One `kagi.news` query per interest with queries or a gloss, angled at a launch; the angle
    rotates by ISO week so the same interest is not asked the same way every time."""
    week = reports.week_of(now.date().isoformat())
    angle = LAUNCH_ANGLES[int(week.split("-W")[1]) % len(LAUNCH_ANGLES)]
    searched, notes = 0, []
    for it in interests:
        if not it.queries and not it.gloss:
            continue  # nothing to search by but a task title [same rule as gaps.py]
        q = f"{it.queries[0] if it.queries else it.name} {angle}"
        try:
            found = kagi.news(q, ledger, now)
        except kagi.NoKey:
            notes.append("KAGI_API_KEY is not set; nothing searched")
            return searched, notes
        except kagi.OverBudget as e:
            notes.append(str(e))
            break
        except kagi.KagiError as e:
            notes.append(f"kagi: {e}")
            continue
        searched += 1
        for r in found:
            _add(cands, r["url"], r["title"], kagi_hit=True)
    return searched, notes


def _novel(cands: dict[str, Candidate], known_urls: dict[str, str], index_text: str,
          subscribed: set[str]) -> dict[str, Candidate]:
    """Drop what the vault already knows: an exact source URL, a subscribed feed's host, or a
    name already in `Index.md`."""
    known_hosts = {u.split("/", 1)[0] for u in known_urls}
    out = {}
    for key, c in cands.items():
        if any(_canonical(u) in known_urls for u in c.urls):
            continue
        if key in known_hosts or key in subscribed:
            continue
        label = key.rsplit("/", 1)[-1] if key.startswith("github.com/") else key
        if label and label.casefold() in index_text:
            continue
        out[key] = c
    return out


def _judge_candidates(vault: Path, cands: list[Candidate], interests: list[Interest],
                      usage: dict[str, Any]) -> dict[int, dict]:
    interest_state = {it.id: it.state() for it in interests}

    def ask(chunk: list[Candidate], offset: int) -> dict[int, dict]:
        keys = [f"c{offset + j}" for j in range(len(chunk))]
        state = {"interests": interest_state, "candidates": {k: c.state() for k, c in zip(keys, chunk, strict=True)}}
        questions: dict[str, judge.Question] = {}
        for k in keys:
            questions[f"kind_{k}"] = Q.scout_kind(k)
            questions[f"value_{k}"] = Q.scout_value(k)
            questions[f"action_{k}"] = Q.scout_actionable(k)
        try:
            answers, u = judge.judge(vault, state, questions)
        except judge.StateTooLarge:
            raise
        except judge.JudgmentFailed as e:
            usage["errors"].append(str(e)[:200])
            return {}
        usage["requests"] += u.requests
        usage["usd"] += u.usd
        out = {}
        for j, k in enumerate(keys):
            value = answers.get(f"value_{k}")
            if value is None or value.p is None:
                continue
            kind, action = answers.get(f"kind_{k}"), answers.get(f"action_{k}")
            out[offset + j] = {"kind": kind.top if kind else None, "value": round(value.p, 4),
                               "actionable": round(action.p, 4) if action and action.p is not None else None}
        return out

    return in_chunks(cands, CANDIDATES_PER_REQUEST, ask)


def render_scout(week: str, picks: list[dict], now: datetime) -> str:
    lines = [
        "---",
        f"description: Radar scout week {week} — {len(picks)} new source(s) worth knowing about",
        f"source: candidates mined from feed items, your own clips and Kagi launch queries, ISO week {week}",
        f"created: {now.date().isoformat()}",
        "kind: radar-scout",
        "via: radar",
        "status: draft",
        "tags:",
        "  - radar",
        "---",
        "",
        f"# Radar scout {week}",
        "",
        f"{len(picks)} new source(s) this week, ranked by value against your interests.",
        "",
    ]
    if not picks:
        lines += ["Nothing new and valuable enough this week.", ""]
    for n, r in enumerate(picks, 1):
        evidence = []
        if r["feed_hits"]:
            evidence.append(f"{r['feed_hits']} feed item(s) ({len(r['feeds'])} feed(s))")
        if r["clip_hits"]:
            evidence.append(f"{r['clip_hits']} of your own clips")
        if r["kagi_hits"]:
            evidence.append(f"{r['kagi_hits']} Kagi hit(s)")
        example = f' — e.g. "{r["examples"][0]}"' if r["examples"] else ""
        actionable = "actionable now" if (r["actionable"] or 0) >= 0.5 else "needs more research first"
        lines += [
            f"### {n}. [{r['key']}]({r['url']})",
            "",
            f"**{r['kind'] or '?'}** · value p={r['value']:.2f} · {actionable}",
            "",
            f"{', '.join(evidence) or 'seen once'}{example}",
            "",
        ]
    lines += ["## Next actions", "",
              "- [ ] Distill anything worth keeping (a new tool or dataset probably deserves its own note); "
              "delete this capture after.",
              "- [ ] A `feed` candidate above joined `radar.py discover`'s OPML — import it in Reader after "
              "reading why.",
              ""]
    return "\n".join(lines)


def scout(vault: Path, out: Path, now: datetime, week: str | None = None, force: bool = False,
         dry_run: bool = False) -> dict[str, Any]:
    from radar import read_jsonl, vault_sources  # lazy: radar imports this module (like gaps.py)

    wk = week or reports.week_of(now.date().isoformat())
    written = out / "scout.jsonl"
    already = written.is_file() and any(
        json.loads(ln).get("week") == wk for ln in written.read_text(encoding="utf-8").splitlines() if ln.strip())
    if (vault / "01_Capture" / f"Radar-Scout-{wk}.md").exists() or already:
        if not force and not dry_run:
            return {"status": "exists", "week": wk, "detail": f"the scout capture for {wk} was already written"}

    interests = interests_mod.load(vault)
    if not interests:
        return {"status": "no-interests", "detail": "no interests: set `interests_note` in Config/toolkit/radar.md"}
    reason = judge.unavailable_reason(vault)
    if reason:
        return {"status": "SKIPPED", "detail": f"judgment backend unavailable ({reason}); nothing sent"}

    since_dt = now - timedelta(days=policy.SCOUT_WINDOW_DAYS)
    since = since_dt.date().isoformat()
    rows = read_jsonl(out / "state.jsonl")
    the_clips = clips_mod.load(vault, since_dt.date())

    cands: dict[str, Candidate] = {}
    _from_state(cands, rows, since)
    _from_clips(cands, the_clips)

    ledger = kagi.Ledger(out / "kagi-ledger.jsonl",
                         float(profile_value(vault, "kagi_weekly_budget_usd", kagi.DEFAULT_WEEKLY_BUDGET_USD)))
    spent_before = ledger.spent_this_week(now)
    searched, notes = _from_kagi(cands, now, interests, ledger)

    # Never 01_Capture: an un-distilled clip's own `source:` is exactly the raw material scout
    # mines for candidates, not something the vault already knows — a clip in this week's own
    # inbox must not make its own primary link look pre-existing. [earned: 2026-09-24 eval — a
    # clip's own source made vault_sources() call it already known the moment it landed]
    known_urls = {u: p for u, p in vault_sources(vault).items() if not p.startswith("01_Capture/")}
    index_path = vault / "Index.md"
    index_text = index_path.read_text(encoding="utf-8", errors="replace").casefold() if index_path.is_file() else ""
    try:
        subscribed = discover_mod.subscribed_sites(since_dt)
    except reader.NoToken:
        subscribed = set()
        notes.append("READWISE_TOKEN is not set; cannot tell already-subscribed feeds")
    except reader.ReaderError as e:
        subscribed = set()
        notes.append(f"reader: {e}")

    survivors = _novel(cands, known_urls, index_text, subscribed)
    ranked = sorted(survivors.values(), key=lambda c: -c.mentions())[:policy.SCOUT_MAX_JUDGED]

    usage: dict[str, Any] = {"requests": 0, "usd": 0.0, "errors": []}
    judged = _judge_candidates(vault, ranked, interests, usage) if ranked else {}
    t = policy.thresholds(judge.load_config(vault)["backend"])
    results = []
    for n, c in enumerate(ranked):
        if n not in judged:
            continue
        j = judged[n]
        results.append({
            "key": c.key, "url": c.link(), "kind": j["kind"], "value": j["value"], "actionable": j["actionable"],
            "feed_hits": c.feed_hits, "feeds": sorted(c.feeds), "clip_hits": c.clip_hits,
            "kagi_hits": c.kagi_hits, "examples": c.examples, "proposed": j["value"] >= t["T_SCOUT_VALUE"],
        })
    results.sort(key=lambda r: -r["value"])
    picks = [r for r in results if r["proposed"]][:policy.SCOUT_TOP_N]

    feed_seeds = [r["url"] for r in picks if r["kind"] == "feed"]
    discover_result = discover_mod.discover(vault, out, now, None, feed_seeds, queries_per_interest=0) if feed_seeds else None

    text = render_scout(wk, picks, now)
    result: dict[str, Any] = {
        "status": "ok", "week": wk, "candidates": len(cands), "novel": len(survivors),
        "judged": len(results), "proposed": len(picks), "kagi_searched": searched,
        "kagi_usd": round(ledger.spent_this_week(now) - spent_before, 4),
        "judgment": {"requests": usage["requests"], "usd": round(usage["usd"], 5), "errors": usage["errors"][:3]},
        "notes": notes,
    }
    if discover_result is not None:
        result["feeds_seeded"] = len(feed_seeds)
        result["discover"] = {k: discover_result.get(k) for k in ("status", "proposed", "opml") if k in discover_result}
    if dry_run:
        return {**result, "dry_run_capture": text}
    try:
        path = reports.write_weekly(vault, wk, text, force, written, prefix="Radar-Scout")
    except FileExistsError as e:
        return {**result, "status": "exists", "detail": str(e)}
    result["capture"] = path.relative_to(vault).as_posix()
    return result
