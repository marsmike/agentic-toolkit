---
description: Example profile for the obsidian plugin — copy the frontmatter shape below into your own vault's Config/toolkit/obsidian.md.
kind: profile
status: active
plugin: obsidian
search_score_gate: 0.70
default_capture_prefixes:
  - Readwise-
  - Research-
  - X-Bookmark-
inference_backend: ollama
inference_base_url: http://localhost:11434
inference_model: null
enrichment_targets: []
tags:
  - domain/toolkit-meta
  - profile
---

# obsidian plugin profile (example)

Copy this file's frontmatter shape to `$VAULT/Config/toolkit/obsidian.md` to override the plugin's
shipped defaults. Every field below is optional — an absent file, or an absent field within it,
falls back to the plugin's built-in default. See `contract/PROFILE.md` for the full resolution
order (env var → this note → shipped default).

## Fields

- **`search_score_gate`** — overrides the 0.70 default for what counts as an enrichment-grade
  match in `scripts/search.py` and the distill skill. Recalibrate per embedding model if you enable
  the optional semantic layer.
- **`default_capture_prefixes`** — origin prefixes the plugin recognizes when scanning
  `01_Capture/` (used by `distill`'s triage mode and by `retrieval-verification`'s inbox summary).
- **`inference_backend` / `inference_base_url` / `inference_model`** — the LLM backend `checks/*.py`
  and `vault_normalize.py` call for description generation, tag classification, and broken-link
  resolution. `inference_backend` is `ollama` (default, talks to a local Ollama server) or
  `openai-compatible` (any OpenAI-chat-compatible endpoint). Leave `inference_model` unset and the
  LLM-assisted checks report a clear "no model configured" skip rather than guessing one.
- **`enrichment_targets`** — vault-relative note names (as wikilinks) that `distill` treats as
  mandatory enrichment candidates regardless of semantic score, e.g. a personal profile note that
  should always learn about new maintenance-relevant material.

## Secrets

No credential belongs in this file, ever — see `contract/PROFILE.md`'s Secrets section. An
OpenAI-compatible API key is an environment variable (`TOOLKIT_OBSIDIAN_INFERENCE_API_KEY`),
referenced here only by name if at all.

## Env var overrides

Every field above also has a `TOOLKIT_OBSIDIAN_<FIELD>` environment variable that wins over this
note, per `contract/PROFILE.md`'s resolution order — e.g. `TOOLKIT_OBSIDIAN_SEARCH_SCORE_GATE=0.6`.
