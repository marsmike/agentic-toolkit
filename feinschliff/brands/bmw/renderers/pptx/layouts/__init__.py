"""Feinschliff layout registry.

Each entry here is a (slug, module) pair. The module exposes:
  NAME   — human-readable name shown in PowerPoint's Insert → New Slide menu
  build  — function that takes a SlideLayout and paints it in place

Adding a new layout (future flow):
  1. Drop a new module next to this file, e.g. `timeline.py`, with
     `NAME` and `build(layout)`.
  2. Append it to `LAYOUTS` below. The order here is the order layouts
     appear in PowerPoint's Insert → New Slide menu.
  3. If you need one more layout than python-pptx provides by default (11),
     `master.ensure_n_layouts(prs, N)` auto-clones additional ones.
"""
from __future__ import annotations

from . import (
    title_orange,
    title_ink,
    title_picture,
    agenda,
    chapter_orange,
    chapter_ink,
    kpi_grid,
    two_column_cards,
    three_column,
    four_column_cards,
    text_picture,
    full_bleed_cover,
    bar_chart,
    components_showcase,
    quote,
    end,
    graphical,
    action_title,
    horizontal_bullets,
    vertical_bullets,
    matrix_2x2,
    waterfall,
    process_flow,
    stacked_bar,
    table,
    pyramid,
    key_takeaways,
    executive_summary,
    line_chart,
    scorecard,
    gantt,
    funnel,
    venn,
    diagram,
    tech_radar_full_bleed,
    v_model,
)

LAYOUTS = [
    title_orange,
    title_ink,
    title_picture,
    agenda,
    chapter_orange,
    chapter_ink,
    kpi_grid,
    two_column_cards,
    three_column,
    four_column_cards,
    text_picture,
    full_bleed_cover,
    bar_chart,
    components_showcase,
    quote,
    end,
    graphical,
    action_title,
    horizontal_bullets,
    vertical_bullets,
    matrix_2x2,
    waterfall,
    process_flow,
    stacked_bar,
    table,
    pyramid,
    key_takeaways,
    executive_summary,
    line_chart,
    scorecard,
    gantt,
    funnel,
    venn,
    diagram,
    tech_radar_full_bleed,
    v_model,
]


def build_all(prs):
    """Paint every registered layout onto the presentation's SlideLayouts."""
    master = prs.slide_masters[0]
    layout_objs = list(master.slide_layouts)
    assert len(layout_objs) >= len(LAYOUTS), (
        f"need {len(LAYOUTS)} layouts, have {len(layout_objs)} — "
        "call master.ensure_n_layouts(prs, N) first"
    )
    for module, layout in zip(LAYOUTS, layout_objs):
        module.build(layout)


def layout_by_name(prs, name: str):
    """Look up a SlideLayout by its registered name (e.g. 'Feinschliff · KPI Grid')."""
    for layout in prs.slide_masters[0].slide_layouts:
        if layout.name == name:
            return layout
    raise KeyError(f"no layout named {name!r}")
