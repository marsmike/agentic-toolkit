---
description: Reading toolkit doctor output — active vault, profile completeness, the graph/inference section, and DLQ surfacing — to debug config that isn't behaving as expected.
status: active
created: 2026-02-21
kind: guide
topics:
  - onboarding
  - cli
tags:
  - domain/toolkit-meta
---

# Troubleshooting `toolkit doctor`

`toolkit doctor` (see [[Toolkit-CLI]]) is the first thing to run when something isn't resolving
the way it's expected to. It reports four things, and most config confusion traces to one of
them:

1. **Which vault is active, and how it was resolved.** If a real vault was expected but `./vault`
   shows up instead, `TOOLKIT_VAULT` likely isn't set in the environment the command is actually
   running in — see [[Using-Your-Own-Vault]].
2. **Profile completeness per plugin** — present or missing, per plugin, nothing finer. Doctor
   does *not* report which resolution step (env var, vault profile note, or shipped default)
   supplied a setting's current value — that distinction isn't in its output at all. A setting
   that "isn't taking" is still almost always a profile note in the wrong path, not a bug in the
   plugin; you just confirm that by reading the profile note and environment directly rather than
   from doctor's report. See [[Profiles-and-Config]].
3. **The graph section** — [[Gaiafield]] node/edge/dangling/boundary counts and index freshness,
   when a gaiafield binary and graph database are present; `"gaiafield not present"` when the
   binary can't be found at all. When the graph section is present, it nests an `inference`
   sub-section reporting one of three states: a v1 binary that predates inference ("engine lacks
   inference"), a v2 binary that hasn't run `gaiafield infer` yet ("not inferred — run `gaiafield
   infer`"), or — once inference has run — the model name, high/low gates, and inferred/ambiguous
   edge counts. Doctor only ever reports this state; it never runs `index` or `infer` itself, so a
   stale or absent graph section means an operator needs to run those commands, not that doctor is
   broken. See [[Gaiafield]] and [[Capability-Probing]] for how the three states are told apart.
4. **Dead-letter entries waiting for review** — surfaced here rather than left silent in
   `00_Memory/dlq/`, so an operator doesn't have to know to go looking. See
   [[Dead-Letter-Queues-for-Automation]].

## When doctor itself looks wrong

Doctor reads the same resolution order every plugin does — it has no special-cased knowledge. If
its report is wrong, the bug is almost always upstream (a malformed profile note, an unset env
var) rather than in doctor's own logic, since it isn't doing anything plugins don't also do.

## Related

- [[Toolkit-CLI]]
- [[Using-Your-Own-Vault]]
- [[Profiles-and-Config]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Gaiafield]]
- [[Capability-Probing]]
