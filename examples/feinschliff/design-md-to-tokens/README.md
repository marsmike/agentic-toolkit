# Example — DESIGN.md → Brand pack (`/compile`, v0.2 preview)

> **Status:** v0.2 feature preview. The DESIGN.md ingestion path lands in feinschliff v0.2; this example documents the intended workflow.

Demonstrates the planned v0.2 feature: drop a DESIGN.md from [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (34k★, 76 design systems) into a brand-pack scaffold and have `/compile` generate `tokens.json` + the Claude Design HTML reference.

## Input — `vercel.design.md` (excerpt)

```markdown
# Vercel Design System

## 2. Color Palette & Roles

- background: #000000
- foreground: #FFFFFF
- accent: #FFFFFF
- muted: #888888
- success: #0070F3
- destructive: #FF0000

## 3. Typography Rules

- display: Inter, system-ui, sans-serif
- body: Inter, system-ui, sans-serif
- mono: Geist Mono, ui-monospace, monospace

(... 7 more sections per the awesome-design-md spec ...)
```

(Full DESIGN.md files live in [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md), MIT-licensed.)

## Command (v0.2)

```bash
# Future v0.2 invocation — not yet shipped
/compile --from-design-md vercel.design.md --brand vercel
```

This will:

1. Parse the DESIGN.md (9-section schema per awesome-design-md).
2. Generate `feinschliff/brands/vercel/tokens.json` with the colors + fonts mapped to feinschliff's neutral semantic token names (`accent`, `accent-hover`, `highlight`, `ink`, `graphite`, etc.).
3. Generate a starter `feinschliff/brands/vercel/claude-design/vercel-2026.html` that visualises the tokens in a 33-slide showcase.
4. Inherit renderer code from the closest existing brand pack.
5. Run the brand-pack smoke test to verify the build is green.

## Expected output (v0.2)

```
feinschliff/brands/vercel/
├── tokens.json
├── claude-design/
│   ├── vercel-2026.html
│   └── assets/
├── catalog/layouts.json
├── renderers/
│   └── pptx/
└── README.md
```

## Notes

- The brand-pack contract stays unchanged in v0.2. DESIGN.md is added as an alternative authoring path, not a replacement.
- Trademark caveat: brand packs derived from DESIGN.md files reference the source brand's tokens but do **not** include the source brand's logo or wordmark. The Vercel and Linear and Stripe brands are trademarks of their respective owners.
