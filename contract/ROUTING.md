# Routing

Hard rules for which model handles which work, and how far a subagent may fan out.

## Model tiering

- **Cheap/local models** — bulk mechanical work: formatting, rote transforms, high-volume
  low-judgment passes.
- **Frontier models** — judgment calls and supervision: anything where a wrong call is expensive
  to detect after the fact.

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
