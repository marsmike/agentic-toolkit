"""Port every v1-only layout in a brand to v2, with HQ visual verification.

For each layout in <brand>/catalog/layouts.json that has only `module` (v1):
  1. Run extract_v2_template.py to produce the .pptx artifact.
  2. Run verify_v2_template.py to phash-diff filled v2 against the v1 demo slide.
  3. On pass: add `source` + `sha256` to the catalog entry.
  4. On fail: log to <brand>/.port-needs-review.txt with the distance.

Layouts missing a `layout_name` field are skipped (no extraction target).
The script saves the catalog after each layout's status is decided so a crash
mid-port leaves a partial-but-consistent state.

Usage:
    uv run --directory feinschliff python scripts/port_brand.py --brand bmw
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _format_catalog(cat: dict) -> str:
    return json.dumps(cat, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--threshold", type=int, default=8)
    ap.add_argument("--verify-out-dir", default=None,
                    help="Where per-layout verify renders are kept; defaults to "
                         "<brand>/.port-verify/")
    args = ap.parse_args()

    brand_root = REPO_ROOT / "feinschliff" / "brands" / args.brand
    catalog_path = brand_root / "catalog" / "layouts.json"
    templates_dir = brand_root / "templates" / "pptx"
    templates_dir.mkdir(parents=True, exist_ok=True)
    review_path = brand_root / ".port-needs-review.txt"

    demo_decks = list((brand_root / "renderers" / "pptx" / "out").glob("*.pptx"))
    if not demo_decks:
        print(f"no demo deck in {brand_root}/renderers/pptx/out/; run build.py first", file=sys.stderr)
        return 1
    demo_deck = demo_decks[0]

    verify_out = Path(args.verify_out_dir) if args.verify_out_dir else (brand_root / ".port-verify")
    verify_out.mkdir(parents=True, exist_ok=True)

    cat = json.loads(catalog_path.read_text())

    extract_script = REPO_ROOT / "feinschliff" / "scripts" / "extract_v2_template.py"
    verify_script = REPO_ROOT / "feinschliff" / "scripts" / "verify_v2_template.py"

    ported = []
    skipped_already_v2 = []
    skipped_no_layout_name = []
    failed_extract = []
    failed_verify = []

    for entry in cat["layouts"]:
        layout_id = entry["id"]
        pptx = entry.get("renderer", {}).get("pptx", {})
        if "source" in pptx:
            skipped_already_v2.append(layout_id)
            continue
        layout_name = pptx.get("layout_name")
        if not layout_name:
            skipped_no_layout_name.append(layout_id)
            continue

        out_path = templates_dir / f"{layout_id}.pptx"

        # Extract
        try:
            subprocess.run(
                ["uv", "run", "--directory", "feinschliff", "python", str(extract_script),
                 "--input", str(demo_deck.relative_to(REPO_ROOT / "feinschliff")),
                 "--layout-name", layout_name,
                 "--out", str(out_path.relative_to(REPO_ROOT / "feinschliff"))],
                check=True, capture_output=True, cwd=REPO_ROOT,
            )
        except subprocess.CalledProcessError as e:
            failed_extract.append((layout_id, e.stderr.decode()[:200]))
            continue

        # Verify
        verify_dir = verify_out / layout_id
        result = subprocess.run(
            ["uv", "run", "--directory", "feinschliff", "python", str(verify_script),
             "--demo-deck", str(demo_deck.relative_to(REPO_ROOT / "feinschliff")),
             "--layout-name", layout_name,
             "--v2-template", str(out_path.relative_to(REPO_ROOT / "feinschliff")),
             "--out-dir", str(verify_dir),
             "--threshold", str(args.threshold)],
            capture_output=True, cwd=REPO_ROOT,
        )
        verdict_line = result.stdout.decode().strip().splitlines()[-1] if result.stdout else ""

        if result.returncode == 0:
            sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
            pptx["source"] = f"templates/pptx/{layout_id}.pptx"
            pptx["sha256"] = sha
            ported.append((layout_id, verdict_line))
            # Save incrementally
            catalog_path.write_text(_format_catalog(cat))
        else:
            failed_verify.append((layout_id, verdict_line))
            # Leave the .pptx in place for inspection; do NOT add v2 fields.

    # Final write (idempotent).
    catalog_path.write_text(_format_catalog(cat))

    # Review log
    review_lines = []
    if failed_verify:
        review_lines.append("# Visual verification failed (phash > threshold). Render PNGs are in")
        review_lines.append(f"# {verify_out.relative_to(REPO_ROOT)}/<layout_id>/. Inspect and decide:")
        review_lines.append("# - if v2 looks correct (e.g. v1 was buggy), bump catalog by hand")
        review_lines.append("# - if v2 looks wrong, fix the extractor and re-run port_brand.py")
        review_lines.append("")
        for layout_id, line in failed_verify:
            review_lines.append(f"{layout_id}\t{line}")
    if failed_extract:
        review_lines.append("\n# Extraction failed:")
        for layout_id, err in failed_extract:
            review_lines.append(f"{layout_id}\t{err}")
    if review_lines:
        review_path.write_text("\n".join(review_lines) + "\n")

    print(f"\n=== {args.brand} ===")
    print(f"  ported:               {len(ported)}")
    print(f"  already v2 (skipped): {len(skipped_already_v2)}")
    print(f"  no layout_name:       {len(skipped_no_layout_name)}")
    print(f"  extraction failed:    {len(failed_extract)}")
    print(f"  verify failed:        {len(failed_verify)}")
    if failed_verify or failed_extract:
        print(f"  → see {review_path.relative_to(REPO_ROOT)}")
    return 0 if not failed_extract else 2


if __name__ == "__main__":
    sys.exit(main())
