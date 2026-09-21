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
judgment_backend: jev
judgment_base_url: https://openrouter.ai/api
judgment_model: jev-latest
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
- **`judgment_backend` / `judgment_base_url` / `judgment_model`** — the typed-judgment backend
  `scripts/distill_judge.py` asks for advisory probabilities during a distill run (is this found
  note really related, which enrichment level, which folder, does this capture add anything over
  its sibling). `jev` (default) is TypeSafe's System One model, reached through OpenRouter; `none`
  switches the layer off. **With a key set, the text of the capture and of the related notes it
  is compared with is sent to that hosted service.** With no key the layer prints `SKIPPED`,
  sends nothing, and distill runs exactly as before. Thresholds are deliberately not profile
  keys: they are policy, live in `distill_judge.py` per backend, and move only after a
  calibration run (`judgment-calibration` skill).
- **`domains`** (optional, not set above) — your vault's own domain taxonomy, as a mapping of
  name to a one-line meaning (`ai-ml: "machine learning and language models themselves"`), or a
  plain list of names. Names are the part after `domain/`. When set, it replaces the starter
  taxonomy in `checks/tags.py` for the tag audit, the LLM tag classifier and the judgment
  questions alike. The one-line meanings matter: they are what a judgment backend reads.
- **`enrichment_targets`** — vault-relative note names (as wikilinks) that `distill` treats as
  mandatory enrichment candidates regardless of semantic score, e.g. a personal profile note that
  should always learn about new maintenance-relevant material.

## Secrets

No credential belongs in this file, ever — see `contract/PROFILE.md`'s Secrets section. An
OpenAI-compatible API key is an environment variable (`TOOLKIT_OBSIDIAN_INFERENCE_API_KEY`),
referenced here only by name if at all. The judgment backend reads
`TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY`, falling back to `OPENROUTER_API_KEY`.

## Env var overrides

Every field above also has a `TOOLKIT_OBSIDIAN_<FIELD>` environment variable that wins over this
note, per `contract/PROFILE.md`'s resolution order — e.g. `TOOLKIT_OBSIDIAN_SEARCH_SCORE_GATE=0.6`.
