"""BMW PowerPoint Template — build entrypoint.

Run:   uv run python build.py
Output: out/BMW-Template.pptx
"""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from master import (
    apply_bmw_theme, set_slide_size, ensure_n_layouts,
    reset_master_shapes, reset_layout,
)
import layouts
import slides

OUT_DIR = HERE / "out"
OUT_FILE = OUT_DIR / "BMW-Template.pptx"


def main(include_demo_slides: bool = True):
    OUT_DIR.mkdir(exist_ok=True)

    prs = Presentation()

    # 1. 16:9 @ 1920×1080 CSS px
    set_slide_size(prs)

    # 2. Theme (colour + font scheme) → BMW tokens
    apply_bmw_theme(prs)

    # 3. Grow the layout set to hold every feinschliff layout
    ensure_n_layouts(prs, len(layouts.LAYOUTS))

    # 4. Strip stock shapes from master + every layout, paint feinschliff chrome/content
    reset_master_shapes(prs.slide_masters[0])
    for layout in prs.slide_masters[0].slide_layouts:
        reset_layout(layout)
    layouts.build_all(prs)

    # 5. Optional demo deck — one slide per layout showing the HTML reference content
    if include_demo_slides:
        slides.build_demo_deck(prs)

    prs.save(OUT_FILE)
    size_kb = OUT_FILE.stat().st_size // 1024
    print(f"✓ Wrote {OUT_FILE} ({size_kb} KB, "
          f"{len(prs.slides)} slides, {len(layouts.LAYOUTS)} layouts)")


if __name__ == "__main__":
    main()
