---
description: Running the toolkit's skills in a non-interactive claude -p session — the --allowedTools shape that actually works, and the gotchas that each cost a debugging round.
status: active
created: 2026-07-26
kind: guide
topics:
  - onboarding
  - automation
tags:
  - domain/toolkit-meta
---

# Scripting the Toolkit Headless

The plugins' skills shell out to scripts and engine binaries, so a headless `claude -p` session
needs explicit tool grants — the default permission mode blocks execution, and a skill will
(correctly, not by accident) fall back to filesystem-only analysis instead of crashing when it
can't run a command.

## The working invocation

```bash
claude -p --allowedTools "Bash(uv run:*),Bash(uv:*),Bash(env:*),Bash(python3:*)" "..."
```

Add the engine binaries explicitly if a headless run should exercise them too:

```bash
claude -p \
  --allowedTools "Bash(uv run:*),Bash(uv:*),Bash(env:*),Bash(python3:*),Bash(./bin/farsight:*),Bash(./bin/gaiafield:*)" \
  "..."
```

## Three gotchas, each earned by a real debugging round

`[earned: cold-boot test 2026-07-26]` — see [[The-Cold-Boot-Ritual]] for the check that found all
three:

1. **`--allowedTools` takes one comma-separated argument, not repeated flags.** Passing it multiple
   times, or space-separated, silently drops everything after the first.
2. **`Bash(env:*)` is required even if nothing in the prompt mentions `env`.** Skills compose
   command lines like `env VAR=... uv run ...` internally to set per-invocation environment
   variables (`TOOLKIT_FARSIGHT_BIN`, `TOOLKIT_GAIAFIELD_BIN`, and similar) — without the grant,
   every one of those composed commands is blocked, not just a bare `env` call.
3. **The permission-mode wall degrades silently, which can look like success.** A skill denied tool
   access doesn't error — it falls back to filesystem-only analysis and reports normally. If a
   headless run is supposed to be exercising an engine binary, check for explicit evidence it did
   (e.g. the cold-boot ritual's own `"ENGINES: ok"` sentinel), not just a clean exit.

## Isolating a headless run entirely

A headless session driven for testing (rather than real personal use) should run against an
isolated `CLAUDE_CONFIG_DIR` and an explicit `TOOLKIT_VAULT`, never a developer's real config or
vault — see [[The-Cold-Boot-Ritual]] for the full isolation recipe, including how to supply
credentials to a scratch config directory without touching the real one.

## Related

- [[The-Cold-Boot-Ritual]]
- [[Capability-Probing]]
- [[Toolkit-CLI]]
- [[Quick-Start]]
- [[Using-Your-Own-Vault]]
