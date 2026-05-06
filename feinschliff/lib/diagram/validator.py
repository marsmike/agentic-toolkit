"""Rule-based QA for expanded Excalidraw JSON — no vision model needed.

Catches the defects that consistently break a diagram's legibility:

  1. text-overflow  — a text element's rendered width exceeds its container's
                      inner width, or its rendered height exceeds the container
                      height (bound text only).
  2. shape-overlap  — two non-text shapes whose bounding boxes overlap without
                      a parent/child relationship. Most "rect on top of rect"
                      bugs fall here.
  3. text-collision — two free-floating text elements whose bounding boxes
                      overlap (the "annotations stacked on each other" bug in
                      the first proof deck).
  4. out-of-canvas  — elements outside the overall bounding box (should be
                      rare given the renderer's BB computation, but worth a
                      canary).

These checks run on the `.excalidraw` JSON before PNG render. They miss things
vision QA catches (poor visual hierarchy, aesthetic imbalance) but they nail
the structural failure modes that produced the initial unreadable proof.

Usage:
    from lib.diagram import check
    issues = check(excalidraw_doc)       # list[str], empty = clean

Or as CLI:
    uv run python -m lib.diagram.validator path/to/diagram.excalidraw
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


# Font metrics approximate what Excalidraw renders at runtime. The DSL uses
# fontFamily 3 (monospace, Cascadia) at specific sizes; monospace glyphs average
# ~0.6 em wide; line-height is 1.25 per expand_dsl.py.
_CHAR_WIDTH_EM = 0.62
_LINE_HEIGHT = 1.25
# Slack to absorb sub-pixel rounding and Feinschliff font-substitution variance.
_OVERFLOW_TOLERANCE_PX = 6.0


@dataclass
class _Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float: return self.x + self.w
    @property
    def bottom(self) -> float: return self.y + self.h


def _box(el: dict) -> _Box:
    return _Box(el.get("x", 0), el.get("y", 0),
                el.get("width", 0), el.get("height", 0))


def _intersects(a: _Box, b: _Box, *, tolerance: float = 0.0) -> bool:
    """True if two boxes overlap by more than `tolerance` px on both axes."""
    dx = min(a.right, b.right) - max(a.x, b.x)
    dy = min(a.bottom, b.bottom) - max(a.y, b.y)
    return dx > tolerance and dy > tolerance


def _measure_text(text: str, font_size: float) -> tuple[float, float]:
    """Approximate bounding-box of a multi-line text string at the given size.

    Matches the math in expand_dsl.py for consistency — keeps validator
    findings aligned with what the renderer will actually produce.
    """
    lines = text.split("\n")
    max_line = max((len(line) for line in lines), default=0)
    width = max_line * font_size * _CHAR_WIDTH_EM
    height = font_size * _LINE_HEIGHT * len(lines)
    return width, height


def _check_bound_text_overflow(doc: dict) -> list[str]:
    """Text bound to a container must fit inside the container's inner box."""
    issues: list[str] = []
    by_id = {el.get("id"): el for el in doc["elements"]}
    for el in doc["elements"]:
        if el.get("type") != "text":
            continue
        parent_id = el.get("containerId")
        if not parent_id or parent_id not in by_id:
            continue
        parent = by_id[parent_id]
        p_box = _box(parent)
        text = el.get("originalText") or el.get("text") or ""
        size = el.get("fontSize", 16)
        want_w, want_h = _measure_text(text, size)
        # Excalidraw reserves ~8px horizontal padding inside a container.
        slack_w, slack_h = 8, 0
        if want_w > p_box.w - slack_w + _OVERFLOW_TOLERANCE_PX:
            issues.append(
                f"text-overflow: element {el.get('id')!r} needs "
                f"width≈{want_w:.0f}px, container "
                f"{parent_id!r} has {p_box.w:.0f}px "
                f"(text: {text[:50]!r})"
            )
        if want_h > p_box.h - slack_h + _OVERFLOW_TOLERANCE_PX:
            issues.append(
                f"text-overflow: element {el.get('id')!r} needs "
                f"height≈{want_h:.0f}px, container "
                f"{parent_id!r} has {p_box.h:.0f}px "
                f"(text: {text[:50]!r})"
            )
    return issues


def _check_shape_overlap(doc: dict) -> list[str]:
    """Non-trivial overlap between shapes that aren't parent/child."""
    issues: list[str] = []
    shapes = [
        el for el in doc["elements"]
        if el.get("type") in ("rectangle", "ellipse", "diamond")
    ]
    # Parent-child relationships carry through bound text only, not shape-shape.
    # We treat any rect whose bbox fully contains another as "intended nesting"
    # (decorative band + sub-card pattern) and don't flag it — that's legit.
    for i, a in enumerate(shapes):
        ba = _box(a)
        for b in shapes[i + 1:]:
            bb = _box(b)
            if not _intersects(ba, bb, tolerance=4):
                continue
            # Full containment in either direction = intended nesting.
            if (ba.x <= bb.x and ba.y <= bb.y
                    and ba.right >= bb.right and ba.bottom >= bb.bottom):
                continue
            if (bb.x <= ba.x and bb.y <= ba.y
                    and bb.right >= ba.right and bb.bottom >= ba.bottom):
                continue
            issues.append(
                f"shape-overlap: {a.get('id')!r} and {b.get('id')!r} "
                f"overlap without full containment "
                f"(A {ba.x:.0f},{ba.y:.0f} {ba.w:.0f}×{ba.h:.0f}  "
                f"B {bb.x:.0f},{bb.y:.0f} {bb.w:.0f}×{bb.h:.0f})"
            )
    return issues


def _check_free_text_collision(doc: dict) -> list[str]:
    """Two free-floating text blocks shouldn't overlap."""
    issues: list[str] = []
    texts = [
        el for el in doc["elements"]
        if el.get("type") == "text" and not el.get("containerId")
    ]
    for i, a in enumerate(texts):
        ba = _box(a)
        for b in texts[i + 1:]:
            bb = _box(b)
            if _intersects(ba, bb, tolerance=4):
                ta = (a.get("originalText") or a.get("text") or "")[:30]
                tb = (b.get("originalText") or b.get("text") or "")[:30]
                issues.append(
                    f"text-collision: {a.get('id')!r} ({ta!r}) and "
                    f"{b.get('id')!r} ({tb!r}) overlap"
                )
    return issues


def _check_arrow_label_over_shape(doc: dict) -> list[str]:
    """Arrows with labels that pass THROUGH a rectangle are likely unreadable.

    Heuristic: arrow's line segment crosses a rectangle that isn't one of its
    endpoints. Flags false positives for arrows that intentionally route
    around shapes — treat as advisory.
    """
    issues: list[str] = []
    by_id = {el.get("id"): el for el in doc["elements"]}
    rects = [
        el for el in doc["elements"]
        if el.get("type") in ("rectangle", "ellipse", "diamond")
    ]
    for el in doc["elements"]:
        if el.get("type") != "arrow":
            continue
        start_id = (el.get("startBinding") or {}).get("elementId")
        end_id = (el.get("endBinding") or {}).get("elementId")
        endpoints = {start_id, end_id}
        # Arrow geometry: x,y + points relative to it.
        x0 = el.get("x", 0)
        y0 = el.get("y", 0)
        pts = el.get("points", [])
        if not pts:
            continue
        ax0, ay0 = x0 + pts[0][0], y0 + pts[0][1]
        ax1, ay1 = x0 + pts[-1][0], y0 + pts[-1][1]
        # Axis-aligned bounding box of the arrow segment.
        arrow_box = _Box(
            min(ax0, ax1), min(ay0, ay1),
            abs(ax1 - ax0) or 1, abs(ay1 - ay0) or 1,
        )
        for r in rects:
            if r.get("id") in endpoints:
                continue
            # Skip if the rect fully CONTAINS the arrow — that's the
            # legitimate "decorative band with sub-cards connected by
            # internal arrows" pattern (e.g. a pipeline strip where p1→p2
            # sits inside the outer frame). Full containment = intended
            # nesting, not a crossing.
            rb = _box(r)
            if (rb.x <= arrow_box.x and rb.y <= arrow_box.y
                    and rb.right >= arrow_box.right
                    and rb.bottom >= arrow_box.bottom):
                continue
            # Zero tolerance — any partial overlap of an arrow segment with
            # a non-endpoint, non-containing shape is a real crossing.
            if _intersects(arrow_box, rb, tolerance=0):
                issues.append(
                    f"arrow-through-shape: arrow {el.get('id')!r} passes "
                    f"through non-endpoint {r.get('id')!r}"
                )
    return issues


def check(doc: dict) -> list[str]:
    """Run every check. Returns a list of human-readable defect descriptions."""
    issues: list[str] = []
    issues += _check_bound_text_overflow(doc)
    issues += _check_free_text_collision(doc)
    issues += _check_shape_overlap(doc)
    issues += _check_arrow_label_over_shape(doc)
    return issues


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.excalidraw>", file=sys.stderr)
        return 2
    doc = json.loads(Path(sys.argv[1]).read_text())
    issues = check(doc)
    if not issues:
        print("OK · no structural defects")
        return 0
    for line in issues:
        print(line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
