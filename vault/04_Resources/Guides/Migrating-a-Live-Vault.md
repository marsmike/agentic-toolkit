---
description: Moving a long-lived personal vault onto this toolkit's plugins without touching it until a copy has passed every step — dry run, profile, parity checks, recalibration, cutover.
status: active
created: 2026-09-22
kind: guide
topics:
  - migration
  - reliability
tags:
  - domain/toolkit-meta
  - domain/knowledge-management
---

# Migrating a Live Vault

[[Using-Your-Own-Vault]] covers pointing the toolkit at a fresh vault. This guide is for the
harder case: a vault with years of notes that already runs on something else (an older plugin
set, an editor plugin's embeddings, hand-rolled scripts) and cannot afford a bad afternoon. The
rule is the one that holds for backups: a migration that has not been rehearsed is a hypothesis.

## 1. Rehearse on a copy, never on the vault

```bash
rsync -a --exclude .obsidian --exclude .smart-env --exclude .git "$REAL_VAULT/" "$COPY/"
export TOOLKIT_VAULT="$COPY"
```

Every step below runs against `$COPY` until the last section. Put the copy under version
control (`git init && git add -A && git commit -m baseline`) so every step's effect is a diff
you can read.

## 2. Baselines

What one real 1,476-note vault showed at this step (2026-09-22), so you know what to expect:
81 notes with frontmatter that does not parse (an unquoted colon in `description:` is the usual
cause), 1,633 dangling wikilinks, 18 links from active notes into the archive, and, once the
graph was embedded, over 2,000 pairs above gaiafield's shipped gate. None of these is a reason
to stop; all of them are reasons to run the read-only passes before any `--fix`.

`toolkit engines install`, then `toolkit doctor`: note counts, dangling links, boundary
violations, which vault and profile were resolved. Save the output; the later steps compare against it.

## 3. Give the vault a profile

Create `Config/toolkit/obsidian.md` (and `readwise.md`, `memory.md` if you use those plugins) from
each plugin's `profile.example.md`. The fields that differ most on a real vault: see
[[Profiles-and-Config]] and [[Fill-From-Obsidian-Profiles]].

- `default_capture_prefixes`: every origin prefix your inbox actually uses.
- `domains`: your own taxonomy, name to one-line meaning. The meanings are read by the
  judgment questions, so write them as you would explain the domain to a colleague.
- `judgment_*`: leave the default, or `judgment_backend: none`. With a key in the environment,
  note text is sent to the hosted backend; decide that on purpose (see [[Typed-Judgments]]).

Create `00_Memory/dlq/` so the first ambiguous step has somewhere to go
([[Dead-Letter-Queues-for-Automation]]).

## 4. Read-only passes first

Run `vault_lint.py` and `vault_normalize.py` (audit only, no `--fix`) and look at the *volume*
of findings before anything else. A thousand "non-canonical domain tag" warnings means the
`domains` key is wrong, not the vault. Then `vault_judge.py` for the quality reading list; it
writes nothing.

## 5. Search parity before you drop the old search

Take twenty queries you have really asked of this vault. Run each through the old search and
through `search.py` (farsight when installed), and compare the top five by hand. Where a
judgment backend is configured, `distill_judge.py`'s `p_relevant` is the tie-breaker the old
similarity score used to be ([[Semantic-Search-Score-Calibration]]). Only when parity holds do
the old index and its maintenance rituals go.

## 6. Reconcile the workflows

An older distill workflow usually has steps this one lacks, each earned by a failure of its
own. List them. For every one decide: port it (with its dated receipt, per
[[The-Graduation-Pattern]]) or drop it explicitly. Do not let a step vanish because the new
workflow never mentions it. Two that matter on most real vaults: deletion must go through
`trash` when the vault has a delete guard (the workflow prefers it when present), and any
"verify every URL survived" gate.

## 7. Recalibrate; nothing calibrated on the example vault transfers

This toolkit learned it twice ([[Calibration-Bias]], and the link-judgment cuts in
[[Typed-Judgments]]): rankings transfer between vaults, thresholds do not.

- gaiafield gates: `gaiafield calibrate --clusters <your spec>`.
- Judgment thresholds and wording: run the `judgment-calibration` skill on ten to twenty real
  captures. Label blind, keep a held-out slice, let a human confirm every `must` row.
- The description-quality cut in `vault_judge.py`: read the ranking first, then set the cut.

## 8. Ingest catch-up on the copy

If a highlight pipeline has been idle, its watermark is old. Run a bounded ingest first (five
documents) and check that de-duplication by document id holds before the full sweep.

## 9. Cut over

Snapshot the real vault (sync history, a tarball, or both). Point `TOOLKIT_VAULT` at it, run
`toolkit doctor`, distill **one** capture end to end with the Phase 1 checkpoint on, read the
diff. Then the backlog, in batches small enough to review. Update the vault's own `CLAUDE.md`
last, once it describes what actually runs.

## Related

- [[Using-Your-Own-Vault]]
- [[Profiles-and-Config]]
- [[The-Distill-Workflow]]
- [[Typed-Judgments]]
- [[Calibration-Bias]]
- [[Troubleshooting-Toolkit-Doctor]]
- [[Vault-Maintenance-and-Linting]]
