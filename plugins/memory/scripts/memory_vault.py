"""memory_vault.py — minimal, dependency-free vault primitives for the memory plugin.

Deliberately reimplements a small, controlled subset of YAML frontmatter I/O rather
than depending on PyYAML: every note this plugin ever writes uses only scalars
(str/int/float/bool/null) and flat lists of scalars, by construction, so a compact
hand-rolled codec covers 100% of what this plugin needs to read or write. This keeps
the SessionEnd hook (hooks/lib/session_capture.py, which imports this module) free of
any pip dependency — a hook must never fail because a venv wasn't set up.

Self-contained by design (no import of `core` or a sibling plugin): a plugin's scripts
must run standalone even if only `plugins/memory/` is present, matching the
independence rule plugins/obsidian/scripts/vault_utils.py documents for itself.

Codec contract: `parse_frontmatter`/`read_note` accept only flat scalars and flat
lists of scalars — the exact shape `dump_frontmatter`/`write_note` ever produce.
Input outside that shape (a nested mapping, a `|`/`>` block scalar) is not silently
reinterpreted or dropped: parsing raises `ValueError` naming the offending key,
rather than guessing at a structure this codec was never built to represent.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

MARKETPLACE_MARKER = Path(".claude-plugin") / "marketplace.json"
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)

PROFILE_PLUGIN_NAME = "memory"


# ---------------------------------------------------------------------------
# Vault resolution (contract/PROFILE.md: TOOLKIT_VAULT env var -> ./vault -> none)
# ---------------------------------------------------------------------------


def find_repo_root(start: Path) -> Path | None:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / MARKETPLACE_MARKER).is_file():
            return candidate
    return None


def resolve_vault() -> Path | None:
    """`TOOLKIT_VAULT` env var wins if set and points at a real directory; otherwise
    `./vault` relative to the repo root. Returns None (never raises) when nothing is
    resolvable — callers (the SessionEnd hook) treat that as a silent no-op, per
    contract/PROFILE.md's resolution order and this plugin's "never break a session
    for users without a vault" requirement.
    """
    env_value = os.environ.get("TOOLKIT_VAULT")
    if env_value:
        p = Path(env_value).expanduser().resolve()
        return p if p.is_dir() else None
    repo_root = find_repo_root(Path.cwd()) or find_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        return None
    candidate = repo_root / "vault"
    return candidate if candidate.is_dir() else None


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "note"


def project_name(cwd: str | None) -> str:
    if not cwd:
        return "unknown"
    return Path(cwd).name or "unknown"


# ---------------------------------------------------------------------------
# Minimal frontmatter codec — flat scalars and flat lists of scalars only.
# Not a general YAML parser; sufficient for every shape this plugin emits.
# ---------------------------------------------------------------------------


def _dump_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    needs_quoting = (
        text == ""
        or text != text.strip()
        or text.lower() in ("true", "false", "null", "~")
        or re.search(r'[:#\[\]{}&*!|>\'"%@`]', text)
    )
    return json.dumps(text) if needs_quoting else text


def _parse_scalar(text: str):
    text = text.strip()
    if text == "" or text in ("~",) or text.lower() == "null":
        return None
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text[1:-1]
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        return text[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def dump_frontmatter(frontmatter: dict) -> str:
    lines: list[str] = []
    for key, value in frontmatter.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_dump_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    return "\n".join(lines) + "\n"


_BLOCK_SCALAR_RE = re.compile(r"[|>][+-]?\d*")


def parse_frontmatter(raw: str) -> dict:
    data: dict = {}
    key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") or line.startswith("- "):
            item = line.split("- ", 1)[1]
            if key is not None:
                if not isinstance(data.get(key), list):
                    data[key] = []
                data[key].append(_parse_scalar(item))
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            if k != k.lstrip():
                # Indented "key: ..." that isn't a "- " list item -> a nested mapping,
                # which this codec cannot represent. Fail loud rather than silently
                # promoting it to a bogus top-level key (see module docstring).
                raise ValueError(
                    f"memory_vault's frontmatter codec supports only flat scalars and "
                    f"flat lists of scalars; nested mapping under {key!r} is not supported"
                )
            key = k.strip()
            v = v.strip()
            if _BLOCK_SCALAR_RE.fullmatch(v):
                raise ValueError(
                    f"memory_vault's frontmatter codec supports only flat scalars and "
                    f"flat lists of scalars; block scalar for key {key!r} is not supported"
                )
            if v == "[]":
                data[key] = []
            elif v == "":
                data[key] = None  # becomes a list if bullet lines follow
            else:
                data[key] = _parse_scalar(v)
    return data


def read_note(path: Path) -> tuple[dict, str]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    return parse_frontmatter(match.group(1)), text[match.end() :]


def unique_path(directory: Path, base_name: str, suffix: str = ".md") -> Path:
    """`directory/base_name.md`, or `-2`/`-3`/... appended if that already exists.

    Shared by every writer that must never overwrite an existing note on collision
    (a DLQ entry, a session record) — same suffix rule, one implementation.
    """
    dest = directory / f"{base_name}{suffix}"
    n = 2
    while dest.exists():
        dest = directory / f"{base_name}-{n}{suffix}"
        n += 1
    return dest


def write_note(path: Path, frontmatter: dict, body: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\n{dump_frontmatter(frontmatter)}---\n{body}"
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Dead-letter queue — 00_Memory/dlq/, matching plugins/obsidian's convention
# ---------------------------------------------------------------------------


def write_dlq_note(
    vault: Path,
    slug: str,
    title: str,
    what_happened: str,
    why_recorded: str,
    resolution: str = "Unresolved — needs manual review.",
    confidence: str = "low",
) -> Path:
    """Write a dead-letter entry instead of silently guessing or erroring, matching
    the vault's DLQ convention (description/status/created/confidence frontmatter,
    a What happened / Why it's here / Resolution body) — see 00_Memory/dlq/*.md in
    the example vault and plugins/obsidian/scripts/vault_utils.write_dlq_note()."""
    dlq_dir = Path(vault) / "00_Memory" / "dlq"
    today = time.strftime("%Y-%m-%d")
    dest = unique_path(dlq_dir, f"{today}-{slug}")
    fm = {
        "description": title,
        "status": "active",
        "created": today,
        "confidence": confidence,
        "tags": ["agent/memory", "domain/toolkit-meta"],
    }
    body = (
        f"# DLQ — {title}\n\n"
        f"**What happened:** {what_happened}\n\n"
        f"**Why it's here:** {why_recorded}\n\n"
        f"**Resolution:** {resolution}\n"
    )
    write_note(dest, fm, body)
    return dest


# ---------------------------------------------------------------------------
# Journal — 00_Memory/journal/<date>.md, matching the vault's own convention
# (see 00_Memory/README.md in the example vault); this is v1's `/journal`
# command's format, folded in here as a shared primitive rather than a
# standalone skill (see plugins/memory/README.md's dropped-components table).
# ---------------------------------------------------------------------------


def append_journal_line(vault: Path, entry: str) -> Path:
    today = time.strftime("%Y-%m-%d")
    journal_dir = Path(vault) / "00_Memory" / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_file = journal_dir / f"{today}.md"
    if not entry.endswith("\n"):
        entry += "\n"
    if not journal_file.exists():
        header = (
            "---\n"
            f'description: "Journal: {today}"\n'
            "kind: journal\n"
            "tags:\n"
            "  - agent/journal\n"
            "  - agent/self\n"
            "---\n\n"
            f"# {today}\n\n"
        )
        journal_file.write_text(header + entry, encoding="utf-8")
    else:
        with journal_file.open("a", encoding="utf-8") as f:
            f.write(entry)
    return journal_file


# ---------------------------------------------------------------------------
# Profile (contract/PROFILE.md: env -> $VAULT/Config/toolkit/memory.md -> default)
# ---------------------------------------------------------------------------


def _profile_note_path(vault: Path) -> Path:
    return Path(vault) / "Config" / "toolkit" / f"{PROFILE_PLUGIN_NAME}.md"


def read_profile(vault: Path) -> dict:
    """This plugin's profile frontmatter, or {} if no such note exists — a missing
    profile is a normal, fully-functional state."""
    path = _profile_note_path(vault)
    if not path.is_file():
        return {}
    fm, _ = read_note(path)
    return fm


def profile_value(vault: Path, key: str, default=None):
    """Resolve one profile value: `TOOLKIT_MEMORY_<KEY>` env var -> profile note field
    -> `default`. The type of `default` decides how an env var string is coerced."""
    env_name = f"TOOLKIT_MEMORY_{key.upper()}"
    if env_name in os.environ:
        raw = os.environ[env_name]
        if isinstance(default, list):
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(default, bool):
            return raw.strip().lower() in ("1", "true", "yes")
        if isinstance(default, int):
            try:
                return int(raw)
            except ValueError:
                return default
        return raw
    profile = read_profile(vault)
    if key in profile:
        return profile[key]
    return default
