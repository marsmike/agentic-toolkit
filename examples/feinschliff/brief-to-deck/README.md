# Example — Brief → Branded deck (`/deck`)

Demonstrates `/deck` taking a one-paragraph natural-language brief and producing a brand-compliant `.pptx`.

## Input — `brief.txt`

```
Q1 2026 update for the leadership team. Three customers shipped on the new
plan, $4.2M ARR, churn down to 2.1%. Two product launches landed: the
public API in February and the OAuth2 hardening in March. Two open risks:
the AWS bill is up 18% YoY (new analytics workload), and we're still
hiring for the platform staff role we opened in January.

Audience: CEO + 4 VPs. ~6 minutes total. End with the two risks framed
as decisions we want their input on.
```

## Command

```bash
# In Claude Code, after `/plugin marketplace add marsmike/agentic-toolkit`
/deck "Q1 2026 update for the leadership team..."
```

`/deck` will:

1. Ask one clarifying question (perfection bar — 3 default / 6 perfectionist iterations).
2. Parse the brief into `content_plan.json` + `design_brief.json` and present a one-screen approval gate.
3. Pick layouts per the inferred narrative frame (likely SCQA for a status update).
4. Render via the active brand's Baukasten → `out/<deckname>.pptx`.
5. Run the 11-class verify pass; iterate up to the budget; emit `out/verify_report.md`.

## Expected output

- `q1-2026-leadership-update.pptx` — 8–10 slides, Feinschliff-themed.
- `verify_report.md` — green on all 11 defect classes after 1–3 iterations.

## Notes

- Replace the brief above with your own — anything from one paragraph to a structured outline works.
- Use `polish` mode to reflow an existing rough deck instead: `/deck polish my-rough-deck.pptx`.
- Use `critique` mode to get a defect analysis without changes: `/deck critique existing.pptx`.
