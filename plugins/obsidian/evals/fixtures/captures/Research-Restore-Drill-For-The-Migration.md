---
captured: 2026-08-09
origin: research-session
---

# Restore drill plan for the home-lab migration cutover

For the migration weekend: before each service is cut over to the new box, restore last
night's backup of that service onto the new box and start it from the restored data, not from
a live copy. If the restore fails, the cutover for that service is postponed. Order: DNS
first, then the file share, then the media server. Record each drill in that week's review.
This is the concrete schedule for the rule that an untested backup is only a hypothesis.
