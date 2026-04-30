# Changelog

All notable changes to this project will be documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Four new `feinschliff` brand packs derived from getdesign.md, each with a generic non-trademarked glyph and a stable PDF preview committed to `examples/feinschliff/template-preview-{brand}/`:
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

## [0.1.0] — 2026-05-01

### Added
- Initial public release.
- **`feinschliff`** plugin (anchor) — brand-pluggable design system that turns Claude Design HTML into brand-perfect PowerPoint decks. Ships with the eponymous `feinschliff` brand pack (indigo palette + Noto Sans, MIT). Three skills: `/deck`, `/extend`, `/compile`.
- Marketplace skeleton: LICENSE (MIT), NOTICE, CONTRIBUTING (DCO), CODE_OF_CONDUCT, SECURITY.
- GitHub: 12 topics, branch protection, issue/PR templates, DCO check, CI workflow.

[Unreleased]: https://github.com/marsmike/agentic-toolkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/marsmike/agentic-toolkit/releases/tag/v0.1.0
