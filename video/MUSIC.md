# Music

One instrumental bed under the whole film, **generated**, not downloaded: `npm run music` runs
`scripts/make_music.py`, which writes `public/music/explainer-bed.wav` (gitignored). It is deterministic (a fixed seed),
so there is no licence to check and no attribution to give.

**What it is:** calm and understated. A warm pad in D major (Dmaj9, Bm9, Gmaj9, Asus2, one chord every two bars), a
soft plucked arpeggio from the vault scene on, and a quiet sub pulse from the plugins scene to the end card. No
drums and no drops. It is loud enough to carry the film (about -17 LUFS before the render's 0.8 volume), never
louder than the picture.

**How it follows the picture:** it reads `src/timeline.json`, the file the video reads. 80 BPM puts one bar at
3 s, and every scene starts on a bar, so the music changes where the picture does. A low-pass filter opens as the
graph forms and again for INFERRED, then settles for the end card. Each cue gets one soft bell in key: the three
search hits, the neighbours lighting up, the three INFERRED pairs and "your call".

**In the render:** `src/Explainer.tsx` plays it from the first frame at `volume` 0.8 (`music.json`), fades in over
1.5 s and out over the last 3 s. No voice anywhere.

**Replaces** the Satie *Gymnopédie No. 1* recording the first cut used (decision D5): slow, sad piano was too heavy
for a short product film. The operator approves this bed before any publish.
