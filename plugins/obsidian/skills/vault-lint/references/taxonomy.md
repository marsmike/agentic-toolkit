# Tag Taxonomy

`checks/tags.py`'s `DOMAIN_TAGS` ships a small starter set. Treat it as an example to
replace, not a schema to conform to — every vault accretes its own recurring topics.

## Starter domain tags (edit these)

| Tag | Description |
|-----|-------------|
| `domain/ai-ml` | AI/ML concepts, models, applications |
| `domain/agent-systems` | Agent architectures, orchestration, tool use |
| `domain/software-engineering` | Design, architecture, testing, DevOps |
| `domain/knowledge-management` | PKM, note-taking systems, linking practices |
| `domain/productivity` | Workflows, focus, task management |
| `domain/toolkit-meta` | Notes about this vault/toolkit's own operation |

## Content-type and lifecycle conventions (freeform, not `domain/*`-namespaced)

These coexist with `domain/*` tags in the same `tags:` list — namespacing is a
convention layered onto one field, not a separate mechanism (contract/VAULT_SCHEMA.md).

| Tag | Use for |
|-----|---------|
| `#wiki` | Comprehensive knowledge resources (MOCs, guides) |
| `#bookmark` | Reference material and external resources |
| `#atomic-note` | Single-concept notes and quick captures |
| `#meeting` | Meeting notes and discussion records |
| `#profile` | Profile/config notes (see contract/PROFILE.md) |

## Assignment guidelines

- Aim for 3-7 tags per note: one or two content-type tags, one or two `domain/*` tags,
  optionally a scope tag (`#project`, `#area`).
- A tag count of exactly 1 is a common typo/over-specificity signal — check it.
- Prefer an existing tag over inventing a near-synonym; `vault_normalize.py --check
  tags` migrates known legacy synonyms onto the canonical set via `LEGACY_MIGRATION`
  in `checks/tags.py` — extend that table as your vault's history warrants.

## Tag health audit

1. List all tags in use: `grep -rhoE '"?domain/[a-z-]+"?' "$VAULT"/{02_Projects,03_Areas,04_Resources} | sort | uniq -c | sort -rn`
2. Look for count-1 tags (typos/over-specific), non-canonical `domain/*` values, and
   plural/singular inconsistencies.
3. Run `vault_normalize.py --check tags --fix --dry-run` to preview LLM-assisted
   classification for untagged notes before applying.

## Maintenance

- Review new content for taxonomy adherence during distillation, not as a separate pass.
- When a `domain/*` value stops being useful (too broad, too narrow), update
  `DOMAIN_TAGS` and add the old value to `LEGACY_MIGRATION` rather than leaving both live.
