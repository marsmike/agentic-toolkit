# Narrative Frames

Four frames that structure a deck's spine. Step 1 infers the frame from the brief / existing content. Step 2 uses it to order slides and assign roles. Step 4 checks red-line breaks against it.

## SCQA (Minto Pyramid)

**Use when:** the audience needs an answer fast — exec updates, decision proposals, technical recommendations to non-technical stakeholders.

**Don't use when:** the deck is exploratory, a discovery journey, or the conclusion depends on the walk-through.

**Slide roles in order:**
1. `hook` — optional, often skipped for SCQA
2. `context` — Situation (stable baseline)
3. `complication` — Complication (what changed / broke)
4. `recommendation` — Answer (your action)
5. `support` / `evidence` — 2–3 points backing the recommendation
6. `close`

**Inference cues:** brief contains "recommend", "propose", "decision"; exec audience; short time budget (≤15 min).

## PSSR (Problem / Search / Solution / Result)

**Use when:** presenting a project, evaluation outcome, or status update where the journey matters.

**Don't use when:** the audience is too senior to care about the journey (use SCQA instead) or there's no meaningful search phase (use Sparkline).

**Slide roles in order:**
1. `hook`
2. `complication` — the Problem (pain, quantified)
3. `context` — the Search (approaches tried, tradeoffs)
4. `recommendation` — the Solution (what won)
5. `evidence` — the Result (quantified impact)
6. `close`

**Inference cues:** brief contains "we evaluated", "we tried", "status update", "post-mortem", "retrospective".

## Sparkline (Duarte — What Is / What Could Be)

**Use when:** vision pitch, change proposal, call to action. Oscillates current painful reality with desirable future.

**Don't use when:** no meaningful gap between present and future (use SCQA), or audience is tactical/operational (use PSSR).

**Slide roles in order (each pair oscillates):**
1. `hook`
2. `complication` — what is (pain)
3. `recommendation` — what could be (possibility)
4. `complication` — next pain beat
5. `recommendation` — next possibility beat
6. (repeat as needed)
7. `close` — "new bliss"

**Inference cues:** brief contains "vision", "imagine", "transform", "future of", "where we're going".

## Man-in-a-Hole (Vonnegut)

**Use when:** story of an incident, migration, crisis-and-recovery. Simple, emotionally engaging arc.

**Don't use when:** no real fall happened (use SCQA or PSSR).

**Slide roles in order:**
1. `hook`
2. `context` — Equilibrium (what was normal)
3. `complication` — the Fall (what broke)
4. `complication` — the Pit (bottom, quantified impact)
5. `recommendation` — the Climb (how it was resolved)
6. `evidence` — Resolution (new equilibrium, better than before)
7. `close`

**Inference cues:** brief contains "incident", "outage", "migration", "post-mortem", "then X happened", "we ended up".

## Picking a frame (when inference is ambiguous)

- If the content has a quantified recommendation → **SCQA**.
- If it has a journey with alternatives evaluated → **PSSR**.
- If it's selling a future state → **Sparkline**.
- If something broke and got fixed → **Man-in-Hole**.
- Still ambiguous → default to **SCQA** (safest bet for technical audiences; always passable for exec).

Always write `frame_rationale` in `design_brief.json` naming the runner-up frame and why it was rejected. The runner-up is a hint to the user at the step-1b gate if they want to override.
