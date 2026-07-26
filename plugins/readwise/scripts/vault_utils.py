"""Shared vault utilities for the readwise plugin's scripts.

Vault resolution, frontmatter I/O, and the dead-letter-queue (DLQ) convention — used by
build_captures.py, daily_digest.py, and status.py.

Self-contained by design (no import of `core`, no import of a sibling plugin): a plugin's
scripts must run standalone via `uv run` even if only `plugins/readwise/` is present, per
contract/KNOWLEDGE_API.md's "no cross-plugin imports" rule. This is a deliberately small
subset of the same conventions `plugins/obsidian/scripts/vault_utils.py` ships — copied
rather than imported, and trimmed to only what readwise's scripts need.
"""
from __future__ import annotations

import io
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MARKETPLACE_MARKER = Path(".claude-plugin") / "marketplace.json"
PROFILE_PLUGIN_NAME = "readwise"

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
    """This plugin's profile frontmatter, or {} if no profile note exists.

    Uses `strict=True` so a profile note whose frontmatter fails to parse raises rather than
    silently reading as "no config" — that ambiguity (a note the user believes is active,
    quietly ignored) is exactly the unreadable-profile case README's DLQ convention calls
    out, so it's recorded via `write_dlq_note()` before falling back to defaults.
    """
    path = _profile_note_path(vault)
    if not path.is_file():
        return {}
    try:
        fm, _ = read_frontmatter(path, strict=True)
    except UnparseableFrontmatter as exc:
        write_dlq_note(
            vault,
            slug="readwise-profile-unreadable",
            title="Readwise profile note has unparseable frontmatter",
            what_happened=(
                f"{path} exists but its frontmatter did not parse as YAML ({exc}); every "
                "profile field fell back to its shipped default for this run."
            ),
            why_recorded=(
                "Silently defaulting the whole profile from a config note the user believes "
                "is active would hide a misconfiguration instead of surfacing it for repair."
            ),
            resolution="Fix the YAML frontmatter in the profile note, then re-run.",
            confidence="medium",
        )
        return {}
    return fm


def profile_value(vault: Path, key: str, default: Any = None) -> Any:
    """Resolve one profile value: `TOOLKIT_READWISE_<KEY>` env var -> profile note -> default."""
    env_name = f"TOOLKIT_READWISE_{key.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
    note = read_profile(vault)
    if key in note and note[key] not in (None, ""):
        return note[key]
    return default


# ---------------------------------------------------------------------------
# Frontmatter I/O — tolerant per contract/VAULT_SCHEMA.md's "floor, not ceiling" rule
# ---------------------------------------------------------------------------


class UnparseableFrontmatter(Exception):
    """A `---` block exists but is not valid YAML — must never be conflated with "no
    frontmatter" (see plugins/obsidian/scripts/vault_utils.py for the full rationale)."""


_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def read_frontmatter(path: Path, strict: bool = False) -> tuple[dict, str]:
    """Parse YAML frontmatter. Returns (frontmatter, body); ({}, full_text) if none present."""
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


def unique_path(directory: Path, base_name: str, suffix: str = ".md") -> Path:
    """`directory/base_name.md`, or `-2`/`-3`/... appended if that already exists.

    Shared by every writer here that must never overwrite an existing note on
    collision (a DLQ entry, a capture note) — same suffix rule, one implementation.
    """
    dest = directory / f"{base_name}{suffix}"
    n = 2
    while dest.exists():
        dest = directory / f"{base_name}-{n}{suffix}"
        n += 1
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
    related: list[str] | None = None,
) -> Path:
    """Write a dead-letter entry to 00_Memory/dlq/ instead of silently guessing.

    Matches the vault's DLQ convention (see 00_Memory/dlq/*.md in the example vault):
    frontmatter carries description/status/created/confidence; body has "What happened" /
    "Why it's here" / "Resolution" sections plus a Related list. Every script here that
    can fail ambiguously (a doc_id with no source_url, a coverage-check gap, an unreadable
    profile) calls this rather than proceeding on a guess.
    """
    dlq_dir = vault / "00_Memory" / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    dest = unique_path(dlq_dir, f"{today}-{slug}")

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
# Capture discovery — used by dedup checks and the daily digest
# ---------------------------------------------------------------------------


def iter_captures(vault: Path, prefix: str = "Readwise-") -> list[Path]:
    """List this plugin's own captures in 01_Capture/ — flat, per contract/VAULT_SCHEMA.md."""
    capture_dir = vault / "01_Capture"
    if not capture_dir.is_dir():
        return []
    return sorted(p for p in capture_dir.glob(f"{prefix}*.md") if p.is_file())


def find_capture_by_doc_id(vault: Path, doc_id: str, prefix: str = "Readwise-") -> Path | None:
    """Return the existing capture carrying this `readwise_doc_id`, if any.

    The dedup-before-distill rule (contract/templates/VAULT_CLAUDE.md, earned by the
    2026-07-26 X-Bookmark/Readwise double-distill collision) is primarily distill's job at
    the cross-origin level. Within readwise's own ingest, the equivalent responsibility is
    idempotency: a re-run must never write a second capture for a doc_id already present.
    """
    for path in iter_captures(vault, prefix=prefix):
        try:
            fm, _ = read_frontmatter(path)
        except UnparseableFrontmatter:
            continue
        if str(fm.get("readwise_doc_id", "")) == str(doc_id):
            return path
    return None
