# GitHub Enrichment Reference

## Fetch

`github_meta.fetch_repo_meta("owner/repo")` runs `gh api repos/{owner}/{repo}` under the
hood and returns:

```json
{
  "full_name": "owner/repo", "description": "...", "language": "Python",
  "stars": 24346, "forks": 1200, "open_issues": 40,
  "created_at": "...", "pushed_at": "...", "topics": ["..."],
  "license": "MIT", "archived": false
}
```

or `{"error": "..."}` on any failure (no `gh`, rate limit, 404, private repo).

## Activity status

`github_meta.activity_status(meta)`:

| Condition | Status |
|---|---|
| `archived` is true | Archived |
| `pushed_at` in current or last year | Active |
| otherwise | Stale |

## Output table

```markdown
## Enrichment

### GitHub Repos

| Repo | Stars | Language | Last Push | Status | Description |
|------|-------|----------|-----------|--------|-------------|
| [owner/repo](https://github.com/owner/repo) | 24,346 | Python | 2026-03-10 | Active | Short description |
```

Sort by stars descending. Skip repos whose fetch returned `{"error": ...}` rather than
rendering a broken row — or render a row with `—` placeholders and a one-line note,
whichever the capture's other rows already do (consistency within one table matters more
than which convention).
