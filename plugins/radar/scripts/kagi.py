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
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        raise KagiError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}") from e
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        raise KagiError(f"request failed: {e}") from e


class Ledger:
    """`kagi-ledger.jsonl` in the radar dir: one row per call, {at, kind, query, usd, balance}."""

    def __init__(self, path: Path, weekly_budget: float):
        self.path, self.weekly_budget = path, weekly_budget

    def rows(self) -> list[dict]:
        if not self.path.is_file():
            return []
        return [json.loads(ln) for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def spent_this_week(self, now: datetime) -> float:
        since = now - timedelta(days=7)
        return sum(r["usd"] for r in self.rows() if datetime.fromisoformat(r["at"]) >= since)

    def last_balance(self) -> float | None:
        rows = [r for r in self.rows() if r.get("balance") is not None]
        return rows[-1]["balance"] if rows else None

    def record(self, row: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


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
