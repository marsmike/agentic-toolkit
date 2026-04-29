# Slide Design Anti-Patterns

Six patterns the verify step (step 4) flags. Each one lists: detection, why-it-fails, and the fix.

## 1. claim-title (title is a topic, not a claim)

**Detection:** the title slot lacks a verb beyond copulas AND lacks a specific number with unit AND doesn't name an outcome / decision. See `slide-claim-test.md` for the full rubric.

**Why it fails:** Readers scanning a deck in skim-mode use titles as the summary. A topic-title is a placeholder, not a message — the reader has to read the whole slide to extract the point.

**Fix:** Rewrite the title using the body's claim. See rewrite patterns in `slide-claim-test.md`.

## 2. one-idea-violated (multiple points on one slide)

**Detection:**
- Body contains connectives suggesting a second thought: "and also", "furthermore", "additionally", "in addition", "on top of that".
- Multiple disjoint claim sentences in the same body slot.
- Two independent visuals (two charts, two diagrams) that don't compose.

**Why it fails:** Audiences process one idea at a time. A slide with two ideas gets half-remembered.

**Fix:** Split into two slides. If splitting creates excessive navigation, consider whether one of the ideas is actually the primary and the other is evidence — demote to a sub-point or move to the next slide.

## 3. bullet-dump (5+ peer-level bullets, no hierarchy)

**Detection:** 5 or more top-level bullets in the body slot, no visual nesting or grouping, no apparent synthesis.

**Why it fails:** A wall of bullets signals the author didn't decide what matters. Cognitive load spikes; rule-of-three violated; no visual hierarchy to guide the eye.

**Fix:** Three options:
- **Subordinate** — identify the one claim, make bullets sub-support of it. Shorten to 3.
- **Group** — introduce 2–3 categories, bullets nest under them (convert to two-column-cards or three-column).
- **Split** — if the bullets are genuinely 5+ ideas, that's one-idea-violated. Split across multiple slides.

## 4. audience-mismatch (jargon or abstraction level off)

**Detection:** per `audience-calibration.md` for the slide's audience:
- exec: any un-translated technical term; any content not expressible in money / time / risk.
- manager: deep implementation details without operational framing; pure vision without cost numbers.
- developer: pure business framing without technical grounding; hand-waving over mechanisms.
- peer: re-establishing shared context; business framing they don't need.

**Why it fails:** The slide is pitched at the wrong level. The audience either doesn't follow or feels condescended to.

**Fix:** Rewrite using the target audience's preferred framing. See `audience-calibration.md` — "what lands" section for each audience.

## 5. red-line-break (slide role doesn't match frame position)

**Detection:** the slide's `role` in `design_brief.json` is out of order for the chosen `frame`:
- SCQA: context → complication → recommendation → support/evidence → close.
- PSSR: complication → context → recommendation → evidence → close.
- Sparkline: alternating complication / recommendation pairs.
- Man-in-Hole: context → complication → complication → recommendation → evidence → close.

A slide's position in the deck should respect the frame's role order.

**Why it fails:** Breaks the narrative spine. The audience loses track of where they are in the argument.

**Fix:** Reorder slides, or re-role the slide, or re-frame the whole deck (if many slides break the order, the frame is wrong).

## 6. curse-of-knowledge (technical term without grounding for audience)

**Detection:** the slide uses a term that:
- is not defined in earlier slides,
- is not in the audience's assumed vocabulary per `audience-calibration.md`,
- is load-bearing for the slide's claim.

**Why it fails:** The audience doesn't share the background the author assumes. Elizabeth Newton's tapping experiment: the tapper hears a song; the listener hears random taps.

**Fix:** Three options:
- **Translate** to plain English (per the audience's tolerance).
- **Define inline** in 5–10 words, parenthetically.
- **Demote** — move the jargon to a supporting detail and lead with the value.

Cross-reference: `audience-calibration.md` for jargon tolerances per bucket.
