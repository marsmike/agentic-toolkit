---
type: llm
focus: last_message
weight: 2
---
PASS if the reply is a proposal that stops for the user's review: it names a proposed
placement folder, lists related existing notes with a proposed enrichment level each,
and asks for confirmation (or says it is waiting for it) before writing anything.
FAIL if the reply reports that a note was written, a capture was moved, or an existing
note was changed.
