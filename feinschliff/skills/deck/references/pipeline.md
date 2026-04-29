# /deck Pipeline

The 7-step recipe that `/deck` follows for all modes. Read this before the skill body for the full detail; the skill body is a thin index over this file.

## Step 0 — Set the perfection bar (ask the user)

Before ingesting, ask the user once:

> **How perfect should this be?** Default is **3 iterations** (good enough for most decks). Say "perfectionist" or "polish it" if you want **6 iterations** (first-impression decks, exec audiences, board materials).

The answer sets the iteration budget for step 6. Defaults to 3 if the user doesn't respond or says "normal" / "default".

## Step 1 — Ingest

**Create mode:** parse the brief. Identify:
- Overall deck purpose (executive update, technical review, product announcement, etc.).
- Each distinct concept / topic → one slide.
- Quantitative data → kpi-grid or bar-chart candidates.
- Comparisons → 2-column-cards or bar-chart.
- Sections → chapter-opener if >2 sections.

**Polish mode:** open the `.pptx` with python-pptx. For each slide:
- Extract: title, body text, bullet lists, image references, table data.
- Classify concept (via LLM): one of [title, chapter, agenda, data-quantity, data-comparison, content, quote, closer].
- Capture raw content verbatim — don't paraphrase.

**Critique mode:** same as polish ingest (content is derived from the existing `.pptx`).

**Also infer the design brief.** See `design-brief-schema.md` for fields. Write `design_brief.json` alongside `content_plan.json`.

### Brief inference — concrete procedure

Given `content_plan.json`, produce `design_brief.json` in one LLM pass:

1. **Audience:** infer per `audience-calibration.md` inference cues. Default to `manager` when ambiguous. Record a one-sentence `audience_notes`.
2. **Takeaway:** the single sentence the audience should repeat. Derive from the brief's strongest claim; if several compete, pick the one aligned with the business outcome.
3. **Frame:** apply `narrative-frames.md` inference cues. If ambiguous, SCQA is the default. Name the runner-up in `frame_rationale`.
4. **Hook:** pick a technique (`startling-stat` / `provocative-question` / `brief-story` / `demonstration` / `contrast`) and draft the opener ≤20 words.
5. **Red line:** one sentence capturing the slide sequence's argument arc.
6. **Slides[]:** for each slide in `content_plan.json`, assign a `role` (from the frame's role set), a `claim` (see `slide-claim-test.md` — must be a claim, not a topic), and a one-sentence `audience_fit`.

Validate the result against the schema:

```python
import sys
sys.path.insert(0, "/<path>/agentic-toolkit/feinschliff/skills/deck/lib")
from design_brief import save_brief

save_brief(brief, Path("design_brief.json"))  # raises ValueError on invalid
```

If validation fails, the inference is broken — re-run with the error as additional context.

Output:
- `content_plan.json` — an ordered list of slide intents + raw content.
- `design_brief.json` — audience + narrative frame + takeaway + hook + red line + per-slide role and claim.

## Step 1b — Present the plan (single approval gate)

Print the `design_brief.json` as a compact summary + the planned slide order with roles and claims. Exact format in `modes.md`.

Ask once:

> Approve? (press enter) · Edit: say what to change · Redo from scratch: type 'redo'

### Handling the response

**Empty / "y" / "ok" / "approve":**
Proceed to step 2.

**Free-form edit request** — examples and handling:

| User says | Revise |
|---|---|
| "make it 6 slides" | Cap `slides[]` to 6 by merging / dropping the weakest claims. Re-print. |
| "audience is developers" | Change `audience` to `developer`, re-derive `audience_notes`, re-write each `slides[].audience_fit`, re-print. |
| "drop slide 5" | Remove `slides[4]`, renumber indices, re-print. |
| "use PSSR instead" | Change `frame` to `pssr`, re-sequence slide `role`s per the frame's role order, re-print. |
| "make the takeaway punchier" | Rewrite `takeaway`; if it shifts the whole deck, offer a redo. Re-print. |

Targeted revision preserves everything the user didn't complain about. Re-print the full summary (so the user sees the delta in context); re-ask.

**"redo" / "start over":**
Discard `design_brief.json` and `content_plan.json`, re-run step 1 from scratch, re-print.

### For `/deck critique` mode only

After step 1b displays, stop here. Don't proceed to step 2. Jump directly to step 4 on the existing `.pptx`. See `modes.md`.

## Step 2 — Plan

Read `feinschliff/<brand-root>/catalog/layouts.json` (the active brand's catalog — see `../SKILL.md` for how `<brand-root>` resolves; defaults to `brands/feinschliff/`).

For each slide in `content_plan.json`:
1. Match the concept to candidate layouts via `layouts.json` (use the `concepts` + `role` fields).
2. Pick the best layout using `when_to_use` / `when_not_to_use` guidance. See `visual-vocabulary.md` for the generic concept → visual-type mapping.
   - **Diagram trigger — ALWAYS pick `diagram` when the user's brief mentions** *diagram*, *flowchart*, *architecture*, *architectural overview*, *system overview*, *system architecture*, *layers*, *concept map*, *mind map*, *block diagram*, or phrases like *"show how X connects to Y"*. Also pick `diagram` for any rich free-form visual argument that doesn't fit a parameterized template (process-flow, pyramid, venn, 2x2-matrix, funnel, gantt — prefer those when they fit). **Author the DSL inline** as the `dsl` slot value. Read `../../../excalidraw/references/dsl-syntax.md` on demand for the DSL grammar. One big diagram per slide — never split one concept across two diagram slides.
   - **Tech-radar trigger — ALWAYS pick `tech-radar` when the user's brief mentions** *tech radar*, *technology radar*, *technology landscape*, *what we're tracking*, *GenAI radar*, *ThoughtWorks radar*, or asks for a *"radar of <X>"*. Slot args: `view` (one of: `genai-thoughtworks`, `genai-agents`, `genai-models`, `genai-skills`, `genai-tooling` — see `<vault>/Tech-Radar/Views.yaml` for the live list), and optional `volume` (edition number; defaults to latest+1) and `new_since` (ISO date for the NEW badge; defaults to today−14 days). Pick `genai-thoughtworks` for the all-blips overview unless the user names a specific quadrant. The radar SVG paints its own logo/title/footer, so don't double up with deck-level chrome.
3. Fill each layout's slots per the JSON Schema in `layouts.json`. The slide's `claim` from `design_brief.json` is the raw material for the title slot.
4. If content overflows the layout's slot caps: either shorten (see `content-best-practices.md`) or split into two slides.

Output: `deck_plan.json` — an ordered list of `{layout_id, slot_values}` pairs.

## Step 3 — Build

Import the active brand's Baukasten. The renderer module path depends on the resolved brand pack (`<brand-root>` is `brands/feinschliff/` by default):

```python
import os, sys
ACTIVE_BRAND = os.environ.get("FEINSCHLIFF_BRAND", "feinschliff")
BRAND_ROOT = f"brands/{ACTIVE_BRAND}"

sys.path.insert(0, f"/<path>/agentic-toolkit/feinschliff/{BRAND_ROOT}/renderers/pptx")
from pptx import Presentation
from master import (
    apply_feinschliff_theme,  # or apply_<brand>_theme — exported by the active pack's master.py
    set_slide_size, ensure_n_layouts, reset_master_shapes, reset_layout,
)
import layouts as layouts_mod
import slides as slides_mod
```

Each brand pack exposes its own `apply_<slug>_theme(prs)` function in `master.py`. The feinschliff pack ships `apply_feinschliff_theme`. Use the function exported by the resolved pack.

For each entry in `deck_plan.json`:
- Fetch the renderer module via `layouts.json -> layouts[i].renderer.pptx.module`.
- Add a slide from that layout: `prs.slides.add_slide(layouts_mod.layout_by_name(prs, layout_name))`.
- Fill slots using the `placeholder_map` in the catalog entry. Slots addressed as `"columns[0].body"` map to placeholder idx 22 (for example).
- If the layout is `diagram`: instead of only filling placeholders, call `slides.add_diagram(prs, slug="<NN-topic>", dsl=<dsl-string>, out_dir=<deck-out-dir>, eyebrow=..., title=..., caption=...)`. This runs the DSL → expand → apply the active brand's theme → render PNG pipeline and embeds the PNG into the slide's diagram frame. All four artifacts (`<slug>.dsl`, `<slug>.excalidraw`, `<slug>-<brand>.excalidraw`, `<slug>-<brand>.png`) are preserved under `<deck-out-dir>/diagrams/` for post-build editing.
- If the layout is `tech-radar`: instead of only filling placeholders, call `slides.add_radar(prs, slug="<NN-topic>", view=<view-name>, vault=<vault-path>, out_dir=<deck-out-dir>, volume=<int|None>, new_since=<"YYYY-MM-DD"|None>)`. This runs the radar-engine pipeline (load blips → magnetic positioning → snapshot edition → SVG → PNG) and embeds the rendered PNG full-bleed at (0, 0, 1920, 1080). All artifacts (`<view>.svg`, `<view>.png`, `meta.json`) are preserved under `<deck-out-dir>/radars/<slug>/`. The edition snapshot lands under `<vault>/Tech-Radar/editions/vol-<N>.yaml` (skip with `publish=False` for preview-only renders that should not affect edition history).

Output: `out/<name>.pptx` (draft).

## Step 4 — Verify (visual + theory) — MANDATORY, NEVER SKIPPED

**This step runs at least once. No exceptions.** You do not know whether step 3 succeeded until you look at the rendered PNGs. "The build didn't error" is not verification. Even if the iteration budget is 1, you still run one verify pass before declaring completion.

Render the draft:
```bash
soffice --headless --convert-to pdf --outdir /tmp/deck-verify out/<name>.pptx
pdftoppm -r 96 -png /tmp/deck-verify/<name>.pdf /tmp/deck-verify/slide
```

For each PNG, LLM inspects (visually read the PNG file — do not skip the Read call) for all 11 defect classes per `iteration-loop.md`. The canonical visual reference for "what this layout should look like" is the active brand's `feinschliff/<brand-root>/claude-design/<brand>-2026.html` (e.g. `feinschliff/brands/feinschliff/claude-design/feinschliff-2026.html` by default) — open it alongside when uncertain whether a slide matches brand intent.

**Required artifact:** write `out/verify_report.md` — human-readable, overwritten on each verify pass. Shape:

```markdown
# Verify Report — <name>.pptx

- **Iteration:** 1 of 3
- **Verdict:** dirty — 2 defects across 1 of 8 slides
- **Rendered PNGs:** `/tmp/deck-verify/slide-*.png`
- **Reference:** `feinschliff/<brand-root>/claude-design/<brand>-2026.html`

---

## Slide 3 — "Our Approach" (layout: two-column-cards)

- **claim-title** — title "Our Approach" is a topic noun.
  **Fix:** Rewrite as a claim, e.g. "We ship daily because we test first".
- **bullet-dump** — 7 peer-level bullets, no hierarchy.
  **Fix:** Subordinate under 3 sub-headings; drop weakest two bullets.

## Slide 5 — "Q1 Results" (layout: kpi-grid) ✅

_No defects._

<!-- ...one section per slide... -->
```

The header block is the completion gate: `Verdict:` must be readable by both Claude (to decide whether to loop) and the user (to understand what's wrong). If `verdict` is `clean`, list every slide with `✅ No defects.` so the user sees the full coverage — don't silently omit passing slides.

`out/verify_report.md` is overwritten on each iteration; the file always reflects the most recent build. If you need iteration history, prior reports are recoverable from `git log` or conversation transcript.

If the file does not exist on disk, the deck is not done — regardless of how confident you feel about the build. Before telling the user "done", confirm the file exists and the header says `Verdict: clean` (or budget is exhausted and you're emitting residuals per step 5).

## Step 5 — Revise (if defects)

If `verify_report.md` header says `Verdict: dirty`: adjust `deck_plan.json` (change layouts, shorten text, split slides, rewrite titles as claims) and loop back to step 3. Increment `Iteration:` in the next verify report.

**Hard stop at the budget set in step 0.** Default = 3 iterations, perfectionist = 6. Each iteration = one build + one verify pass. The verify pass runs on iteration 1 too — there is no "skip verify on the last happy-path build" shortcut.

If the final iteration still has defects:
- Emit the current draft to `out/<name>.pptx`.
- Emit `out/RESIDUAL_ISSUES.md` listing unresolved defects (derived from the final `verify_report.md`).
- Surface both to the user, explicitly noting "budget exhausted with N defects remaining".

## Critique-mode flow (variant)

`/deck critique existing.pptx` runs a subset of the pipeline:

```
Step 0   ASK perfection bar                             — SKIPPED (no iteration loop)
Step 1   INGEST existing .pptx → content_plan.json
         DERIVE design_brief.json from extracted content
Step 1b  PRESENT brief for approval / edit             — user can correct audience/frame
Step 2   PLAN                                          — SKIPPED
Step 3   BUILD                                         — SKIPPED
Step 4   VERIFY                                        — runs on the existing .pptx
Step 5   REVISE                                        — SKIPPED (read-only)
```

Outputs next to the source `.pptx`:
- `<name>-critique.md` — per-slide defect list with suggested fixes.
- `design_brief.json` — the brief Claude derived.

No mutation of the source. See `modes.md` for the critique output format.

## Out of scope

- Chart regeneration (charts in the source pptx stay embedded as pictures).
- Animations and transitions.
- Speaker-notes reformatting (copy verbatim).
- Multi-brand within a single deck (one active brand pack per `/deck` invocation, resolved from `FEINSCHLIFF_BRAND` / `--brand`).
