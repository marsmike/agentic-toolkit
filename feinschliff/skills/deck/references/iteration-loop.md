# Iteration Loop — Build, Verify, Revise

The central discipline that separates Feinschliff decks from one-shot AI generators: after building, LOOK at what you generated and revise until it's good.

## The non-negotiable rule

**You never declare the deck done without running the verify pass at least once.** One build + zero looks = not a deck, a guess. The failure mode this prevents: Claude builds a `.pptx`, sees no Python error, announces "done", and hands the user a draft with empty placeholders, text overflow, and off-brand colours because nobody ever opened the rendered output.

Concretely:
- **Minimum 1 verify pass**, always — even on the happy path where the first build looks plausible.
- **`out/verify_report.md` is the completion gate.** Markdown, human-readable, so the user can scan it without parsing JSON. If it isn't on disk, the skill hasn't finished. See `pipeline.md` step 4 for the format.
- **The HTML design is the visual ground truth.** The active brand's `feinschliff/<brand-root>/claude-design/<brand>-2026.html` defines what each layout should look like (e.g. `feinschliff/brands/feinschliff/claude-design/feinschliff-2026.html` by default). When the rendered PNG diverges from the HTML reference for that layout, that's a defect — even if it doesn't map cleanly to one of the 11 named classes.

## Budget (ask the user at the start)

Ask once, before the first build: **"How perfect should this be?"**

| Answer | Iteration budget | When to use |
|---|---|---|
| default / normal / "3" | **3 iterations** | Everyday decks — weekly updates, internal reviews, working drafts. Catches obvious defects without spiraling. |
| perfectionist / "polish it" / "6" | **6 iterations** | First-impression decks — exec audiences, board packs, client-facing teasers. Extra passes for typography tuning, overflow edge cases, cover-slide polish. |

Default to 3 if the user doesn't respond or says "normal". **The budget is a ceiling on revise cycles, not a floor on verify passes — verify always runs at least once regardless of budget.**

## Loop

```
 build    ─┐
           ▼
     render (soffice → PDF → pdftoppm → PNGs)
           ▼
     verify (LLM eyeballs each slide for defects)
           ▼
       ┌───────┐
       │ pass? │── yes ──> done
       └───┬───┘
           │ no
           ▼
       revise (adjust deck_plan.json, e.g. change layout, shorten text)
           │
           └──────────────────────┐
                                  ▼
                             (back to build)

Max N iterations total (N = 3 or 6 per the budget ask).
After iter N, emit RESIDUAL_ISSUES.md.
```

## What "verify" checks — 11 defect classes

For each slide in the rendered PNG, inspect for all 11 classes in a single LLM pass. Same prompt as before, extended to cover theory alongside visual.

### Visual defects (5 classes — existing)

1. **text-overflow**: text bleeding past layout placeholder. Fix: shorten source text OR move to a layout that accommodates longer content.
2. **empty-placeholder**: a placeholder that didn't get filled. Fix: the source content didn't match the layout's slot expectations — move to a smaller layout, or add the missing content if reasonable.
3. **layout-concept-mismatch**: the chosen layout doesn't match the content's concept (e.g. comparing 2 items but used 4-column-cards). Fix: pick a better layout from the catalog.
4. **brand-violation**: a colour or font off-brand. Fix: a slot was filled with raw html/markdown that overrode styling. Plain-text the content.
5. **density-mismatch**: slide feels too dense or too sparse. Fix: split or merge slides.

### Theory defects (6 classes — new in v1)

6. **claim-title**: title is a topic not a claim. Detection per `slide-claim-test.md`. Fix: rewrite as a claim sentence (verb or specific number).
7. **one-idea-violated**: body has connectives ("and also", "furthermore") or multiple disjoint claims. Detection per `anti-patterns.md`. Fix: split into two slides.
8. **bullet-dump**: 5+ peer-level bullets with no hierarchy. Detection per `anti-patterns.md`. Fix: subordinate / group / split.
9. **audience-mismatch**: jargon density or abstraction level off for `design_brief.audience`. Detection per `audience-calibration.md`. Fix: translate or re-level.
10. **red-line-break**: slide's `role` doesn't match its position in the `design_brief.frame`'s role order. Detection per `narrative-frames.md`. Fix: reorder, re-role, or re-frame.
11. **curse-of-knowledge**: technical term used without grounding for the audience. Detection: term is not defined earlier, not in the audience's tolerated vocabulary (per `audience-calibration.md`), and load-bearing for the slide's claim. Fix: translate / define inline / demote.

## Verify-pass LLM prompt (outline)

Build a side-by-side PNG montage for the LLM — or Read each PNG directly. **You must actually look at the images**; don't invent verdicts from deck_plan.json alone.

For each slide, note defects as `{class, detail, fix}` triples. Any slide with ≥1 defect is "dirty". If any slide is dirty, the overall verdict is `dirty`.

Write the findings as `out/verify_report.md` — the human-readable format in `pipeline.md` step 4. Every slide gets a section; passing slides show `✅ No defects.` so the user sees full coverage at a glance. Writing this file is not optional — it is the artifact that proves verification happened, AND the document the user actually reads to understand what's wrong.

## Budget mechanics

- Each iteration = 1 build + 1 LibreOffice render + 1 LLM eyeball pass. Iteration 1 always includes a verify pass — there is no iteration 0.
- `verify_report.md` header says `Verdict: clean` → done, emit the deck.
- `Verdict: dirty` and iteration < budget → revise and re-build.
- `Verdict: dirty` and iteration == budget → stop; emit residuals.
- If at the final iteration issues remain, emit:
  - Final draft `out/<name>.pptx` (with whatever improvements did land).
  - `out/RESIDUAL_ISSUES.md` listing specifically what's still off (derived from the final `verify_report.md`).
  - User decides: accept, manual-fix, or re-run with different inputs.

Theory defects and visual defects share the same iteration budget. A slide with both `claim-title` and `text-overflow` is one defective slide; one revise pass can fix both.

## Completion checklist

Before telling the user the deck is ready, confirm all of these:

- [ ] `out/<name>.pptx` exists.
- [ ] `out/verify_report.md` exists, is human-readable, and its `Iteration:` header matches the last build.
- [ ] Either the header says `Verdict: clean`, OR `Iteration == budget` AND `out/RESIDUAL_ISSUES.md` exists summarising what's left.
- [ ] You actually read the rendered PNGs during the last verify pass — not just ran `soffice` and assumed.

Skipping this checklist is the failure mode the iteration loop exists to prevent.

## Why a cap at all

One-shot agents produce garbage. 15-shot agents spiral and burn budget. A hard stop keeps iteration a discipline, not a compulsion. **3 is the sweet spot for everyday work** — enough to catch obvious defects, not enough to dither. **6 is for first-impression decks** where the extra passes are worth the cost: cover-slide polish, typography tuning, overflow edge cases that only show up on 3rd-render eyeball.

## Implementation notes

- Always render via `soffice --headless --convert-to pdf` not PowerPoint — LibreOffice is faster, headless, and deterministic.
- `pdftoppm -r 96 -png` gives 1280×720 images that are good enough for LLM eyeballing without being huge.
- Use `PIL.Image.new` to build a side-by-side "before / after" grid for the LLM's eyeball pass — makes defect-spotting fast.
