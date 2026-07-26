captured: 2026-07-19
origin: research-session

Notes from a research pass on community detection algorithms for the graph engine. Leiden
improves on Louvain by guaranteeing well-connected communities (Louvain can produce disconnected
ones as an artifact of the merge order). Relevant because the graph engine's v3 milestone wants
community detection over the wikilink graph — see the toolkit plan.

Open question I didn't resolve: resolution parameter tuning. Too coarse and birding notes and
homelab notes end up in the same community because they're both "Alex's stuff" and share a couple
bridge notes; too fine and every project note is its own singleton community. Needs a real corpus
to tune against, not just reading about it.

Raw, not yet distilled — do not treat this as the concept note.
