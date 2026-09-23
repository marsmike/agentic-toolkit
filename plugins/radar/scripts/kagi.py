"""Kagi Search API client for the radar: discovery only, never the daily scan.

Uses the v0 search endpoint (`Authorization: Bot`), which reports the account balance with every
answer; the ledger records the balance delta as the call's cost, so spend is measured, not
estimated. A weekly budget (`kagi_weekly_budget_usd`, default 1.00) is enforced from the ledger
before every call. [v1 answered non-JSON on 2026-09-23; v0 is the documented stable shape]

What leaves the machine: the search queries from the interests note.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

SEARCH_URL = "https://kagi.com/api/v0/search"
DEFAULT_WEEKLY_BUDGET_USD = 1.00
USD_PER_SEARCH = 0.025  # list price; used only when the answer carries no balance
HTTP_TIMEOUT = 30


class NoKey(RuntimeError):
    """KAGI_API_KEY is not set. Callers report SKIPPED."""


class KagiError(RuntimeError):
    pass


class OverBudget(KagiError):
    pass


def _request(url: str) -> dict:
    """The one network call in this module. Evals replace it with a stub."""
    key = os.environ.get("KAGI_API_KEY")
    if not key:
        raise NoKey("KAGI_API_KEY is not set")
    req = urllib.request.Request(url, headers={"Authorization": f"Bot {key}"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        raise KagiError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}") from e
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        raise KagiError(f"request failed: {e}") from e


class Ledger:
    """`kagi-ledger.jsonl` in the radar dir: one row per call, {at, query, usd, balance}."""

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


def search(query: str, ledger: Ledger, limit: int = 10, now: datetime | None = None) -> list[dict[str, str]]:
    """[{url, title, snippet}] for one query; raises OverBudget before the call if the week's
    spend plus one search would pass the budget."""
    now = now or datetime.now(UTC)
    if ledger.spent_this_week(now) + USD_PER_SEARCH > ledger.weekly_budget:
        raise OverBudget(f"Kagi weekly budget ${ledger.weekly_budget:.2f} reached")
    before = ledger.last_balance()
    data = _request(f"{SEARCH_URL}?{urllib.parse.urlencode({'q': query, 'limit': limit})}")
    if data.get("error"):
        raise KagiError(str(data["error"])[:200])
    balance = (data.get("meta") or {}).get("api_balance")
    usd = USD_PER_SEARCH
    if isinstance(balance, (int, float)) and before is not None and 0 <= before - balance < 1:
        usd = round(before - balance, 6)
    ledger.record({"at": now.isoformat(), "query": query, "usd": usd, "balance": balance})
    return [{"url": str(r.get("url") or ""), "title": str(r.get("title") or ""), "snippet": str(r.get("snippet") or "")}
            for r in data.get("data") or [] if r.get("t") == 0 and r.get("url")]
