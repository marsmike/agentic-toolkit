# gaiafield

Knowledge-graph extraction *and inference* over an agentic-toolkit vault. Named in `docs/PLAN.md`
(Engines) and `contract/KNOWLEDGE_API.md`. Two layers, never conflated:

- **v1, `extracted`** — deterministic: parse wikilinks, frontmatter, and tags into a queryable
  SQLite store. No model call, no edge that can hallucinate — see
  `vault/04_Resources/Concepts/Deterministic-vs-Inferred-Graph-Edges.md`.
- **v2, `inferred`** — statistical: embed every node's content and score pairwise similarity.
  Report-only, forever — nothing here writes vault content, and nothing here mutates an
  `extracted` row (`contract/KNOWLEDGE_API.md`, "v2 — inferred edges", rules 1–2).

## Usage

```bash
gaiafield index [--vault ./vault] [--db <path>] [--full] [--json]
gaiafield neighbors <note> [--depth N] [--direction in|out|both] [--include-inferred] [--json]
gaiafield stats [--json]
gaiafield path <from> <to> [--include-inferred] [--json]

# v2 — inferred edges
gaiafield infer [--vault] [--db] [--full|--reset] [--json]
gaiafield candidates <note> [--k N] [--include-ambiguous] [--json]
gaiafield surprise [--top N] [--min-score f] [--include-ambiguous] [--json]
gaiafield calibrate --clusters <spec.json> [--json]
```

- `--vault <path>` — explicit vault path. Falls back to `TOOLKIT_VAULT`, then `./vault` relative
  to a repo root found by walking up for `.claude-plugin/marketplace.json` (mirrors
  `crates/farsight` and `core/toolkit_core/vault.py::resolve_vault`).
- `--db <path>` — SQLite database location. Defaults to `<vault>/.gaiafield/graph.db`.
- `<note>` (for `neighbors`/`path`) — a vault-relative path (with or without `.md`) or a bare
  note name, resolved with wikilink semantics. A bare name matching more than one indexed note
  (this vault plants exactly one such case: `Weekly-Review`, once per project) is reported as
  ambiguous with every candidate listed — never picked silently.

## Node scope

Nodes are the schema's active-content notes — `02_Projects/`, `03_Areas/`, `04_Resources/`
(`contract/VAULT_SCHEMA.md`; matches `vault/Index.md`'s stated count) — **plus** any note directly
at the vault root whose own frontmatter declares `status: active`. In the example vault that adds
exactly one node: `Alex-Vega.md`.

**Why the addition:** taken literally, the schema's active-content filter is exactly those three
folders for "any generated index," which would exclude a root-level note. But
`vault/04_Resources/Guides/Test-Corpus-Map.md` names Alex-Vega as *the* bridge note ("root
persona, links into all three clusters"), and excluding it would make the planted bridge structure
this vault was built to test unreachable. The note's own frontmatter already opts in
(`status: active` — the note-lifecycle meaning of "active" in the same schema's frontmatter table,
distinct from the folder-level filter), so this crate honors that self-declaration narrowly:
nothing else at the root joins the node set (`Index.md` and `CLAUDE.md` carry no frontmatter at
all), and `Config/`/`Templates/` are never scanned — they hold plugin config and templates, not
vault content.

`00_Memory/`, `01_Capture/`, and `05_Archive/` are never nodes. A wikilink from active content
into one of them is recorded as a **boundary violation**, not a normal edge — the schema forbids
the link outright.

## Edge extraction

Edges come from body wikilinks only (`[[Target]]` / `[[Target|Alias]]`) — not from frontmatter
fields such as `enrichment_targets`, and not from shared tags. `docs/PLAN.md` describes v1's
inputs as "wikilinks/frontmatter/tags"; this crate reads frontmatter and tags into **node
metadata** (`title`, `description`, `status`, `kind`, `tags`) and reserves tag/frontmatter-derived
*edges* for a later increment, since v1's job is proving out the deterministic wikilink graph
first.

Each wikilink target resolves one of four ways:

1. **Node** — resolves to another indexed node; recorded as an `EXTRACTED` edge.
2. **Boundary violation** — resolves to a real file inside `00_Memory`/`01_Capture`/`05_Archive`;
   recorded with a flag, counted separately in `stats`.
3. **Out of scope** — resolves to a real vault file that simply isn't a node (`Config/`,
   `Templates/`, a root note without `status: active`, `Index.md`, `CLAUDE.md`). Not an error, not
   flagged — just outside what this graph models, the same way search's active-content filter
   silently doesn't surface it either. No edge row is written.
4. **Dangling** — doesn't resolve to any file anywhere in the vault; recorded with a flag. The
   example vault plants exactly one: `[[Nonexistent-Note-For-Linting-Demo]]` in
   `Vault-Maintenance-and-Linting.md`.

A bare-name target ambiguous between multiple real files (the planted `Weekly-Review` case) is
resolved same-folder-first — if the linking note's own directory holds one of the candidates,
that one wins, matching how every planted in-folder `[[Weekly-Review]]` link in this vault is
meant to resolve. If it's still ambiguous (no same-folder candidate — the two cross-cluster
mentions in `Toolkit-Maintenance.md` and `Running-Evals.md`), the extractor records an edge to
*every* candidate rather than silently guessing one — deterministic in the sense that it never
hallucinates a choice the source text doesn't make. This is deliberately more permissive than the
CLI's own bare-name lookup (`neighbors`/`path`), which has no source-note context to disambiguate
by proximity and refuses to guess at all.

## Incremental indexing

`index` compares each node's file mtime + size against the stored value and only re-extracts
new/changed notes; rows for notes removed from the vault are deleted along with their outgoing
edges. `--full` drops and rebuilds everything. This mirrors farsight's staleness-averse design
philosophy applied to a persisted store instead of a stateless scan — a graph has to persist to be
queryable by `neighbors`/`path`/`stats`, so unlike farsight it can't avoid a cache; incremental
re-extraction is the freshness discipline it gets instead.

## Graph queries

- `neighbors` — BFS out to `--depth` hops (default 1). `--direction` filters to `in`, `out`, or
  the default `both` (an edge is traversable either way) — "what's connected to this note" is
  usually the more useful question than a direction-strict one. `--include-inferred` adds every
  note with a *direct* inferred edge to the queried note (see "neighbors/path --include-inferred"
  below); without the flag, output is byte-identical to a db that was never `infer`'d.
- `path` — shortest path via BFS over the same undirected view of the graph, or a clear
  not-connected answer. `--include-inferred` lets the route use inferred edges as real hops.
- `stats` — node/edge counts, dangling-edge and boundary-violation counts, the top 10 notes by
  in-degree, and (once `infer` has run at least once) inferred/ambiguous edge counts, the model
  name, and the high/low gates.

`context` is named alongside `neighbors` in `contract/KNOWLEDGE_API.md`'s reserved surface but not
implemented here — the same incremental-delivery pattern farsight used for its own vector half:
the reserved verb exists, the increment that ships it doesn't yet.

## Embedding backend

`infer` needs a text-embedding model that is deterministic (same text → same vector), fully
offline at inference time, small, and — the hard constraint, since the release workflow
cross-compiles `aarch64`/`x86_64-unknown-linux-musl` — either pure Rust or a verified
musl-cross-compilable dependency (`ort`/ONNX runtime is historically painful there).

**Chosen: [model2vec-rs](https://github.com/MinishLab/model2vec-rs) +
[potion-base-8M](https://huggingface.co/minishlab/potion-base-8M)** (MinishLab's static
embeddings). Model2Vec is *not* a transformer — encoding a note is a deterministic
tokenize-lookup-and-average over a fixed embedding table, so there's no ONNX/libtorch runtime to
cross-compile in the first place, and no sampling to make output nondeterministic.

**musl cross-compile story, verified, not assumed:** both `model2vec-rs` and its `tokenizers`
dependency ship convenience feature flags (`onig`/`fancy-regex`) that *also* pull in
`tokenizers/esaxx_fast`, which compiles a C++ library (`esaxx-rs`, built with the `cpp` feature) —
exactly the risk this constraint warns about. This crate avoids it entirely by depending on
`tokenizers` directly with `default-features = false, features = ["fancy-regex"]` (satisfying
`tokenizers`' own `compile_error!` — it requires one of `onig`/`fancy-regex` — without asking for
`esaxx_fast`) and on `model2vec-rs` with `default-features = false, features = ["local-only"]`
(dropping its bundled `hf-hub`/`ureq`; this crate owns the download-and-verify path itself, see
below). Verified via `cargo build -v`: with this exact feature set, `esaxx-rs` compiles with
neither `cc` nor `cpp` active (it has a pure-Rust fallback), and grepping the full verbose build
log for `cc`/`clang`/`gcc`/`g++` finds nothing — **zero C/C++ compilation**, the same guarantee
`farsight` has. See `Cargo.toml`'s dependency comments for the exact feature lines.

The one dependency that *is* in the same risk class as `rusqlite`'s bundled SQLite: `ureq` (used to
download the pinned model files) pulls in `rustls` + `ring`, and `ring` does compile a small amount
of C/assembly for some targets.

**Honest status, not yet verified (Fix 3):** the `aarch64-unknown-linux-musl` release build that's
actually been proven end-to-end (`gaiafield-v0.1.0` tag, "Cross-compilation note" below) is v1 —
`rusqlite`'s bundled SQLite only, no `ring` anywhere in that dependency tree. The mechanism this
crate depends on for `ring` — `taiki-e/setup-cross-toolchain-action` setting `CC_<target>`/
`CXX_<target>`/`AR_<target>` for `cc-rs` — is the *same* mechanism already proven for SQLite's C
amalgamation, which is why it's reasonable to expect it to also cover `ring`'s C/assembly. But
"the same mechanism, applied to a dependency verified elsewhere" is a prediction, not a
verification: no v2 tag has actually built `aarch64-unknown-linux-musl` with `ring` in the
dependency tree yet, and `ring`'s assembly (not straight C) is a slightly different code path than
`libsqlite3-sys`'s C amalgamation even under the same toolchain. This gets verified, not assumed,
the first time a `gaiafield-v0.2.0`+ (or later) tag's release workflow actually builds and ships
the `aarch64-unknown-linux-musl` asset with `model2vec-rs`/`ureq` in the tree — check that tag's
workflow run before trusting this target for a v2+ release the way "Cross-compilation note" already
lets v1 be trusted.

**Model acquisition:** `infer` downloads three files (`config.json`, `tokenizer.json`,
`model.safetensors`, ~29 MB total) from a *pinned* HuggingFace revision
(`MODEL_REVISION` in `src/lib.rs`) into a local model cache directory, verifying each against a
pinned sha256 (`MODEL_FILES`) before ever loading it — a hash mismatch is a hard error, never a
silent fallback. Already-present, already-verified files are never re-downloaded, so every run
after the first is fully offline. Cache location: `<db-parent>/models/potion-base-8M/` by default,
overridable with `TOOLKIT_GAIAFIELD_MODEL_DIR` (the test suite uses this to share one download
across many throwaway test databases).

Model: **`potion-base-8M`** (`minishlab/potion-base-8M` at commit `bf8b0566…`), 256 dimensions.
Every JSON output that reports a score also reports the model name (contract rule 3 — "a gate
value without its model name is meaningless"): `infer` and `calibrate` carry it at the top level;
`stats --json` is the single source of truth for a currently-inferred db's model + gates.
`candidates` rows don't repeat it per-row — every row is scoped to the one queried note across a
single call, so `stats` is the intended cross-reference for that surface. `surprise` rows *do*
carry it per-row as of Fix 2 (see "Surprise scoring" below): unlike `candidates`, a `surprise` call
isn't scoped to one note, and a row's `label` is only meaningful alongside the model that produced
its score.

## Calibration

`gaiafield calibrate --clusters <spec.json>` measures whether the model actually separates
same-topic from different-topic content, against ground truth: a
`{"clusters": {"name": [paths...]}}` spec naming known clusters of already-`infer`'d notes. It
groups every pairwise cosine similarity by cluster pair and reports:

```json
{"intra_mean": f, "cross_mean": f, "separation": f,
 "suggested_high_gate": f, "suggested_low_gate": f, "model": "...",
 "tight_clusters": ["..."],
 "cluster_pairs": {"<a>~<b>": {"mean": f, "n": usize}, ...}}
```

`cluster_pairs` is the full per-cluster-pair breakdown (every pair, `a == b` for an intra-cluster
group) that `intra_mean`/`cross_mean` compress away — see "The bias lesson" below for why the
compressed numbers alone were actively misleading. `tight_clusters` lists which clusters
`intra_mean`/`cross_mean` are actually derived from (see "Tightness rule" below).

### The bias lesson — pooled means overfit to cluster-size imbalance

**This crate shipped with calibration that was statistically broken, found and fixed in R5.** The
original method pooled *every* intra-cluster pair across *every* cluster into one `intra_mean`, and
every cross-cluster pair into one `cross_mean` — weighted, implicitly, by `C(n, 2)`: quadratic in
cluster size. Against `./vault`'s three planted clusters (`Test-Corpus-Map.md`: toolkit-concepts —
57 notes, `04_Resources/{Concepts,Guides,Tools}/` plus `Alex-Vega.md`; birding — 7 notes,
`02_Projects/field-guide/` plus `03_Areas/Birding.md`; homelab — 7 notes,
`02_Projects/home-lab-migration/` plus `03_Areas/Home-Network-Administration.md`), that pooling
gave toolkit-concepts 1596 intra-pairs against birding's and homelab's 21 apiece — toolkit-concepts
alone is ~97% of every intra-pair in the pool. The reported numbers,

```
intra_mean: 0.6222   cross_mean: 0.5418   separation: 0.0804
suggested_high_gate: 0.6021   suggested_low_gate: 0.5619
```

were therefore *measuring the grab-bag, not the signal*. The tell: `birding`'s and `homelab`'s own
notes score **0.630** similarity to *each other* (a genuine cross-cluster pair) — higher than
toolkit-concepts' own diluted intra-mean of **0.617**. A "different topic" pair out-scored a "same
topic" pair. Gates derived from that pooled gap (real practical consequence, measured against a
fresh copy of `./vault` under the R5 recalibration below): at high/low 0.60/0.56, **1405** of all
non-linked pairs in the vault landed `INFERRED`+`AMBIGUOUS` (1037 `INFERRED`, 368 `AMBIGUOUS`), and
the birding note `Publisher-Outreach-Log.md`'s top-15 candidates by raw score held only **2**
same-cluster hits.

### Tightness rule, objective and self-excluding

For each cluster `C`, compute a **leave-one-out reference cross-mean**: the pooled mean over every
cross-cluster pair *not involving* `C` (this deliberately excludes any cross pair `C` itself might
be contaminating). `C` is **tight** iff its own intra-mean exceeds that reference. `intra_mean`/
`cross_mean` are then recomputed pooled over only the tight clusters' own pairs (intra: within a
tight cluster; cross: between two tight clusters — a pair touching a non-tight cluster is dropped
entirely, not folded into either side). With ≥ 3 clusters this is always well-defined; with exactly
2, there's no pair excluding either one, so both are trivially tight (nothing to compare against);
with 1, there are no cross pairs at all, so it's trivially tight too (`separation` reads `0.0`,
correctly signaling "no cross-cluster signal available").

On `./vault`'s three clusters: `birding` (intra 0.806) clears the bar set by
`homelab~toolkit-concepts` (0.529); `homelab` (intra 0.808) clears the bar set by
`birding~toolkit-concepts` (0.544); `toolkit-concepts` (intra 0.617) does **not** clear the bar set
by `birding~homelab` (0.630) — it self-excludes exactly as its own diluted intra-mean predicts it
should. `tight_clusters: ["birding", "homelab"]`.

### R5 recalibration — new numbers

Recomputed pooled over only `birding`/`homelab`'s own pairs (a fresh `./vault` copy, scratch
db, same model/revision):

```
intra_mean: 0.8067   cross_mean: 0.6298   separation: 0.1769
suggested_high_gate: 0.7183   suggested_low_gate: 0.6740
```

`suggested_high_gate` is now the **midpoint** of the gap (`cross_mean + 0.5 * separation`), not the
old 0.75-of-gap split. The 75% figure was deliberately biased toward precision *to compensate for a
gap the old method couldn't trust* (0.08, mostly grab-bag noise); now that `separation` reflects a
real, more-than-double-the-old gap (0.177) between two demonstrably tight clusters, that
compensation isn't needed — the midpoint is the unbiased split between the two distributions.
`suggested_low_gate` keeps the same 25%-of-gap shape as before, just recentered on the tightened
numbers.

Rounded to `DEFAULT_HIGH_GATE = 0.72`, `DEFAULT_LOW_GATE = 0.67`. Switching `MODEL_REVISION`
invalidates all of the above and requires a fresh `calibrate` run.

**Measured consequence**, same fresh `./vault` copy, `infer --full` at the new gates vs. the old:

| | old (0.60 / 0.56) | new (0.72 / 0.67) |
|---|---|---|
| `INFERRED` | 1037 | 226 |
| `AMBIGUOUS` | 368 | 254 |
| **total** | **1405** | **480** |

`Publisher-Outreach-Log.md`'s candidates dropped from 31 total (top-15 held 2 same-cluster hits)
to **6** total: the single `INFERRED` one (`03_Areas/Birding.md`, score 0.728) is the same-cluster
hit — same-cluster hits *dominate* the default (`INFERRED`-only) view a caller sees without asking
for `--include-ambiguous`. The 5 `AMBIGUOUS` rows split 1 more same-cluster
(`Reference-Library.md`) against 4 cross-cluster (a homelab `Weekly-Review.md`, the `Alex-Vega`
bridge note, and two toolkit-concepts guides) — exactly the fuzzy-band mix `AMBIGUOUS` exists to
hold: generic documentation-vocabulary overlap that a human, not a gate, should adjudicate.

`intra_mean > cross_mean` is exercised by
`infer_produces_inferred_edges_with_calibration_separation` in `tests/graph_test.rs`; the tightness
rule itself (self-exclusion, `cluster_pairs` breakdown) is exercised by
`calibrate_self_excludes_the_grab_bag_cluster_via_cluster_pairs_breakdown`.

## Surprise scoring

`candidates`/`surprise` share one formula (`surprise_score` in `src/lib.rs`), never reimplemented:

```
det_distance = BFS distance over extracted edges only (undirected), or null if unreachable
surprise     = score * (1 - 1 / (1 + det_distance))     if det_distance is finite
             = score * 1                                 if det_distance is null (unreachable)
```

A same-neighborhood inferred edge (small `det_distance`) is unsurprising even at a high score; an
edge between two notes with no deterministic route at all is maximally surprising. `same_subtree`
(a `surprise`-only field) is a cheap structural heuristic, not the planted cluster labels: the
first two path segments (e.g. `02_Projects/field-guide`), or the whole path for a root note with
no second segment.

**`surprise` row shape and gating (Fix 2 — the original CLI spec this crate was built against was
wrong for `surprise`, and the binding contract wins):** each row is pair-shaped — `a`/`b` (both
vault-relative paths; there's no single "queried note" the way `candidates` has), `score`,
`surprise`, `det_distance`, `same_subtree`, plus **`label`** (`INFERRED`/`AMBIGUOUS`) and **`model`**.
The spec `surprise` was originally built against had neither field and no `--include-ambiguous`
flag, which meant `surprise` — unlike `candidates` — could leak the `AMBIGUOUS` band by default
with no way for a caller to even see which label a row carried, violating
`contract/KNOWLEDGE_API.md`'s v2 rule that `AMBIGUOUS` is "surfaced only when a caller explicitly
asks; never proposed proactively." `gaiafield surprise --include-ambiguous` (default: excluded)
now mirrors `candidates --include-ambiguous` exactly; `model` is included per-row here (unlike
`candidates`, see "Embedding backend" above) since a `surprise` row's `label` is only meaningful
alongside the model that produced its score, and `surprise` rows can span calls against
differently-inferred dbs where `candidates` rows are always scoped to one queried note. Exercised
by `surprise_gates_ambiguous_band_and_every_row_carries_label_and_model` in `tests/graph_test.rs`.

## neighbors/path --include-inferred

`neighbors --include-inferred` unions the exact v1 `extracted` BFS (`kind: "extracted"`,
unchanged) with every note that has a *direct* inferred edge to the queried note (`kind:
"inferred"`, always reported at `depth: 1` regardless of `--depth`). Inferred edges are a
similarity score, not a chain — unlike wikilinks, this crate deliberately does not walk them
hop-by-hop for `neighbors`, so a note only ever surfaces as an inferred neighbor when it has a
*direct* inferred edge to the note you asked about. A note reachable both ways keeps its
`extracted` record (contract rule 4 — the deterministic edge always wins a conflict).

`path --include-inferred` has no such ambiguity — a path is one concrete route, not an aggregated
set — so it runs a real BFS over the union of both edge kinds, letting an inferred edge serve as a
genuine hop when no all-extracted route exists (or a shorter mixed one does). Each hop after the
first carries its `kind` (`"extracted"`/`"inferred"`, plus `label`/`score` for the latter); the
first entry is the start note itself, `kind: "start"`. Extracted edges are offered to BFS before
inferred ones at every node, so a tie in route length prefers the deterministic one.

Without `--include-inferred`, both commands call the untouched v1 functions — verified
byte-identical on an `infer`'d db by
`neighbors_without_include_inferred_is_byte_identical_on_an_inferred_db` in `tests/graph_test.rs`
(contract rule 4: traversal defaults to deterministic).

## Testing

`tests/graph_test.rs` is the only test file, run against the repo's own `./vault` (never a user's
vault, per `CONTRIBUTING.md`) against the planted structure in
`vault/04_Resources/Guides/Test-Corpus-Map.md`: node count and link density, the one planted
dangling edge, zero boundary violations, the Alex-Vega bridge reaching all three clusters within
depth 2, a birding-to-homelab path, the ambiguous `Weekly-Review` lookup, incremental re-indexing
touching only the changed note, incremental deletion never corrupting the graph — plus, for v2:
`infer` producing real edges with calibration separation on the planted clusters, `calibrate`'s
tightness rule self-excluding the planted grab-bag cluster (`cluster_pairs` breakdown), `candidates`
surfacing a same-cluster note while excluding already-wikilinked pairs, `surprise` surfacing
cross-subtree pairs and gating its `AMBIGUOUS` band the same way `candidates` does (every row
carrying `label`/`model`), `infer --reset` restoring the exact v1 graph row-for-row, and `neighbors`
without `--include-inferred` staying byte-identical on an `infer`'d db. Every test uses its own
throwaway database under the system temp dir — never `vault/.gaiafield/graph.db` — so a test run
never leaves an untracked database inside the example vault. The v2 tests share one model-cache
directory (`shared_model_dir()`, a fixed path under the system temp dir, not per-test) so the
~29 MB model download happens at most once per machine, not once per test — `gaiafield::infer`
takes the model directory as an explicit argument specifically so tests never need to touch
process environment (`TOOLKIT_GAIAFIELD_MODEL_DIR` is for real CLI usage, e.g. sharing a cache
across several vaults).

## Cross-compilation note

This crate's `rusqlite` dependency uses the `bundled` feature, which compiles SQLite's C
amalgamation — unlike `farsight`, which has no C dependencies at all. `.github/workflows/
release-binaries.yml` cross-compiles `aarch64-unknown-linux-musl` via
`taiki-e/setup-cross-toolchain-action`, which (per its own `main.sh`) pulls a real cross
toolchain image and sets `CC_<target>`/`CXX_<target>`/`AR_<target>` env vars that `cc-rs` (the
build-time dependency `libsqlite3-sys` uses to invoke a C compiler) reads directly — so this
works without a workflow change. **Verified for v1:** the `gaiafield-v0.1.0` tag push built and
released all 4 target assets, including `aarch64-unknown-linux-musl` — with `rusqlite`'s bundled
SQLite as the *only* C dependency in that tree.

The v2 embedding backend was chosen specifically to avoid *adding* a second C dependency in this
same risk class — see "Embedding backend" above for the (verified) zero-C-compilation story for
`model2vec-rs`/`tokenizers` — with one exception: `ureq`'s TLS stack (`ring`), which does compile
C/assembly, and which the v0.1.0 verification above never exercised (v1 has no `ureq` dependency
at all). **Not yet verified for v2 (Fix 3, honest pending item):** the expectation that the same
`taiki-e/setup-cross-toolchain-action` mechanism proven for `libsqlite3-sys`'s C amalgamation also
covers `ring`'s C/assembly is a reasonable prediction — same env vars, same `cc-rs` machinery — not
a demonstrated fact. This gets marked verified only once a `gaiafield-v0.2.0`+ tag's release
workflow run actually completes the `aarch64-unknown-linux-musl` build with `model2vec-rs`/`ureq`
in the dependency tree; check that tag's own workflow run rather than assuming this note's v1
verification extends to it.
