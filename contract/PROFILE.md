# Profile

"Fill from Obsidian": plugins get identity and configuration from the vault, never hard-coded in
the repo. The repo ships behavior; the vault carries the specifics.

## Resolution order

For a plugin's own configuration:

1. Environment variable, if the plugin defines one for that setting.
2. `$VAULT/Config/toolkit/<plugin>.md` — frontmatter holds structured data, the note body holds
   human-readable prose (rationale, caveats, anything useful to whoever edits it).
3. The plugin's shipped default.

For locating the vault itself:

1. `TOOLKIT_VAULT` environment variable.
2. `./vault` — the bundled example vault, as fallback.

`toolkit doctor` reports which vault is active and which step of each resolution order supplied
the answer.

## Secrets

Secrets never live in the vault or in the repo — only in environment variables, the owner's key
file, or a keychain. The key file is `TOOLKIT_KEYS_FILE`, default `~/.env`, `NAME=value` lines.
Each script reads the one key it needs itself (`vault_utils.secret(name)`: the environment first,
then the key file) and keeps it in the process that makes the call: it never exports it, so
nothing the script starts, and no agent that started the script, holds it. The unattended
pipeline relies on this: its agent runs without any key in its environment and may not read
the key file. [earned: 2026-09-24, review-01 SEC-1] A profile note may reference that a
credential exists and where to configure it; it never carries the credential's value. A plugin that calls a hosted service says so next to the profile key that
enables it, names what leaves the machine, and does nothing over the network while the
credential is absent.

## Shipping a profile

Every plugin that reads a profile ships a `profile.example.md` alongside it: the exact frontmatter
shape it expects, with placeholder values, and body prose explaining each field. `toolkit vault
init` and the plugin's own docs point here rather than duplicating the shape elsewhere.

## Tests and evals

Tests and evals always target `./vault`, regardless of what `TOOLKIT_VAULT` is set to in the
environment they run in. A real vault reached via `TOOLKIT_VAULT` is never read or written by CI
or by test/eval runs.
