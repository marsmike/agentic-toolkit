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

Secrets never live in the vault or in the repo — only in environment variables or a keychain. A
profile note may reference that a credential exists and where to configure it; it never carries
the credential's value.

## Shipping a profile

Every plugin that reads a profile ships a `profile.example.md` alongside it: the exact frontmatter
shape it expects, with placeholder values, and body prose explaining each field. `toolkit vault
init` and the plugin's own docs point here rather than duplicating the shape elsewhere.

## Tests and evals

Tests and evals always target `./vault`, regardless of what `TOOLKIT_VAULT` is set to in the
environment they run in. A real vault reached via `TOOLKIT_VAULT` is never read or written by CI
or by test/eval runs.
