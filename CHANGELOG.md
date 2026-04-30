# Changelog

All notable changes to this project will be documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Changed (repo layout)
- Examples moved from repo-root `examples/feinschliff/` into the plugin folder: `feinschliff/examples/`. Per-brand preview folders renamed from `template-preview-{brand}/` to just `{brand}/` so a GitHub user landing on the plugin sees `examples/spotify/`, `examples/bmw/`, etc. — the brand IS the folder name. The eponymous Feinschliff preview lives at `feinschliff/examples/feinschliff/`. The repo root no longer carries an `examples/` directory.

### Added
- Four new `feinschliff` brand packs derived from getdesign.md, each with a generic non-trademarked glyph and a stable PDF preview committed to `feinschliff/examples/{brand}/`:
  - **Spotify** — Spotify-green accent on true-black canvas, geometric sans, three-bar equalizer glyph.
  - **Binance** — Binance-yellow accent on crypto-black, IBM Plex Sans tabular, four-segment diamond glyph.
  - **BMW** — corporate-blue accent on pure-white canvas, condensed grotesque, quartered-disc glyph (generic pie geometry, not the BMW roundel).
  - **Ferrari** — Rosso Corsa + Modena-yellow on cinematic black, classical serif/sans pairing, heraldic-shield silhouette (the Cavallino Rampante is intentionally not reproduced).

### Changed
- **BMW pack** elevated from token-swap to first reference brand pack with **brand-specific design language**, derived from the canonical [getdesign.md/bmw](https://getdesign.md/bmw/design-md) DESIGN.md. Five new policy blocks shipped alongside DTCG tokens — `layout`, `cover`, `section-marker`, `photography`, `headline-rule`, `chip-rule` — plus an explicit `chip-rule` for the iconic "LEARN MORE ›" inline CTA. Renderer changes to give the deck visible BMW DNA:
  - Light canvas + dark navy hero band rhythm (was dark-canvas-first).
  - 700 / 300 weight ladder with weight 500 explicitly absent (the BMW editorial signature).
  - All display tracking forced to 0; Apple-style negative letter-spacing removed (off-brand for BMW Type Next).
  - 4px M-stripe primitive (`add_m_stripe`) used at chapter dividers and cover boundaries.
  - "LEARN MORE ›" chevron-link primitive (`add_chevron_link`) — UPPERCASE 1.5px tracked.
  - 1px hairline divider primitive (`add_hairline`).
  - Cover, both chapters, and KPI grid rebuilt to BMW-canonical compositions (HairlineHeader cover, M-stripe chapter dividers, spec-cell KPI pattern).
  - Quote and End slides moved off forbidden full-bleed BMW Blue onto compliant dark navy / mirrored cover treatments.
- New radius-aware primitive `add_rounded_rect(radius_px=…)` plumbed through `add_button` / `add_chip` / `add_column(as_card=True)`. Reads from new `radius.btn`, `radius.chip`, `radius.card` token slots so brand packs flip pill / rounded / sharp shapes by editing tokens, never the renderer. BMW (radius=0) falls through to the existing `MSO_SHAPE.RECTANGLE` path — output is pixel-identical to the prior frozen build (verified by per-page PNG diff).
- **Spotify pack** elevated to the second reference brand pack, demonstrating the policy-driven architecture in its mirror-opposite mode from BMW (pills + rounded cards + heavy shadows + dark canvas, vs. BMW's sharp rectangles + hairlines + light canvas). Same primitive set, different token values:
  - `radius.btn = radius.chip = 9999` → fully-rounded pill buttons; `radius.card = 8` → 8px rounded album-art card register. BMW's `add_button` / `add_chip` / `add_column(as_card)` produce pills here without a renderer change.
  - `add_rounded_rect` extended with a `shadow="elevated"|"dialog"` parameter that injects OOXML drop shadows per Spotify DESIGN.md §6 — `rgba(0,0,0,0.3) 0px 8px 8px` for cards, `rgba(0,0,0,0.5) 0px 8px 24px` for modals. Spotify needs heavy shadows on the dark canvas; BMW (no shadows ever) ignores the parameter via the existing `shadow.inherit = False` default.
  - New chrome primitive `add_equalizer_marker` — three-to-four green pill bars of varying height, replacing BMW's `add_m_stripe` role at chapter dividers.
  - New chrome primitive `add_pill_link` — UPPERCASE 1.4px-tracked label voice for inline pill-density CTAs (Spotify analog of BMW's `add_chevron_link`).
  - Bold/regular weight binary (700/400) replaces BMW's 700/300 ladder — the binary IS the typographic hierarchy per DESIGN.md.
  - Cover (album-art shelf + green PLAY pill), both chapters (equalizer marker + soft chapter watermark), KPI grid (4-up rounded shadowed cards on dark canvas), Quote, and End layouts rebuilt as Spotify-canonical compositions. Title Accent and End slides moved off forbidden full-bleed Spotify Green onto dark canvas with green pill CTAs.
  - Six new policy blocks (`layout`, `cover`, `section-marker`, `photography`, `headline-rule`, `chip-rule`, `shadow`) — same shape as BMW's, different values. Confirms the architecture generalizes.
- **Ferrari pack** elevated to the third reference brand pack — cinematic editorial register, sharp 0px corners, single sans family at 500/400/700 weights. Distinct from both BMW (light canvas, 700/300 ladder, M-stripe) and Spotify (pills + heavy shadows, 700/400 binary, equalizer marker):
  - Tokens rebuilt against canonical [getdesign.md/ferrari](https://getdesign.md/ferrari/design-md): Rosso Corsa `#DA291C` (was `#FF2800` placeholder), near-black canvas `#181818` (slightly warm, never pure black), single FerrariSans / Inter family across every text role (was an off-brand serif/sans pair).
  - Display weight is 500 (medium), NEVER bold — DESIGN.md is explicit: *"Don't bold display copy. The cinematic photography does the visual heavy-lifting."* Bold (700) is reserved for component titles, button labels, and the `number-display` (KPI value + race-position cell).
  - Negative letter-spacing on display is the brand's editorial signature — `headline-rule.tracking-em = -0.02` (-1.6px @ 80px display-mega). BMW says no negative tracking; Ferrari says yes.
  - Sharp 0px corners on every CTA, card, band — `radius.btn = radius.card = 0`. Same code path that produces BMW's rectangles produces Ferrari's; opposite of Spotify's pills. Pill geometry (`radius.chip = 9999`) reserved for the badge-pill — the ONE place pill is allowed.
  - New chrome primitive `add_livery_band` — full-width Rosso Corsa accent band, replacing BMW's `add_m_stripe` role and Spotify's `add_equalizer_marker` role at chapter dividers.
  - New chrome primitive `add_uppercase_link` — UPPERCASE 1.4px-tracked button-voice inline link, NO terminator (DESIGN.md is explicit — labels end at the last letter, never with `›` or `→`).
  - New chrome primitive `add_hairline` — 1px brightness-step divider on dark (`#303030` — same hex as canvas-elevated, reads as a tone-step). Ferrari has no shadow tiers; depth comes from hairlines + brightness-step + cinematic photography ONLY.
  - Cover (`title_ink` cinematic dark + Rosso Corsa CTA), accent cover (`title_orange` 60/40 dark/livery-band split), both chapters (chapter_ink 50/50 cinema-photo split, chapter_orange livery-band rule), KPI grid (4-up spec-cell pattern with one cell highlighted in Rosso Corsa as `race-position-cell`), Quote (display-mega 500/-0.02 pull quote), and End (cinematic dark + centered "Grazie." + Rosso Corsa CTA) layouts rebuilt as Ferrari-canonical compositions.
  - Seven new policy blocks (`layout`, `cover`, `section-marker`, `photography`, `headline-rule`, `chip-rule`, `shadow`) — same shape as BMW/Spotify, with `shadow.elevated = "none"` confirming the architecture supports a "shadow-free" brand alongside Spotify's heavy-shadow brand.
  - Heraldic-shield glyph kept (generic abstraction, not the licensed Cavallino Rampante); wordmark continues as "FERRARI" UPPERCASE per the brand's classical lockup register.

## [0.1.0] — 2026-05-01

### Added
- Initial public release.
- **`feinschliff`** plugin (anchor) — brand-pluggable design system that turns Claude Design HTML into brand-perfect PowerPoint decks. Ships with the eponymous `feinschliff` brand pack (indigo palette + Noto Sans, MIT). Three skills: `/deck`, `/extend`, `/compile`.
- Marketplace skeleton: LICENSE (MIT), NOTICE, CONTRIBUTING (DCO), CODE_OF_CONDUCT, SECURITY.
- GitHub: 12 topics, branch protection, issue/PR templates, DCO check, CI workflow.

[Unreleased]: https://github.com/marsmike/agentic-toolkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/marsmike/agentic-toolkit/releases/tag/v0.1.0
