"""Signal: what is taking off, not only what is relevant. Every stream the radar has becomes
mentions of named things (`entities.py`), and each thing gets a signal strength from how many
independent sources carry it, how fast it is growing, how much engagement it draws, how relevant
the judge found it and whether the owner's own vault already has it.

Streams, all read from files, none fetched here except the optional web check:
- feed items the scan judged (`state.jsonl`), family by origin: reddit, arxiv, github or feed;
- the sensors' day files (`sensors/YYYY-MM-DD.json`, `sensors.py`): Hacker News, Hugging Face,
  GitHub, Reddit with scores, plain RSS; each item counts once, on the day it was first seen;
- the vault itself (`vault_pulse.py`): notes and clips, and which of their tags are rising;
- the owner's knowledge graph (`vault_graph.py`, gaiafield): the notes of any date a thing is
  anchored in, how large their linked neighbourhood is, the hubs it connects to, and the hubs the
  week's new notes are thickening;
- the web check, once a day for the few new names with the least corroboration (`CHECKS_PER_DAY`,
  ledger and weekly budget as everywhere): Tavily's week of the web through the `tvly` CLI, or Kagi
  news when Tavily is not available; `signal-tavily.jsonl` / `signal-kagi.jsonl` remember what was
  asked, and both count while their answers are a week old.

Writes `00_Memory/radar/signal.json` (the data), `Signal-Radar-scope.svg` and `Signal-Radar-momentum.svg` (what the note embeds), `Signal-Radar.html` (the page the routine
publishes as an artifact and the vault keeps) and `Signal-Radar.md` (the same, as a note), all in
the radar dir. Nothing else in the vault changes.

What leaves the machine: with `--check`, up to CHECKS_PER_DAY entity names a day, to Tavily (or Kagi).
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import entities
import interests as interests_mod
import kagi
import reports
import signal_render
import tavily
import vault_graph
import vault_pulse
from judgments.urls import _canonical
from vault_utils import atomic_write

RECENT_DAYS = 3          # "now": today and the two days before
BASELINE_DAYS = 14       # what "now" is compared with, the days before RECENT_DAYS
WINDOW_DAYS = 7          # breadth and engagement look at the last week
EARLY_HOURS = 72
MAX_BLIPS = 60
MAX_SECTORS = 6
MIN_RELEVANCE = 0.35     # a judged thing below this for every interest is not the owner's business
BLIND_SPOT_STRENGTH = 30
CHECKS_PER_DAY = 6
# Weights of the strength parts; they sum to 1.
WEIGHTS = {"breadth": 0.25, "velocity": 0.20, "engagement": 0.20, "relevance": 0.10, "volume": 0.15, "vault": 0.10}
STAGE_HOT = 70
FAMILY_LABELS = {"hn": "Hacker News", "hf": "Hugging Face", "github": "GitHub", "reddit": "Reddit", "rss": "Blogs & news",
                 "arxiv": "arXiv", "feed": "Reader feeds", "kagi": "Kagi news", "tavily": "Tavily web", "kagi_news": "Kagi News",
                 "vault": "Your vault"}


@dataclass
class Entity:
    key: str
    names: Counter = field(default_factory=Counter)
    mentions: list[dict] = field(default_factory=list)


def _day(stamp: Any) -> str | None:
    s = str(stamp or "")[:10]
    try:
        date.fromisoformat(s)
    except ValueError:
        return None
    return s


def feed_family(row: dict) -> str:
    host = (row.get("url") or "").split("/")[2].removeprefix("www.") if "://" in (row.get("url") or "") else ""
    if host.endswith("reddit.com"):
        return "reddit"
    if host.endswith("arxiv.org"):
        return "arxiv"
    if host == "github.com":
        return "github"
    return "feed"


def feed_mentions(rows: list[dict], since: str) -> list[dict]:
    out = []
    for r in rows:
        at = _day(reports.arrived(r))
        if not at or at < since:
            continue
        out.append({"at": at, "family": feed_family(r), "origin": r.get("feed") or "", "title": r.get("title") or "",
                    "url": r.get("url") or "", "summary": "", "score": None, "p": r.get("p") or None, "kind": r.get("kind")})
    return out


def sensor_mentions(out: Path, since: str) -> tuple[list[dict], list[dict]]:
    """(mentions, per-source status of the latest run). An item seen on several days counts once,
    on its first day, with the highest score any day gave it."""
    folder = out / "sensors"
    items: dict[str, dict] = {}
    status: list[dict] = []
    if not folder.is_dir():
        return [], []
    for path in sorted(folder.glob("*.json")):
        day = _day(path.stem)
        if not day or day < since:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for k, row in (data.get("items") or {}).items():
            first = _day(row.get("first_seen")) or day
            prev = items.get(k)
            score = row.get("score")
            if prev is None:
                items[k] = {"at": first, "family": row.get("source") or "rss", "origin": row.get("origin") or "",
                            "title": row.get("title") or "", "url": row.get("url") or "",
                            "summary": row.get("summary") or "", "score": score, "p": row.get("p"),
                            "kind": row.get("kind"), "entities": row.get("entities") or []}
            else:
                if score is not None and (prev["score"] is None or score > prev["score"]):
                    prev["score"] = score
                prev["p"] = prev["p"] or row.get("p")
        if data.get("status"):
            status = [{"family": n, **s} for n, s in data["status"].items()]
    return list(items.values()), status


# Sensors that fetch the same publisher feeds Reader subscribes to: one article through both pipes is
# one source. HN, Hugging Face and Kagi News linking it are attention of their own and stay separate.
# Reader's family for an item -> the sensor that fetches the same kind of feed.
SAME_PIPE = {"feed": "rss", "github": "github", "reddit": "reddit"}


def one_per_pipe(feed: list[dict], sensed: list[dict]) -> list[dict]:
    """Reader's items and the sensors', with an article that arrived both ways counted once: the
    sensor's row (it carries a score), the judge's relevance from Reader's when the sensor has
    none, the earlier day. [earned: 2026-09-27, the owner imported the radar's music feeds into
    Reader, so every music article would have counted as two families]"""
    by_pipe = {(m["family"], _canonical(m["url"])): m for m in sensed if m["family"] in SAME_PIPE.values() and m.get("url")}
    out = list(sensed)
    for m in feed:
        pipe = SAME_PIPE.get(m["family"])
        twin = by_pipe.get((pipe, _canonical(m["url"]))) if pipe and m.get("url") else None
        if twin is None:
            out.append(m)
            continue
        twin["p"] = twin.get("p") or m.get("p")
        twin["at"] = min(twin["at"], m["at"])
    return out


def add_eng_pct(mentions: list[dict]) -> None:
    """Percentile of each score within its family and day: 400 HN points and 40 Hugging Face
    likes are not the same number."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for m in mentions:
        if m.get("score") is not None:
            groups[(m["family"], m["at"])].append(m)
    for ms in groups.values():
        ms.sort(key=lambda m: m["score"])
        n = len(ms)
        for i, m in enumerate(ms):
            m["eng_pct"] = round((i + 1) / n, 3) if n > 1 else 0.5


def collect(mentions: list[dict], vault_keys: dict[str, str], vocab: Counter | None = None) -> dict[str, Entity]:
    """Entities by key. A vault note's specific tags count as its entities only where the outside
    world has the same name; the vault's own topics are the pulse's business."""
    ents: dict[str, Entity] = {}
    for m in mentions:
        names = entities.of(m["title"], "" if m["family"] == "vault" else m["url"], m.get("entities"), vocab)
        if m["family"] == "vault":
            names += [vault_keys[entities.key(t)] for t in m.get("tags") or [] if entities.key(t) in vault_keys]
        seen: set[str] = set()
        for n in names:
            k = entities.key(n)
            if not k or k in seen:
                continue
            seen.add(k)
            e = ents.setdefault(k, Entity(k))
            e.names[n] += 1
            e.mentions.append(m)
    return merge_variants(ents)


def merge_variants(ents: dict[str, Entity]) -> dict[str, Entity]:
    """'Claude Code Projects' into 'Claude Code', 'Claude Opus 5.5' into 'Opus 5.5': a key that
    starts or ends with a more-mentioned key of at least four characters is that thing."""
    order = sorted(ents, key=lambda k: (-len(ents[k].mentions), len(k)))
    for k in sorted(ents, key=len, reverse=True):
        if k not in ents:
            continue
        for base in order:
            if base == k or base not in ents or len(base) < 4 or len(base) >= len(k):
                continue
            if (k.startswith(base) or k.endswith(base)) and len(ents[base].mentions) >= len(ents[k].mentions):
                ents[base].names.update(ents[k].names)
                ents[base].mentions += [m for m in ents[k].mentions if m not in ents[base].mentions]
                del ents[k]
                break
    return ents


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def display_name(e: Entity) -> str:
    """The thing's own name, not a merged variant's: most used among the names with its key,
    then the shortest."""
    own = [n for n in e.names if entities.key(n) == e.key] or list(e.names)
    top = max(e.names[n] for n in own)
    name = min((n for n in own if e.names[n] * 3 >= top), key=lambda n: (len(n), n.islower(), -e.names[n], n))
    # a family is named by its family word: "Qwen 27b FP8" -> "Qwen" while the key stays the same
    words = re.split(r"(?<=\S)[ -](?=\S)", name)
    while len(words) > 1 and entities.key(" ".join(words[:-1])) == e.key:
        words.pop()
    return name[:len(" ".join(words))] if len(words) > 1 else words[0]


def score(e: Entity, today: date, anchor_of=None, horizons: dict[str, str] | None = None,
          alias: dict[str, str] | None = None) -> dict[str, Any] | None:
    """A blip, or None when the thing is too thin or not the owner's business. `anchor_of(key,
    window_paths)` gives its place in the graph (`vault_graph.anchor`)."""
    recent_from = (today - timedelta(days=RECENT_DAYS - 1)).isoformat()
    base_from = (today - timedelta(days=RECENT_DAYS + BASELINE_DAYS - 1)).isoformat()
    window_from = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    outside = [m for m in e.mentions if m["family"] != "vault"]
    if not outside:
        return None  # the vault's own topics are shown by the pulse, not as blips
    recent = sum(1 for m in outside if m["at"] >= recent_from)
    base = sum(1 for m in outside if base_from <= m["at"] < recent_from)
    week = [m for m in outside if m["at"] >= window_from]
    if not week:
        return None
    families = sorted({m["family"] for m in week})
    eng = max((m.get("eng_pct") or 0.0 for m in week), default=0.0)
    if len(week) < 2 and eng < 0.85:
        return None
    judged = [max(m["p"].values()) for m in outside if m.get("p")]
    relevance = max(judged) if judged else 0.5
    in_window = [m for m in e.mentions if m["family"] == "vault"]
    anchored = anchor_of(e.key, [m["url"] for m in in_window]) if anchor_of else \
        {"notes": [{"title": m["title"], "path": m["url"]} for m in in_window], "neighborhood": 0, "hubs": [], "total": len(in_window)}
    if judged and relevance < MIN_RELEVANCE and not anchored["notes"]:
        return None
    expected = base / BASELINE_DAYS * RECENT_DAYS
    velocity = (recent + 0.5) / (expected + 0.5)
    parts = {
        "breadth": _clamp((len(families) - 1) / 3),
        "velocity": _clamp(math.log2(velocity) / 3),
        "engagement": round(eng, 3),
        "relevance": round(relevance, 3),
        "volume": _clamp(math.log2(1 + len(week)) / 4),
        "vault": 0.5 * _clamp(anchored["total"] / 3) + 0.5 * _clamp(math.log2(1 + anchored["neighborhood"]) / 6),
    }
    strength = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()))
    # First seen by anything the owner has: a mention, or a note of any date anchoring it. A thing
    # first seen on its source's horizon (the first day that source has data) may be older than
    # the data: a source's first run sees every trending repo "for the first time".
    first_seen = min([m["at"] for m in e.mentions] + [n for n in anchored.get("created", []) if n])
    first = min(outside, key=lambda m: m["at"])
    on_horizon = first["at"] <= (horizons or {}).get(first["family"], "")
    if not on_horizon and first_seen >= (today - timedelta(days=RECENT_DAYS - 1)).isoformat():
        stage = "new"
    elif strength >= STAGE_HOT:
        stage = "hot"
    elif velocity >= 2 and recent >= 2:
        stage = "rising"
    elif recent == 0:
        stage = "fading"
    else:
        stage = "steady"
    spark = Counter(m["at"] for m in outside)
    items = sorted(week, key=lambda m: (m.get("eng_pct") or 0, max((m.get("p") or {}).values(), default=0)), reverse=True)
    interest_weight, interest_support = _interest_weights(e.mentions, alias)
    return {
        "key": e.key, "name": display_name(e), "stage": stage, "strength": strength,
        "parts": {k: round(v, 3) for k, v in parts.items()}, "families": families, "mentions": len(week),
        "recent": recent, "velocity": round(velocity, 2), "first_seen": first_seen, "in_vault": anchored["total"],
        "new_in_vault": sum(1 for c in anchored.get("created", []) if c and c >= window_from),
        "spark": [spark.get((today - timedelta(days=d)).isoformat(), 0) for d in range(13, -1, -1)],
        "items": [{"title": m["title"], "url": m["url"], "family": m["family"], "origin": m["origin"], "at": m["at"],
                   "score": m.get("score")} for m in items[:6]],
        "vault_notes": anchored["notes"][:4],
        "graph": {"neighborhood": anchored["neighborhood"], "hubs": anchored["hubs"]},
        "_interests": interest_weight,
        "_interest_support": interest_support,
    }


def current_ids(old_ids, names: dict[str, str]) -> dict[str, str]:
    """Backup guess for a rename with no `aliases:` entry yet: the current id sharing its first two
    slug words. Only a fallback now — `interests_mod.alias_map()` (the profile's own `aliases:`)
    is tried first and is what a real rename should carry, since this heuristic can miss one (it
    matched "AI Agents" renames fine, but "Obsidian & Knowledge Management" -> "Obsidian & Agentic
    Knowledge Management" shares only its first word, not its first two)."""
    out = {}
    for old in old_ids:
        if old in names:
            continue
        head = old.split("-")[:2]
        match = [iid for iid in names if iid.split("-")[:2] == head]
        if len(match) == 1:
            out[old] = match[0]
    return out


def resolve_ids(old_ids, names: dict[str, str], amap: dict[str, str]) -> dict[str, str]:
    """Every id a state/sensor row's `p` dict might carry -> the live interest it counts toward:
    `amap` (`interests_mod.alias_map()`, the profile's explicit `aliases:`) first, `current_ids`'
    heuristic as a backup for a rename that has no alias entry yet. An id neither resolves is
    dropped — a truly retired interest, not carried forward as its own phantom sector. [earned:
    2026-09-28, the owner's Obsidian-plugin renames]"""
    out = dict(amap)
    out.update(current_ids([i for i in old_ids if i not in out], names))
    return out


def _interest_weights(mentions: list[dict], alias: dict[str, str] | None = None) -> tuple[Counter, Counter]:
    """(summed weight, distinct-mention support) per interest, both keyed the same way. `support`
    is how many different mentions cleared the bar for that interest — one mention naming several
    interests at once (a single ambiguous item scoring 0.5+ on two of them) supports each of those
    once, not zero; it is `assign_sectors` that then asks for more than one such mention before it
    trusts the sector, which this alone does not decide.

    `alias` (typically `resolve_ids()`'s output) resolves a row's possibly-old interest id to the
    one it counts toward today; an id it cannot resolve is dropped rather than kept as itself, so
    a retired interest's rows never become their own phantom sector. `alias=None` (no map given at
    all, distinct from an empty-but-real one) skips resolution entirely and keeps every id as-is —
    the identity behaviour a caller with no rename bookkeeping still gets."""
    def resolve(iid: str) -> str | None:
        return iid if alias is None else alias.get(iid)

    w: Counter = Counter()
    n: Counter = Counter()
    for m in mentions:
        for iid, p in (m.get("p") or {}).items():
            if p >= 0.5:
                key = resolve(iid)
                if key is None:
                    continue
                w[key] += p
                n[key] += 1
        for iid in m.get("interests") or []:
            key = resolve(iid)
            if key is None:
                continue
            w[key] += 1.0
            n[key] += 1
    return w, n


def pretty_id(iid: str) -> str:
    """An interest id no longer in the interests note (renamed since it was judged), readable."""
    small = {"ai", "llm", "cd", "ci", "mcp", "api"}
    return " ".join(w.upper() if w in small else w.capitalize() for w in iid.split("-"))


def short_name(name: str) -> str:
    for sep in (" & ", ", ", " — ", ": "):
        name = name.split(sep)[0]
    words = name.split()
    while len(words) > 1 and len(" ".join(words)) > 16:  # a sector label on the scope stays short
        words.pop()
    return " ".join(words)


# A sector is what an entity IS, not which single item it happened to be mentioned in: one
# incidental co-occurrence (a DJ-gear driver post that mentions "Windows 11", one ambiguous
# reddit thread that scores both "AI Agents" and "Frontier Models") should not pin a sector on its
# own. Require at least two distinct mentions to agree before trusting a specific interest; a
# generic tech or celebrity name that only ever clears the bar once falls back to Other instead of
# being early-warned under a sector it is not really about. [earned: 2026-09-28, review —
# "Windows 11" under Music Production from one Native Instruments forum post, "SpaceX" under AI
# Agents from one reddit thread that also happened to name Anthropic]
MIN_SECTOR_SUPPORT = 2

# A single strong mention still earns a sector when the entity's own NAME — not just the article
# that mentioned it — is what the interest is about: a literal word from the interest's own gloss,
# tags or queries, or a sibling in a well-known model family the interest already names a member
# of. Small and non-exhaustive on purpose (in the spirit of entities.py's BRANDS/FILLER lists): a
# family or word absent here just falls back to the two-mention rule like anything else. [earned:
# 2026-09-28, "Sonnet 5.5" fell to Other on one mention despite p=0.8 on Claude Code & Anthropic
# Ecosystem, the interest whose own query already reads "Opus Fable pricing"]
MODEL_FAMILIES = (
    {"claude", "opus", "sonnet", "haiku", "fable"},
    {"gpt", "chatgpt", "o1", "o3", "o4"},
    {"gemini", "gemma"},
    {"qwen"}, {"deepseek"}, {"llama"}, {"mistral"}, {"grok"}, {"kimi"}, {"mimo"}, {"minimax"},
)


def _interest_vocab(it: interests_mod.Interest) -> set[str]:
    """Lowercase, non-generic words from an interest's own name, gloss, tags and queries."""
    text = " ".join([it.name, it.gloss, *it.tags, *it.queries])
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.'-]*", text)}
    return words - entities.GENERIC


def _head_word(name: str) -> str:
    """The name's first word, casefolded: "sonnet" from "Sonnet 5.5", "qwen" from "Qwen3.8"."""
    m = re.match(r"[A-Za-z][A-Za-z+#'-]*", name)
    return m.group(0).lower() if m else name.lower()


def _named_for(entity_name: str, vocab: set[str]) -> bool:
    head = _head_word(entity_name)
    if head in vocab:
        return True
    return any(head in fam and fam & vocab for fam in MODEL_FAMILIES)


def assign_sectors(blips: list[dict], names: dict[str, str], interest_list: list[interests_mod.Interest] = ()) -> list[dict]:
    vocabs = {it.id: _interest_vocab(it) for it in interest_list}
    counts: Counter = Counter()
    for b in blips:
        support = b.get("_interest_support") or Counter()
        candidates = [iid for iid, _ in b["_interests"].most_common()
                      if support.get(iid, 0) >= MIN_SECTOR_SUPPORT or _named_for(b["name"], vocabs.get(iid, set()))]
        b["sector"] = candidates[0] if candidates else "other"
        counts[b["sector"]] += 1
    keep = [iid for iid, _ in counts.most_common() if iid != "other"][:MAX_SECTORS]
    for b in blips:
        if b["sector"] not in keep:
            b["sector"] = "other"
    sectors = [{"id": iid, "name": names.get(iid) or pretty_id(iid),
                "short": short_name(names.get(iid) or " ".join(pretty_id(iid).split()[:2])),
                "blips": sum(1 for b in blips if b["sector"] == iid)} for iid in keep]
    rest = sum(1 for b in blips if b["sector"] == "other")
    if rest:
        sectors.append({"id": "other", "name": "Other", "short": "Other", "blips": rest})
    return sectors


class _Skip(Exception):
    """The backend cannot run (no key, no CLI, over budget): the check is skipped, not failed."""


def _load_check_row(line: str) -> dict | None:
    """One line of `signal-tavily.jsonl` / `signal-kagi.jsonl`, or None for a truncated or
    malformed one (killed mid-append) or a row missing what every reader needs — must not crash
    the once-a-day name check. [earned: 2026-09-28 week review]"""
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict) or not {"day", "key", "name", "hits"} <= row.keys():
        return None
    return row


def _name_check(out: Path, candidates: list[dict], now: datetime, family: str, log_name: str,
                ask: Any = None) -> tuple[list[dict], dict]:
    """One backend's check: ask `ask(name)` about the newest, least corroborated names, at most
    CHECKS_PER_DAY a day and each name once a week, logging every answer in `log_name`; then every
    answer on record from the last week becomes a mention of `family`. `ask=None` only reads."""
    log = out / log_name
    rows = []
    for ln in (log.read_text(encoding="utf-8").splitlines() if log.is_file() else []):
        if ln.strip() and (row := _load_check_row(ln)) is not None:
            rows.append(row)
    today = now.date().isoformat()
    week_ago = (now.date() - timedelta(days=7)).isoformat()
    asked_today = sum(1 for r in rows if r["day"] == today)
    recent_keys = {r["key"] for r in rows if r["day"] >= week_ago}
    status = {"family": family, "label": FAMILY_LABELS[family], "status": "ok", "items": 0, "detail": ""}
    for b in sorted(candidates, key=lambda b: (len(b["families"]), -b["strength"])) if ask else []:
        if asked_today >= CHECKS_PER_DAY:
            break
        if b["key"] in recent_keys:
            continue
        try:
            hits = ask(b["name"])
        except _Skip as e:
            status.update(status="skipped", detail=str(e)[:160])
            break
        except (kagi.KagiError, tavily.TavilyError) as e:
            status.update(status="failed", detail=str(e)[:160])
            break
        row = {"day": today, "key": b["key"], "name": b["name"], "hits": hits[:5]}
        rows.append(row)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        asked_today += 1
    mentions = []
    for r in rows:
        if r["day"] < week_ago:
            continue
        for h in r["hits"]:
            mentions.append({"at": _day(h.get("published")) or r["day"], "family": family,
                             "origin": FAMILY_LABELS[family], "title": h["title"], "url": h["url"], "summary": "",
                             "score": None, "p": None, "entities": [r["name"]]})
    status["items"] = len(mentions)
    return mentions, status


def _tavily_ask(vault: Path, out: Path, now: datetime) -> Any:
    from radar import profile_number  # lazy: radar imports this module

    ledger = tavily.ledger(out, profile_number(vault, "tavily_weekly_budget_usd", tavily.DEFAULT_WEEKLY_BUDGET_USD),
                           signal=True)

    def ask(name: str) -> list[dict]:
        try:
            # "Is this name taking off this week": Tavily's news index first (one credit); a name
            # too new to be news yet still shows up in the general web index, so ask that only
            # when news came back empty (another credit, still under the same budget). [earned:
            # 2026-09-28 week review]
            found = tavily.search(f'"{name}"', ledger, max_results=5, time_range="week", topic="news", now=now)
            if not found:
                found = tavily.search(f'"{name}"', ledger, max_results=5, time_range="week", now=now)
        except (tavily.NoKey, tavily.NoCli, tavily.OverBudget) as e:
            raise _Skip(str(e)) from e
        except tavily.TavilyError as e:  # rate limit, HTTP, a bad answer: Kagi still gets its turn [PR #75 review]
            raise _Skip(f"failed: {e}") from e
        # time_range=week filters on Tavily's side; its results carry no date, so they count today.
        return [{"title": f["title"], "url": f["url"], "published": ""} for f in found]
    return ask


def _kagi_ask(vault: Path, out: Path, now: datetime) -> Any:
    from radar import profile_number  # lazy: radar imports this module

    ledger = kagi.ledger(out, profile_number(vault, "kagi_weekly_budget_usd", kagi.DEFAULT_WEEKLY_BUDGET_USD),
                         signal=True)
    week_ago = (now.date() - timedelta(days=7)).isoformat()

    def ask(name: str) -> list[dict]:
        try:
            found = kagi.news(name, ledger, now)
        except (kagi.NoKey, kagi.OverBudget) as e:
            raise _Skip(str(e)) from e
        return [{"title": f["title"], "url": f["url"], "published": f.get("published", "")} for f in found
                if _day(f.get("published")) and _day(f.get("published")) >= week_ago]
    return ask


def web_check(vault: Path, out: Path, candidates: list[dict], now: datetime) -> tuple[list[dict], list[dict]]:
    """The name check: Tavily through `tvly`, Kagi news when Tavily cannot run. Returns the
    mentions of both backends still on record and the status of the one that asked."""
    t_ms, t_status = _name_check(out, candidates, now, "tavily", "signal-tavily.jsonl", _tavily_ask(vault, out, now))
    if t_status["status"] == "skipped":
        k_ms, k_status = _name_check(out, candidates, now, "kagi", "signal-kagi.jsonl", _kagi_ask(vault, out, now))
        k_status["detail"] = "; ".join(x for x in (f"Tavily skipped: {t_status['detail']}", k_status["detail"]) if x)
        return t_ms + k_ms, [k_status]
    k_ms, _ = _name_check(out, candidates, now, "kagi", "signal-kagi.jsonl")
    return t_ms + k_ms, [t_status]


# A card is a stronger claim than a dot on the scope: something with a real sector is already
# corroborated (assign_sectors required two mentions to agree, or a name match), so the existing
# new/recent/multi-source-or-engaged gate is enough. An Other-sector thing — no interest it clearly
# belongs to — needs to earn its place instead of riding in on raw source count: a celebrity or
# generic-tech name picked up by three outlets (SpaceX: hn, kagi_news, reddit) is still noise if
# only one of those mentions was ever judged relevant to anything. "Independent sources" here means
# mentions that separately cleared the judge's bar for some interest (_interest_support), not just
# distinct families. [earned: 2026-09-28, SpaceX/Windows 11/Soup filling half the early-warning
# cards once the two-mention sector rule correctly parked them in Other]
EARLY_OTHER_MIN_RELEVANCE = 0.8  # the judge's own "strong" bar (judgments/policy.py T_STRONG)
EARLY_OTHER_MIN_SOURCES = 2


def _early_eligible(b: dict) -> bool:
    if b["sector"] != "other":
        return True
    support = b.get("_interest_support") or {}
    return b["parts"]["relevance"] >= EARLY_OTHER_MIN_RELEVANCE or max(support.values(), default=0) >= EARLY_OTHER_MIN_SOURCES


def build(vault: Path, out: Path, now: datetime, check: bool = False) -> dict[str, Any]:
    today = now.date()
    since = (today - timedelta(days=RECENT_DAYS + BASELINE_DAYS)).isoformat()
    state = reports_rows(out)
    sensed, sensor_status = sensor_mentions(out, since)
    mentions = one_per_pipe(feed_mentions(state, since), sensed)
    pulse = vault_pulse.pulse(vault, now)
    vault_ms = [m for m in pulse.get("mentions", []) if (m.get("at") or "") >= since]
    add_eng_pct(mentions)
    outside_keys: dict[str, str] = {}
    # Vocabulary from prose only: a repo or model id written in lower case is still a name.
    vocab = entities.lowercase_vocabulary(m["title"] for m in mentions + vault_ms if m["family"] not in ("github", "hf"))
    for m in mentions:
        for n in entities.of(m["title"], m["url"], m.get("entities"), vocab):
            outside_keys.setdefault(entities.key(n), n)
    interest_list = interests_mod.load(vault)
    names = {it.id: it.name for it in interest_list}
    alias = resolve_ids({i for m in mentions for i in (m.get("p") or {})}, names, interests_mod.alias_map(interest_list))
    ents = collect(mentions + vault_ms, outside_keys, vocab)
    graph, by_key, notes, graph_section = vault_graph.build(vault, now)

    def anchor_of(k: str, window_paths: list[str]) -> dict:
        # A versioned name without notes of its own is anchored in its family's: `qwen` notes for `qwen38`.
        own = by_key.get(k) or by_key.get(entities.family_key(k), [])
        paths = list(dict.fromkeys([*own, *(p for p in window_paths if p in notes)]))
        return {**vault_graph.anchor(graph, notes, paths), "total": len(paths),
                "created": [notes[p]["created"] for p in paths if notes[p].get("created")]}

    horizons: dict[str, str] = {}
    for m in mentions:
        horizons[m["family"]] = min(horizons.get(m["family"], m["at"]), m["at"])
    blips = [b for b in (score(e, today, anchor_of, horizons, alias) for e in ents.values()) if b]

    sources = [{"family": f, "label": FAMILY_LABELS.get(f, f), "status": "ok",
                "items": sum(1 for m in mentions if m["family"] == f), "detail": ""}
               for f in ("feed", "reddit", "arxiv", "github") if any(m["family"] == f for m in mentions)]
    for s in sensor_status:
        fam = s["family"]
        sources = [x for x in sources if x["family"] != fam]
        sources.append({"family": fam, "label": FAMILY_LABELS.get(fam, fam), "status": s.get("status", "ok"),
                        "items": s.get("items", 0), "detail": s.get("detail", "")})
    if check:
        cands = [b for b in blips if b["stage"] in ("new", "rising")]
        check_ms, check_status = web_check(vault, out, cands, now)
        if check_ms:
            add_eng_pct(check_ms)
            ents = collect(mentions + check_ms + vault_ms, outside_keys, vocab)
            blips = [b for b in (score(e, today, anchor_of, horizons, alias) for e in ents.values()) if b]
        sources.extend(check_status)
    sources.append({"family": "vault", "label": FAMILY_LABELS["vault"], "status": "ok", "items": len(vault_ms), "detail": ""})
    sources.append({"family": "graph", "label": "Knowledge graph", "status": graph_section["status"],
                    "items": graph_section.get("nodes") or 0, "detail": graph_section.get("detail", "")})

    blips.sort(key=lambda b: (-b["strength"], b["key"]))
    blips = blips[:MAX_BLIPS]
    sectors = assign_sectors(blips, names, interest_list)
    early_from = (now - timedelta(hours=EARLY_HOURS)).date().isoformat()
    early = [b["key"] for b in blips if b["stage"] == "new" and b["first_seen"] >= early_from
             and (len(b["families"]) >= 2 or (b["parts"]["engagement"] >= 0.9 and b["parts"]["relevance"] >= 0.6))
             and _early_eligible(b)]
    for b in blips:
        del b["_interests"]
        del b["_interest_support"]
    week = reports.week_of(today.isoformat())
    trend = reports.trend(state, week, alias) if state else {}
    data = {
        # UTC, `Z`-suffixed — the same `ingested_at`/`distilled_at` format (contract/VAULT_SCHEMA.md).
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vault_name": vault.name,
        "window_days": WINDOW_DAYS,
        "sources": sources,
        "sectors": sectors,
        "blips": blips,
        "early": early,
        "blind_spots": [b["key"] for b in blips if b["strength"] >= BLIND_SPOT_STRENGTH and b["in_vault"] == 0],
        "vault": {k: v for k, v in pulse.items() if k != "mentions"},
        "graph": graph_section,
        "interest_trend": sorted(({"id": iid, "name": names.get(iid) or pretty_id(iid), "scanned": t["scanned"], "strong": t["strong"],
                                   "baseline": t.get("baseline"), "rising": t.get("rising", False)} for iid, t in trend.items()),
                                 key=lambda r: (-r["strong"], r["id"])),
        "stats": {"mentions": len(mentions) + len(vault_ms), "entities": len(ents),
                  "families": dict(Counter(m["family"] for m in mentions + vault_ms))},
    }
    return data


def reports_rows(out: Path) -> list[dict]:
    path = out / "state.jsonl"
    if not path.is_file():
        return []
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows


def write(vault: Path, out: Path, now: datetime, check: bool = False) -> dict[str, Any]:
    data = build(vault, out, now, check)
    atomic_write(out / "signal.json", json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    atomic_write(out / "Signal-Radar.html", signal_render.render_html(data))
    atomic_write(out / "Signal-Radar.md", signal_render.render_md(data))
    # The note embeds these two: Obsidian shows an SVG inline, never the .html page.
    atomic_write(out / signal_render.SCOPE_SVG, signal_render.render_scope_svg(data))
    atomic_write(out / signal_render.MOMENTUM_SVG, signal_render.render_momentum_svg(data))
    files = ("signal.json", "Signal-Radar.html", "Signal-Radar.md", signal_render.SCOPE_SVG, signal_render.MOMENTUM_SVG)
    return {"status": "ok", "blips": len(data["blips"]), "early": len(data["early"]),
            "blind_spots": len(data["blind_spots"]), "entities": data["stats"]["entities"],
            "sources": {s["family"]: s["status"] for s in data["sources"]},
            "html": (out / "Signal-Radar.html").relative_to(vault).as_posix(),
            "files": [(out / f).relative_to(vault).as_posix() for f in files], "generated": data["generated"]}
