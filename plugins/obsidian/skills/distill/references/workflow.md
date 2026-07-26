# Distillation Workflow

Filesystem-only throughout: every step below uses `Read`/`Write`/`Edit`/`Grep`/`Glob`/`Bash`
directly against vault-relative paths. No app CLI, no embeddings store, no vendored
environment is required for any step to succeed.

## 1. Read the capture

```bash
cat "$VAULT/01_Capture/<capture-name>.md"
```

Extract the original source URL or citation from frontmatter (`source:`, `url:`,
`author:`) or body. **Every distilled note must carry this.** If none is identifiable,
say so explicitly in the Phase 1 handoff rather than inventing one.

## 2. Check for prior distillation

Grep the active vault for the capture's URL(s) before assuming the material is new —
overlapping capture sources collide more often than expected:

```bash
grep -rlF "https://example.com/the-url" "$VAULT/02_Projects" "$VAULT/03_Areas" "$VAULT/04_Resources"
```

A hit inside a note's frontmatter (`source:`) means that note is the canonical
distillation already — switch to enrichment-only mode (step 8) rather than writing a
near-duplicate. A hit only in body prose is adjacency, not provenance; treat it as a
related note, not evidence the capture is already distilled.

## 3. Read Index.md, then search — both, not either

First pass: read `Index.md` at the vault root and skim for topic-area entries. This is
cheap and catches things by name, but an Index.md miss does not mean nothing related
exists — it only covers what's been catalogued.

Second pass, required: run the search script.

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/search.py" \
  "3-5 key concepts from the capture" --top 10 --json
```

It reports `semantic_available: false` and a short explanation when no optional
embeddings dependency is installed — that's an expected, correct state on a fresh
clone, not an error to route around. Either way, the keyword + Index.md-summary channel
always runs; a distill pass never proceeds with zero search. Results at or above the
vault's `search_score_gate` (default 0.70, see `profile.example.md`) are enrichment
candidates (step 8).

### Graph context (if a gaiafield binary is available)

`scripts/graph.py` mirrors `search.py`'s farsight preference chain: a `gaiafield` binary
(`TOOLKIT_GAIAFIELD_BIN` env var, else PATH) is optional, deterministic-only (v1 scope —
wikilinks/frontmatter/tags, no inferred edges), and this step must never block the
workflow when it's absent.

```python
import graph

if graph.available():
    graph.ensure_index(vault)  # incremental — cheap on repeat runs
    context = graph.graph_context(vault, [m["path"] for m in top_matches], k=1)
```

When `context` comes back as a dict (not `graph.GraphUnavailable`), fold it into the
Phase 1 handoff's related-notes list, labeled distinctly from the search-scored matches:

- **Backlink candidates** (`context["backlink_candidates"]`) — notes directly linked to a
  top match that the text search itself didn't surface. Propose these as additional
  Level-1 backlinks (step 8), same as a search hit above the score gate.
- **Bridge opportunities** (`context["bridge_opportunities"]`) — the subset of the above
  living in a different top-level PARA subtree (`02_Projects`/`03_Areas`/`04_Resources`,
  or a root-level note) than the capture's proposed placement. Call these out by that
  exact name, **"bridge opportunity,"** in the Phase 1 handoff. This is a deterministic
  precursor of the surprise scoring a later gaiafield increment adds
  (`crates/gaiafield/README.md`) — present it as "worth a look," never as a ranked or
  scored recommendation.

When `graph.available()` is false (`GraphUnavailable` reason `"no-binary"`), skip this
section entirely and proceed with steps 4+ exactly as they read below — the search
step's results are the only related-notes source, and the Phase 1 handoff says so in one
line rather than silently doing less than a run where the binary was present. A failed
invocation of a binary that IS present (`"call-failed"`) writes a DLQ note automatically
(`scripts/graph.py`'s `_dlq_on_call_failure`) and degrades the same way.

### Inferred candidates (if the binary supports gaiafield v2)

**Rule 1, verbatim from `contract/KNOWLEDGE_API.md`'s v2 section: report-only, forever.**
No automation writes vault content — a link, an enrichment, a note — from an inferred
edge without explicit human confirmation in that session. Everything below is a
candidate for a human decision, never an input to an autonomous write.

After the deterministic graph-context step above, when `graph.available()` is true, try
the statistical layer too:

```python
top_matches = [m["path"] for m in matches[:3]]  # the proposed placement's top matches
inferred = graph.inferred_candidates(vault, top_matches[0], k=5)  # not GraphUnavailable("no-inference") only on a v2 binary
```

- If `inferred` comes back as a list (not `GraphUnavailable`): present it as its own,
  clearly separated block in the Phase 1 handoff — never merged into the deterministic
  backlink/bridge lists above — labeled along these lines:

  > **Inferred candidates (statistical, report-only — confirm before any use)**
  > model=`<inferred["model"] if surfaced>`
  > - `path` — score `0.NN` (INFERRED)

  Only rows labeled `INFERRED` by default. A row labeled `AMBIGUOUS` exists in the model's
  gate band and is shown only if the human explicitly asks for it (`include_ambiguous=True`);
  never surface one proactively.
- If `inferred` comes back as `GraphUnavailable("no-inference", ...)`: the binary predates
  gaiafield v2 — say so in one line, same as the `"no-binary"` case, and move on; this is
  a normal, silent degradation, not an error.
- **Surprise candidates** (`graph.surprise_candidates(vault, top=10)`) are cross-domain
  leads — mention them as an optional extra the human can request ("want me to check for
  cross-domain surprise candidates too?"), never run or presented unprompted.

## 4. Extract core mechanics (reasoning, not writing yet)

For each key idea: what's the underlying mechanism that makes this work? Name it as a
principle. Note which existing vault notes (found in steps 2-3) share that principle,
even across domains — the goal is a graph of interconnected mechanics, not a filing
cabinet of topic summaries.

## 5. Phase 1 handoff — wait for confirmation

Report back and stop:

- 3-5 core insights/mechanics and the principle(s) they map to.
- The original source (confirm you identified it, or flag that you couldn't).
- Proposed PARA placement (see rules.md) and title.
- Top 3-5 related notes with scores, and proposed enrichment level per note (L1/2/3).
- If graph context ran: any backlink candidates and bridge opportunities it added, or one
  line saying it didn't run (no gaiafield binary available).
- If inferred candidates ran: the separated, labeled block from the section above (or one
  line saying it didn't — no gaiafield v2 support). Never conflate these with the
  deterministic backlink/bridge lists.
- Already-distilled mode if step 2 found a canonical hit: `new-note | enrich-only | hybrid`.

Wait for confirm / redirect / reject. Skip only with an explicit `--auto` instruction.

## 6. Write the distilled note

Create the file directly with `Write` under the placement from step 5. Body must
include a `*Source: <url>*` line near the top; if genuinely none, write
`*Source: (none — originated from <context>)*` — never omit the line silently.

Set frontmatter: `status: distilled`, `processed_date: <today>`, `source: <url>`,
`tags: [...]`. `source` must be set even to the none-placeholder, never `unknown` — see
rules.md for why that specific string is actively harmful.

## 7. Verify source and URL preservation

```bash
grep -nE '\[\[[^]]*01_Capture|\]\([^)]*01_Capture' "$distilled_note_path" && echo "FAIL: links into 01_Capture" || echo "OK"
```

Confirm the `*Source:*` line and `source:` frontmatter both point at the external
original, never at `01_Capture/` or `05_Archive/`. If the capture carried other
substantive URLs (papers, repos, docs), confirm each landed in the note or in a
`## See also` section — a dropped link is unrecoverable once the capture is retired.

## 8. Enrich related notes — three-level decision per note

For each related note at or above the score gate (step 3), in `02_Projects`,
`03_Areas`, or `04_Resources` only (never `05_Archive`):

- **L1 (default) — append backlink** to a "Related"/"See Also" section. Create the
  section if missing.
- **L2 — merge inline**, only when you can cite a specific sentence/section the new note
  strengthens or extends. Insert alongside it, plus the L1 backlink.
- **L3 — flag contradiction**, only when the new note contradicts a specific existing
  claim. Insert an Obsidian callout adjacent to the contradicted line — never silently
  overwrite:

  ```markdown
  > [!warning] Contradicted by [[New Note]] (YYYY-MM-DD)
  > Brief summary of what changed.
  ```

Default to L1 when unsure. Each related note gets exactly one level.

## 9. Retire the capture

**Default: archive**, preserving provenance verbatim:

```bash
mkdir -p "$VAULT/05_Archive/<Origin>-Captures-$(date +%Y-%m)"
mv "$capture_path" "$VAULT/05_Archive/<Origin>-Captures-$(date +%Y-%m)/<stem>--FULLCAPTURE.md"
```

Write/update a `README.md` manifest in that folder naming the batch and where each
distilled output landed — this doubles as the run summary (step 11).

**Delete instead** only for duplicates, empty stubs, or explicit user instruction:
`rm "$capture_path"`.

Either way, the capture must leave `01_Capture/` — an inbox is ephemeral, and anything
left behind gets reprocessed on the next triage pass.

## 10. Update Index.md

Find the section for the note's folder (`## 04_Resources` → the right H3, creating it
if missing). Add or replace: `- [[rel/path/Note Name|Note Name]] — <one-line summary,
≤20 words>`, alphabetically within its section. Refresh entries for any note enriched at
L2/L3 whose "what this is about" changed.

## 11. Journal and log

Append to `00_Memory/journal/<today>.md`:

```
- [HH:MM] <project> | Distilled [title] into [location]. Enriched N notes.
```

Then:

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/log_vault.py" distill "Note Title"
```

---

## Triage mode

1. List captures: `ls "$VAULT/01_Capture/"*.md`
2. Preview each with `Read` to assess relevance.
3. Categorize: **distill** (run the full workflow above) / **quick file** (move to a
   PARA folder with minimal frontmatter, no full distillation) / **discard** (`rm`, for
   outdated or low-value material).

## Insight mode

Filing a conversation synthesis rather than an external capture:

1. Identify the content to file; ask the user to narrow scope if ambiguous.
2. Write it as a new capture: `01_Capture/insight-<unix-timestamp>.md` with
   `source: conversation` in frontmatter.
3. Run the full distill workflow above against that file — same rules, same checkpoint.
4. Log: `uv run ... log_vault.py file-insight "Note Title"`.

## When something is genuinely unresolvable

If search results are untrustworthy (e.g., a query that should obviously match returns
nothing), placement is truly ambiguous after one honest attempt, or a required piece of
provenance can't be recovered — don't guess and don't silently skip the step. Write a
dead-letter note instead:

```python
from vault_utils import write_dlq_note
write_dlq_note(vault, slug="short-slug", title="...", what_happened="...", why_recorded="...", confidence="low")
```

Say so in the Phase 1 handoff too. See rules.md's "Dead-letter queue" section.
