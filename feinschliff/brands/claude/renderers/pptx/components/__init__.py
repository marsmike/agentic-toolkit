"""Baukasten — Feinschliff component kit.

Every symbol here is a pure function that places native PowerPoint shapes on
a target (a Slide, SlideLayout, or SlideMaster). Higher-level `layouts.py`
composes these into named PowerPoint SlideLayouts.

Adding a new component to the kit (future flow):
  1. Drop a new module next to this file (e.g. `timeline.py`) with
     `add_timeline(target, x, y, w, h, **props)`.
  2. Re-export it below so callers can `from components import add_timeline`.
  3. Wire it into one of the layouts in `layouts.py` (or create a new one).
"""
from components.primitives import add_rect, add_line, add_text, set_solid_fill
from components.type import (
    add_rule, add_eyebrow, add_slide_title, add_display,
    add_huge, add_subtitle, add_body, add_mono_caption,
)
from components.chrome import (
    add_logo, add_pgmeta, add_footer_left, add_footer_right,
    paint_chrome,
)
from components.controls import add_button, add_chip
from components.data import add_kpi, add_bar_row
from components.stacked_bar import add_stacked_bar
from components.media import add_image_placeholder
from components.cards import add_column, add_agenda_row
from components.funnel import add_funnel, funnel_geometry
from components.pyramid import add_pyramid, pyramid_geometry
from components.line_chart import add_line_chart
from components.waterfall import add_waterfall
from components.matrix_2x2 import add_matrix_2x2
from components.process_flow import add_process_flow
from components.gantt import add_gantt
from components.scorecard import add_scorecard
from components.venn import add_venn
from components.graphical_bars import add_graphical_bars
from components.data_table import add_data_table
from components.v_model import add_v_model
from components.placeholders import (
    add_text_placeholder, add_picture_placeholder,
    set_layout_background, set_layout_name, clear_layout_shapes,
)

__all__ = [
    # primitives
    "add_rect", "add_line", "add_text", "set_solid_fill",
    # type
    "add_rule", "add_eyebrow", "add_slide_title", "add_display",
    "add_huge", "add_subtitle", "add_body", "add_mono_caption",
    # chrome
    "add_logo", "add_pgmeta", "add_footer_left", "add_footer_right",
    "paint_chrome",
    # controls
    "add_button", "add_chip",
    # data
    "add_kpi", "add_bar_row", "add_stacked_bar",
    # media
    "add_image_placeholder",
    # cards
    "add_column", "add_agenda_row",
    # funnel
    "add_funnel", "funnel_geometry",
    # pyramid
    "add_pyramid", "pyramid_geometry",
    # line chart
    "add_line_chart",
    # waterfall
    "add_waterfall",
    # 2×2 matrix
    "add_matrix_2x2",
    # process flow
    "add_process_flow",
    # gantt
    "add_gantt",
    # scorecard
    "add_scorecard",
    # venn
    "add_venn",
    # graphical bars
    "add_graphical_bars",
    # data table
    "add_data_table",
    # v-model
    "add_v_model",
    # placeholders
    "add_text_placeholder", "add_picture_placeholder",
    "set_layout_background", "set_layout_name", "clear_layout_shapes",
]
