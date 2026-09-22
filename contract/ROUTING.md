# Routing

Hard rules for which model handles which work, and how far a subagent may fan out.

## Model tiering

- **Cheap/local models** — bulk mechanical work: formatting, rote transforms, high-volume
  low-judgment passes.
- **Frontier models** — judgment calls and supervision: anything where a wrong call is expensive
  to detect after the fact.
- **Typed-judgment models** — narrow, independent questions answered with a probability instead
  of prose (is this note about the same mechanism, which of these folders, does A add anything
  B lacks), many of them batched over one shared state in a single request. The model supplies
  the number; **code owns the policy**: thresholds, gates and what a number leads to live in the
  calling script, never in question text, and are kept per backend because a threshold tuned on a
  calibrated model does not transfer to an uncalibrated one. Their output is advice to the
  frontier model's checkpoint, never an action (see `KNOWLEDGE_API.md`, "Judgments").
  `[earned: R8, 2026-09-21 — once farsight supplied raw BM25 scores, the 0.70 enrichment gate
  became "informational only" (scripts/search.py), leaving "which found notes are really
  related" to unaided prose judgment on every capture]`
  **Removal condition:** the hosted default (`judgment_backend: jev`) goes once a local backend
  passes `eval_distill_judge`'s live phase at parity; this tier then folds into "Cheap/local
  models" and only the code-owns-policy rule survives.

## Spawn depth

- A subagent spawned on a cheap/local model **never spawns further subagents.** Fan-out happens at
  the frontier-model level only.
- On ambiguity, a subagent escalates to its parent rather than guessing or spawning a helper to
  resolve it.
- No unbounded spawn depth: every spawn chain terminates at a fixed, small depth.

## Fallback (aspiration, R1+)

A local model as fallback when the API is unavailable is an aspiration, not yet implemented — do
not build against it as if it exists. **Removal condition:** delete this section once local-model
fallback ships and is covered by an eval, folding whatever rule survives into "Model tiering"
above.
