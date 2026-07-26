---
name: handoff-resume
description: Resume from the latest handoff in this repo — load it and continue from the next step. Also surfaces any newer PreCompact auto-snapshot.
allowed-tools: Bash, Read
---

# Handoff Resume

1. Run:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handoff.py" resume
   ```
2. Read the printed handoff (and any newer auto-snapshot — printed only when it postdates
   the handoff, per `../handoff/references/workflow.md`'s auto-snapshot note). **Orient**:
   restate the goal, what's done, and what was ruled out in 3–5 lines.
3. Announce the plan and continue from the **Next Step**. Don't redo settled work.

No `_handoff/` directory, or no handoff files in it, both print a plain "nothing to
resume" message — not an error; a repo that has never used this plugin is a normal state.
