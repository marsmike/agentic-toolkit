"""Vault resolution and frontmatter I/O.

Resolution order (contract/PROFILE.md): the `TOOLKIT_VAULT` env var wins; otherwise the
vault is `./vault` relative to the repo root, found by walking up from this package's
install location and from the current working directory, looking for
`.claude-plugin/marketplace.json`.

Frontmatter I/O is tolerant per contract/VAULT_SCHEMA.md's "floor, not ceiling" rule:
parsing never rejects a note for carrying an unrecognized field, and a write-back never
drops a field the caller didn't touch. `FrontmatterError` is raised only for YAML that
fails to parse at all.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MARKETPLACE_MARKER = Path(".claude-plugin") / "marketplace.json"

# PARA folders, in the order they appear in contract/VAULT_SCHEMA.md.
PARA_FOLDERS = (
    "00_Memory",
    "01_Capture",
    "02_Projects",
    "03_Areas",
    "04_Resources",
    "05_Archive",
    "Templates",
)

# Folders that search, enrichment, and generated indexes are allowed to consider.
ACTIVE_CONTENT_FOLDERS = ("02_Projects", "03_Areas", "04_Resources")

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


class FrontmatterError(ValueError):
    """Frontmatter YAML failed to parse. Never raised for merely-unrecognized fields."""


class VaultInitError(Exception):
    """`vault init` refused to scaffold (e.g. target directory is non-empty)."""


@dataclass(frozen=True)
class VaultResolution:
    path: Path | None
    source: str  # "env:TOOLKIT_VAULT" | "default:./vault" | "not-found"
    repo_root: Path | None = None


def find_repo_root(start: Path | None = None) -> Path | None:
    """Walk upward from `start` for the directory containing `.claude-plugin/marketplace.json`."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / MARKETPLACE_MARKER).is_file():
            return candidate
    return None


def resolve_vault() -> VaultResolution:
    """Resolve the active vault path per contract/PROFILE.md's resolution order."""
    env_value = os.environ.get("TOOLKIT_VAULT")
    if env_value:
        return VaultResolution(Path(env_value).expanduser().resolve(), "env:TOOLKIT_VAULT")

    repo_root = find_repo_root(Path.cwd()) or find_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        return VaultResolution(None, "not-found")
    return VaultResolution(repo_root / "vault", "default:./vault", repo_root)


# --- Frontmatter I/O ---------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict, str, bool]:
    """Split `text` into (frontmatter dict, body, had_frontmatter).

    Raises FrontmatterError if a frontmatter block is present but its YAML doesn't parse
    or isn't a mapping. A note with no frontmatter block at all is not an error — it
    returns ({}, text, False).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, False

    raw = match.group(1)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"malformed YAML frontmatter: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter block did not parse to a mapping")

    return data, text[match.end() :], True


def render_frontmatter(frontmatter: dict, body: str, had_frontmatter: bool = True) -> str:
    """Reassemble a note. Key order is preserved (dict insertion order -> sort_keys=False)."""
    if not frontmatter and not had_frontmatter:
        return body
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{dumped}---\n{body}"


def read_note(path: Path) -> tuple[dict, str]:
    """Read a note, returning (frontmatter, body). Tolerant: unknown keys pass through."""
    text = Path(path).read_text(encoding="utf-8")
    frontmatter, body, _ = parse_frontmatter(text)
    return frontmatter, body


def write_note(path: Path, frontmatter: dict, body: str, had_frontmatter: bool = True) -> None:
    Path(path).write_text(render_frontmatter(frontmatter, body, had_frontmatter), encoding="utf-8")


def update_note_frontmatter(path: Path, updates: dict) -> dict:
    """Merge `updates` into a note's frontmatter and write it back.

    Fields not present in `updates` are left exactly as read — this is the "never
    strips a field the caller didn't touch" guarantee from contract/KNOWLEDGE_API.md.
    """
    path = Path(path)
    frontmatter, body = read_note(path)
    frontmatter.update(updates)
    write_note(path, frontmatter, body)
    return frontmatter


# --- Note listing --------------------------------------------------------------------


def list_active_notes(vault_path: Path) -> list[Path]:
    """List notes under the active-content folders only (02_Projects/03_Areas/04_Resources).

    00_Memory, 01_Capture, and 05_Archive are always excluded, per contract/VAULT_SCHEMA.md.
    """
    vault_path = Path(vault_path)
    notes: list[Path] = []
    for folder in ACTIVE_CONTENT_FOLDERS:
        folder_path = vault_path / folder
        if folder_path.is_dir():
            notes.extend(sorted(folder_path.rglob("*.md")))
    return notes


def para_folder_status(vault_path: Path) -> dict[str, bool]:
    """Which PARA folders exist directly under `vault_path`."""
    vault_path = Path(vault_path)
    return {folder: (vault_path / folder).is_dir() for folder in PARA_FOLDERS}


def note_counts(vault_path: Path) -> dict[str, int]:
    """Count of .md files (recursive) under each PARA folder that exists."""
    vault_path = Path(vault_path)
    counts = {}
    for folder in PARA_FOLDERS:
        folder_path = vault_path / folder
        counts[folder] = len(list(folder_path.rglob("*.md"))) if folder_path.is_dir() else 0
    return counts


def frontmatter_parse_errors(vault_path: Path) -> list[dict]:
    """Notes whose frontmatter block is present but fails to parse (malformed YAML only)."""
    vault_path = Path(vault_path)
    errors = []
    for note_path in sorted(vault_path.rglob("*.md")):
        try:
            text = note_path.read_text(encoding="utf-8")
            parse_frontmatter(text)
        except FrontmatterError as exc:
            errors.append({"path": str(note_path.relative_to(vault_path)), "error": str(exc)})
        except (OSError, UnicodeDecodeError) as exc:
            errors.append({"path": str(note_path.relative_to(vault_path)), "error": f"unreadable: {exc}"})
    return errors


def dlq_status(vault_path: Path) -> dict:
    """Status of the dead-letter queue at 00_Memory/dlq/ (contract/ROUTING.md's DLQ concept)."""
    dlq_path = Path(vault_path) / "00_Memory" / "dlq"
    if not dlq_path.is_dir():
        return {"present": False, "count": 0, "note": "no DLQ entries"}
    count = len(list(dlq_path.rglob("*.md")))
    return {
        "present": True,
        "count": count,
        "note": "no DLQ entries" if count == 0 else f"{count} DLQ entr{'y' if count == 1 else 'ies'}",
    }


# --- Capture-inbox append ------------------------------------------------------------


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-")
    return slug or "capture"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 2
    while True:
        candidate = path.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def append_capture(vault_path: Path, origin: str, title: str, content: str) -> Path:
    """Write a new capture into 01_Capture/: flat, origin-prefixed, per contract/VAULT_SCHEMA.md."""
    capture_dir = Path(vault_path) / "01_Capture"
    capture_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{origin}-{_slugify(title)}.md"
    dest = _dedupe_path(capture_dir / filename)
    dest.write_text(content, encoding="utf-8")
    return dest


# --- vault init scaffold ---------------------------------------------------------------


def scaffold_vault(path: Path, claude_md_template: Path, force: bool = False) -> None:
    """Scaffold a new vault at `path`: PARA folders, Config/toolkit/, CLAUDE.md, Index.md.

    Refuses a non-empty target directory unless `force` is set.
    """
    path = Path(path)
    if path.exists() and path.is_dir() and any(path.iterdir()) and not force:
        raise VaultInitError(f"{path} is not empty; pass force=True (--force) to init anyway")
    if path.exists() and path.is_file():
        raise VaultInitError(f"{path} exists and is a file, not a directory")

    path.mkdir(parents=True, exist_ok=True)
    for folder in PARA_FOLDERS:
        (path / folder).mkdir(parents=True, exist_ok=True)
    (path / "Config" / "toolkit").mkdir(parents=True, exist_ok=True)

    claude_md_template = Path(claude_md_template)
    (path / "CLAUDE.md").write_text(claude_md_template.read_text(encoding="utf-8"), encoding="utf-8")

    index_path = path / "Index.md"
    if not index_path.exists():
        index_path.write_text("", encoding="utf-8")
