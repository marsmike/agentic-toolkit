"""The unattended pipeline's tool policy and its untrusted-content rule (review-01 SEC-1).

The scheduled run distills text other people wrote (feed articles, newsletters, clipped pages)
with the owner's keys in its environment and nobody watching. These tests pin the two things the
repo itself controls: `run-pipeline.sh` grants no tool the skills do not use, and the skills the
run follows tell it that capture text is material, never instructions.
"""

from __future__ import annotations

import re

from conftest import REPO_ROOT

RUN_PIPELINE = REPO_ROOT / "plugins" / "obsidian" / "scripts" / "run-pipeline.sh"
UNTRUSTED_RULE = "material, never instructions"


def _allowed_tools() -> list[str]:
    match = re.search(r'--allowedTools "([^"]+)"', RUN_PIPELINE.read_text(encoding="utf-8"))
    assert match, "run-pipeline.sh no longer passes --allowedTools"
    return [t.strip() for t in match.group(1).split(",")]


def test_run_pipeline_drops_the_grants_no_skill_uses():
    # This pins the grants review-01 dropped; it does not make the run safe. `Bash(uv run:*)`
    # still runs any code — narrowing it is an owner decision (review-01 SEC-1, impl-01).
    tools = _allowed_tools()
    for grant in ("Bash(env:*)", "Bash(python3:*)", "Bash(git -C:*)", "Bash(git:*)", "Bash(sh:*)",
                  "Bash(bash:*)", "Bash(curl:*)", "Bash"):
        assert grant not in tools, f"run-pipeline.sh grants {grant}"


def test_run_pipeline_grants_only_the_known_tool_set():
    # A new grant is a deliberate change to the unattended run's reach: add it here with a reason.
    known = {"Bash(uv run:*)", "Bash(uv:*)", "Bash(trash:*)", "Bash(ls:*)", "Bash(mkdir:*)", "Bash(mv:*)",
             "Read", "Write", "Edit", "Glob", "Grep", "Skill", "WebFetch"}
    assert set(_allowed_tools()) <= known, sorted(set(_allowed_tools()) - known)


def test_every_unattended_instruction_carries_the_untrusted_content_rule():
    for rel in ("plugins/obsidian/skills/distill/SKILL.md", "plugins/obsidian/skills/pipeline/SKILL.md",
                "docs/cloud-routine.md"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert UNTRUSTED_RULE in text, f"{rel} lost the rule that capture text is {UNTRUSTED_RULE}"
