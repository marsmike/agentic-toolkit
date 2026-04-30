"""Feinschliff · V-Model — paired verification/validation phases + pivot.

Reference: Claude Design `Feinschliff Showcase Deck.html` slide 32.

Composition:
  - Chrome (logo, pgmeta, footer) painted by `paint_chrome`.
  - Kicker (mono orange uppercase) under the logo rail — frames the two
    arms of the V (Verification · Validation).
  - Action title — hero sentence at 52px medium — carries the message.
  - V-Model diagram in the lower two-thirds: four phase/test pairs on a
    tapered 16-col grid, each joined by a dashed connector with a
    centred pill-tag, closing at a dark pivot box ("Coding").

Placeholder map:
    0    action_title
    11   kicker
    20,21  pair 1 left_counter, left_title
    22,23  pair 1 right_counter, right_title
    24     pair 1 connector
    25..29 pair 2 (left_c, left_t, right_c, right_t, conn)
    30..34 pair 3
    35..39 pair 4
    40,41  pivot counter, pivot title
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, add_v_model,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · V-Model"

# ─── Geometry (1920 × 1080) ──────────────────────────────────────────────
_CONTENT_X = 100
_CONTENT_W = 1720

_KICKER_Y = 180
_TITLE_Y = 220
_TITLE_H = 160

_DIAGRAM_X = 160
_DIAGRAM_Y = 420
_DIAGRAM_W = 1600
_DIAGRAM_H = 560


# ─── Default prompts (shown in an un-filled layout) ──────────────────────
_SAMPLE_PAIRS = [
    ("Phase 01", "Requirement gathering", "Test 01", "Acceptance testing",  "Acceptance plan"),
    ("Phase 02", "System analysis",       "Test 02", "System testing",      "System test plan"),
    ("Phase 03", "Software design",       "Test 03", "Integration testing", "Integration"),
    ("Phase 04", "Module design",         "Test 04", "Unit testing",        "Unit tests"),
]
_SAMPLE_PIVOT = ("Pivot", "Coding & implementation")


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="V-Model")

    # ── Kicker (mono orange uppercase) ───────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Kicker", ph_type="body",
        x_px=_CONTENT_X, y_px=_KICKER_Y, w_px=_CONTENT_W, h_px=30,
        prompt_text="Verification · Validation",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.12,
    )

    # ── Action title (hero sentence, idx=0) ──────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Action Title", ph_type="title",
        x_px=_CONTENT_X, y_px=_TITLE_Y, w_px=_CONTENT_W, h_px=_TITLE_H,
        prompt_text=(
            "Every design step on the left has a matching test on the "
            "right — the V-model pairs them."
        ),
        size_px=52, weight="medium",
        color=T.BLACK, tracking_em=-0.015, line_height=1.15,
    )

    # ── V-Model diagram ──────────────────────────────────────────────────
    bboxes = add_v_model(
        layout, _DIAGRAM_X, _DIAGRAM_Y, _DIAGRAM_W, _DIAGRAM_H,
    )

    # Each pair uses 5 placeholder idxs: left_counter, left_title,
    # right_counter, right_title, connector. Base = 20, step = 5.
    for i, (lc, lt, rc, rt, ct) in enumerate(_SAMPLE_PAIRS):
        idx_base = 20 + i * 5
        pbox = bboxes["phases"][i]
        tbox = bboxes["tests"][i]
        cbox = bboxes["conns"][i]

        # Left phase · counter (mono graphite) · title (medium ink, left)
        add_text_placeholder(
            layout, idx=idx_base, name=f"Pair {i+1} L Counter", ph_type="body",
            x_px=pbox["text_x"], y_px=pbox["counter_y"],
            w_px=pbox["text_w"], h_px=20,
            prompt_text=lc, size_px=12, font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.14,
        )
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Pair {i+1} L Title", ph_type="body",
            x_px=pbox["text_x"], y_px=pbox["title_y"],
            w_px=pbox["text_w"], h_px=46,
            prompt_text=lt, size_px=15, weight="medium",
            color=T.INK, line_height=1.15, tracking_em=-0.01,
        )

        # Right test · counter (mono orange_hover) · title (medium ink, right)
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Pair {i+1} R Counter", ph_type="body",
            x_px=tbox["text_x"], y_px=tbox["counter_y"],
            w_px=tbox["text_w"], h_px=20,
            prompt_text=rc, size_px=12, font=T.FONT_MONO,
            color=T.ACCENT_HOVER, uppercase=True, tracking_em=0.14,
            align="r",
        )
        add_text_placeholder(
            layout, idx=idx_base + 3, name=f"Pair {i+1} R Title", ph_type="body",
            x_px=tbox["text_x"], y_px=tbox["title_y"],
            w_px=tbox["text_w"], h_px=46,
            prompt_text=rt, size_px=15, weight="medium",
            color=T.INK, line_height=1.15, tracking_em=-0.01,
            align="r",
        )

        # Connector tag (mono graphite, centred on the pill rect)
        add_text_placeholder(
            layout, idx=idx_base + 4, name=f"Pair {i+1} Connector", ph_type="body",
            x_px=cbox["x"] + 8, y_px=cbox["y"] + 4,
            w_px=cbox["w"] - 16, h_px=cbox["h"] - 8,
            prompt_text=ct, size_px=11, font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
            align="c",
        )

    # ── Pivot (INK fill, orange top border, white text centred) ──────────
    piv = bboxes["pivot"]
    pvc, pvt = _SAMPLE_PIVOT
    add_text_placeholder(
        layout, idx=40, name="Pivot Counter", ph_type="body",
        x_px=piv["text_x"], y_px=piv["counter_y"],
        w_px=piv["text_w"], h_px=20,
        prompt_text=pvc, size_px=12, font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.14,
        align="c",
    )
    add_text_placeholder(
        layout, idx=41, name="Pivot Title", ph_type="body",
        x_px=piv["text_x"], y_px=piv["title_y"],
        w_px=piv["text_w"], h_px=40,
        prompt_text=pvt, size_px=22, weight="medium",
        color=T.BLACK, tracking_em=-0.012, align="c",
    )
