import json
from pathlib import Path

import pytest
from pptx import Presentation

from lib.catalog import load_catalog, get_renderer_kind, RendererKind, V2RendererSpec
from lib.pptx_fill import load_template, fill_slot, write_filled


REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_ROOT = REPO_ROOT / "brands" / "feinschliff"
CATALOG_PATH = BRAND_ROOT / "catalog" / "layouts.json"


def _entry(layout_id: str) -> dict:
    cat = load_catalog(CATALOG_PATH)
    for layout in cat["layouts"]:
        if layout["id"] == layout_id:
            return layout
    raise KeyError(layout_id)


@pytest.mark.parametrize("layout_id", ["title-orange", "kpi-grid", "text-picture"])
def test_v2_layout_round_trip(layout_id, tmp_path):
    entry = _entry(layout_id)
    assert get_renderer_kind(entry, "pptx") is RendererKind.V2
    spec = V2RendererSpec.from_entry(entry, "pptx")
    template_path = BRAND_ROOT / spec.source
    assert template_path.is_file(), f"missing template file {template_path}"

    prs = load_template(template_path)
    for slot_name, idx in spec.placeholder_map.items():
        fill_slot(prs.slides[0], idx=idx, text=f"<{slot_name}>")
    out = tmp_path / f"{layout_id}.pptx"
    write_filled(prs, out)
    Presentation(out)  # round-trip parse
