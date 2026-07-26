captured: 2026-07-22
origin: readwise

Highlight dump, unprocessed. BM25 alone misses paraphrase; pure vector search misses exact
identifiers (error codes, package names). Several teams converging on BM25 + dense vector fused
at query time (reciprocal rank fusion, mostly) rather than picking one. One thread argued the
fusion weight should shift based on query shape — short exact-match-y queries lean BM25, long
descriptive queries lean vector — but didn't have a citation for the threshold, just vibes from
running it in prod.

Also flagged: a tangent about chunking strategy for PDFs vs. markdown notes, probably a separate
note if it goes anywhere.

TODO: check whether this overlaps with the Research- capture on Leiden clustering before
distilling either.
