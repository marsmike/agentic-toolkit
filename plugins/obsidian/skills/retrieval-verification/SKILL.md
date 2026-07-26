---
name: retrieval-verification
description: Audit vault note descriptions by predicting content from title+description alone and scoring the prediction against the real body. Use for periodic vault maintenance or after a bulk distill/import.
allowed-tools:
  - Bash
  - Read
---

# Retrieval Verification

The description-quality loop this toolkit's contract cites as the maintenance-facing
half of the dual-channel-descriptions concept (`docs/PLAN.md` — retrieval-verification
loop): a description earns its keep only if a reader (or a BM25 query, or you) could
predict the note's actual content from title + description alone, without opening it.

This is an **agent-executed workflow**, not a script you run to completion — the
predict-then-score step is your own reasoning, done deliberately blind to the body.
`scripts/retrieval_verification.py` handles the two mechanical halves around it
(sampling, and turning your scores into a report).

## Workflow

1. **Sample.** Pull N active notes, title + description only — the script withholds
   the body on purpose:
   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/retrieval_verification.py" sample --n 15 --json > samples.json
   ```
2. **Predict, then read, then score — per note, in that order.** For each sampled note:
   - Read only its `title` and `description` from `samples.json`. Write down what you
     expect the body to contain.
   - Only then read the actual note (`Read` the path).
   - Score 1-5: does the body match what the description predicted?
     - **5** — description alone would have led you straight to this content.
     - **3** — plausible but generic; several different notes could share this description.
     - **1** — description is actively misleading or says nothing the title didn't.
   - A note with no `description` at all scores as flagged automatically — it can't be
     predicted from what isn't there.
3. **Build the scores map** — `{"<path>": {"score": N, "predicted": "...", "note": "why"}}`
   for every sampled path — and hand it to the reporting half:
   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/retrieval_verification.py" \
     report --samples samples.json --scores scores.json
   ```
   This writes a JSON report to `00_Memory/retrieval-verification/<timestamp>.json` and
   appends a summary capture to `01_Capture/` (flagged notes named, with the report
   path) — a normal capture-inbox item for a human or a later distill pass to triage,
   per contract/VAULT_SCHEMA.md's capture conventions.
4. **Rewrite flagged descriptions** (score < 3) directly with `Edit` — this skill
   surfaces the problem, it doesn't silently rewrite content on your behalf.

## Dead-letter behavior

If a sampled path never gets a score (an interrupted run), `report` writes a dead-letter
note to `00_Memory/dlq/` naming exactly which paths are missing, rather than silently
producing a report that looks complete. See distill's rules.md for the DLQ convention
this follows.

## Reference

- [methodology.md](references/methodology.md) — why prediction-then-score, BM25 dilution, sample-size guidance
