# Handoff narrative template

Write these sections into `_handoff/.draft.md`. Frontmatter, repo/git state, and the
chain link are added by the script — do **not** write them yourself. Omit a section only
if it is genuinely empty. Bias everything toward what the next session needs to *act*.

```markdown
## Goal

One or two sentences: what we're ultimately trying to achieve (the outcome, not the task).

## Status

Where we are right now. What works, what's half-done, what's untouched. Be concrete.

## Tried & Ruled Out

Append-only dead-end ledger — the highest-leverage section. Each bullet: what was tried,
why it failed or was rejected, so nobody re-explores it.
- Tried X → didn't work because Y.
- Considered Z → rejected: <reason>.

## Key Decisions

Choices made and the reasoning, so they aren't relitigated.
- Chose A over B because C.

## Evidence & Data

Concrete facts the next session shouldn't re-derive: measurements, error messages,
command outputs, API responses, file:line references.

## Next Step

THE exact next action — specific enough to start immediately. Include the file:line to
edit, the command to run, or the question to resolve. If there's an ordered list, give it.
1. …
2. …

## How to Verify

How to confirm the next step worked (test command, expected output, manual check).

## Quick Start

The literal first move for the next session (e.g. run the `handoff-resume` skill, then
`open generate_html.py:412`).
```

## Guidance

- **Forward, not backward.** A record of finished work is low value; direction and
  open decisions are high value.
- **Specific beats complete.** "Fix the sort" is useless; "in `generate_html.py:412`
  the comparator sorts strings not numbers — cast to int" is a handoff.
- **Keep it short.** If it's longer than ~1 screen, you're logging, not handing off.
- **Same stream tag** across sessions on one effort → they chain automatically.
