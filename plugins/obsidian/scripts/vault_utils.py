"""Shared vault utilities for the obsidian plugin's scripts.

Vault resolution, frontmatter I/O, note discovery, profile-driven LLM config, Index.md
parsing, and the dead-letter-queue (DLQ) convention — used by vault_lint.py,
vault_normalize.py, checks/*.py, search.py, and retrieval_verification.py.

Self-contained by design (no import of `core`): a plugin's scripts must run standalone
via `uv run` even if only `plugins/obsidian/` is present, per docs/PLAN.md's plugin
independence rule. Its conventions deliberately mirror `core/toolkit_core/vault.py` and
`profile.py` so behavior stays consistent across the repo.
"""
from __future__ import annotations

import copy
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COG = "⚙"
CHECK_MARK = "✓"
WARNING = "⚠"

MARKETPLACE_MARKER = Path(".claude-plugin") / "marketplace.json"

# Order matches contract/VAULT_SCHEMA.md.
PARA_FOLDERS = ("00_Memory", "01_Capture", "02_Projects", "03_Areas", "04_Resources", "05_Archive", "Templates")
ACTIVE_CONTENT_FOLDERS = ("02_Projects", "03_Areas", "04_Resources")
ARCHIVE_FOLDER = "05_Archive"
EXCLUDE_DIRS = {"assets", "node_modules", "out", "public", "src", ".obsidian", ".smart-env", ".trash"}

# Canonical aliased index entry: `- [[rel/path/Name|Name]] — summary ⚙?`. Tolerates the
# bare `- [[Name]] — summary` form too.
ENTRY_RE = re.compile(r"^- \[\[([^\]|]+)(?:\|([^\]]+))?\]\] — (.+?)(\s*[⚙✓⚠]+)?\s*$")

PROFILE_PLUGIN_NAME = "obsidian"

DEFAULT_INFERENCE: dict[str, Any] = {
    "backend": "ollama",
    "base_url": "http://localhost:11434",
    "model": None,  # unset by default — LLM-assisted checks skip cleanly, never guess a model
    "temperature": 0.2,
    "max_tokens": 120,
}


# ---------------------------------------------------------------------------
# Vault resolution (contract/PROFILE.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VaultResolution:
    path: Path | None
    source: str  # "env:TOOLKIT_VAULT" | "default:./vault" | "not-found"


def find_repo_root(start: Path | None = None) -> Path | None:
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / MARKETPLACE_MARKER).is_file():
            return candidate
    return None


def resolve_vault() -> VaultResolution:
    """`TOOLKIT_VAULT` env var wins; otherwise `./vault` relative to the repo root."""
    env_value = os.environ.get("TOOLKIT_VAULT")
    if env_value:
        return VaultResolution(Path(env_value).expanduser().resolve(), "env:TOOLKIT_VAULT")
    repo_root = find_repo_root(Path.cwd()) or find_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        return VaultResolution(None, "not-found")
    return VaultResolution(repo_root / "vault", "default:./vault")


def require_vault() -> Path:
    """Resolve the vault or raise SystemExit(1) with a clear message. For CLI entry points."""
    res = resolve_vault()
    if res.path is None:
        raise SystemExit(
            "No vault found: set TOOLKIT_VAULT or run from inside the agentic-toolkit repo "
            "(needs .claude-plugin/marketplace.json above the cwd)."
        )
    if not res.path.is_dir():
        raise SystemExit(f"Vault path does not exist: {res.path} (resolved via {res.source})")
    return res.path


# ---------------------------------------------------------------------------
# Profile (contract/PROFILE.md resolution order: env -> vault note -> default)
# ---------------------------------------------------------------------------


def _profile_note_path(vault: Path) -> Path:
    return vault / "Config" / "toolkit" / f"{PROFILE_PLUGIN_NAME}.md"


def read_profile(vault: Path) -> dict:
    """This plugin's profile frontmatter, or {} if no profile note exists."""
    path = _profile_note_path(vault)
    if not path.is_file():
        return {}
    try:
        fm, _ = read_frontmatter(path)
    except UnparseableFrontmatter:
        return {}
    return fm


def profile_value(vault: Path, key: str, default: Any = None) -> Any:
    """Resolve one profile value: `TOOLKIT_OBSIDIAN_<KEY>` env var -> profile note -> default."""
    env_name = f"TOOLKIT_OBSIDIAN_{key.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
    note = read_profile(vault)
    if key in note and note[key] not in (None, ""):
        return note[key]
    return default


def load_inference_config(vault: Path) -> dict[str, Any]:
    """Merge DEFAULT_INFERENCE with profile_value overrides for each inference_* field."""
    cfg = copy.deepcopy(DEFAULT_INFERENCE)
    cfg["backend"] = profile_value(vault, "inference_backend", cfg["backend"])
    cfg["base_url"] = profile_value(vault, "inference_base_url", cfg["base_url"])
    cfg["model"] = profile_value(vault, "inference_model", cfg["model"])
    return cfg


# ---------------------------------------------------------------------------
# Frontmatter I/O — tolerant per contract/VAULT_SCHEMA.md's "floor, not ceiling" rule
# ---------------------------------------------------------------------------


class UnparseableFrontmatter(Exception):
    """A `---` block exists but is not valid YAML.

    Must never be conflated with "no frontmatter": returning {} for a note that has real
    metadata makes every caller believe every field is missing, and a write-back then
    emits a *second* frontmatter block above the first — Obsidian reads only the first,
    so the note silently loses its real tags/source/description. Every write path must
    call read_frontmatter(strict=True) and handle this exception instead of proceeding.
    """


_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def read_frontmatter(path: Path, strict: bool = False) -> tuple[dict, str]:
    """Parse YAML frontmatter. Returns (frontmatter, body); ({}, full_text) if none present.

    With strict=True, raises UnparseableFrontmatter on a `---` block that fails to parse
    instead of silently treating it as absent. Every write path must use strict=True.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        if strict:
            raise UnparseableFrontmatter(f"{path}: {exc}") from exc
        return {}, text

    if data is None:
        data = {}
    if not isinstance(data, dict):
        if strict:
            raise UnparseableFrontmatter(f"{path}: frontmatter block did not parse to a mapping")
        return {}, text

    return dict(data), text[match.end():]


def write_frontmatter(path: Path, frontmatter: dict, body: str) -> None:
    """Write frontmatter + body back atomically. Unknown/extra keys are preserved verbatim
    since callers only ever mutate a dict they first read with read_frontmatter."""
    stream = io.StringIO()
    yaml.safe_dump(frontmatter, stream, sort_keys=False, allow_unicode=True, default_flow_style=False)
    atomic_write(path, f"---\n{stream.getvalue()}---\n{body}")


def atomic_write(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Note discovery
# ---------------------------------------------------------------------------


def _has_index_false(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            if f.readline().strip() != "---":
                return False
            for line in f:
                if line.strip() == "---":
                    return False
                if re.match(r"^\s*index\s*:\s*false\s*$", line):
                    return True
    except OSError:
        return False
    return False


def _is_recent(path: Path, cutoff_ts: float, since: str, distilled_only: bool) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return False
    m = re.search(r"^processed_date:\s*['\"]?(\d{4}-\d{2}-\d{2})", head, re.MULTILINE)
    if m:
        return m.group(1) >= since
    if distilled_only:
        return False
    try:
        return path.stat().st_mtime >= cutoff_ts
    except OSError:
        return False


def discover_notes(
    vault: Path,
    scope: str | None = None,
    include_archive: bool = False,
    exclude: Sequence[str] | None = None,
    since: str | None = None,
    distilled_only: bool = False,
) -> list[Path]:
    """Walk active PARA folders (02-04) and return eligible .md paths, sorted POSIX-wise.

    Per contract/VAULT_SCHEMA.md, 00_Memory/01_Capture/05_Archive are excluded from any
    generated view by default; pass include_archive=True to add 05_Archive explicitly
    (never 00_Memory or 01_Capture — those are never in scope for search/enrichment).
    """
    folders = (scope,) if scope else ACTIVE_CONTENT_FOLDERS + ((ARCHIVE_FOLDER,) if include_archive else ())
    exclude = tuple(exclude or ())
    cutoff_ts = time.mktime(time.strptime(since, "%Y-%m-%d")) if since else None

    found: list[Path] = []
    for folder in folders:
        root = vault / folder
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for fn in filenames:
                if not fn.endswith(".md") or fn.startswith("."):
                    continue
                p = Path(dirpath) / fn
                if _has_index_false(p):
                    continue
                rel = p.relative_to(vault).as_posix()
                if any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in exclude):
                    continue
                if cutoff_ts is not None and not _is_recent(p, cutoff_ts, since, distilled_only):
                    continue
                found.append(p)
    found.sort(key=lambda p: p.as_posix())
    return found


# ---------------------------------------------------------------------------
# Capture-inbox append (contract/KNOWLEDGE_API.md's v0 surface)
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-")
    return slug or "capture"


def append_capture_note(vault: Path, origin: str, title: str, content: str) -> Path:
    """Write a new capture into 01_Capture/: flat, origin-prefixed, per contract/VAULT_SCHEMA.md.

    `content` is the full file text (frontmatter + body) — callers build it themselves
    since capture shape varies by origin; this only handles placement and naming.
    """
    capture_dir = vault / "01_Capture"
    capture_dir.mkdir(parents=True, exist_ok=True)
    dest = capture_dir / f"{origin}-{_slugify(title)}.md"
    n = 2
    while dest.exists():
        dest = capture_dir / f"{origin}-{_slugify(title)}-{n}.md"
        n += 1
    dest.write_text(content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Dead-letter queue — 00_Memory/dlq/ (contract's doctor-surfaced DLQ convention)
# ---------------------------------------------------------------------------


def write_dlq_note(
    vault: Path,
    slug: str,
    title: str,
    what_happened: str,
    why_recorded: str,
    resolution: str = "Unresolved — needs manual review.",
    confidence: str = "low",
    related: Sequence[str] | None = None,
) -> Path:
    """Write a dead-letter entry to 00_Memory/dlq/ instead of silently guessing.

    Matches the vault's existing DLQ convention (see 00_Memory/dlq/*.md in the example
    vault): frontmatter carries description/status/created/confidence; the body has
    "What happened" / "Why it's here" / "Resolution" sections plus a Related list.
    Every script in this plugin that can fail ambiguously (LLM backend down, placement
    genuinely unclear, search index untrustworthy) calls this rather than proceeding.
    """
    dlq_dir = vault / "00_Memory" / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    dest = dlq_dir / f"{today}-{slug}.md"
    n = 2
    while dest.exists():
        dest = dlq_dir / f"{today}-{slug}-{n}.md"
        n += 1

    related_lines = "\n".join(f"- [[{r}]]" for r in (related or [])) or "- (none)"
    fm = {
        "description": title,
        "status": "active",
        "created": today,
        "tags": ["domain/toolkit-meta"],
        "confidence": confidence,
    }
    body = (
        f"\n# DLQ — {title}\n\n"
        f"**What happened:** {what_happened}\n\n"
        f"**Why it's here and not just a skipped step:** {why_recorded}\n\n"
        f"**Resolution:** {resolution}\n\n"
        f"## Related\n\n{related_lines}\n"
    )
    write_frontmatter(dest, fm, body)
    return dest


# ---------------------------------------------------------------------------
# LLM chat — backend-agnostic (Ollama or OpenAI-compatible), profile-configured
# ---------------------------------------------------------------------------


class NoModelConfigured(RuntimeError):
    """No inference_model set in profile/env. Callers should skip cleanly, not guess."""


def llm_chat(
    system_prompt: str,
    user_content: str,
    vault: Path,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_schema: dict[str, Any] | None = None,
) -> str:
    """Backend-agnostic LLM chat, configured via the profile (see profile.example.md).

    Raises NoModelConfigured if no model is set — a fresh clone with no Ollama running
    should skip LLM-assisted checks cleanly rather than hang or crash on a connection
    error. Raises RuntimeError for any other failure (backend unreachable, bad response).

    response_schema constrains generation to a JSON Schema for any caller that will
    json.loads() the result — unconstrained small local models emit markdown-fenced or
    malformed JSON at high rates. Ollama maps it to `format`; OpenAI-compatible backends
    to `response_format: json_schema`.
    """
    cfg = load_inference_config(vault)
    if not cfg.get("model"):
        raise NoModelConfigured(
            "No inference_model configured — set it in Config/toolkit/obsidian.md or "
            "TOOLKIT_OBSIDIAN_INFERENCE_MODEL. See profile.example.md."
        )

    temp = temperature if temperature is not None else cfg["temperature"]
    mtok = max_tokens if max_tokens is not None else cfg["max_tokens"]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    if cfg["backend"] == "ollama":
        url = f"{cfg['base_url']}/api/chat"
        payload: dict[str, Any] = {
            "model": cfg["model"], "messages": messages, "stream": False,
            "options": {"temperature": temp, "num_predict": mtok},
        }
        if response_schema is not None:
            payload["format"] = response_schema
        return _http_llm_request(url, payload, extract_ollama=True)

    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": cfg["model"], "messages": messages, "temperature": temp,
        "max_tokens": mtok, "stream": False,
    }
    if response_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": response_schema, "strict": True},
        }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("TOOLKIT_OBSIDIAN_INFERENCE_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return _http_llm_request(url, payload, extract_ollama=False, headers=headers)


def _http_llm_request(
    url: str, payload: dict, extract_ollama: bool, headers: dict | None = None,
) -> str:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers=headers or {"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM request failed: {e}. URL: {url}") from e

    data = json.loads(raw)
    if extract_ollama:
        text = ((data.get("message") or {}).get("content") or "").strip()
    else:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI-compatible API returned no choices.")
        text = (choices[0].get("message", {}).get("content") or "").strip()

    if not text:
        raise RuntimeError("LLM returned empty content.")
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Index.md parsing / updating
# ---------------------------------------------------------------------------


def parse_existing_index(index_path: Path) -> dict[str, tuple[str, str]]:
    """Index.md -> {relative_path: (summary, markers)}. markers is "⚙"/"✓"/"⚠"/"" ."""
    if not index_path.exists():
        return {}
    result: dict[str, tuple[str, str]] = {}
    for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ENTRY_RE.match(line)
        if not m:
            continue
        result[m.group(1).strip()] = (m.group(3).strip(), (m.group(4) or "").strip())
    return result


def update_index_markers(index_path: Path, markers: dict[str, str]) -> None:
    """Update markers (⚙/✓/⚠) on existing Index.md entries in place."""
    if not index_path.exists():
        return
    lines = index_path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines = []
    for line in lines:
        m = ENTRY_RE.match(line)
        if m and m.group(1).strip() in markers:
            alias = f"|{m.group(2)}" if m.group(2) else ""
            marker = markers[m.group(1).strip()]
            suffix = f" {marker}" if marker else ""
            line = f"- [[{m.group(1).strip()}{alias}]] — {m.group(3).strip()}{suffix}"
        new_lines.append(line)
    atomic_write(index_path, "\n".join(new_lines) + "\n")
