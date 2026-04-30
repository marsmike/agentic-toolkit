"""Feinschliff · Horizontal Bullets — three parallel drivers/forces/buckets (HTML 17).

Classic McKinsey three-column "forces" pattern: a shared action title up top,
then three equal-width columns each carrying a mono orange counter, a display
heading, and a 2–5-item bulleted list. Thin fog-coloured rules separate the
columns so the eye reads them as parallel tracks.

Schema (preserved verbatim from the generated stub so /compile --check stays
clean):
  * kicker          — short mono eyebrow
  * action_title    — the takeaway
  * columns[3]      — each {counter, heading, bullets[1-5]}

Idx allocation (mirrors catalog placeholder_map, stride=4):
  0            action_title
  10           kicker
  20/21/22     col 0: counter / heading / bullets  (multi-line bulleted text)
  24/25/26     col 1: counter / heading / bullets
  28/29/30     col 2: counter / heading / bullets
  60           source
"""
from __future__ import annotations

import theme as T
from components import (
    add_line, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header


NAME = "Feinschliff · Horizontal Bullets"
BG = "white"
PGMETA = "Horizontal Bullets"
EYEBROW_PROMPT = "Context"
TITLE_PROMPT = (
    "Three forces pull the 2026 roadmap: regulation, margin, and shared software."
)

# SLOTS_SCHEMA preserved verbatim from the /compile --apply stub so
# test_compile_drift stays clean. `bullets` is an array-of-strings; the
# renderer joins them with newlines into one multi-line placeholder per column.
SLOTS_SCHEMA = {
    "kicker": {
        "type": "string",
        "maxLength": 40,
        "optional": True
    },
    "action_title": {
        "type": "string",
        "maxLength": 180
    },
    "columns": {
        "type": "array",
        "minItems": 3,
        "maxItems": 3,
        "items": {
            "type": "object",
            "properties": {
                "counter": {
                    "type": "string",
                    "maxLength": 30
                },
                "heading": {
                    "type": "string",
                    "maxLength": 120
                },
                "bullets": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {
                        "type": "string",
                        "maxLength": 140
                    }
                }
            },
            "required": [
                "counter",
                "heading",
                "bullets"
            ]
        }
    }
}


# ─── Sample content — mirrors HTML section 17 ─────────────────────────────
COLUMNS = [
    (
        "01 · Regulation",
        "Energy and repair rules are tightening across EMEA.",
        (
            "EU Ecodesign 2027 raises minimum efficiency one full class.",
            "Right-to-repair mandates in DE, FR, NL by end of 2026.",
            "Refrigerant phase-down accelerates for commercial lines.",
        ),
    ),
    (
        "02 · Margin",
        "Component cost is stable but service cost is climbing.",
        (
            "Field-service visits up 7% YoY on premium products.",
            "Warranty reserve exceeds plan in 3 of 5 product lines.",
            "Remote-diagnosis deflection saves an average 38 EUR / visit.",
        ),
    ),
    (
        "03 · Platform",
        "The platform is becoming the product, not an add-on.",
        (
            "New SKUs must ship with the platform from day one.",
            "One update path cuts firmware maintenance headcount 22%.",
            "Shared telemetry unlocks usage-driven feature priority.",
        ),
    ),
]


def _format_bullets(items) -> str:
    """Render bullets as a single newline-separated string, each prefixed
    with a disc + hair-space. `add_text_placeholder` disables OOXML bullet
    metadata (buNone) so we paint the marker inline — this keeps the whole
    list editable as one text frame without the user needing bullet keys."""
    return "\n".join(f"•  {item}" for item in items)


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # Content area geometry.
    content_x0 = 100
    content_y0 = 460
    content_w = 1720
    n_cols = 3
    gap = 60  # space between columns; thin fog rule centred in each gap
    col_w = (content_w - gap * (n_cols - 1)) // n_cols  # 3W + 2*60 = 1720 → W = 533

    # Per-column text-stack bands.
    counter_y = content_y0
    counter_h = 30
    heading_y = content_y0 + 52
    heading_h = 130
    bullets_y = content_y0 + 200
    bullets_h = 420

    # Vertical fog rules between columns, spanning the counter-to-bullets stack.
    rule_top = content_y0 - 4
    rule_h = bullets_h + (bullets_y - rule_top)
    for i in range(n_cols - 1):
        rule_x = content_x0 + (i + 1) * col_w + i * gap + (gap // 2) - 1
        add_line(layout, rule_x, rule_top, 1, rule_h, T.FOG)

    # Column placeholders.
    for i, (counter, heading, items) in enumerate(COLUMNS):
        x = content_x0 + i * (col_w + gap)
        idx_base = 20 + i * 4

        # Counter — mono orange, tracked, uppercase.
        add_text_placeholder(
            layout, idx=idx_base, name=f"Col{i+1} Counter", ph_type="body",
            x_px=x, y_px=counter_y, w_px=col_w, h_px=counter_h,
            prompt_text=counter,
            size_px=T.SIZE_PX["col_num"], weight="bold", font=T.FONT_DISPLAY,
            color=T.ACCENT, uppercase=True, tracking_em=0.1,
        )

        # Heading — display medium, black.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Col{i+1} Heading", ph_type="body",
            x_px=x, y_px=heading_y, w_px=col_w, h_px=heading_h,
            prompt_text=heading,
            size_px=T.SIZE_PX["col_title"], weight="medium",
            color=T.BLACK, tracking_em=-0.012, line_height=1.15,
        )

        # Bullets — single multi-line body placeholder, disc marker painted
        # inline so the run stays style-consistent with every other body
        # placeholder in the Baukasten. Generous line-height gives each item
        # room to breathe like the HTML <li> stack.
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Col{i+1} Bullets", ph_type="body",
            x_px=x, y_px=bullets_y, w_px=col_w, h_px=bullets_h,
            prompt_text=_format_bullets(items),
            size_px=T.SIZE_PX["col_body"],
            color=T.GRAPHITE, line_height=1.55,
        )

    # Source line — mono, bottom rail.
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=content_x0, y_px=1000, w_px=content_w, h_px=30,
        prompt_text="Source · Strategy review, Q4 2025",
        size_px=14, weight="bold", font=T.FONT_DISPLAY, color=T.GRAPHITE,
        uppercase=True, tracking_em=0.1,
    )
