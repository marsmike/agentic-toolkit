# Backlink Workflows

## Post-distillation verification

After creating a distilled note with bidirectional links:

1. **Check the new note has at least one backlink:**
   ```bash
   grep -rl "\[\[$(basename "$new_note" .md)\]\]" "$VAULT"/{02_Projects,03_Areas,04_Resources}
   ```
   Expected: at least one hit from a note you enriched (step 8 of distill's workflow.md).

2. **Check enriched notes reference the new note back:** `Read` each enriched note and
   confirm the wikilink is present and reads sensibly in context.

3. **Verify no broken links resulted:**
   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/vault_normalize.py" --check links --scope 04_Resources
   ```

## Orphan detection

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/vault_lint.py" --json
```

Read the `orphans` list. Flag notes with:

- Links added from a relevant MOC or topic note.
- A mention added to related notes discovered via search.
- A connection made the next time distill touches adjacent material.

## Connection discovery

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/search.py" "key concept from note" --top 10 --json
```

Review hits at or above the `search_score_gate` (default 0.70, `above_enrichment_gate:
true` in the JSON output). Add bidirectional wikilinks where meaningful, following the
same active-folders-only, no-`05_Archive`, no-`01_Capture` rules as distill's
enrichment step.
