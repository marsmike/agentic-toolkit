---
description: Run the full Readwise pipeline: ingest, then optional GitHub/YouTube enrichment
argument-hint: [--category tweet|article|video|email|pdf|epub] [--since 7d] [--dry-run]
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
---

Use the `readwise:ingest` skill, then the `readwise:enrich` skill over what it wrote.
