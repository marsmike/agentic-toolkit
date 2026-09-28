"""Kagi API client for the radar: feed discovery, the weekly gap search and the kagi skill; never
the daily scan.

Uses the v0 endpoints (`Authorization: Bot`): search, enrich/news (recent small-web and news
posts), fastgpt (an answer with references) and summarize (the Universal Summarizer). Every answer
reports the account balance; the ledger records the balance delta as the call's cost, so spend is
measured, not estimated. A weekly budget (`kagi_weekly_budget_usd`, default 1.00) is checked
against the list price before every call. [v1 answered non-JSON on 2026-09-23; v0 is the
documented stable shape]

What leaves the machine: search queries (the interests' queries, or what the skill is asked),
and for summarize the address of the page to summarise.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vault_utils import secret

BASE = "https://kagi.com/api/v0"
DEFAULT_WEEKLY_BUDGET_USD = 1.00
# List prices: the budget check before a call, and the cost when an answer carries no balance or
# the balance has not moved yet. The summarizer bills per 1k tokens; a long page cost $0.315
# [earned: 2026-09-23 probe], so it is budgeted at a long page's price.
PRICES = {"search": 0.025, "news": 0.002, "fastgpt": 0.015, "summarize": 0.30}
USD_PER_SEARCH = PRICES["search"]
HTTP_TIMEOUT = 60


class NoKey(RuntimeError):
    """KAGI_API_KEY is not set. Callers report SKIPPED."""


class KagiError(RuntimeError):
    pass


class OverBudget(KagiError):
    pass


def _request(url: str, body: dict | None = None) -> dict:
    """The one network call in this module (POST when `body` is given). Evals replace it with a stub."""
    key = secret("KAGI_API_KEY")
    if not key:
        raise NoKey("KAGI_API_KEY is not set")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bot {key}", **({"Content-Type": "application/json"} if data else {})}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise KagiError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        # A timeout during resp.read() raises bare TimeoutError/OSError, not URLError. [earned:
        # 2026-09-28 week review — an unattended run crashed instead of reporting a Kagi failure]
        raise KagiError(f"request failed: {e}") from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise KagiError(f"request failed: non-JSON response: {e}") from e


# One ledger file per writer, one budget over all of them: the pipeline routine and the Signal Radar
# routine both call Kagi and both push the vault, and two appends to one file make git's rebase
# conflict, which loses a whole pipeline run. [earned: 2026-09-27, routine-dependency review]
LEDGER = "kagi-ledger.jsonl"                # scan-side commands: gaps, discover, scout, the kagi skill
SIGNAL_LEDGER = "kagi-ledger-signal.jsonl"  # the Signal Radar's corroboration check


class Ledger:
    """A ledger file in the radar dir: one row per call, {at, kind, query, usd, balance}. Writes only
    `path`; the week's spend and the last balance also read `shared`, the other writers' files."""

    def __init__(self, path: Path, weekly_budget: float, shared: tuple[Path, ...] = ()):
        self.path, self.weekly_budget, self.shared = path, weekly_budget, shared

    @staticmethod
    def _read(path: Path) -> list[dict]:
        """Tolerant of a truncated last line (killed mid-append) or a row missing what every
        reader needs: skipped rather than crashing every command that shares this ledger.
        [earned: 2026-09-28, week review — one bad line broke scan/gaps/discover/scout/signal]"""
        if not path.is_file():
            return []
        rows = []
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and "at" in row and "usd" in row:
                rows.append(row)
        return rows

    def rows(self) -> list[dict]:
        return self._read(self.path)

    def all_rows(self) -> list[dict]:
        return sorted((r for p in (self.path, *self.shared) for r in self._read(p)), key=lambda r: r["at"])

    def spent_this_week(self, now: datetime) -> float:
        """A soft cap: the other routine's calls count once its ledger is pushed, and two routines
        checking at the same moment can both pass; the overshoot is at most one run's calls."""
        since = now - timedelta(days=7)
        return sum(r["usd"] for r in self.all_rows() if datetime.fromisoformat(r["at"]) >= since)

    def last_balance(self) -> float | None:
        rows = [r for r in self.all_rows() if r.get("balance") is not None]
        return rows[-1]["balance"] if rows else None

    def record(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def ledger(out: Path, weekly_budget: float, signal: bool = False) -> Ledger:
    """This writer's ledger in the radar dir `out`, budgeted together with the other one."""
    own, other = (SIGNAL_LEDGER, LEDGER) if signal else (LEDGER, SIGNAL_LEDGER)
    return Ledger(out / own, weekly_budget, shared=(out / other,))


def _paid(kind: str, url: str, ledger: Ledger, label: str, now: datetime | None = None, body: dict | None = None) -> dict:
    """One billed call: refused before it when the week's spend plus its list price would pass the
    budget; recorded afterwards with what it actually cost."""
    now = now or datetime.now(UTC)
    price = PRICES[kind]
    if ledger.spent_this_week(now) + price > ledger.weekly_budget:
        raise OverBudget(f"Kagi weekly budget ${ledger.weekly_budget:.2f} reached")
    before = ledger.last_balance()
    data = _request(url) if body is None else _request(url, body)
    if data.get("error"):
        raise KagiError(str(data["error"])[:200])
    balance = (data.get("meta") or {}).get("api_balance")
    usd = price
    if isinstance(balance, (int, float)) and before is not None and 0 < before - balance < 1:
        usd = round(before - balance, 6)
    ledger.record({"at": now.isoformat(), "kind": kind, "query": label, "usd": usd, "balance": balance})
    return data


def _results(data: dict) -> list[dict]:
    return [r for r in data.get("data") or [] if r.get("t") == 0 and r.get("url")]


def search(query: str, ledger: Ledger, limit: int = 10, now: datetime | None = None) -> list[dict[str, str]]:
    """Web search: [{url, title, snippet}]."""
    data = _paid("search", f"{BASE}/search?{urllib.parse.urlencode({'q': query, 'limit': limit})}", ledger, query, now)
    return [{"url": str(r["url"]), "title": str(r.get("title") or ""), "snippet": str(r.get("snippet") or "")}
            for r in _results(data)]


def news(query: str, ledger: Ledger, now: datetime | None = None) -> list[dict[str, str]]:
    """Recent small-web and news posts (Kagi's enrichment index): [{url, title, snippet, published}]."""
    data = _paid("news", f"{BASE}/enrich/news?{urllib.parse.urlencode({'q': query})}", ledger, query, now)
    return [{"url": str(r["url"]), "title": str(r.get("title") or ""), "snippet": str(r.get("snippet") or ""),
             "published": str(r.get("published") or "")} for r in _results(data)]


def fastgpt(query: str, ledger: Ledger, now: datetime | None = None) -> dict:
    """Kagi's answer engine: {output, references: [{title, url}]}."""
    data = _paid("fastgpt", f"{BASE}/fastgpt", ledger, query, now, body={"query": query})
    d = data.get("data") or {}
    return {"output": str(d.get("output") or ""),
            "references": [{"title": str(r.get("title") or ""), "url": str(r.get("url") or "")}
                           for r in d.get("references") or []]}


def summarize(url: str, ledger: Ledger, now: datetime | None = None) -> str:
    """The Universal Summarizer on one page, video or document."""
    q = urllib.parse.urlencode({"url": url, "summary_type": "summary"})
    data = _paid("summarize", f"{BASE}/summarize?{q}", ledger, url, now)
    return str((data.get("data") or {}).get("output") or "")
