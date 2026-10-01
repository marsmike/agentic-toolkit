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
# A blind spot is the owner's business: a thing an interest's sector holds, or an unsectored one the
# judge scored this relevant. [earned: 2026-10-01 — "Delhi", "Netherlands", "Ukraine", "Pac-Man" and
# "White House" were blind spots, and Now.md and the morning push said "Not in your vault: … Delhi"]
BLIND_SPOT_OTHER_RELEVANCE = 0.6
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


def _merge_qualifier(short_key: str, long_key: str) -> str:
    """What `long_key` adds over `short_key` — "meta" for metamuse/muse, "gpt61" for
    gpt61sol/sol — or "" when `long_key` does not actually contain `short_key` whole."""
    if long_key.startswith(short_key):
        return long_key[len(short_key):]
    if long_key.endswith(short_key):
        return long_key[:len(long_key) - len(short_key)]
    return ""


def _related(short_key: str, long_key: str, short_mentions: list[dict]) -> bool:
    """Whether `long_key` is really `short_key`, not just a string that happens to contain or be
    contained by it. Two kinds of evidence:

    - `long_key` is exactly `short_key` plus a trailing version number ("zither10" over "zither",
      "astra6" over "astra") — `entities._spans` only ever attaches a bare version right after a
      name it already matched, so this shape is never a coincidence, the way a shared word is.
    - failing that, the qualifier `long_key` adds over `short_key` ("meta" for metamuse/muse,
      "gpt61" for gpt61sol/sol) appears as a whole word in one of the shorter entity's own mention
      titles. Two or three characters are too easily a coincidence ("6", "ai"); a bare digit here
      (unlike the version-number case above, which is the whole remainder, not a word found loose
      in running text) never qualifies anything on its own.

    [earned: 2026-10-01, Signal Radar 2026-10-01 04:15 UTC: pure string containment let "machines"
    absorb the unrelated GitHub repo sleeping_machines, "scope" absorb Dental Scope and "sift"
    absorb LatentSift — merge_variants had no way to tell a shared ending from a shared subject]"""
    if entities.family_key(long_key) == short_key:
        return True
    qualifier = _merge_qualifier(short_key, long_key)
    if len(qualifier) < 3 or qualifier.isdigit():
        return False
    return any(qualifier in entities.title_words(m.get("title")) for m in short_mentions)


def merge_variants(ents: dict[str, Entity]) -> dict[str, Entity]:
    """'Claude Code Projects' into 'Claude Code', 'Claude Opus 5.5' into 'Opus 5.5', 'Muse' into
    'Meta Muse': a key that starts or ends with another of at least three characters is a
    *candidate* to be the same thing — string containment alone over- and under-merges (see
    `_related`'s earned-note and `_merge_checks` in the eval). The candidate only merges on
    evidence of relatedness (`_related`), and then the more-mentioned of the two is what the
    merged thing is called: a fragment with fewer mentions folds into the qualified name with
    more, never the reverse, regardless of which string is longer. [earned: 2026-10-01, Signal
    Radar 2026-10-01 04:15 UTC: direction used to require the *shorter* key to have the most
    mentions, so Muse(12) could never fold into Meta Muse(65), Sol(2) into GPT-6.1 Sol(8), Gemini
    4(3) into Gemini 4 Argon(11) — the fragment always has fewer mentions than the qualified name
    that grew past it]"""
    keys = list(ents)
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        root = k
        while parent[root] != root:
            root = parent[root]
        while parent[k] != root:
            parent[k], k = root, parent[k]
        return root

    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            short, long_ = (a, b) if len(a) <= len(b) else (b, a)
            if len(short) < 3 or len(short) >= len(long_):
                continue
            if not (long_.startswith(short) or long_.endswith(short)):
                continue
            if _related(short, long_, ents[short].mentions):
                ra, rb = find(short), find(long_)
                if ra != rb:
                    parent[ra] = rb

    groups: dict[str, list[str]] = defaultdict(list)
    for k in keys:
        groups[find(k)].append(k)

    merged: dict[str, Entity] = {}
    for members in groups.values():
        # the most-mentioned member is what the group is; on a tie, a key that is just another
        # member plus a trailing version number is the version, not the identity ("zither", not
        # "zither10"), so it loses the tie to one that isn't; failing that the more qualified
        # (longer) key wins ("Claude Red" over bare "Red", both from the same one mention)
        head = max(members, key=lambda k: (len(ents[k].mentions), not entities.family_key(k), len(k)))
        e = Entity(head)
        for mk in members:
            e.names.update(ents[mk].names)
            for m in ents[mk].mentions:
                if m not in e.mentions:
                    e.mentions.append(m)
        merged[head] = e
    return merged


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


def _ambiguous(name: str) -> bool:
    """A one-word name without a digit ("Traktor", "Muse", "jeff"): asked bare, the web answers
    about namesakes."""
    return re.fullmatch(r"[A-Za-z]+", name) is not None


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
    # A row records what disambiguated its name (`context`, maybe ""). A one-word name's row without
    # that record may have been asked bare: its hits are as likely namesakes as the thing, so it is
    # no evidence and does not stop the name being asked again with context. [earned: 2026-10-01 —
    # the 09-30 "jeff" row (an obituary, a TV host, a governor) kept the Jeff decision models HOT at
    # 70 for its whole week after check_candidates had learned to add context]
    rows = [r for r in rows if "context" in r or not _ambiguous(r["name"])]
    today = now.date().isoformat()
    week_ago = (now.date() - timedelta(days=7)).isoformat()
    asked_today = sum(1 for r in rows if r["day"] == today)
    recent_keys = {r["key"] for r in rows if r["day"] >= week_ago}
    status = {"family": family, "label": FAMILY_LABELS[family], "status": "ok", "items": 0, "detail": ""}
    # Watched names first (`b["watched"]`, the profile's `watch`), then the least corroborated.
    for b in sorted(candidates, key=lambda b: (not b.get("watched"), len(b["families"]), -b["strength"])) if ask else []:
        if asked_today >= CHECKS_PER_DAY:
            break
        if b["key"] in recent_keys:
            continue
        try:
            hits = ask(b["name"], b.get("context", ""))
        except _Skip as e:
            status.update(status="skipped", detail=str(e)[:160])
            break
        except (kagi.KagiError, tavily.TavilyError) as e:
            status.update(status="failed", detail=str(e)[:160])
            break
        row = {"day": today, "key": b["key"], "name": b["name"], "context": b.get("context", ""), "hits": hits[:5]}
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

    def ask(name: str, context: str = "") -> list[dict]:
        query = f'"{name}" {context}'.strip()
        try:
            # "Is this name taking off this week": Tavily's news index first (one credit); a name
            # too new to be news yet still shows up in the general web index, so ask that only
            # when news came back empty (another credit, still under the same budget). [earned:
            # 2026-09-28 week review]
            found = tavily.search(query, ledger, max_results=5, time_range="week", topic="news", now=now)
            if not found:
                found = tavily.search(query, ledger, max_results=5, time_range="week", now=now)
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

    def ask(name: str, context: str = "") -> list[dict]:
        try:
            found = kagi.news(f"{name} {context}".strip(), ledger, now)
        except (kagi.NoKey, kagi.OverBudget) as e:
            raise _Skip(str(e)) from e
        return [{"title": f["title"], "url": f["url"], "published": f.get("published", "")} for f in found
                if _day(f.get("published")) and _day(f.get("published")) >= week_ago]
    return ask


def _profile_watch(vault: Path) -> list[str]:
    from vault_utils import profile_value
    raw = profile_value(vault, "watch", None)
    return [str(w).strip() for w in (raw if isinstance(raw, list) else str(raw or "").split(",")) if str(w).strip()]


def check_candidates(blips: list[dict], names: dict[str, str], watch: list[str]) -> list[dict]:
    """What the web check may spend its CHECKS_PER_DAY on: new or rising things in a sector, and an
    Other-sector one whose mentions a judged interest stands behind (unsectored is not evidence a
    thing is not real); an Other-sector name with no interest at all is skipped. A one-word name without a digit ("Traktor",
    "Muse", "jeff") is asked with disambiguating context beside it — its sector's name when it has
    a real one, else its single best-scoring judged interest if any mention cleared the judge's
    own bar (`_interest_weights`' 0.5) even without the two-mention support `assign_sectors` wants
    — or the web answers about a Turkish tractor maker, a Muse fan outlet, or five unrelated people
    named Jeff. [earned: 2026-09-30, DevDay 2026 never checked; earned: 2026-10-01, Signal Radar
    2026-10-01 04:15 UTC: excluding Other from the context fix meant for it left "jeff" HOT (70)
    on one real mention plus five unrelated Tavily namesakes, asked with no context at all]"""
    pattern = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(w) for w in watch) + r")(?![a-z])", re.I) if watch else None
    out = []
    for b in blips:
        if b["stage"] not in ("new", "rising"):
            continue
        ambiguous = _ambiguous(b["name"])
        sector_name = names.get(b.get("sector"), "")
        if not sector_name and b.get("_interests"):
            top_id, top_p = next(iter(b["_interests"].most_common(1)), (None, 0))
            if top_p >= 0.5:
                sector_name = names.get(top_id, "")
        if not sector_name:
            # an Other-sector name no interest stands behind ("Delhi", "Netherlands") is not worth
            # one of the day's checks: its hits are unrelated and would count as a second source
            # [earned: 2026-09-30, three of six checks; kept 2026-10-01 when "jeff" got its context]
            continue
        context = re.sub(r"[^\w ]+", " ", sector_name).split() if ambiguous else []
        out.append({**b, "watched": bool(pattern and pattern.search(b["name"])), "context": " ".join(context)})
    return out


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


def blind_spot(b: dict) -> bool:
    """Strong, anchored by no note, and the owner's business: in an interest's sector, or unsectored
    with relevance of at least BLIND_SPOT_OTHER_RELEVANCE."""
    return (b["strength"] >= BLIND_SPOT_STRENGTH and b["in_vault"] == 0
            and (b.get("sector") != "other" or b["parts"].get("relevance", 0) >= BLIND_SPOT_OTHER_RELEVANCE))


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
        sectored = [dict(b) for b in blips]  # sectors are assigned for real after the check; this is a look ahead
        assign_sectors(sectored, names, interest_list)
        cands = check_candidates(sectored, names, _profile_watch(vault))
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
        "blind_spots": [b["key"] for b in blips if blind_spot(b)],
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
