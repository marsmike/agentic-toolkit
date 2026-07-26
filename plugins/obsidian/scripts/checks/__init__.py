"""Check interface and shared data types for vault_normalize.py."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Issue:
    """A problem found during audit."""
    note: Path
    check: str          # "frontmatter", "tags", "source", "links", "summary"
    severity: str       # "error", "warning", "info"
    description: str
    proposed_fix: str


@dataclass
class FixResult:
    """A correction applied (or skipped) during fix."""
    note: Path
    check: str
    applied: bool
    description: str
