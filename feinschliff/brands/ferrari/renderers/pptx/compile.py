#!/usr/bin/env python3
"""Feinschliff /compile — drift detector + catalog/stub generator.

Two modes:

* `--check` (default): verify `brands/feinschliff/claude-design/feinschliff-2026.html`
  and `brands/feinschliff/catalog/layouts.json` are in sync. Exits non-zero
  on drift or on HTML contract violations; prints the Claude Design prompt
  when the HTML doesn't meet contract.

* `--apply`: for every HTML section without a catalog entry, generate
  a catalog entry (copied from data-*) plus a stub renderer .py file
  under `layouts/`, and register the new module in `layouts/__init__.py`.
  Renderer stubs use the universal `emit_stub_layout` engine — legible
  and on-brand, not McKinsey-pretty. Replace with hand-tuned layouts via
  `/extend` when visual fidelity matters.

Conventions:
  * Each catalog entry carries an `html_label` field pointing to the
    HTML section it was generated from. Entries without `html_label` are
    code-first (e.g. `bar-chart`) — they stay in the catalog but need no
    HTML section.
  * Slug rule for new ids: lowercase, strip punctuation, split on runs
    of non-alphanumerics, join with hyphens. "MCK · 2×2 Matrix" →
    "mck-2x2-matrix".
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML_PATH = HERE.parent.parent / "claude-design" / "feinschliff-2026.html"
CATALOG_PATH = HERE.parent.parent / "catalog" / "layouts.json"
PROMPT_PATH = HERE.parent.parent.parent.parent / "references" / "claude-design-prompt.md"
LAYOUTS_DIR = HERE / "layouts"

REQUIRED_SECTION_ATTRS: tuple[str, ...] = (
    "data-label",
    "data-role",
    "data-concepts",
    "data-when-to-use",
    "data-when-not-to-use",
    "data-slots",
)

# Slot names the Feinschliff chrome paints automatically — do not round-trip
# them into the catalog's `slots` nor emit placeholders for them.
CHROME_SLOT_KEYS: set[str] = {"logo", "pgmeta", "tracker"}

BG_BY_ROLE = {
    "title-primary": "white",
    "chapter-opener": "accent",
    "closer": "ink",
}


# ─── HTML parsing ───────────────────────────────────────────────────────────


def _section_blocks(html: str) -> list[dict]:
    """Parse every `<section>` tag and its attributes — supports both quote styles.

    data-slots uses single-quoted JSON (since JSON uses double quotes inside);
    other attrs are double-quoted.
    """
    out = []
    for open_tag in re.finditer(r"<section\b([^>]*)>", html):
        attrs = open_tag.group(1)
        d = {}
        for m in re.finditer(
            r'\b(data-[a-z-]+)=(?:"([^"]*)"|\'([^\']*)\')', attrs
        ):
            d[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
        if d:
            out.append(d)
    return out


def _parse_slots(raw: str) -> dict:
    """data-slots is HTML-entity-encoded JSON — decode entities before parsing."""
    decoded = html.unescape(raw)
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return json.loads(re.sub(r"\s+", " ", decoded).strip())


# ─── Catalog helpers ────────────────────────────────────────────────────────


def load_catalog(catalog_path: Path = CATALOG_PATH) -> dict:
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def catalog_label_map(catalog: dict) -> dict[str, str]:
    """Build {html_label: catalog_id} from the catalog's html_label fields."""
    return {
        entry["html_label"]: entry["id"]
        for entry in catalog["layouts"]
        if "html_label" in entry
    }


def catalog_code_first(catalog: dict) -> set[str]:
    """Return catalog ids that intentionally have no HTML section."""
    return {entry["id"] for entry in catalog["layouts"] if "html_label" not in entry}


# ─── Slug & name helpers ────────────────────────────────────────────────────


def _strip_brand_prefix(label: str) -> str:
    """Drop 'MCK · ' or similar co-brand prefixes.

    The HTML carries the prefix as design-brief provenance, but once a
    layout is in the Baukasten it's a Feinschliff layout — users and /deck
    shouldn't see 'MCK' in the name. html_label keeps the original
    string so round-trips still work.
    """
    for prefix in ("MCK · ", "MCK·", "MCK "):
        if label.startswith(prefix):
            return label[len(prefix):]
    return label


def slugify_id(label: str) -> str:
    """Slug rule: strip co-brand prefix, lowercase, × → x, hyphenate.

    "MCK · 2×2 Matrix" → "2x2-matrix"
    "Graphical"        → "graphical"
    """
    s = _strip_brand_prefix(label).lower().replace("×", "x")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)


def module_basename(slug: str) -> str:
    """snake_case valid Python identifier derived from the slug.

    A slug beginning with a digit (e.g. '2x2-matrix') gets a 'layout_' prefix
    so it's a valid Python identifier.
    """
    base = re.sub(r"[^a-z0-9_]", "_", slug.replace("-", "_"))
    if base and base[0].isdigit():
        base = "layout_" + base
    return base


def pretty_name(label: str) -> str:
    return f"Feinschliff · {_strip_brand_prefix(label)}"


# ─── Drift & contract check ─────────────────────────────────────────────────


def check_html_contract(html_path: Path = HTML_PATH) -> list[str]:
    """Verify every <section> carries all 6 required data-* attributes."""
    sections = _section_blocks(html_path.read_text(encoding="utf-8"))
    if not sections:
        return ["No `<section>` tags found in HTML."]
    problems: list[str] = []
    for sec in sections:
        label = sec.get("data-label", "<unlabeled>")
        missing = [a for a in REQUIRED_SECTION_ATTRS if a not in sec]
        if missing:
            problems.append(f"section {label!r} missing: {', '.join(missing)}")
    return problems


def check(
    html_path: Path = HTML_PATH,
    catalog_path: Path = CATALOG_PATH,
) -> list[str]:
    """Return list of drift problems. Empty = clean."""
    catalog = load_catalog(catalog_path)
    label_map = catalog_label_map(catalog)
    code_first = catalog_code_first(catalog)
    catalog_ids = {e["id"] for e in catalog["layouts"]}

    problems: list[str] = []
    seen_labels: set[str] = set()
    for sec in _section_blocks(html_path.read_text(encoding="utf-8")):
        label = sec.get("data-label", "<unlabeled>")
        seen_labels.add(label)
        if label not in label_map:
            problems.append(
                f"HTML section {label!r} has no catalog entry. "
                f"Run `compile.py --apply` to generate one."
            )
        elif label_map[label] not in catalog_ids:
            problems.append(
                f"HTML label {label!r} maps to catalog id "
                f"{label_map[label]!r}, but that id is missing."
            )

    for entry in catalog["layouts"]:
        if entry["id"] in code_first:
            continue
        if entry.get("html_label") not in seen_labels:
            problems.append(
                f"Catalog entry {entry['id']!r} claims HTML label "
                f"{entry.get('html_label')!r} but it is not in the HTML."
            )

    return problems


# ─── Catalog entry codegen ──────────────────────────────────────────────────


def _strip_chrome_slots(slots: dict) -> dict:
    return {k: v for k, v in slots.items() if k not in CHROME_SLOT_KEYS}


def _build_catalog_entry(
    section: dict,
    *,
    slug: str,
    module_base: str,
    placeholder_map: dict[str, int],
) -> dict:
    slots = _strip_chrome_slots(_parse_slots(section["data-slots"]))
    label = section["data-label"]
    return {
        "id": slug,
        "html_label": label,
        "name": pretty_name(label),
        "role": section["data-role"],
        "concepts": [c.strip() for c in section["data-concepts"].split(",")],
        "when_to_use": section["data-when-to-use"],
        "when_not_to_use": section["data-when-not-to-use"],
        "slots": slots,
        "renderer": {
            "pptx": {
                "module": f"feinschliff.brands.feinschliff.renderers.pptx.layouts.{module_base}",
                "layout_name": pretty_name(label),
                "placeholder_map": placeholder_map,
                "kind": "stub",  # flag for /extend work — drop when hand-tuned
            }
        },
    }


# ─── Stub .py codegen ───────────────────────────────────────────────────────


STUB_PY_TEMPLATE = '''\
"""{pretty_name} — STUB (awaiting /extend for hand-tuned visual design)."""
from __future__ import annotations

from layouts._stub import emit_stub_layout

NAME = {name!r}
BG = {bg!r}
PGMETA = {pgmeta!r}
EYEBROW_PROMPT = {eyebrow_prompt!r}
TITLE_PROMPT = {title_prompt!r}

SLOTS_SCHEMA = {slots_schema_literal}


def build(layout):
    emit_stub_layout(
        layout,
        name=NAME,
        slots_schema=SLOTS_SCHEMA,
        eyebrow_prompt=EYEBROW_PROMPT,
        title_prompt=TITLE_PROMPT,
        bg=BG,
        pgmeta=PGMETA,
    )
'''


def _render_stub_py(
    section: dict,
    *,
    pretty_name_: str,
) -> str:
    """Deterministic .py source for a stub layout."""
    slots = _strip_chrome_slots(_parse_slots(section["data-slots"]))
    # Pretty-print the schema so re-running --apply produces stable diffs.
    schema_literal = json.dumps(slots, indent=4, ensure_ascii=False)
    # json.dumps → JSON dict is valid Python literal for strings/dicts/lists/
    # numbers/booleans/None once we swap true/false/null → True/False/None.
    schema_literal = re.sub(r"\btrue\b", "True", schema_literal)
    schema_literal = re.sub(r"\bfalse\b", "False", schema_literal)
    schema_literal = re.sub(r"\bnull\b", "None", schema_literal)

    bg = BG_BY_ROLE.get(section["data-role"], "white")
    label = section["data-label"]
    eyebrow_prompt = _derive_eyebrow_prompt(label)
    title_prompt = _derive_title_prompt(label, section)
    pgmeta = _strip_brand_prefix(label)

    return STUB_PY_TEMPLATE.format(
        pretty_name=pretty_name_,
        name=pretty_name_,
        bg=bg,
        pgmeta=pgmeta,
        eyebrow_prompt=eyebrow_prompt,
        title_prompt=title_prompt,
        slots_schema_literal=schema_literal,
    )


def _derive_eyebrow_prompt(label: str) -> str:
    return _strip_brand_prefix(label).removeprefix("Feinschliff · ")


def _derive_title_prompt(label: str, section: dict) -> str:
    return section["data-when-to-use"].split(".")[0][:60] + "."


# ─── Apply mode ─────────────────────────────────────────────────────────────


def apply(
    html_path: Path = HTML_PATH,
    catalog_path: Path = CATALOG_PATH,
    *,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    """Generate catalog entries + stub .py files for any HTML section
    missing from the catalog.

    Returns (added_slugs, skipped_labels). Idempotent: existing catalog
    entries (by html_label) are left alone.
    """
    # Import _stub lazily so this script works even without pptx installed
    # when only --check is used.
    sys.path.insert(0, str(HERE))
    try:
        from layouts._stub import plan_placeholders  # noqa: E402
    finally:
        sys.path.remove(str(HERE))

    catalog = load_catalog(catalog_path)
    label_map = catalog_label_map(catalog)
    html = html_path.read_text(encoding="utf-8")
    sections = _section_blocks(html)

    added: list[str] = []
    skipped: list[str] = []
    new_modules: list[tuple[str, str]] = []  # (slug, module_base) in HTML order

    for sec in sections:
        label = sec["data-label"]
        if label in label_map:
            skipped.append(label)
            continue
        slug = slugify_id(label)
        module_base = module_basename(slug)
        pmap = plan_placeholders(_strip_chrome_slots(_parse_slots(sec["data-slots"])))
        entry = _build_catalog_entry(
            sec, slug=slug, module_base=module_base, placeholder_map=pmap
        )
        catalog["layouts"].append(entry)
        new_modules.append((slug, module_base))
        added.append(slug)

        if dry_run:
            continue

        stub_src = _render_stub_py(sec, pretty_name_=pretty_name(label))
        (LAYOUTS_DIR / f"{module_base}.py").write_text(stub_src, encoding="utf-8")

    if added and not dry_run:
        catalog_path.write_text(
            json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _register_modules(new_modules)

    return added, skipped


def _register_modules(new_modules: list[tuple[str, str]]) -> None:
    """Append new modules to layouts/__init__.py's import list and LAYOUTS registry."""
    init_path = LAYOUTS_DIR / "__init__.py"
    src = init_path.read_text(encoding="utf-8")

    import_block_end = src.index(")", src.index("from . import"))
    imports_before_close = src[: import_block_end].rstrip().rstrip(",")
    new_imports = "\n".join(f"    {mb}," for _, mb in new_modules)
    src = imports_before_close + ",\n" + new_imports + "\n" + src[import_block_end:]

    layouts_list_start = src.index("LAYOUTS = [")
    layouts_list_end = src.index("]", layouts_list_start)
    list_before_close = src[:layouts_list_end].rstrip().rstrip(",")
    new_list_entries = "\n".join(f"    {mb}," for _, mb in new_modules)
    src = list_before_close + ",\n" + new_list_entries + "\n" + src[layouts_list_end:]

    init_path.write_text(src, encoding="utf-8")


# ─── Reports & CLI ──────────────────────────────────────────────────────────


def _report(html_labels: list[str], catalog: dict) -> None:
    label_map = catalog_label_map(catalog)
    code_first = catalog_code_first(catalog)
    catalog_ids = [e["id"] for e in catalog["layouts"]]
    html_backed = set(label_map.values())
    print(f"HTML: {len(html_labels)} sections, catalog: {len(catalog_ids)} layouts")
    print()
    for label in html_labels:
        if label in label_map:
            kind = "stub" if _is_stub(catalog, label_map[label]) else "layout"
            print(f"  [{kind}]       {label} → {label_map[label]}")
        else:
            print(f"  [UNKNOWN]    {label}")
    print()
    for cat_id in catalog_ids:
        if cat_id in code_first:
            print(f"  [code-first] {cat_id}")
        elif cat_id in html_backed:
            kind = "stub" if _is_stub(catalog, cat_id) else "hand"
            print(f"  [{kind}]       {cat_id}")
        else:
            print(f"  [UNTRACKED]  {cat_id}")
    print()


def _is_stub(catalog: dict, cat_id: str) -> bool:
    for entry in catalog["layouts"]:
        if entry["id"] == cat_id:
            return entry.get("renderer", {}).get("pptx", {}).get("kind") == "stub"
    return False


def _print_design_prompt() -> None:
    print()
    print("=" * 72)
    print("HTML does not match the Feinschliff Claude Design contract.")
    print("Hand the prompt below to Claude Design and replace feinschliff-2026.html")
    print("with the result. Then re-run `compile.py --check` to verify.")
    print("=" * 72)
    print()
    if PROMPT_PATH.exists():
        print(PROMPT_PATH.read_text(encoding="utf-8"))
    else:
        print(f"(prompt not found at {PROMPT_PATH})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="drift check (default)")
    parser.add_argument("--verbose", action="store_true", help="classification report")
    parser.add_argument(
        "--apply", action="store_true",
        help="generate catalog entries + stub .py files for unknown HTML sections",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="with --apply: print what would be added without writing files",
    )
    args = parser.parse_args()

    if args.apply:
        added, skipped = apply(dry_run=args.dry_run)
        print(f"apply: {len(added)} new layouts, {len(skipped)} already in catalog")
        for slug in added:
            print(f"  + {slug}")
        if args.dry_run:
            print("\n(dry-run: no files written)")
        return 0

    if args.verbose:
        _report(
            [s["data-label"] for s in _section_blocks(HTML_PATH.read_text(encoding="utf-8"))],
            load_catalog(),
        )

    contract_problems = check_html_contract()
    if contract_problems:
        print(f"HTML CONTRACT VIOLATED ({len(contract_problems)}):")
        for p in contract_problems:
            print(f"  - {p}")
        _print_design_prompt()
        return 1

    problems = check()
    if problems:
        print(f"DRIFT DETECTED ({len(problems)}):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK — HTML and catalog are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
