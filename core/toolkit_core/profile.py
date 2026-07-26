"""Profile resolution: env var -> vault note frontmatter -> caller default.

Per contract/PROFILE.md, a plugin's configuration resolves in this order:

1. `TOOLKIT_<PLUGIN>_<KEY>` environment variable.
2. `$VAULT/Config/toolkit/<plugin>.md` frontmatter.
3. The caller-supplied default.

A missing profile note is a normal condition, not an error — plugins run fine with no
profile configured, falling through to their shipped defaults.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from toolkit_core.vault import parse_frontmatter


def profile_note_path(vault_path: Path, plugin: str) -> Path:
    return Path(vault_path) / "Config" / "toolkit" / f"{plugin}.md"


def read_profile_note(vault_path: Path, plugin: str) -> dict:
    """Return a plugin's profile frontmatter, or {} if no such note exists."""
    path = profile_note_path(vault_path, plugin)
    if not path.is_file():
        return {}
    frontmatter, _, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return frontmatter


def _env_prefix(plugin: str) -> str:
    return f"TOOLKIT_{plugin.upper()}_"


def env_overrides(plugin: str) -> dict:
    """All `TOOLKIT_<PLUGIN>_<KEY>` env vars currently set, keyed by lowercased <KEY>."""
    prefix = _env_prefix(plugin)
    return {
        name[len(prefix) :].lower(): value
        for name, value in os.environ.items()
        if name.startswith(prefix)
    }


def resolve_profile(vault_path: Path, plugin: str) -> dict:
    """The full merged profile for a plugin: note frontmatter, with env vars overriding."""
    merged = dict(read_profile_note(vault_path, plugin))
    merged.update(env_overrides(plugin))
    return merged


def get(vault_path: Path, plugin: str, key: str, default=None):
    """Resolve one profile value: env var -> note field -> default."""
    env_name = f"{_env_prefix(plugin)}{key.upper()}"
    if env_name in os.environ:
        return os.environ[env_name]
    note = read_profile_note(vault_path, plugin)
    if key in note:
        return note[key]
    return default


def known_plugins(repo_root: Path | None) -> list[str]:
    """Plugin names declared in the repo's `.claude-plugin/marketplace.json`, or []."""
    if repo_root is None:
        return []
    marketplace_path = Path(repo_root) / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        return []
    try:
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [entry["name"] for entry in data.get("plugins", []) if "name" in entry]
