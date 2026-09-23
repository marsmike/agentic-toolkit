---
name: distill
description: Process captures into vault knowledge — triage the inbox, distill one or more captures, or file a conversation insight. Use when working with 01_Capture/.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# Distill

A capture in `01_Capture/` becomes a note that keeps the best of it, sits where it belongs,
is linked to what it draws on, and can be found from a vague question a year later. You
decide how; two tools do the mechanical parts and check the result.

```bash
S() { uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/$1" "${@:2}"; }  # a function, not a string: zsh does not word-split [earned: 2026-09-23 first pipeline run]
S distill_judge.py 01_Capture/<capture>.md --dossier --json   # everything known about it, before you read it
S distill_check.py <note> 01_Capture/<capture>.md --ask "<a question a reader would type>" --ask "…"
```

**The dossier** is one JSON block per capture: what kind of material it is, which existing
notes it is really about (`related`, with `judged_relevant`, `bridge` for same-principle
links across fields, `via` for notes reached through the graph, and a suggested L1/L2/L3),
whether a note already covers the same source (`already_distilled`), placement, the
capture's essence (`passages`: which paragraphs carry a claim or number, and how the
pipeline's synthesis relates to the article), and graph context. Several captures at once
add a pairwise `cluster` block: duplicates and near-duplicates. It is advice with numbers
attached; you read the notes it points at and decide. Without a judgment backend it prints
`SKIPPED` and you work from `search.py` alone. [Reading it](references/dossier.md).

**The check** is the definition of done. Hard gates: frontmatter (`source`, `status:
distilled`, `processed_date`, `description`), a `*Source: …*` line naming the capture's own
source, a stored document linked when the capture has one, no wikilink into `01_Capture/`
or `05_Archive/`, no dangling wikilink, an Index.md line. Soft, reported: which of the
capture's other URLs the note dropped, whether your `--ask` questions find the note in the
top three, and which of the capture's kept passages the note does not carry. A capture is
retired only after the check passes and you have answered every soft finding: put it in,
or name it in the handoff as deliberate.

## Invariants

1. **Two phases, one checkpoint.** Propose (what you learned, where it goes, what it links
   to and at which level, what you disagree with in the dossier and why), then stop for
   review. Skip only on an explicit `--auto`; the `pipeline` skill runs with `--auto`, and the
   vault's git commit per run is the undo.
2. **Every note carries its source**, and never the string `unknown`: `(none — <context>)`
   when there is none, today's date for `processed_date`.
3. **Advice never writes.** Dossier rows, inferred edges, adjudications: candidates for your
   decision, never applied by a script.
4. **L1 is the default; L2 and L3 need a cited sentence** in the note being enriched. Never
   overwrite existing text; a contradiction is a callout next to the claim.
5. **Cluster mode is member notes plus a hub.** One note per capture that has its own
   specifics, a hub that states the shared principle and links them. A synthesis alone
   dropped two thirds of the specifics [earned: 2026-09-22 acceptance run].
6. **The capture leaves `01_Capture/`**: archived (default) as
   `05_Archive/<Origin>-Captures-<YYYY-MM>/<stem>--FULLCAPTURE.md` plus one line in that
   folder's `README.md` manifest, or deleted (`trash` if present) only for duplicates and stubs.
7. **Ambiguity goes to the DLQ**, not a guess: `vault_utils.write_dlq_note()`, and say so.
8. **The owner's clips never drop.** Every capture is distilled the same way whatever its
   source; `provenance.via` decides only whether it may leave without a note. A `clip` (or a
   capture without `via`) always becomes a note or enriches one; a `radar` or `newsletter`
   capture may be retired when triage says discard, with the reason in the manifest line.
   [Mike, 2026-09-23: one pipeline, different sources]

Placement, enrichment levels and the DLQ convention in detail: [rules.md](references/rules.md).
Modes: triage the inbox (run the dossier over `01_Capture/*.md`, decide distill / quick-file /
discard per capture; a discard is always yours to make, and never a clip's), or file a conversation insight as a
capture first and distill it like any other.
