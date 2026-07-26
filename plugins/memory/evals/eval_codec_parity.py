"""Eval: memory_vault's hand-rolled frontmatter codec (scripts/memory_vault.py) does
what its module docstring promises — for the flat-scalars/lists shape this plugin
actually writes, and for input outside that shape.

Two checks:

(a) Round trip a fixture note — unknown fields (`maturity`, `ring`), unicode (umlauts,
    an em dash), and a colon-in-value string — through read -> modify -> write -> read,
    and confirm every field survives unchanged. If `pyyaml` is importable (it's a repo
    dev dependency, see core/pyproject.toml — never a dependency of the shipped plugin
    scripts themselves), also confirm `yaml.safe_load` parses the written file
    identically to the codec. If pyyaml isn't importable, that half is skipped with a
    detail rather than failing — this eval must still pass in an environment that only
    has stdlib.

(b) Feed the codec a nested mapping and a `|` block scalar and confirm it raises
    `ValueError` — the documented contract added to memory_vault.py's module docstring
    — rather than silently mis-parsing (the behavior an earlier review flagged).

Fixture-driven, no network. Writes, so runs against a sandbox copy of ./vault.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

FIXTURE_FRONTMATTER = {
    "description": "Café notes — Müller's review",
    "kind": "fact",
    "status": "active",
    "maturity": "seedling",  # unknown to this plugin's own schema, on purpose
    "ring": 2,               # ditto
    "detail": "See section: intro for context",  # colon inside a plain scalar value
    "tags": ["agent/memory", "domain/toolkit-meta"],
}

NESTED_MAPPING_FRONTMATTER = "outer:\n  inner: 1\n  other: 2\n"
BLOCK_SCALAR_FRONTMATTER = "body: |\n  line one\n  line two\n"


def run(vault: Path) -> dict:
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import memory_vault as mv

    sandbox_vault = make_sandbox(vault)
    problems: list[str] = []
    parity_detail = ""
    try:
        # --- (a) read -> modify -> write -> read round trip ---
        note_path = sandbox_vault / "00_Memory" / "notes" / "codec-parity-fixture.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        mv.write_note(note_path, dict(FIXTURE_FRONTMATTER), "# Codec parity fixture\n\nBody text.\n")

        fm1, body1 = mv.read_note(note_path)
        fm1["ring"] = 3
        fm1["reviewed"] = True
        mv.write_note(note_path, fm1, body1)

        fm2, _body2 = mv.read_note(note_path)

        expected = dict(FIXTURE_FRONTMATTER)
        expected["ring"] = 3
        expected["reviewed"] = True
        for key, value in expected.items():
            if fm2.get(key) != value:
                problems.append(f"field {key!r} did not survive read-modify-write-read: expected {value!r}, got {fm2.get(key)!r}")

        try:
            import yaml
        except ImportError:
            parity_detail = "pyyaml unavailable — parity not checked"
        else:
            raw_text = note_path.read_text(encoding="utf-8")
            fm_block = raw_text.split("---", 2)[1]
            yaml_parsed = yaml.safe_load(fm_block) or {}
            disagreements = [
                key for key, value in expected.items() if yaml_parsed.get(key) != value
            ]
            if disagreements:
                problems.append(
                    f"yaml.safe_load disagrees with the codec on {disagreements!r}: "
                    f"yaml={{k: yaml_parsed.get(k) for k in disagreements}}"
                )
            parity_detail = "codec output parses identically under yaml.safe_load"

        # --- (b) nested mapping / block scalar: must raise per documented contract ---
        docstring = mv.__doc__ or ""
        if "ValueError" not in docstring:
            problems.append("memory_vault module docstring no longer documents a raise-on-non-flat-input contract")

        for label, raw in (("nested mapping", NESTED_MAPPING_FRONTMATTER), ("block scalar", BLOCK_SCALAR_FRONTMATTER)):
            try:
                result = mv.parse_frontmatter(raw)
            except ValueError:
                pass
            except Exception as exc:
                problems.append(f"{label} input raised {type(exc).__name__}, not ValueError: {exc}")
            else:
                problems.append(f"{label} input did not raise — codec silently mis-parsed it as {result!r}")

        if problems:
            return {"eval": "codec_parity", "pass": False, "detail": "; ".join(problems)}
        return {
            "eval": "codec_parity",
            "pass": True,
            "detail": f"round trip preserved all fields ({parity_detail}); nested mapping and block scalar both raised ValueError",
        }
    finally:
        teardown_sandbox(sandbox_vault)
