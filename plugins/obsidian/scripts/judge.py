"""Typed judgments — narrow yes/no and pick-one questions answered with probabilities.

A judgment backend takes one JSON `state` plus a dict of questions and returns a
probability per question, never prose. Callers combine the numbers in code: thresholds,
gates, and what happens next are policy and live with the caller, not in question text
(contract/ROUTING.md, "Typed-judgment models").

The shipped backend is `jev`: TypeSafe's System One model, reached over its HTTP API
(OpenRouter by default). It is one POST, so this module speaks the wire format with the
stdlib, like `vault_utils._http_llm_request`, and a fresh clone needs no extra package.

The representation is backend-neutral on purpose. A later local logit-readout backend
can answer `choice` directly and `noul` as a two-option choice; it cannot answer an
ordered `score`, so nothing in this plugin asks one. Such a backend sets
`Answer.calibrated = False` and callers keep a separate threshold table for it.

This module never decides what is sent. Callers pass text from notes they reached through
`vault_utils.discover_notes(exclude=...)` or that the user named explicitly.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vault_utils import PROFILE_PLUGIN_NAME, profile_value

DEFAULT_BACKEND = "jev"
DEFAULT_BASE_URL = "https://openrouter.ai/api"
DEFAULT_MODEL = "jev-latest"
SYSTEM_ONE_PATH = "/v1/systemone"
API_KEY_ENV = (f"TOOLKIT_{PROFILE_PLUGIN_NAME.upper()}_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
USD_PER_M_INPUT = 0.042  # jev list price; output is free. Used only when the API reports no cost.
MAX_CHOICE_OPTIONS = 255
HTTP_TIMEOUT = 60


@dataclass(frozen=True)
class Question:
    """One narrow judgment. `criteria`: noul -> {"true": ..., "false": ...} or None;
    choice -> {label: description}."""

    kind: Literal["noul", "choice"]
    instructions: str
    criteria: dict[str, str] | None = None


@dataclass(frozen=True)
class Answer:
    kind: str
    p: float | None = None  # noul: P(yes)
    probs: dict[str, float] = field(default_factory=dict)  # choice: label -> probability
    top: str | None = None  # choice: most probable label
    calibrated: bool = True

    def margin(self) -> float:
        """Distance between the two most probable choice labels (1.0 for a lone label)."""
        ranked = sorted(self.probs.values(), reverse=True)
        return ranked[0] - ranked[1] if len(ranked) > 1 else 1.0


@dataclass
class Usage:
    backend: str = DEFAULT_BACKEND
    model: str = ""
    requests: int = 0
    input_tokens: int = 0
    usd: float = 0.0
    splits: int = 0
    skipped: list[str] = field(default_factory=list)
    last_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend, "model": self.model, "requests": self.requests,
            "input_tokens": self.input_tokens, "usd": round(self.usd, 6),
            "splits": self.splits, "skipped": self.skipped,
        }


class JudgmentUnavailable(RuntimeError):
    """No usable backend (disabled, or no API key). The normal state before adoption:
    callers report SKIPPED and carry on; they never guess and never write a DLQ note."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class JudgmentFailed(RuntimeError):
    """A configured backend answered nothing, even after splitting the request. Not a
    normal degrade path: the caller records it in the dead-letter queue."""


class StateTooLarge(JudgmentFailed):
    """The backend refused the request for its size. Halving the questions cannot help,
    since every half carries the same state; the caller has to send less state per request.
    [earned: 2026-09-22, first run on a 1,476-note vault — one capture with 40 widened
    candidates hit `max_tokens_exceeded`, and the halving retried it seven times for nothing]"""


class _CallError(RuntimeError):
    def __init__(self, detail: str, retryable_by_split: bool):
        super().__init__(detail)
        self.retryable_by_split = retryable_by_split


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config(vault: Path) -> dict[str, str]:
    return {
        "backend": str(profile_value(vault, "judgment_backend", DEFAULT_BACKEND)).strip().lower(),
        "base_url": str(profile_value(vault, "judgment_base_url", DEFAULT_BASE_URL)).rstrip("/"),
        "model": str(profile_value(vault, "judgment_model", DEFAULT_MODEL)),
    }


def _api_key() -> str | None:
    """Secrets come from the environment only (contract/PROFILE.md), never the profile note."""
    for name in API_KEY_ENV:
        if os.environ.get(name):
            return os.environ[name]
    return None


def unavailable_reason(vault: Path) -> str | None:
    cfg = load_config(vault)
    if cfg["backend"] in ("none", "off", ""):
        return "disabled"
    if cfg["backend"] not in _BACKENDS:
        return f"unknown-backend:{cfg['backend']}"
    if not _api_key():
        return "no-key"
    return None


def available(vault: Path) -> bool:
    return unavailable_reason(vault) is None


def policy_for(table: dict[str, dict[str, float]], backend: str) -> dict[str, float]:
    """A caller's per-backend policy/threshold table, looked up the same safe way everywhere:
    raise JudgmentFailed — the same exception a backend that answers nothing raises, so every
    existing caller's degrade path (a DLQ note, or SKIPPED/failed reporting) already handles
    this too — instead of a bare KeyError, or silently substituting another backend's
    calibration, when `backend` has no entry. `judge.judge()` only ever returns a `backend`
    that is registered in `_BACKENDS`, but a table here can still lag behind `_BACKENDS`
    when a new backend is added without updating every caller's table."""
    if backend not in table:
        raise JudgmentFailed(f"no policy for judgment backend {backend!r}; add one before using it")
    return table[backend]


# ---------------------------------------------------------------------------
# jev backend (TypeSafe System One wire format)
# ---------------------------------------------------------------------------


def _post(url: str, payload: dict, headers: dict[str, str]) -> dict:
    """The one network call in this module. Evals replace it with a stub."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        if "max_tokens_exceeded" in detail:
            raise StateTooLarge(f"HTTP {e.code}: {detail}") from e
        # 401/403 will not improve by asking less; everything else might (one bad question, a blip).
        raise _CallError(f"HTTP {e.code}: {detail}", retryable_by_split=e.code not in (401, 403)) from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise _CallError(str(e), retryable_by_split=True) from e


def _wire_question(q: Question) -> dict[str, Any]:
    wire: dict[str, Any] = {"type": q.kind, "instructions": q.instructions}
    if q.criteria is not None:
        wire["criteria"] = q.criteria
    return wire


def _parse_answer(raw: dict) -> Answer | None:
    kind = raw.get("type")
    if kind == "noul" and isinstance(raw.get("noul"), (int, float)):
        return Answer(kind="noul", p=float(raw["noul"]))
    if kind == "choice" and isinstance(raw.get("probabilities"), dict) and raw["probabilities"]:
        try:
            probs = {str(k): float(v) for k, v in raw["probabilities"].items()}
        except (TypeError, ValueError):
            return None
        top = raw.get("choice")
        if top not in probs:  # a label the backend did not score is not a usable top
            top = max(probs, key=probs.get)
        return Answer(kind="choice", probs=probs, top=top)
    return None


def _jev_call(cfg: dict[str, str], state: Any, questions: dict[str, Question], usage: Usage) -> dict[str, Answer]:
    payload = {
        "state": state,
        "model": cfg["model"],
        "questions": {qid: _wire_question(q) for qid, q in questions.items()},
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_api_key()}"}
    data = _post(cfg["base_url"] + SYSTEM_ONE_PATH, payload, headers)
    usage.requests += 1
    usage.model = data.get("model") or cfg["model"]
    reported = data.get("usage") or {}
    tokens = int(reported.get("input_tokens") or 0)
    usage.input_tokens += tokens
    usage.usd += float(reported["cost"]) if "cost" in reported else tokens * USD_PER_M_INPUT / 1e6
    answers = {}
    for qid in questions:
        parsed = _parse_answer((data.get("answers") or {}).get(qid) or {})
        if parsed is None:
            usage.skipped.append(qid)
        else:
            answers[qid] = parsed
    return answers


_BACKENDS: dict[str, Callable[[dict[str, str], Any, dict[str, Question], Usage], dict[str, Answer]]] = {
    "jev": _jev_call,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _ask(call, cfg, state, questions: dict[str, Question], usage: Usage) -> dict[str, Answer]:
    """One request; on a failure that asking less might fix, halve the questions (same
    state) and retry each half, down to a single question, which is then skipped."""
    try:
        return call(cfg, state, questions, usage)
    except _CallError as e:
        if not e.retryable_by_split or len(questions) == 1:
            usage.skipped.extend(questions)
            usage.last_error = str(e)
            return {}
    usage.splits += 1
    ids = list(questions)
    mid = len(ids) // 2
    left = _ask(call, cfg, state, {i: questions[i] for i in ids[:mid]}, usage)
    right = _ask(call, cfg, state, {i: questions[i] for i in ids[mid:]}, usage)
    return left | right


def judge(vault: Path, state: Any, questions: dict[str, Question]) -> tuple[dict[str, Answer], Usage]:
    """Answer every question over one shared state. Questions cannot see each other.

    Raises JudgmentUnavailable when there is no usable backend, JudgmentFailed when a
    configured backend answered none of the questions.
    """
    reason = unavailable_reason(vault)
    if reason:
        raise JudgmentUnavailable(reason)
    if not questions:
        raise ValueError("judge() needs at least one question")
    for qid, q in questions.items():
        if q.kind == "choice" and not 2 <= len(q.criteria or {}) <= MAX_CHOICE_OPTIONS:
            raise ValueError(f"choice question {qid!r} needs 2..{MAX_CHOICE_OPTIONS} options")

    cfg = load_config(vault)
    usage = Usage(backend=cfg["backend"], model=cfg["model"])
    answers = _ask(_BACKENDS[cfg["backend"]], cfg, state, questions, usage)
    if not answers:
        raise JudgmentFailed(usage.last_error or "backend returned no answers")
    return answers, usage
