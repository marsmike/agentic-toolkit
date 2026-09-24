# Music (decision D5: proposed, awaiting the operator's approval)

One instrumental track under all 118 seconds. It is **not committed**: `npm run fetch-music` downloads it to
`public/music/` (gitignored) and refuses a file whose sha256 differs. `music.json` is what the script and the
render read; this page is for people.

| | |
|---|---|
| Work | Erik Satie, *Gymnopédie No. 1* ("Lent et douloureux"), 1888 |
| Performer | Robin Alciatore (piano), recording published by [Musopen](https://musopen.org) |
| Source page | https://commons.wikimedia.org/wiki/File:Erik_Satie_-_gymnopedies_-_la_1_ere._lent_et_douloureux.ogg |
| File URL | https://upload.wikimedia.org/wikipedia/commons/9/90/Erik_Satie_-_gymnopedies_-_la_1_ere._lent_et_douloureux.ogg |
| sha256 | `419e37656856224227086df32d6d481a00a738961e08fca9f6147e472beea53e` |
| sha1 | `96b2343c81047abd9723488d8540b5a2af688233` (matches the sha1 Wikimedia Commons publishes for the file) |
| Format | Ogg Vorbis, stereo, 44.1 kHz, 3:03.6, 3,696,351 bytes |
| Licence | **Public domain**, as Wikimedia Commons lists it (`LicenseShortName` "Public domain", `AttributionRequired` false, credit musopen.com). The composition is out of copyright (Satie died in 1925). Only the Commons listing was checked, not Musopen's own terms. |
| Attribution | None required. Crediting "Music: Erik Satie, Gymnopédie No. 1, performed by Robin Alciatore (Musopen), public domain" in the release notes is a courtesy, not an obligation, so the locked end card is unchanged. |

**How it is used:** playback starts 2.0 s into the recording (`startSeconds`, skipping its 2.2 s of silent lead-in),
fades in over the first second, plays at 70 % volume and fades out over the last 3 seconds; the video ends at 118 s,
before the piece does. No voice anywhere.

**Why this track:** solo piano, slow and quiet, so it sits under dense on-screen text without competing; no
lyrics; and a public-domain licence removes the attribution the locked storyboard has no place for.

**Checked on 2026-09-24:** the licence fields above were read from the Commons API (`prop=imageinfo`,
`extmetadata`). The operator approves the track before the render is accepted.
