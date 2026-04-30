"""Feinschliff SVG renderer — build entrypoint.

Run:   python build.py
Output: out/<id>.svg, one per registered layout
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree.ElementTree import ElementTree, indent

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from geometry import CANVAS_H, CANVAS_W, VIEWBOX  # noqa: E402
from primitives import svg_root  # noqa: E402
import layouts  # noqa: E402

OUT_DIR = HERE / "out"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    for module in layouts.LAYOUTS:
        root = svg_root(width=CANVAS_W, height=CANVAS_H, viewBox=VIEWBOX)
        module.build(root)

        out_path = OUT_DIR / f"{module.ID}.svg"
        tree = ElementTree(root)
        # Pretty-print so committed artifacts are human-readable in diff
        # review (stdlib since Python 3.9).
        indent(tree, space="  ")
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
        size_kb = out_path.stat().st_size / 1024
        print(f"✓ Wrote {out_path.relative_to(HERE.parent.parent.parent)} "
              f"({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
