"""Shared vault utilities for the radar plugin's scripts.

A trimmed copy of plugins/obsidian/scripts/vault_utils.py: vault resolution, the profile,
frontmatter I/O, atomic writes and the dead-letter queue — nothing else. Self-contained by
design (no import of `core` or a sibling plugin, contract/KNOWLEDGE_API.md); the frontmatter
reader is held to toolkit_core's by core/tests/test_contract.py.
"""
from __future__ import annotations

import io
import os
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MARKETPLACE_MARKER = Path(".claude-plugin") / "marketplace.json"

PROFILE_PLUGIN_NAME = "radar"


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
    """Resolve one profile value: `TOOLKIT_RADAR_<KEY>` env var -> profile note -> default."""
    env_name = f"TOOLKIT_{PROFILE_PLUGIN_NAME.upper()}_{key.upper()}"
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
    stream = io.StringIO()
    yaml.safe_dump(frontmatter, stream, sort_keys=False, allow_unicode=True, default_flow_style=False)
    atomic_write(path, f"---\n{stream.getvalue()}---\n{body}")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
# Dead-letter queue — 00_Memory/dlq/, shared with every other plugin
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
    """Write a dead-letter entry to 00_Memory/dlq/ instead of silently guessing. Same shape
    as the obsidian plugin's, so the doctor reads both alike."""
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
