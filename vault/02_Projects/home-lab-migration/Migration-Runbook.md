---
description: The repeatable per-service migration procedure used for each of the five home-lab services.
status: active
created: 2026-04-25
tags:
  - domain/homelab
  - workflow
type: project-doc
---

# Migration Runbook

One service at a time, never a big-bang cutover — a lesson from an earlier, unrelated migration
that took three services down simultaneously and made the failure hard to isolate. Per service:

1. **Provision** the service on the new tower per [[Network-Topology]], service stopped on the old
   box but not yet removed.
2. **Restore-test** — pull the latest backup per [[Backup-Strategy]] onto the new box and verify
   it actually serves data before touching production traffic.
3. **Cut over** — repoint whatever clients depend on the service (DNS entry, mount point, git
   remote URL) to the new box.
4. **Soak** — leave the old box's copy running read-only for one week as a fallback.
5. **Decommission** — after a clean week, remove the service from the old box; update
   [[Hardware-Inventory]].

## Related

- [[Home-Lab-Migration]]
- [[Network-Topology]]
- [[Backup-Strategy]]
- [[Hardware-Inventory]]
- [[Weekly-Review]]
- [[Home-Network-Administration]]
