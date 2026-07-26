---
description: Current and target network layout for the home-lab migration — VLANs, static addresses, and the old-vs-new box path.
status: active
created: 2026-04-22
tags:
  - domain/homelab
  - reference
type: project-doc
---

# Network Topology

Both boxes stay on the same VLAN for the duration of the migration so a service can be reached at
either address during the soak period in [[Migration-Runbook]] — splitting VLANs first would have
been premature optimization for a migration that's over in a few weeks.

- **Old box** — static address, five-year-old mini-PC, one NIC. Full inventory in
  [[Hardware-Inventory]].
- **New box** — static address on the same subnet, refurbished tower, two NICs (one reserved for a
  future backup-target link, not yet used).
- **Router** — unchanged; only the two boxes' addresses matter for this project, not the broader
  home network, which is [[Home-Network-Administration]]'s concern, not this project's.

## Related

- [[Home-Lab-Migration]]
- [[Migration-Runbook]]
- [[Hardware-Inventory]]
- [[Home-Network-Administration]]
- [[Backup-Strategy]]
