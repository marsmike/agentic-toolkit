---
captured: 2026-08-08
origin: research-session
source: https://example.org/cheatsheets/restic
---

# restic flags cheat sheet

- `restic init --repo <path>`: create a repository
- `restic backup <dir> --exclude-file <file>`: back up with an exclude list
- `restic snapshots`: list snapshots
- `restic check --read-data`: verify every pack file
- `restic restore <id> --target <dir>`: restore a snapshot
- `restic forget --keep-daily 7 --keep-weekly 4 --prune`: retention
- Environment: `RESTIC_REPOSITORY`, `RESTIC_PASSWORD_FILE`
