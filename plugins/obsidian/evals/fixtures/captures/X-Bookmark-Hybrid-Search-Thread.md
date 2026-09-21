---
captured: 2026-08-11
origin: x-bookmark
---

# Thread: hybrid search in practice

BM25 by itself misses paraphrases, and vector search by itself misses exact identifiers such
as error codes and package names. Teams are converging on running both and fusing the two
rankings at query time, mostly with reciprocal rank fusion, instead of choosing one.
