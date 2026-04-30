"""Feinschliff · Venn — 3-circle strategic overlap diagram with side-column explainers.

The Venn shows the sweet-spot where 2–3 capabilities / audiences / domains
meet. Three semi-transparent circles (orange, ink, graphite) overlap with a
highlighted centre marker. Pairwise + centre intersection labels are
editable placeholders laid on top of the circles; optional side-column
items explain each overlap in prose.

Schema is preserved from the original stub — only `build()` changes.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, add_venn,
    paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header


NAME = 'Feinschliff · Venn'
BG = 'white'
PGMETA = 'Venn'
EYEBROW_PROMPT = 'Where the three businesses meet'
TITLE_PROMPT = (
    "The connected platform is the intersection — only the integrated brand has the "
    "product, the platform, and the service relationship."
)


# ─── Schema (preserved verbatim from stub) ────────────────────────────────
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
    "circles": {
        "type": "array",
        "minItems": 2,
        "maxItems": 3,
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "maxLength": 30
                },
                "subtitle": {
                    "type": "string",
                    "maxLength": 40,
                    "optional": True
                }
            },
            "required": [
                "name"
            ]
        }
    },
    "intersections": {
        "type": "array",
        "minItems": 1,
        "maxItems": 4,
        "items": {
            "type": "object",
            "properties": {
                "members": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Which circles it sits in."
                },
                "label": {
                    "type": "string",
                    "maxLength": 60
                }
            },
            "required": [
                "members",
                "label"
            ]
        }
    },
    "side_items": {
        "type": "array",
        "minItems": 2,
        "maxItems": 4,
        "optional": True,
        "items": {
            "type": "object",
            "properties": {
                "counter": {
                    "type": "string"
                },
                "heading": {
                    "type": "string",
                    "maxLength": 40
                },
                "body": {
                    "type": "string",
                    "maxLength": 180
                }
            },
            "required": [
                "counter",
                "heading",
                "body"
            ]
        }
    }
}


# ─── Geometry ──────────────────────────────────────────────────────────────
# Canvas content area: x=100..1820, y=460..1020.
# Venn sits on the left half (100..1000); side column sits on the right
# (1080..1820) with 4 stacked item cards.
VENN_X = 100
VENN_Y = 460
VENN_W = 900
VENN_H = 540

SIDE_X = 1080
SIDE_Y = 460
SIDE_W = 740
SIDE_H = 540
SIDE_GAP = 16
SIDE_COUNT = 4  # schema allows 2–4; we render all 4 slots

# Per-intersection text-label box sizing (editable placeholders on top).
INTER_W = 240
INTER_H = 40

# Centre sweet-spot label sizing (sits inside the centre marker).
CENTER_LABEL_W = 160
CENTER_LABEL_H = 48


# ─── Sample content (HTML slide 31 reference) ─────────────────────────────
SAMPLE_SETS = [
    {"name": "Consumer",  "subtitle": "Product + brand"},   # circle A · orange
    {"name": "Platform",  "subtitle": "Firmware + API"},      # circle B · ink
    {"name": "Services",  "subtitle": "Install · repair"},    # circle C · graphite
]

SAMPLE_INTERSECTIONS = [
    {"members": ["Consumer", "Platform"],              "label": "Smart product"},
    {"members": ["Consumer", "Services"],              "label": "In-home install"},
    {"members": ["Platform", "Services"],              "label": "Remote diagnostics"},
    {"members": ["Consumer", "Platform", "Services"],  "label": "Connected platform"},
]

SAMPLE_SIDE_ITEMS = [
    {"counter": "01 · Consumer × Platform",
     "heading": "Smart product",
     "body": "Firmware turns the object into an addressable node — the basis for every service we layer on top."},
    {"counter": "02 · Platform × Services",
     "heading": "Remote diagnostics",
     "body": "Telemetry lets service pre-triage a call; first-time-fix rate rises, truck rolls fall."},
    {"counter": "03 · Consumer × Services",
     "heading": "In-home install",
     "body": "Existing service relationship carries trust; we extend it into the subscription tier."},
    {"counter": "Center",
     "heading": "Connected platform",
     "body": "Only Feinschliff sits in all three sets at scale — the moat no single-category competitor can cross."},
]


# ─── Build ─────────────────────────────────────────────────────────────────
def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # ─── Circles + centre marker (pure shapes) ─────────────────────────────
    # Outer set labels are drawn as editable placeholders below instead.
    geom = add_venn(
        layout,
        VENN_X, VENN_Y, VENN_W, VENN_H,
        sets=SAMPLE_SETS,
        intersections=SAMPLE_INTERSECTIONS,
        colors=(T.ACCENT, T.INK, T.GRAPHITE),
        stroke_color=T.INK,
        alpha=50_000,
        draw_outer_labels=False,
        draw_center_marker=True,
    )

    # ─── Set-label placeholders (editable name + subtitle per circle) ──────
    _SET_IDX = (("A", 20, 21), ("B", 24, 25), ("C", 28, 29))
    for (key, idx_name, idx_sub), sample in zip(_SET_IDX, SAMPLE_SETS):
        cx, cy = geom["outer_labels"][key]
        lx = cx - 120
        add_text_placeholder(
            layout, idx=idx_name, name=f"Set {key} Name", ph_type="body",
            x_px=lx, y_px=cy - 14, w_px=240, h_px=26,
            prompt_text=sample["name"],
            size_px=T.SIZE_PX["eyebrow"], weight="semibold", font=T.FONT_DISPLAY,
            color=T.BLACK, uppercase=True, tracking_em=0.1,
            align="c",
        )
        add_text_placeholder(
            layout, idx=idx_sub, name=f"Set {key} Subtitle", ph_type="body",
            x_px=lx, y_px=cy + 16, w_px=240, h_px=22,
            prompt_text=sample.get("subtitle", ""),
            size_px=14, font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=False, tracking_em=0.08,
            align="c",
        )

    # ─── Intersection label placeholders (editable, on top of circles) ─────
    # Pairwise: A×B at top, A×C bottom-left, B×C bottom-right.
    pairwise = [
        (30, ("A", "B"), SAMPLE_INTERSECTIONS[0]["label"]),
        (31, ("A", "C"), SAMPLE_INTERSECTIONS[1]["label"]),
        (32, ("B", "C"), SAMPLE_INTERSECTIONS[2]["label"]),
    ]
    for idx, members, label in pairwise:
        cx, cy = geom["intersections"][members]
        add_text_placeholder(
            layout, idx=idx, name=f"Intersection {''.join(members)}", ph_type="body",
            x_px=cx - INTER_W / 2, y_px=cy - INTER_H / 2,
            w_px=INTER_W, h_px=INTER_H,
            prompt_text=label,
            size_px=16, weight="medium", color=T.INK,
            tracking_em=-0.005, line_height=1.2,
            align="c", anchor="m",
        )

    # Centre sweet-spot label.
    cx, cy = geom["intersections"][("A", "B", "C")]
    add_text_placeholder(
        layout, idx=33, name="Center Intersection", ph_type="body",
        x_px=cx - CENTER_LABEL_W / 2, y_px=cy - CENTER_LABEL_H / 2,
        w_px=CENTER_LABEL_W, h_px=CENTER_LABEL_H,
        prompt_text=SAMPLE_INTERSECTIONS[3]["label"],
        size_px=14, weight="bold", color=T.INK,
        tracking_em=-0.005, line_height=1.1,
        align="c", anchor="m",
    )

    # ─── Side-column items (editable counter / heading / body) ─────────────
    item_h = (SIDE_H - SIDE_GAP * (SIDE_COUNT - 1)) // SIDE_COUNT
    for i in range(SIDE_COUNT):
        item_y = SIDE_Y + i * (item_h + SIDE_GAP)
        idx_base = 40 + i * 4
        sample = SAMPLE_SIDE_ITEMS[i] if i < len(SAMPLE_SIDE_ITEMS) else {
            "counter": "", "heading": "", "body": ""
        }

        # Hairline above each item — orange for the centre (item 4).
        hairline_color = T.ACCENT if i == SIDE_COUNT - 1 else T.FOG
        hairline_h = 2 if i == SIDE_COUNT - 1 else 1
        add_rect(layout, SIDE_X, item_y, SIDE_W, hairline_h, fill=hairline_color)

        # Counter — mono uppercase caption.
        counter_color = T.ACCENT if i == SIDE_COUNT - 1 else T.GRAPHITE
        add_text_placeholder(
            layout, idx=idx_base, name=f"Item {i+1} Counter", ph_type="body",
            x_px=SIDE_X, y_px=item_y + 12, w_px=SIDE_W, h_px=22,
            prompt_text=sample["counter"],
            size_px=14, font=T.FONT_MONO,
            color=counter_color, uppercase=True, tracking_em=0.1,
        )

        # Heading — display medium.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Item {i+1} Heading", ph_type="body",
            x_px=SIDE_X, y_px=item_y + 40, w_px=SIDE_W, h_px=36,
            prompt_text=sample["heading"],
            size_px=24, weight="medium", color=T.INK,
            tracking_em=-0.012, line_height=1.15,
        )

        # Body — graphite explainer.
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Item {i+1} Body", ph_type="body",
            x_px=SIDE_X, y_px=item_y + 80, w_px=SIDE_W, h_px=item_h - 88,
            prompt_text=sample["body"],
            size_px=15, color=T.GRAPHITE, line_height=1.45,
        )
