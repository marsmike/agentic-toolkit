#!/usr/bin/env python3
"""Build Atlas.html: what the vault knows, and how knowledge comes into it, in one page.

    uv run scripts/atlas_build.py [--dry-run] [--json] [--today YYYY-MM-DD]

Deterministic, no model call, no network. The page embeds its data as JSON and filters in the
browser by one range (today, 7 / 30 days, 12 weeks), so "today" is the viewer's today even when the
file was built hours earlier. Two halves:

    inflow     every item the pipeline imported in the window (`imports_log.resolved`, the ledger
               behind Imports.md): where it came from (the owner's own save, a radar feed pick,
               sensor news, a newsletter), what became of it (a new note, an enriched one, dropped,
               waiting, …), how long it took from ingest to retirement, and the domains of the
               notes it became; the radar's funnel per day (`radar_ledger`: judged, worth reading,
               strong, promoted) and per interest (worth reading or better, strong, promoted; strong
               per week), with the strongest items; and the routines' runs, the pipeline's from the
               ledger and the Signal Radar's and the Mac sync's from their commits
    landscape  every active note by domain (the notes and links `map_build` reads): how many, how
               many each day of the window added, the most-linked and the newest notes, the kinds,
               and how often notes in one domain link to notes in another

Note text reaches the page only as JSON and is rendered with textContent, never as HTML: a clip's
title is someone else's words. [earned: 2026-10-01, owner's goal — "visualized the topics and
process very good": Now.md, the Dashboard and the run report each showed one slice, none the whole
vault or the way in]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import imports_log
import radar_ledger
from map_build import (
    DOMAIN_TAG,
    MIN_NOTES,
    WIKILINK,
    MapConfig,
    Note,
    _resolver,
    _tags,
    default_title,
    kind_families,
    kind_family,
    read_config,
    resolve_links,
)
from now_build import _signal_artifact_url
from vault_utils import (
    atomic_write,
    contained,
    discover_notes,
    distilled_when,
    git_output,
    one_line,
    profile_value,
    read_frontmatter,
    read_jsonl,
    require_vault,
    title_of,
    utc_timestamp,
)

OUT = "Atlas.html"
TEMPLATE = Path(__file__).resolve().parent / "atlas_template.html"
WINDOW_DAYS = imports_log.WINDOW_DAYS
HUBS = 6
NEWEST = 6
KINDS = 6
TITLE_CHARS = 120
PROMOTED = Path("00_Memory") / "radar" / "promoted.jsonl"
TOPICS = 40
DOMAIN_TOPICS = 8
# Tags that say how a note arrived or where it is filed, not what it is about: they are left out of
# the topics. [earned: 2026-10-01 — `readwise`, `radar` and the week tags led the vault's tag count]
PROCESS_TAG = re.compile(r"^(readwise|radar|via|source|status|kind|type|project|portfolio|email|service|vehicle)(/|$)"
                         r"|^w\d{2}-\d{4}$|^(wiki|area|book|bookmark|tools|research|clip|newsletter|capture|inbox|"
                         r"tweet|article|video|paper|repo|podcast|moc|index|draft|todo)$")
DESCRIPTION_MAX = 250  # distill_check's soft limit: a description is the note's one line in Index.md
ROUTINES = Path("cloud") / "routines.json"  # in the toolkit checkout that holds this script
ROLE = {"pipeline.prompt.md": "pipeline", "signal.prompt.md": "radar", "watchdog.prompt.md": "watchdog"}
RADAR_SUBJECT = re.compile(r"^signal radar \d{4}-\d{2}-\d{2} \d{2}:\d{2}: (.+)$")
SYNC_SUBJECT = re.compile(r"^vault: hand edits .*\(sync\)$")


def _utc(iso: str) -> str:
    """Any ISO time (git's `%cI` carries the committer's offset) as UTC with a `Z`."""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ""


def _minutes(start: str, end: str) -> int | None:
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    m = round((b - a).total_seconds() / 60)
    return m if 0 <= m <= 60 * 24 * 90 else None


def source_key(url: object) -> str:
    """A source address as the vault's notes and the ledger may both write it: no scheme, no www.,
    no trailing slash, and no query but the parameters that name the page (`v`, `id`)."""
    parts = urlsplit(str(url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""
    keep = "&".join(q for q in parts.query.split("&") if q.split("=", 1)[0] in ("v", "id"))
    return (parts.hostname.removeprefix("www.") + parts.path.rstrip("/") + ("?" + keep if keep else "")).lower()


def collect(vault: Path) -> tuple[list[Note], dict[str, str], dict[str, str], dict[str, list[str]], dict[str, list[str]],
                                  dict[str, tuple[int, bool]]]:
    """Every active note (as map_build reads it), with its distilled day, title and topic tags,
    which notes cite each source address (`source:` and `sources:`), and each note's description
    length and whether it names a source (what the quality panel reads)."""
    notes: list[Note] = []
    meta: dict[str, tuple[int, bool]] = {}
    days: dict[str, str] = {}
    titles: dict[str, str] = {}
    topics: dict[str, list[str]] = {}
    cited: dict[str, list[str]] = defaultdict(list)
    for path in discover_notes(vault):
        fm, body = read_frontmatter(path)
        rel = path.relative_to(vault).with_suffix("").as_posix()
        sources = fm.get("sources") if isinstance(fm.get("sources"), list) else []
        for key in {source_key(s) for s in [fm.get("source"), *sources]} - {""}:
            cited[key].append(rel)
        kind = fm.get("kind")
        notes.append(Note(rel=rel, name=path.stem,
                          kind=str(kind).strip().casefold() if isinstance(kind, str) and kind.strip() else "",
                          description="", when="",
                          domains=sorted({m.group(1).lower() for t in _tags(fm) if (m := DOMAIN_TAG.match(t))}),
                          links={t.strip() for t in WIKILINK.findall(body)}))
        days[rel] = distilled_when(fm)[:10]
        topics[rel] = sorted({t for raw in _tags(fm) if not DOMAIN_TAG.match(raw)
                              and (t := raw.lstrip("#").strip().lower()) and not PROCESS_TAG.match(t)})
        titles[rel] = one_line(title_of(fm, body, path.stem), TITLE_CHARS)
        meta[rel] = (len(" ".join(str(fm.get("description") or "").split())),
                     bool(str(fm.get("source") or "").strip()) and str(fm.get("source")).strip().lower() != "unknown")
    return notes, days, titles, topics, cited, meta


def landscape(since: str, notes: list[Note], days: dict[str, str], titles: dict[str, str],
              topics: dict[str, list[str]], configs: dict[str, MapConfig],
              meta: dict[str, tuple[int, bool]] | None = None) -> dict:
    """Domains with their notes, additions per day since `since`, hubs, newest, kinds and topics,
    and the links between domains. A note in several domains counts in each; a link weighs one in
    all, shared evenly across the domain pairs it joins (diagonal: links inside one domain)."""
    links = resolve_links(notes)
    inbound = Counter(t for targets in links.values() for t in targets)
    members: dict[str, list[Note]] = defaultdict(list)
    for n in notes:
        for d in n.domains:
            members[d].append(n)
    domains = sorted((d for d in members if len(members[d]) >= MIN_NOTES or d in configs),
                     key=lambda d: (-len(members[d]), d))
    index = {d: i for i, d in enumerate(domains)}
    families = {d: kind_families({d: configs[d]} if d in configs else {}) for d in domains}
    by_rel = {n.rel: n for n in notes}
    matrix = [[0.0] * len(domains) for _ in domains]
    for src, targets in links.items():
        here = [index[d] for d in by_rel[src].domains if d in index]
        for t in targets:
            pairs = [(a, b) for a in here for b in (index[d] for d in by_rel[t].domains if d in index)]
            for a, b in pairs:
                matrix[a][b] += 1 / len(pairs)
    out = []
    for d in domains:
        group = members[d]
        added = Counter(days[n.rel] for n in group if days[n.rel] >= since)
        hubs = sorted((n for n in group if inbound[n.rel]), key=lambda n: (-inbound[n.rel], n.name.casefold()))[:HUBS]
        newest = sorted((n for n in group if days[n.rel]), key=lambda n: (days[n.rel], n.name.casefold()), reverse=True)[:NEWEST]
        out.append({
            "id": d, "title": (configs.get(d) or MapConfig()).title or default_title(d), "notes": len(group),
            "added": dict(sorted(added.items())),
            "hubs": [{"t": titles[n.rel], "p": n.rel, "in": inbound[n.rel]} for n in hubs],
            "newest": [{"t": titles[n.rel], "p": n.rel, "d": days[n.rel]} for n in newest],
            "kinds": [[k, c] for k, c in Counter(kind_family(n.kind, n.rel, families[d]) for n in group).most_common(KINDS)],
            "topics": [[t, c] for t, c in Counter(t for n in group for t in topics[n.rel]).most_common(DOMAIN_TOPICS)],
        })
    linked = {n.rel for n in notes if links.get(n.rel) or inbound[n.rel]}
    tag_total = Counter(t for ts in topics.values() for t in ts)
    tag_days: dict[str, Counter] = defaultdict(Counter)
    for rel, ts in topics.items():
        if days[rel] >= since:
            for t in ts:
                tag_days[t][days[rel]] += 1
    # The tags with the most notes, and every tag the window added to at least twice: what the page
    # ranks by any range ("on the move") is among these.
    keep = {t for t, _ in tag_total.most_common(TOPICS)} | {t for t, c in tag_days.items() if sum(c.values()) >= 2}
    tags = [[t, tag_total[t], dict(sorted(tag_days[t].items()))] for t in sorted(keep, key=lambda t: (-tag_total[t], t))]
    # One row per note distilled in the window: [path, day, title, links in, links out, description
    # characters, names a source]. [earned: 2026-10-02 — the page showed how much came in, never how
    # well it was filed; 8 of 65 new notes had no inbound link and nothing on the page said so]
    meta = meta or {}
    quality = [[n.rel, days[n.rel], titles[n.rel], inbound[n.rel], len(links.get(n.rel) or ()),
                *(meta.get(n.rel) or (0, False))]
               for n in sorted(notes, key=lambda n: (days[n.rel], n.rel)) if days[n.rel] and days[n.rel] >= since]
    return {"domains": out, "tags": tags, "matrix": [[round(v, 1) for v in row] for row in matrix], "quality": quality,
            "totals": {"notes": len(notes), "untagged": sum(1 for n in notes if not n.domains),
                       "links": sum(len(t) for t in links.values()), "unlinked": len(notes) - len(linked)},
            "note_domains": {n.rel: [d for d in n.domains if d in index] for n in notes}}


def _lane(item: dict, promoted: dict[str, dict]) -> str:
    """Where an imported item came from: the owner's own save, a newsletter, or the radar (a
    sensor's news item, a gap search, or a pick from the feeds the radar judges)."""
    via = str(item.get("via") or "")
    if via == "clip":
        return "save"
    if via == "newsletter":
        return "newsletter"
    if via == "radar":
        row = promoted.get(str(item.get("doc_id") or ""), {})
        return {"sensors": "sensor", "gaps": "gap"}.get(str(row.get("via") or ""), "feed")
    return "other"


def _outcome(fate: dict) -> str:
    status = fate.get("status", "")
    if status != "distilled":
        return status or "unknown"
    kind = str(fate.get("kind") or "")
    if kind in ("new", "enriched"):
        return kind
    # A legacy item (retired before the ledger carried its kind) says it in its manifest line.
    return "enriched" if re.search(r"\b(enrich|L[123]\b)", str(fate.get("detail") or ""), re.I) else "new"


def inflow(vault: Path, since: str, runs: list[dict], note_domains: dict[str, list[str]], resolve,
           cited: dict[str, list[str]]) -> list[dict]:
    """One row per imported item in the window, oldest first. An item's notes resolve the way links
    do (by path, then by file name); an item whose fate names no note (a manifest line from before
    the ledger carried notes says what happened in prose) takes the notes that cite its source.
    [earned: 2026-10-01 — 151 of 342 distilled items named no note, and half the flow had no domain]"""
    promoted = {str(r.get("id")): r for r in read_jsonl(vault / PROMOTED) if r.get("id")}
    rows = []
    for r in runs:
        if r["run"][:10] < since:
            continue
        for it in r["items"]:
            f = it["fate"]
            notes = list(dict.fromkeys(rel for raw in f.get("notes") or []
                                       if (rel := resolve(str(raw).removesuffix(".md"))) and rel in note_domains))
            if not notes and f.get("status") == "distilled":
                notes = [n for n in cited.get(source_key(it.get("source")), []) if n in note_domains]
            ingested = str(it.get("ingested_at") or r.get("at") or "")
            done = str(f.get("retired_at") or "")
            rows.append({
                "at": _utc(ingested) or r.get("at", ""),
                "t": one_line(it.get("title") or it.get("capture") or it.get("doc_id") or "", TITLE_CHARS),
                "src": str(it.get("source") or "") if str(it.get("source") or "").startswith("http") else "",
                "lane": _lane(it, promoted), "type": str(it.get("category") or ""),
                "out": _outcome(f), "notes": notes[:3],
                "dom": sorted({d for n in notes for d in note_domains[n]}),
                **({"min": m} if (m := _minutes(ingested, done)) is not None else {}),
            })
    return sorted(rows, key=lambda x: x["at"])


def routine_runs(vault: Path, since: str, runs: list[dict]) -> list[dict]:
    """The window's runs: the pipeline's from the ledger (with its counts), the Signal Radar's and
    the Mac sync's from their commits (a sync with nothing to commit leaves none)."""
    out = [{"r": "pipeline", "at": r["at"], "n": r.get("distilled", 0), "dropped": r.get("dropped", 0),
            "failed": r.get("failed", 0), "s": one_line(r.get("summary") or "", 240)}
           for r in runs if r["run"][:10] >= since]
    for line in git_output(vault, "log", f"--since={since}T00:00:00Z", "--format=%cI%x09%s").splitlines():
        when, _, subject = line.partition("\t")
        if m := RADAR_SUBJECT.match(subject):
            out.append({"r": "radar", "at": _utc(when), "s": one_line(m.group(1), 240)})
        elif SYNC_SUBJECT.match(subject):
            out.append({"r": "sync", "at": _utc(when)})
    return sorted((r for r in out if r["at"]), key=lambda r: r["at"])


def routines_file(script: Path | None = None) -> Path | None:
    """`cloud/routines.json` in the toolkit checkout holding this script, looked for upwards: never
    a fixed depth, which a copy of the script elsewhere does not have. [earned: 2026-10-01 — CI's
    pipeline_run eval runs the generators from /tmp/<dir>/, where `parents[3]` raised IndexError]"""
    for parent in (script or Path(__file__)).resolve().parents:
        if (parent / ROUTINES).is_file():
            return parent / ROUTINES
    return None


def routines() -> list[dict]:
    """The cloud routines as the toolkit's `cloud/routines.json` snapshot names them: role (by the
    prompt file each one runs), name, schedule (cron, UTC) and model. Without the snapshot (scripts
    copied out of the repo), none: the page then draws the machine without its schedule."""
    path = routines_file()
    if path is None:
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("routines") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [{"role": ROLE.get(Path(str(r.get("prompt_file") or "")).name, "other"), "name": str(r.get("name") or ""),
             "cron": str(r.get("cron_expression") or ""), "model": str(r.get("model") or "")}
            for r in rows if isinstance(r, dict)]


TOP_RECENT_DAYS, TOP_RECENT, TOP_OLDER = 7, 10, 3


def radar_view(radar: dict, today: date) -> dict:
    """What each interest brought, by day so the page's range filters it, and the strongest items.
    `interests`: id → name, `days` {day: [worth reading or better, strong, promoted]}, `weeks`
    (strong items per ISO week, counted like `days`: once for every interest an item is strong for;
    the ledger's last 8 weeks, labels in `weeks`) and `rising`; a retired interest is left out. `top`: the strongest items, the 10 best
    a day for the last week and the 3 best a day before it (the page shows its range's 10 best),
    with a link only to a web address. [earned: 2026-10-01 — the Dashboard's "Strong per week" and
    "Top feed items" had no counterpart here]"""
    items = radar.get("items") or []
    per: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    strong_weeks: dict[str, Counter] = defaultdict(Counter)
    for it in items:
        y, w, _ = date.fromisoformat(it["day"]).isocalendar()
        for iid in set(it["worth"]) | set(it["strong"]):
            if iid == radar_ledger.RETIRED_ID:
                continue
            c = per[iid][it["day"]]
            c[0] += 1
            if iid in it["strong"]:
                c[1] += 1
                c[2] += bool(it["promoted"])
                strong_weeks[iid][f"{y}-W{w:02d}"] += 1
    labels = list(radar.get("weeks") or {})
    names = {iid: str(v.get("name") or iid) for iid, v in (radar.get("interests") or {}).items()}
    rising = set(radar.get("rising") or [])
    interests = {iid: {"name": names.get(iid, iid), "days": dict(sorted(days.items())),
                       "weeks": [strong_weeks[iid].get(w, 0) for w in labels], "rising": iid in rising}
                 for iid, days in per.items()}
    recent = (today - timedelta(days=TOP_RECENT_DAYS - 1)).isoformat()
    by_day: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        if it["strong"]:
            by_day[it["day"]].append(it)
    top = []
    for day, rows in sorted(by_day.items()):
        for it in sorted(rows, key=lambda r: -r["p"])[:TOP_RECENT if day >= recent else TOP_OLDER]:
            url = it["url"] if urlsplit(it["url"]).scheme in ("http", "https") else ""
            top.append({"d": day, "t": it["title"][:140], "u": url, "f": it["feed"][:60],
                        "i": it["top"] if it["top"] in it["strong"] else it["strong"][0], "p": it["p"],
                        "s": "promoted" if it["promoted"] else "vault" if it["in_vault"] else ""})
    return {"weeks": labels, "interests": interests, "top": top}


def build(vault: Path, today: date) -> dict:
    since = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    notes, days, titles, topics, cited, meta = collect(vault)
    land = landscape(since, notes, days, titles, topics, read_config(vault), meta)
    runs = imports_log.resolved(vault)
    radar = radar_ledger.load(vault, since, today)
    return {
        "vault": vault.name, "built": utc_timestamp(), "today": today.isoformat(), "window": WINDOW_DAYS,
        "links": {"report": str(profile_value(vault, "report_artifact_url") or ""), "signal": _signal_artifact_url(vault),
                  "atlas": str(profile_value(vault, "atlas_artifact_url") or "")},
        "inbox": sum(1 for p in contained((vault / "01_Capture").glob("*.md"), vault) if p.is_file()),
        "totals": land["totals"], "domains": land["domains"], "matrix": land["matrix"], "tags": land["tags"],
        "quality": land["quality"], "description_max": DESCRIPTION_MAX,
        "inflow": inflow(vault, since, runs, land["note_domains"], _resolver(notes), cited),
        "funnel": radar.get("days", {}),
        "radar": radar_view(radar, today),
        "runs": routine_runs(vault, since, runs),
        "routines": routines(),
    }


def render(data: dict) -> str:
    # No raw `<` in the payload, so no title can end (or open) a script element.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true", help="print the embedded data instead of a summary")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    vault = require_vault()
    today = date.fromisoformat(args.today) if args.today else date.today()
    data = build(vault, today)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    if not args.dry_run:
        atomic_write(vault / OUT, render(data))
    if not args.json:
        print(f"{OUT}: {data['totals']['notes']} notes in {len(data['domains'])} domains, "
              f"{len(data['inflow'])} items and {len(data['runs'])} runs in {WINDOW_DAYS} days"
              + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
