# Skill evals (`claude plugin eval`)

Behaviour tests: does Claude, given this plugin's skills, do what the skill says? They
complement `evals/run.py`, which tests the scripts offline and runs in CI. These run a real
model and cost money, so they are run by hand:

```bash
claude plugin eval plugins/obsidian --allow-tools Bash Write Edit --scaffold \
  --runs 1 --ablation none --no-publish --max-cost-usd 5      # pilot
claude plugin eval plugins/obsidian --allow-tools Bash Write Edit --scaffold \
  --model claude-sonnet-5 --judge-model claude-sonnet-5 --no-publish --max-cost-usd 20
```

Each case scaffolds a fresh copy of the example vault into the run's workspace (copied from
this repo, so no case depends on the machine's vault), pre-builds the scripts' environment
on the host (the sandbox has no network), and, when `~/.env` holds an OpenRouter key, puts
it in the workspace's project settings so the judgment backend works inside the run.
Without a key every case still runs, on the no-backend path.

**Jev is the judge where it can be.** `distill-auto` grades the JSON that `distill_check.py`
writes: the hard gates, findability of the agent's own questions, and the preservation
check (kept passages carried), all typed judgments. The LLM grader is left for the one
thing only a reader can judge: is the reply a proposal, does it say where things went.
Use `--judge-model claude-sonnet-5` for it; the default small judge failed a correct
triage reply three votes to none.

| Case | What it checks |
|---|---|
| `distill-auto` | an explicit `--auto` run: dossier ran, a note was written, the check ran, the capture left `01_Capture/` |
| `distill-checkpoint` | without `--auto`: dossier ran, nothing was written, the reply is a proposal that stops for review |
| `triage-inbox` | triage runs the dossier over the inbox, writes nothing, and reports a decision per capture |
