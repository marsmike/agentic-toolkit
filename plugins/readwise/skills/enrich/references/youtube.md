# YouTube Enrichment Reference

## Fetch

`youtube_meta.fetch_video_meta(url, langs="en,de", max_chars=15000)` runs `yt-dlp` once
(metadata + auto-subs together) and returns the metadata dict with `transcript_text` and
`transcript_chars` injected, or `{"error": "..."}`.

Partial subtitle-language availability is normal — `yt-dlp` exits non-zero when *any*
requested language is missing even if another one succeeds. `fetch_video_meta()` already
tolerates this; don't treat a non-zero `yt-dlp` exit as fatal on its own.

## Key takeaways

Extract 3-5 from `transcript_text` (or the description, if no transcript): specific
techniques/tools/commands mentioned, the core argument or thesis, actionable advice,
notable quotes. This is a judgment call for the invoking agent, not something
`youtube_meta.py` does — the script's job stops at clean transcript text.

## Output

```markdown
### YouTube Videos

| Video | Duration | Views | Channel | Key Takeaway |
|-------|----------|-------|---------|--------------|
| [Title](url) | 26m | 3,250 | Channel Name | One-line insight |

#### [Video Title](url)
**Channel:** Name · **Duration:** 26m · **Views:** 3,250

**Key Takeaways:**
- Takeaway 1
- Takeaway 2
```

## Failure modes

- No transcript at all → fall back to the capture's existing Readwise summary/description;
  not an error.
- Private/deleted video → `fetch_video_meta()` returns `{"error": ...}`; log and skip.
- `yt-dlp` not installed → same; the enrich skill continues with GitHub enrichment alone.

## Transcript ordering — do not sort or globally dedupe

`youtube_meta._json3_to_text()` only collapses *consecutive* duplicate caption lines
(rolling auto-captions repeat the same line across events) and preserves chronological
order otherwise. A prior version of this logic used a dedupe step that sorted its input
as a side effect, silently scrambling every transcript into alphabetical order — a
regression specifically worth not reintroducing if this script is ever touched.
