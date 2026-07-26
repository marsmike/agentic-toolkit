---
description: Example profile for the obsidian plugin — demonstrates the fill-from-Obsidian convention documented in contract/PROFILE.md.
kind: profile
status: active
created: 2026-02-03
plugin: obsidian
search_score_gate: 0.70
default_capture_prefixes:
  - Readwise-
  - Research-
  - X-Bookmark-
inference_backend: ollama
inference_base_url: http://localhost:11434
inference_model: null
enrichment_targets:
  - "[[Alex-Vega]]"
tags:
  - domain/toolkit-meta
  - profile
---

# obsidian plugin profile (example)

This is what `$VAULT/Config/toolkit/obsidian.md` looks like once a real vault has one. It is not
consulted by the shipped default — the plugin falls back to its own default when this file is
absent — but a `toolkit vault init` run copies a version of this shape into a new vault so the
placeholders are obvious.

## How the fields are used

- `search_score_gate` overrides the plugin's built-in 0.70 default for what counts as an
  enrichment-grade match. Recalibrate this per embedding model — see
  [[Semantic-Search-Score-Calibration]].
- `default_capture_prefixes` are the origin prefixes the plugin recognizes when scanning
  `01_Capture/` — see [[Capture-Conventions]].
- `inference_backend` / `inference_base_url` / `inference_model` configure the LLM the
  maintenance checks call for description generation and tag classification. With
  `inference_model` unset, LLM-assisted checks report a clear skip instead of guessing.
- `enrichment_targets` names which profile note to flag when a distill run touches
  maintenance-relevant material. Points at [[Alex-Vega]] in this example vault.

The canonical field reference is the plugin's own `profile.example.md` — this note mirrors it and
must stay in sync (CI does not yet enforce this; keep the shapes identical by hand).

No credential of any kind belongs in this file — see `contract/PROFILE.md`'s Secrets section.
Anything the plugin needs to authenticate with (a Readwise token, an API key) is an environment
variable, referenced here only by name if at all.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Alex-Vega]]
- [[Capture-Conventions]]
- [[Semantic-Search-Score-Calibration]]
- [[Obsidian-Plugin]]
