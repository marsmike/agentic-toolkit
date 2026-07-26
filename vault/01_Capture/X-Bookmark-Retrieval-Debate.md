captured: 2026-07-23
origin: x-bookmark

Bookmarked thread arguing pure-vector RAG degrades past a certain corpus size because embedding
similarity is a lossy compression of meaning, and at small-to-medium scale a structured/keyword
approach with the model reasoning at query time beats it outright. Counter-replies pointed out
this trades embedding-time cost for query-time token cost, and that the crossover point depends
heavily on corpus size and query complexity — nobody in the thread had a number, just the
direction of the effect.

Distill note: this is adjacent to, but not the same claim as, the BM25-dilution capture from last
week (that one is about description length diluting keyword scores, not about vector vs.
structured retrieval generally). Keep them separate when writing these up.
