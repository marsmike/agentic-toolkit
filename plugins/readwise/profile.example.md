---
description: Example profile for the readwise plugin — copy the frontmatter shape below into your own vault's Config/toolkit/readwise.md.
kind: profile
status: active
plugin: readwise
backlog_sweep: true
newsletter_senders:
  - Readwise
attachments_folder: 04_Resources/Attachments
tags:
  - domain/toolkit-meta
  - profile
---

# readwise plugin profile (example)

Copy this file's frontmatter shape to `$VAULT/Config/toolkit/readwise.md` to override the
plugin's shipped defaults. Every field below is optional — an absent file, or an absent field
within it, falls back to the plugin's built-in default. See `contract/PROFILE.md` for the full
resolution order (env var → this note → shipped default).

## Fields

- **`newsletter_senders`** — senders (the email's `author`, matched case-insensitively as a substring)
  whose emails are newsletters: distill may drop those without a note. Every other email is a
  clip and always ends as a note or an enrichment, so forward mail to Reader without worry.
  Default `[Readwise]`; add a sender only for mail you are happy to lose.
- **`backlog_sweep`** — whether `ingest` runs the mandatory reconciliation pass over
  `location=new`/`later` in addition to the windowed `updatedAfter` sync. Defaults to `true`;
  set `false` only if you have an external reason to trust the watermark alone (not
  recommended — see `references/ingest-workflow.md` for why the watermark
  alone missed a real clipping for two months in the source project this was ported from).

## Secrets

No credential belongs in this file, ever — see `contract/PROFILE.md`'s Secrets section. The
Readwise API token is the `READWISE_TOKEN` environment variable, referenced here only by name.
Get a token at https://readwise.io/access_token.

## Env var overrides

Every field above also has a `TOOLKIT_READWISE_<FIELD>` environment variable that wins over
this note, per `contract/PROFILE.md`'s resolution order — e.g. `TOOLKIT_READWISE_BACKLOG_SWEEP=false`.

## Attachments

- **`attachments_folder`** — where a `pdf` clipping's original file is stored (vault-relative;
  default `04_Resources/Attachments`). The capture gets `attachment:` in its frontmatter and a
  `**Document:** [[path]]` line; the distilled note must keep that link (distill workflow, step
  6). The extracted text stays in the capture and its archive copy; the note is the map.
