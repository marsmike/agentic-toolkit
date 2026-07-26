# Methodology

## Why predict-then-score, not just "read the description and judge it"

Judging a description in isolation ("does this sound like a good description?") doesn't
catch the failure mode that actually hurts retrieval: a description that reads
perfectly well but doesn't discriminate this note from five others on adjacent topics.
Forcing an explicit prediction *before* opening the body makes the miss visible — if you
predicted "a comparison of vector databases" and the note is actually about calibrating
one specific embedding model's score threshold, that gap is the signal, not a vibe.

This mirrors what a BM25/vector retriever does mechanically: it has no access to the
body at query time either, only to whatever got indexed from the title/description/
summary. If a human predicting from the same inputs gets it wrong, the retriever's
ranking will be wrong for the same reason.

## BM25 dilution — the specific failure this loop targets

Two notes can describe the exact same content at very different retrieval quality:

- A **long, discursive description** ("this note explores the background of X, its
  motivation, its history, and several tangential asides about Y in general...") dilutes
  the keyword weight of the actual distinguishing terms. Every word in the description
  competes for the same term-frequency budget; padding it with scene-setting prose pulls
  weight away from the 3-5 words that would actually separate this note from its
  neighbors in a BM25 or embedding index.
- A **condensed description in high-IDF terms** ("Retrieval-verification loop,
  condensed-description specimen, BM25 test pair.") scores far better on both counts: a
  human predicts its content correctly and faster, and a BM25 query matches it more
  precisely.

The example vault ships a matched pair demonstrating exactly this
(`04_Resources/Concepts/Retrieval-Verification-Loop-Long-Description-Specimen.md` and
its `-Condensed-Description-Specimen.md` sibling) — read both once to calibrate your own
scoring before running this on real notes.

## Sample size

15-20 notes is enough to surface a systemic pattern (e.g. "every note distilled before a
certain date has this problem") without becoming a full-vault audit. Run it periodically
(after a bulk distill/import batch, or on a recurring maintenance cadence) rather than
once — description quality drifts as a vault grows and old conventions get superseded.

## What "flagged" should trigger

A score below 3 means: rewrite the description, don't rewrite the note. The content
might be fine; the retrieval surface for it isn't. Prefer the condensed-specimen style
(lead with the concrete subject, in terms someone would actually search for) over the
long-specimen style when rewriting.
