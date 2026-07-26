---
name: enrich
description: Add optional GitHub repo metadata and YouTube transcripts to already-written Readwise captures. Use after ingest, or when a capture references a repo or video worth enriching.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
---

# Readwise Enrich

Post-processes captures already written by the `ingest` skill: finds GitHub repo and
YouTube video links inside a capture's body, fetches metadata, and appends an
`## Enrichment` section. Both enrichers are independent and optional — a capture with
neither is left untouched, and either enricher's absence never blocks the other.

## Why this is separate from ingest

Enrichment depends on external CLIs (`gh`, `yt-dlp`) that may not be installed; ingest's
job (getting every clipping safely into `01_Capture/`) must never be gated on them. See
`profile.example.md`'s `enrichers` field for enabling/disabling each by default.

## GitHub

```python
import github_meta as gh

if gh.gh_available():
    repos = gh.extract_repo_slugs(capture_body)
    for repo in repos:
        meta = gh.fetch_repo_meta(repo)
        if "error" not in meta:
            status = gh.activity_status(meta)
            # append a row: | [owner/repo](url) | stars | language | last push | status | description |
```

Mind the `.git`-suffix trap: strip it with a suffix check (`re.sub(r"\.git$", "", name)`),
never `str.rstrip(".git")` — that strips any trailing `.`/`g`/`i`/`t` character and
silently mangles names like `microsoft/graphrag` into `microsoft/graphra`. Already handled
inside `github_meta.extract_repo_slugs()`; don't re-implement the regex ad hoc.

No `gh` on PATH, rate-limited, or a private/deleted repo → `fetch_repo_meta()` returns
`{"error": "..."}`. Log it and continue; never fail the whole enrich pass over one repo.

## YouTube

```python
import youtube_meta as yt

if yt.yt_dlp_available():
    meta = yt.fetch_video_meta(video_url, langs="en,de", max_chars=15000)
    if "error" not in meta:
        # append duration/views/channel + up to 3-5 key takeaways from meta["transcript_text"]
```

No transcript available (live keynotes, copyrighted-lyric videos, very short clips) →
`transcript_text` comes back empty; fall through to the capture's existing Readwise
summary rather than treating it as a failure.

## Appending the enrichment section

Read the capture with `vault_utils.read_frontmatter()`, append an `## Enrichment` section
to the body (after `## Full Text`, before `## Processing Notes`), and write back with
`vault_utils.write_frontmatter()` — this preserves every frontmatter field the enrichment
step didn't touch (contract/VAULT_SCHEMA.md's "floor, not ceiling" rule).

## References

- [github.md](references/github.md) — repo metadata fields, activity-status thresholds
- [youtube.md](references/youtube.md) — transcript fetch details, key-takeaway extraction
