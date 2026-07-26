---
description: Reading toolkit doctor output — active vault, resolution step, profile completeness, and DLQ surfacing — to debug config that isn't behaving as expected.
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
the way it's expected to. It reports three things, and most config confusion traces to one of
them:

1. **Which vault is active, and how it was resolved.** If a real vault was expected but `./vault`
   shows up instead, `TOOLKIT_VAULT` likely isn't set in the environment the command is actually
   running in — see [[Using-Your-Own-Vault]].
2. **Profile completeness per plugin**, and which resolution step supplied each setting — env var,
   vault profile note, or shipped default. A setting that "isn't taking" is almost always a profile
   note in the wrong path, not a bug in the plugin. See [[Profiles-and-Config]].
3. **Dead-letter entries waiting for review** — surfaced here rather than left silent in
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
