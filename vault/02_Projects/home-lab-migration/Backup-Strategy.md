---
description: Backup and restore-verification approach used during the home-lab migration, including the restore-drill discipline.
status: active
created: 2026-04-28
tags:
  - domain/homelab
  - reference
type: project-doc
---

# Backup Strategy

The rule this project runs on: **a backup that hasn't been restored is a hypothesis, not a
backup.** Every service migration in the [[Migration-Runbook]] includes a restore-test step
before cutover, not just a "the backup job ran green" check — a lesson from restore-testing a
service during this same migration and discovering the backup had been silently excluding one
directory for months.

- Nightly backups from both boxes to a third location (outside the scope of
  [[Network-Topology]], deliberately off-path).
- Restore drills happen at cutover time (per [[Migration-Runbook]]) and are logged in the relevant
  week's [[Weekly-Review]], not in a separate log — the volume doesn't justify one.

## Related

- [[Home-Lab-Migration]]
- [[Migration-Runbook]]
- [[Network-Topology]]
- [[Weekly-Review]]
- [[Home-Network-Administration]]
