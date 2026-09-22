---
type: llm
focus: last_message
weight: 2
---
PASS if the reply names the note that now holds the capture's content (a new note under
02_Projects, 03_Areas or 04_Resources, or an existing note it enriched instead of
duplicating), lists at least one enrichment with its level (L1, L2 or L3), and states the
result of the check (pass, or which gate failed and why).
FAIL if any of the three is missing, or if the reply asks the user to confirm before
writing (this was an explicit --auto run).
