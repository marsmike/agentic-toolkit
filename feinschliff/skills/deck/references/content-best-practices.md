# Content Best Practices — Feinschliff

## Voice

The default voice rule that ships with the feinschliff pack:

> "Write like an engineer explaining their work to a colleague they respect. Short sentences. Concrete nouns. No superlatives."

Apply this to every text slot you fill. Brand packs that ship their own voice rider override this default — check the active brand's `claude-design/<brand>-2026.html` or pack-level README for brand-specific voice guidance.

## Less is more

- **Title slot**: under 8 words, no period unless statement.
- **Eyebrow**: 2-4 words, mono uppercase. Treat as tag, not sentence.
- **Body**: one complete thought per paragraph, max 2 paragraphs.
- **Column titles**: noun phrase or short statement; max 10 words.
- **Column body**: 1-3 sentences; avoid sub-bullets.
- **KPI value**: a number only. Unit separate. No prefix symbols inside the value.
- **Bar labels**: uppercase country/region/product code. Max 10 chars.

## One idea per slide

If you catch yourself writing "and also..." in body text, split the slide.

## When to add a slide

- Before a major concept shift: chapter opener.
- For every distinct numeric comparison: its own slide.
- Never cram more than 6 items into any layout (the catalog enforces this via schema maxItems).

## When to skip a layout

- No chapter opener if the deck has only one section.
- No agenda for decks under 4 content slides.
- No quote for operational / status updates (feels performative).

## Images

- Path placeholders accept absolute or project-relative paths.
- Image fills proportionally to the layout's picture frame; provide images close to the frame's aspect ratio.
- If no image is available, leave the picture placeholder empty — the striped grey placeholder is part of the design, not an error.

## Numbers

- Value and unit stay separate in KPI slots (`value="62"`, `unit="k"`). Do NOT write `value="62k"`.
- Format values without thousands separators for single digits; with separators for >3-digit figures.
- Deltas always include direction (`+3% YoY`) and period.

## Error on the side of brevity

If you're unsure whether to add detail, don't. Empty space is intentional in the default Feinschliff brand voice.
