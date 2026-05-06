"""One-time helper: extract a single layout from the demo deck into a v2 template file."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from pptx import Presentation


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Built demo deck .pptx")
    ap.add_argument("--layout-name", required=True, help="Slide layout name to extract")
    ap.add_argument("--out", required=True, help="Output single-slide .pptx")
    args = ap.parse_args()

    src = Presentation(args.input)
    target_layout = None
    for sl in src.slide_layouts:
        if sl.name == args.layout_name:
            target_layout = sl
            break
    if target_layout is None:
        layouts = ", ".join(sl.name for sl in src.slide_layouts)
        sys.exit(f"layout {args.layout_name!r} not found. Have: {layouts}")

    demo_slide = None
    for s in src.slides:
        if s.slide_layout.name == args.layout_name:
            demo_slide = s
            break
    if demo_slide is None:
        sys.exit(f"no slide in {args.input} uses layout {args.layout_name!r}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    src.save(out_path)
    new = Presentation(out_path)
    keep_idx = None
    for i, s in enumerate(new.slides):
        if s.slide_layout.name == args.layout_name:
            keep_idx = i
            break
    xml_slides = new.slides._sldIdLst
    slides_list = list(xml_slides)
    for i, sld in enumerate(slides_list):
        if i != keep_idx:
            xml_slides.remove(sld)
    new.save(out_path)

    sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
    print(f"WROTE {out_path} sha256={sha}")


if __name__ == "__main__":
    main()
