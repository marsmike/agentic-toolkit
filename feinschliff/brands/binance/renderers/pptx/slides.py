"""Demo deck — one slide per named feinschliff layout, placeholder content.

Workflow:
  - Pick a layout by name.
  - Add a slide from it.
  - Fill each placeholder (by idx) with neutral placeholder text.

The point of the demo deck is to validate the renderer works — not to tell
a story. PowerPoint users who insert a fresh slide from a layout see the
layout's prompt text instead — so the same layouts work for both the
"finished showcase" generated here and "start from scratch" via Insert →
New Slide.
"""
from __future__ import annotations

from lxml import etree
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu

from pptx import Presentation

import theme as T
from geometry import pt_from_px
from layouts import layout_by_name


# ─── Placeholder-fill helpers ─────────────────────────────────────────────
def _placeholder_by_idx(slide, idx: int):
    """Find a placeholder shape by its idx. idx=0 means the title placeholder."""
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == idx:
            return ph
    return None


def fill(slide, idx: int, text: str):
    """Replace placeholder text by copying the layout placeholder's paragraph
    structure (pPr + rPr) and only swapping the <a:t> text content. This
    preserves font, alignment, tracking, colour and line-height from the
    layout without the slide needing its own copy.
    """
    ph = _placeholder_by_idx(slide, idx)
    if ph is None:
        raise KeyError(f"slide has no placeholder idx={idx}")

    # Pull the matching placeholder off the layout so we can steal its style.
    layout = slide.slide_layout
    layout_ph = None
    for lp in layout.placeholders:
        if lp.placeholder_format.idx == idx:
            layout_ph = lp
            break

    txBody = ph.text_frame._txBody
    # Drop slide placeholder's current paragraphs.
    for p in list(txBody.findall(qn("a:p"))):
        txBody.remove(p)

    lines = text.split("\n")
    if layout_ph is None:
        # No layout counterpart — fall back to plain text.
        for line in lines:
            p = etree.SubElement(txBody, qn("a:p"))
            r = etree.SubElement(p, qn("a:r"))
            t = etree.SubElement(r, qn("a:t"))
            t.text = line
        return

    # Use the layout's first paragraph as the style template.
    layout_txBody = layout_ph.text_frame._txBody
    template_p = layout_txBody.find(qn("a:p"))

    for line in lines:
        new_p = _clone_paragraph_with_text(template_p, line)
        txBody.append(new_p)


def _clone_paragraph_with_text(template_p, text: str):
    """Deep-copy an <a:p> and replace its combined run text with `text`,
    keeping its pPr + first run's rPr verbatim."""
    p = etree.fromstring(etree.tostring(template_p))
    # Remove all existing runs, keeping pPr and (optionally) endParaRPr.
    for child in list(p):
        local = etree.QName(child.tag).localname
        if local in ("r", "br", "fld"):
            p.remove(child)

    # Build a single run using the template's first run's rPr (if any).
    template_r = template_p.find(qn("a:r"))
    if template_r is not None and template_r.find(qn("a:rPr")) is not None:
        rPr_src = etree.fromstring(etree.tostring(template_r.find(qn("a:rPr"))))
    else:
        rPr_src = None

    r = etree.Element(qn("a:r"))
    if rPr_src is not None:
        r.append(rPr_src)
    t = etree.SubElement(r, qn("a:t"))
    t.text = text

    # Insert <a:r> after any pPr, before endParaRPr.
    insert_index = 0
    for i, child in enumerate(p):
        if etree.QName(child.tag).localname == "pPr":
            insert_index = i + 1
    p.insert(insert_index, r)
    return p


def add(prs: Presentation, layout_name: str, **fills):
    """Add a slide from a named layout and fill its placeholders by idx.

    Usage:  add(prs, "Feinschliff · Title · Accent", _10="Eyebrow text", _0="Big title")

    Placeholders the caller didn't fill are stripped from the slide's XML so
    PowerPoint doesn't fall back to its generic "Click to add text" /
    "Text hinzufügen" prompt at render time. The layout's placeholder prompts
    only survive on slides that are explicitly left editable — callers who
    want that can opt out via the `_keep_placeholders=True` kwarg.
    """
    keep_placeholders = bool(fills.pop("_keep_placeholders", False))

    slide = prs.slides.add_slide(layout_by_name(prs, layout_name))
    filled_idxs = set()
    for key, value in fills.items():
        if not key.startswith("_"):
            continue
        idx = int(key[1:])
        fill(slide, idx, value)
        filled_idxs.add(idx)

    if not keep_placeholders:
        _strip_unfilled_placeholders(slide, filled_idxs)

    return slide


def add_diagram(
    prs, *, slug: str, dsl: str, out_dir,
    eyebrow: str | None = None,
    title: str | None = None,
    caption: str | None = None,
):
    """Add a diagram slide. Runs the DSL → expand → feinschliff theme → PNG
    pipeline, embeds the PNG at the diagram frame (aspect-preserved, centered),
    and fills eyebrow/title/caption placeholders.

    slug: filename stem for the artifacts (e.g. "03-architecture-overview").
    dsl:  Excalidraw DSL source.
    out_dir: deck output dir; artifacts land under <out_dir>/diagrams/.

    Returns the slide.
    """
    import sys
    from pathlib import Path
    from PIL import Image
    from pptx.util import Emu
    from geometry import px
    from diagram_pipeline import render_diagram

    import theme as T
    from components.primitives import add_rect

    out_dir = Path(out_dir)
    png_path, issues = render_diagram(dsl, slug, out_dir)
    for line in issues:
        print(f"  [validator] {slug}: {line}", file=sys.stderr)

    # Fill placeholders via the existing add() helper.
    fills = {}
    if eyebrow is not None: fills["_10"] = eyebrow
    if title   is not None: fills["_0"]  = title
    if caption is not None: fills["_11"] = caption
    slide = add(prs, "Feinschliff · Diagram", **fills)

    # Diagram frame: x=100, y=250, w=1720, h=680 (CSS px).
    frame_x, frame_y, frame_w, frame_h = 100, 250, 1720, 680

    # Paint a white rect over the full frame so the layout's FOG background
    # and "DIAGRAM · FILL VIA /DECK" debug label are hidden wherever the
    # aspect-fit PNG doesn't cover. Filled slides look clean; unfilled
    # layouts keep the FOG chrome for visibility.
    add_rect(slide, frame_x, frame_y, frame_w, frame_h, fill=T.WHITE)

    with Image.open(png_path) as img:
        img_w, img_h = img.size
    img_aspect = img_w / img_h
    frame_aspect = frame_w / frame_h
    if img_aspect > frame_aspect:
        # Image wider than frame — fit by width, center vertically.
        new_w = frame_w
        new_h = new_w / img_aspect
    else:
        # Image taller than frame — fit by height, center horizontally.
        new_h = frame_h
        new_w = new_h * img_aspect
    cx = frame_x + (frame_w - new_w) / 2
    cy = frame_y + (frame_h - new_h) / 2

    slide.shapes.add_picture(
        str(png_path),
        Emu(px(cx)), Emu(px(cy)),
        width=Emu(px(new_w)), height=Emu(px(new_h)),
    )
    return slide


def add_radar(
    prs, *, slug: str, view: str, vault, out_dir,
    volume: int | None = None,
    new_since: str | None = None,
    publish: bool = True,
):
    """Add a tech-radar slide. Renders the radar via ``radar-engine`` and drops
    the resulting PNG full-bleed into the ``Feinschliff · Tech Radar · Full Bleed``
    layout.

    The radar SVG already paints its own slide chrome (logo, eyebrow, title,
    subtitle, footer) — see ``tech-radar/engine/templates/radar.svg.j2``. The
    layout is therefore deliberately empty (a single full-canvas image
    placeholder); we paint nothing extra here.

    Mirrors ``add_diagram()`` for consistency: programmatic call → pipeline
    runs → PNG embedded → slide returned.

    slug:    filename stem under ``<out_dir>/radars/`` (e.g. ``"03-genai-tw"``).
             The radar render itself names files after the view (e.g.
             ``genai-thoughtworks.png``); slug exists so multiple radar slides
             in one deck don't collide on disk.
    view:    view name from ``Tech-Radar/Views.yaml``.
    vault:   path to the Obsidian vault root.
    out_dir: deck output dir; renders land under ``<out_dir>/radars/<slug>/``.
    volume:  optional explicit edition volume (defaults to latest+1).
    new_since: optional ISO date threshold for the NEW badge (defaults to
               today − 14 days inside the engine).
    publish: whether to snapshot this render to ``Tech-Radar/editions/``.
    """
    import sys
    from datetime import date as _date
    from pathlib import Path
    from pptx.util import Emu

    # Path-inject the tech-radar plugin so ``engine.api`` is importable —
    # mirrors the cross-plugin pattern used by ``diagram_pipeline`` for the
    # excalidraw skill (see top of that file).
    _HERE = Path(__file__).resolve().parent
    _RADAR_PLUGIN = _HERE.parents[4] / "tech-radar"
    if str(_RADAR_PLUGIN) not in sys.path:
        sys.path.insert(0, str(_RADAR_PLUGIN))

    from engine.api import render_view  # type: ignore[import-not-found]

    out_dir = Path(out_dir)
    radar_out = out_dir / "radars" / slug
    radar_out.mkdir(parents=True, exist_ok=True)

    new_since_date = _date.fromisoformat(new_since) if new_since else None
    result = render_view(
        view=view,
        vault=Path(vault),
        output_dir=radar_out,
        volume=volume,
        new_since=new_since_date,
        publish=publish,
    )

    # Build the slide from the dedicated layout. The layout's image
    # placeholder is purely a marker for human editors — we drop the PNG at
    # the canvas origin sized to the full slide regardless.
    slide = add(prs, "Feinschliff · Tech Radar · Full Bleed")
    slide.shapes.add_picture(
        str(result.png_path),
        Emu(0), Emu(0),
        width=Emu(_px_to_emu_full_canvas()), height=Emu(_px_to_emu_full_canvas(height=True)),
    )
    return slide


def _px_to_emu_full_canvas(*, height: bool = False) -> int:
    """Full-canvas px → EMU. Defers to the project's geometry helper so the
    canvas dimensions stay sourced from feinschliff tokens, not hard-coded here."""
    from geometry import px
    return px(1080) if height else px(1920)


def _strip_unfilled_placeholders(slide, filled_idxs: set[int]) -> None:
    """Remove placeholder <p:sp> shapes the caller didn't fill.

    Title placeholders have no explicit idx attribute in OOXML — python-pptx
    treats their idx as 0. Non-placeholder shapes are untouched.
    """
    spTree = slide.shapes._spTree
    to_remove = []
    for sp in spTree.findall(qn("p:sp")):
        nvSpPr = sp.find(qn("p:nvSpPr"))
        if nvSpPr is None:
            continue
        nvPr = nvSpPr.find(qn("p:nvPr"))
        if nvPr is None:
            continue
        ph = nvPr.find(qn("p:ph"))
        if ph is None:
            continue  # not a placeholder
        idx = int(ph.get("idx", "0"))
        if idx not in filled_idxs:
            to_remove.append(sp)
    for sp in to_remove:
        spTree.remove(sp)


# ─── Demo deck — one slide per named layout, neutral placeholder content ───
def build_demo_deck(prs: Presentation):
    # Title · Accent
    add(prs, "Feinschliff · Title · Accent",
        _10="Layout · title accent",
        _0="Binance\nshowcase deck.")

    # Title · Ink
    add(prs, "Feinschliff · Title · Ink",
        _10="Layout · title ink",
        _0="Title slide,\ndark variant.")

    # Title + Picture
    add(prs, "Feinschliff · Title + Picture",
        _10="Layout · title + picture",
        _0="Title with\na picture.",
        _11="Full-bleed image on the right half, title stacked on the left. Logo and page meta sit on top.")

    # Agenda
    add(prs, "Feinschliff · Agenda",
        _10="Layout · agenda",
        _0="Agenda placeholder.",
        _20="01 / 06", _21="Item 01",  _22="Description for item 01.",
        _23="02 / 06", _24="Item 02",  _25="Description for item 02.",
        _26="03 / 06", _27="Item 03",  _28="Description for item 03.",
        _29="04 / 06", _30="Item 04",  _31="Description for item 04.",
        _32="05 / 06", _33="Item 05",  _34="Description for item 05.",
        _35="06 / 06", _36="Item 06",  _37="Description for item 06.")

    # Chapter · Accent
    add(prs, "Feinschliff · Chapter · Accent",
        _10="Layout · chapter accent",
        _0="01\nChapter.")

    # Chapter · Ink + Picture
    add(prs, "Feinschliff · Chapter · Ink + Picture",
        _10="Layout · chapter ink",
        _0="02\nChapter\n& Picture.")

    # KPI Grid
    add(prs, "Feinschliff · KPI Grid",
        _10="Layout · KPI grid",
        _0="Headline numbers.",
        _20="Metric 1", _21="Caption 1",
        _22="Metric 2", _23="Caption 2",
        _24="Metric 3", _25="Caption 3",
        _26="Metric 4", _27="Caption 4")

    # 2-Column Cards
    add(prs, "Feinschliff · 2-Column Cards",
        _10="Layout · 2-column cards",
        _0="Two columns.",
        _20="01 · Column",
        _21="Lead sentence for the first column.",
        _22="Supporting detail line two.",
        _23="02 · Column",
        _24="Lead sentence for the second column.",
        _25="Supporting detail line two.")

    # 3-Column
    add(prs, "Feinschliff · 3-Column",
        _10="Layout · 3-column",
        _0="Three columns.",
        _20="01", _21="Column one.",
        _22="Description for the first column.",
        _23="02", _24="Column two.",
        _25="Description for the second column.",
        _26="03", _27="Column three.",
        _28="Description for the third column.")

    # 4-Column Cards
    add(prs, "Feinschliff · 4-Column Cards",
        _10="Layout · 4-column cards",
        _0="Four columns.",
        _20="Q1 · Phase",
        _21="Lead sentence for phase one.",
        _22="Supporting detail.",
        _23="Q2 · Phase",
        _24="Lead sentence for phase two.",
        _25="Supporting detail.",
        _26="Q3 · Phase",
        _27="Lead sentence for phase three.",
        _28="Supporting detail.",
        _29="Q4 · Phase",
        _30="Lead sentence for phase four.",
        _31="Supporting detail.")

    # Text + Picture
    add(prs, "Feinschliff · Text + Picture",
        _10="Layout · text + picture",
        _0="Text paired\nwith a\npicture.",
        _11="Body copy on one side, image frame on the other. Replace via /deck.")

    # Full-bleed Cover
    add(prs, "Feinschliff · Full-bleed Cover",
        _10="Layout · full-bleed cover",
        _0="An image does\nthe talking.")

    # Bar Chart
    add(prs, "Feinschliff · Bar Chart",
        _10="Layout · bar chart",
        _0="Headline takeaway from the chart.",
        _20="Bar A", _21="62%",
        _22="Bar B", _23="24%",
        _24="Bar C", _25="11%",
        _26="Bar D", _27="3%",
        _40="Source · placeholder")

    # Components Showcase
    add(prs, "Feinschliff · Components Showcase",
        _10="Layout · components",
        _0="UI library preview.")

    # Quote
    add(prs, "Feinschliff · Quote",
        _0="“A short, memorable line that earns its full slide.”",
        _10="Attribution · placeholder")

    # End
    add(prs, "Feinschliff · End",
        _0="Thank you.",
        _10="Feinschliff · v0.1 · 2026")

    # Funnel
    add(prs, "Feinschliff · Funnel",
        _10="Layout · funnel",
        _0="Headline takeaway about the funnel drop-off.",
        _20="Stage 1", _21="Description",         _22="100",  _23="100%",
        _24="Stage 2", _25="Description",         _26="84",   _27="84%",
        _28="Stage 3", _29="Description",         _30="62",   _31="62%",
        _32="Stage 4", _33="Description",         _34="36",   _35="36%",
        _50="−22 pt", _51="Stage 1 → 2",
        _52="Annotation explaining the largest drop-off.",
        _54="−14 pt", _55="Stage 3 → 4",
        _56="Annotation explaining the secondary drop-off.")

    # Line Chart
    add(prs, "Feinschliff · Line Chart",
        _10="Layout · line chart",
        _0="Headline takeaway from the trend over time.",
        _20="P1", _21="P2", _22="P3", _23="P4", _24="P5",
        _30="Series A",
        _31="Series B",
        _40="Source · placeholder")

    # Waterfall
    add(prs, "Feinschliff · Waterfall",
        _10="Layout · waterfall",
        _0="Headline takeaway about the bridge.",
        _20="13.4",  _21="Base",
        _24="+0.6",  _25="Step 1",
        _28="+0.4",  _29="Step 2",
        _32="+0.3",  _33="Step 3",
        _36="−0.3",  _37="Step 4",
        _40="−0.2",  _41="Step 5",
        _44="14.1",  _45="Total",
        _60="Source · placeholder")

    # Stacked Bar
    add(prs, "Feinschliff · Stacked Bar",
        _10="Layout · stacked bar",
        _0="Headline takeaway about the mix over time.",
        _20="P1", _21="P2", _22="P3", _23="P4", _24="P5",
        _30="11.9", _31="12.4", _32="12.9", _33="13.4", _34="14.1",
        _40="Series A",  _41="−6% · 5y",
        _42="Series B",  _43="+31% · 5y",
        _44="Series C",  _45="+31% · 5y",
        _46="Series D",  _47="+367% · 5y",
        _60="Source · placeholder")

    # 2×2 Matrix
    add(prs, "Feinschliff · 2×2 Matrix",
        _10="Layout · 2×2 matrix",
        _0="Headline takeaway about prioritisation.",
        _20="Top-right item.",
        _21="High-impact, low-effort initiative.",
        _24="Top-left item.",
        _25="High-impact, high-effort initiative.",
        _28="Bottom-right item.",
        _29="Low-impact, low-effort initiative.",
        _32="Bottom-left item.",
        _33="Low-impact, high-effort initiative.",
        _41="Effort to ship",
        _42="I\nm\np\na\nc\nt")

    # Gantt
    add(prs, "Feinschliff · Gantt",
        _10="Layout · Gantt",
        _0="Headline takeaway about the delivery plan.",
        _20="Q1 · Plan", _21="Q2 · Build", _22="Q3 · Pilot", _23="Q4 · Scale",
        _30="Workstream 1\nOwner · Team A",
        _31="Workstream 2\nOwner · Team B",
        _32="Workstream 3\nOwner · Team C",
        _33="Workstream 4\nOwner · Team D",
        _40="Milestone 1",
        _43="Milestone 2",
        _47="Milestone 3",
        _50="Preview",
        _51="GA",
        _60="Committed · Critical path · Dependency window · Milestone")

    # Venn
    add(prs, "Feinschliff · Venn",
        _10="Layout · Venn",
        _0="Headline takeaway about the intersection of three sets.",
        _20="Set A",   _21="Description A",
        _24="Set B",   _25="Description B",
        _28="Set C",   _29="Description C",
        _30="Overlap A∩B",
        _31="Overlap B∩C",
        _32="Overlap A∩C",
        _33="Center\nA∩B∩C",
        _40="01 · A × B",  _41="Overlap label",
        _42="Description of the A × B intersection.",
        _44="02 · B × C",  _45="Overlap label",
        _46="Description of the B × C intersection.",
        _48="03 · A × C",  _49="Overlap label",
        _50="Description of the A × C intersection.",
        _52="Center",      _53="Triple overlap",
        _54="Description of the central intersection.")

    # Scorecard
    add(prs, "Feinschliff · Scorecard",
        _10="Layout · scorecard",
        _0="Headline takeaway about portfolio health.",
        _20="P1", _21="P2", _22="P3", _23="P4",
        _30="Workstream 1",
        _31="Workstream 2",
        _32="Workstream 3",
        _33="Workstream 4",
        _43="Annotation for cell P3 / row 1.",
        _48="Annotation for cell P3 / row 2.",
        _53="Annotation for cell P3 / row 3.",
        _58="Annotation for cell P3 / row 4.",
        _60="Source · placeholder")

    # Pyramid
    add(prs, "Feinschliff · Pyramid",
        _10="Layout · pyramid",
        _0="Headline takeaway about the value hierarchy.",
        _20="Apex line.",
        _21="Description of the top tier.",
        _22="Tier 03 · Apex",
        _24="Middle line.",
        _25="Description of the middle tier.",
        _26="Tier 02 · Middle",
        _28="Base line.",
        _29="Description of the base tier.",
        _30="Tier 01 · Foundation")

    # Process Flow
    add(prs, "Feinschliff · Process Flow",
        _10="Layout · process flow",
        _0="Five stages, one highlighted as active.",
        _20="01", _21="Stage 1", _22="Description for stage 1.",
        _24="02", _25="Stage 2", _26="Description for stage 2.",
        _28="03", _29="Stage 3", _30="Description for stage 3.",
        _32="04", _33="Stage 4", _34="Description for stage 4.",
        _36="05", _37="Stage 5", _38="Description for stage 5.",
        _60="Source · placeholder")

    # Graphical
    add(prs, "Feinschliff · Graphical",
        _10="Layout · graphical bars",
        _0="Headline takeaway from the chart.",
        _20="Bar A",  _21="62%",
        _24="Bar B",  _25="24%",
        _28="Bar C",  _29="11%",
        _32="Bar D",  _33="3%",
        _60="Source · placeholder")

    # Action Title
    add(prs, "Feinschliff · Action Title",
        _10="Layout · action title",
        _0="Full-sentence takeaway that states the recommendation directly.",
        _11="Supporting paragraph that explains the evidence behind the recommendation in two or three sentences.",
        _20="+18", _21="%", _22="KPI label 1", _23="Caption 1",
        _24="2.3", _25="×", _26="KPI label 2", _27="Caption 2",
        _60="Source · placeholder")

    # Horizontal Bullets
    add(prs, "Feinschliff · Horizontal Bullets",
        _10="Layout · horizontal bullets",
        _0="Three structured takeaways across one row.",
        _20="01", _21="Heading 1.",
        _22="•  Bullet 1\n•  Bullet 2\n•  Bullet 3",
        _24="02", _25="Heading 2.",
        _26="•  Bullet 1\n•  Bullet 2\n•  Bullet 3",
        _28="03", _29="Heading 3.",
        _30="•  Bullet 1\n•  Bullet 2\n•  Bullet 3",
        _60="Source · placeholder")

    # Vertical Bullets
    add(prs, "Feinschliff · Vertical Bullets",
        _10="Layout · vertical bullets",
        _0="Six numbered rows, plan-of-record style.",
        _11="Subtitle line one.",
        _12="Subtitle line two.",
        _20="01 / 06", _21="Item 01", _22="Description for item 01.",
        _23="02 / 06", _24="Item 02", _25="Description for item 02.",
        _26="03 / 06", _27="Item 03", _28="Description for item 03.",
        _29="04 / 06", _30="Item 04", _31="Description for item 04.",
        _32="05 / 06", _33="Item 05", _34="Description for item 05.",
        _35="06 / 06", _36="Item 06", _37="Description for item 06.")

    # Table
    add(prs, "Feinschliff · Table",
        _10="Layout · table",
        _0="Headline takeaway about the table data.",
        _20="Column 1", _21="Column 2", _22="Column 3", _23="Column 4", _24="Column 5",
        _30="Row 1",  _40="Cell",  _41="Cell",   _42="Cell",  _43="Cell",
        _31="Row 2",  _44="Cell",  _45="Cell",   _46="Cell",  _47="Cell",
        _32="Row 3",  _48="Cell",  _49="Cell",   _50="Cell",  _51="Cell",
        _33="Row 4",  _52="Cell",  _53="Cell",   _54="Cell",  _55="Cell",
        _34="Row 5",  _56="Cell",  _57="Cell",   _58="Cell",  _59="Cell",
        _60="Source · placeholder")

    # Key Takeaways
    add(prs, "Feinschliff · Key Takeaways",
        _10="Layout · key takeaways",
        _0="Three things to remember from this section.",
        _20="01", _21="Takeaway 1.",
        _22="One- or two-sentence elaboration of the first takeaway.",
        _23="Owner · Role",
        _24="02", _25="Takeaway 2.",
        _26="One- or two-sentence elaboration of the second takeaway.",
        _27="Owner · Role",
        _28="03", _29="Takeaway 3.",
        _30="One- or two-sentence elaboration of the third takeaway.",
        _31="Owner · Role")

    # Executive Summary
    add(prs, "Feinschliff · Executive Summary",
        _10="Layout · executive summary",
        _0="One-line summary statement that frames the entire deck.",
        _11="Two-to-three-sentence paragraph that elaborates on the headline and points to the supporting evidence.",
        _20="Insights",
        _21="Insight 1.",
        _22="Description of insight 1.",
        _23="Insight 2.",
        _24="Description of insight 2.",
        _25="Insight 3.",
        _26="Description of insight 3.",
        _27="Insight 4.",
        _28="Description of insight 4.",
        _30="Next steps",
        _31="Next step 1.",
        _32="Description of next step 1.",
        _33="Next step 2.",
        _34="Description of next step 2.",
        _35="Next step 3.",
        _36="Description of next step 3.",
        _37="Next step 4.",
        _38="Description of next step 4.",
        _50="+5.1", _51="%", _52="KPI label 1",
        _53="2.4",  _54="M", _55="KPI label 2",
        _56="37",   _57="",  _58="KPI label 3",
        _60="Source · placeholder")

    # Diagram — minimal example using neutral DSL
    _demo_dsl = '''# Three-layer architecture (placeholder)
text title 100,20 title "Layer A, Layer B, Layer C"
text sub   100,55 subtitle "A neutral three-layer placeholder diagram"

rect a    120,140 1680x140 secondary "LAYER A\\nDescription line for layer A."
rect b    120,310 1680x160 primary   "LAYER B\\nDescription line for layer B."
rect c    120,500 1680x160 ai        "LAYER C\\nDescription line for layer C."

arrow ab  a->b   label:"flow"
arrow bc  b->c   label:"flow"

rect note  120,700 1680x90 start "A short caption that frames the diagram."
'''
    # Diagram demo skipped in this template build — add_diagram() requires the
    # sibling excalidraw plugin (expand_dsl + render_excalidraw). Users who add
    # an excalidraw plugin alongside this brand pack can call add_diagram(...)
    # from their own pipelines. The Feinschliff · Diagram layout is still
    # registered in the catalog; only the demo invocation is omitted here.

    # V-Model
    add(prs, "Feinschliff · V-Model",
        _11="Verification · Validation",
        _0="Every design step on the left has a matching test on the right.",
        _20="Phase 01", _21="Requirement gathering",
        _22="Test 01",  _23="Acceptance testing",
        _24="Acceptance plan",
        _25="Phase 02", _26="System analysis",
        _27="Test 02",  _28="System testing",
        _29="System test plan",
        _30="Phase 03", _31="Software design",
        _32="Test 03",  _33="Integration testing",
        _34="Integration",
        _35="Phase 04", _36="Module design",
        _37="Test 04",  _38="Unit testing",
        _39="Unit tests",
        _40="Pivot", _41="Coding & implementation")
