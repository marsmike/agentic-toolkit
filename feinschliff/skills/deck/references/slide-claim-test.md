# Slide Claim Test

A rubric for distinguishing claim-titles from topic-titles. Used by step 2 (planning — every slide's title slot is filled with a claim) and step 4 (verify — flags topic-titles as claim-title defects).

## The test

**A claim-title states a point.** A topic-title names a subject.

| Topic (❌) | Claim (✅) |
|---|---|
| "Results" | "Revenue grew 12% YoY" |
| "Our Approach" | "We ship daily because we test first" |
| "Market Overview" | "The market has fragmented into three segments" |
| "Architecture" | "One ingestion pipeline, three consumers" |
| "Summary" | "Ship the feature in Q2; defer scaling to Q3" |
| "Q1 2026" | "Q1 2026 beat plan on every KPI" |

## Concrete rules

A title passes the claim test if AT LEAST ONE of:

1. **Contains a verb beyond copulas.** "We ship" / "cost dropped" / "engineers saved" / "grew" / "collapsed".
   - Copulas alone (is / are / was / has) don't count — they describe state, not action or change.
2. **Contains a specific number with unit.** "€2.4M in 2025" / "62k employees" / "3→15 min".
3. **Names a specific outcome or decision.** "Ship in Q2" / "Adopt GitHub Actions" / "Halt the migration".

## Exceptions (titles that may look like topics but are acceptable)

- **Cover slides** — deck title is a noun phrase by convention ("Q1 2026 Update"). The eyebrow / subtitle carries the claim.
- **Chapter openers** — "Part 2: Implementation" is acceptable as a chapter label.
- **Agenda slides** — "Agenda" is fine.
- **Closer / end slides** — "Thank you" is fine.

Everything else is a content slide and needs a claim-title.

## Rewrite patterns

When flagging a topic-title, offer a rewrite derived from the slide's body content:

| Body content | Topic-title (found) | Claim-title (rewrite) |
|---|---|---|
| "Build times: 45 min → 8 min. ROI: €200K/yr." | "Build Performance" | "Build time cut 83%; €200K/yr recovered" |
| "3 pillars: platform, tooling, people" | "Strategy" | "Our strategy rests on platform, tooling, and people" |
| "Error rate dropped from 1.2% to 0.1%" | "Reliability" | "Error rate fell 12× in one quarter" |

If the body lacks a clear claim: that's a deeper problem. The slide likely violates one-idea — see `anti-patterns.md`.

## Inference + check

- **At plan time (step 2):** every slide's `claim` field from `design_brief.json` is the draft title. Filter candidates through the test; if a candidate fails, rewrite before filling the title slot.
- **At verify time (step 4):** walk the rendered PNG titles. Any slide whose title fails all three rules AND isn't in the exceptions list → emit `claim-title` defect.
