# Feinschliff Remotion Theme

Copy-paste recipe for authoring a Feinschliff-branded Remotion video. Values
are the TypeScript projection of `brands/feinschliff/tokens.json` — when
tokens change, update this file.

## Fonts

Feinschliff uses **Noto Sans** for display/body and **Noto Sans Mono** for eyebrows + labels.

```typescript
import { loadFont as loadNotoSans } from "@remotion/google-fonts/NotoSans";
import { loadFont as loadNotoSansMono } from "@remotion/google-fonts/NotoSansMono";

const { fontFamily: fontSans } = loadNotoSans({
  weights: ["300", "400", "500", "700"],
  subsets: ["latin"],
});
const { fontFamily: fontMono } = loadNotoSansMono({
  weights: ["400", "600"],
  subsets: ["latin"],
});
```

## Colour palette

Mirrors `tokens.json` → `color`. All values are hex.

**Naming projection:** `tokens.json` keys are kebab-case (`accent-hover`,
`kpi-value`) per DTCG convention; the TypeScript theme uses camelCase
(`accentHover`, `kpiValue`) per TS convention. When syncing, translate
`foo-bar` → `fooBar`.

| Token | Hex | Use |
|---|---|---|
| `accent` | `#2C5FE8` | Primary signature accent — sparingly |
| `accentHover` | `#1E47B8` | Interactive hover state |
| `highlight` | `#6B8AEC` | Soft tint / supporting accent |
| `black` | `#0A0E1A` | Max contrast text on light |
| `ink` | `#1A1F2E` | Body ink / dark backgrounds |
| `graphite` | `#5C6470` | Secondary text |
| `steel` | `#8A92A0` | Muted text |
| `silver` | `#B8BEC8` | Dividers, disabled text |
| `fog` | `#DDE1E8` | Hairlines, placeholder stripes |
| `paper` | `#F2F4F8` | Card / panel fills |
| `white` | `#FFFFFF` | Canvas on light |

## Typography scale

Mirrors `tokens.json` → `font-size`. Values are in CSS px, authored against
a 1920×1080 canvas. In Remotion, apply as `fontSize` directly.

| Role | Size | Weight | Line-height | Use |
|---|---|---|---|---|
| `display` | 160 | 300 (light) | 1.0 | Hero stat on intro scene |
| `huge` | 120 | 300 | 1.0 | Big chapter statement |
| `slideTitle` | 37 | 500 | 1.2 | Scene titles |
| `sub` | 44 | 400 | 1.3 | Sub-headlines |
| `body` | 26 | 400 | 1.5 | Paragraphs |
| `eyebrow` | 18 | 500 | 1.0 | **Mono**, uppercase, letter-spacing 0.12em |
| `kpiValue` | 120 | 300 | 1.0 | KPI hero number |
| `kpiUnit` | 40 | 300 | 1.0 | Inline unit (e.g. "k", "%") |
| `kpiKey` | 16 | 500 | 1.0 | **Mono**, uppercase KPI label |
| `colNum` | 14 | 500 | 1.0 | **Mono** column index |
| `colTitle` | 36 | 500 | 1.2 | Column title |
| `colBody` | 22 | 400 | 1.5 | Column body |
| `quote` | 84 | 300 | 1.1 | Full-scene quote |

## Theme object

```typescript
// src/theme.ts
import { loadFont as loadNotoSans } from "@remotion/google-fonts/NotoSans";
import { loadFont as loadNotoSansMono } from "@remotion/google-fonts/NotoSansMono";

const { fontFamily: fontSans } = loadNotoSans({
  weights: ["300", "400", "500", "700"], subsets: ["latin"],
});
const { fontFamily: fontMono } = loadNotoSansMono({
  weights: ["400", "600"], subsets: ["latin"],
});

export const feinschliffTheme = {
  colors: {
    accent: "#2C5FE8",
    accentHover: "#1E47B8",
    highlight: "#6B8AEC",
    black: "#0A0E1A",
    ink: "#1A1F2E",
    graphite: "#5C6470",
    steel: "#8A92A0",
    silver: "#B8BEC8",
    fog: "#DDE1E8",
    paper: "#F2F4F8",
    white: "#FFFFFF",
  },
  fonts: { sans: fontSans, mono: fontMono },
  type: {
    display:    { fontSize: 160, fontWeight: 300, lineHeight: 1.0, fontFamily: fontSans },
    huge:       { fontSize: 120, fontWeight: 300, lineHeight: 1.0, fontFamily: fontSans },
    slideTitle: { fontSize: 37,  fontWeight: 500, lineHeight: 1.2, fontFamily: fontSans },
    sub:        { fontSize: 44,  fontWeight: 400, lineHeight: 1.3, fontFamily: fontSans },
    body:       { fontSize: 26,  fontWeight: 400, lineHeight: 1.5, fontFamily: fontSans },
    eyebrow:    { fontSize: 18,  fontWeight: 500, lineHeight: 1.0, fontFamily: fontMono, textTransform: "uppercase", letterSpacing: "0.12em" },
    kpiValue:   { fontSize: 120, fontWeight: 300, lineHeight: 1.0, fontFamily: fontSans },
    kpiUnit:    { fontSize: 40,  fontWeight: 300, lineHeight: 1.0, fontFamily: fontSans },
    kpiKey:     { fontSize: 16,  fontWeight: 500, lineHeight: 1.0, fontFamily: fontMono, textTransform: "uppercase", letterSpacing: "0.12em" },
    colNum:     { fontSize: 14,  fontWeight: 500, lineHeight: 1.0, fontFamily: fontMono },
    colTitle:   { fontSize: 36,  fontWeight: 500, lineHeight: 1.2, fontFamily: fontSans },
    colBody:    { fontSize: 22,  fontWeight: 400, lineHeight: 1.5, fontFamily: fontSans },
    quote:      { fontSize: 84,  fontWeight: 300, lineHeight: 1.1, fontFamily: fontSans },
  },
  spacing: {
    paddingX: 100,     // left/right slide padding
    paddingYTop: 100,  // top padding
    paddingYBottom: 80 // bottom padding
  },
  canvas: {
    width: 1920,
    height: 1080,
  },
} as const;

export type FeinschliffTheme = typeof feinschliffTheme;
```

## Applying to a composition

```typescript
import { AbsoluteFill } from "remotion";
import { feinschliffTheme as T } from "./theme";

export const KpiScene: React.FC = () => (
  <AbsoluteFill
    style={{
      background: T.colors.white,
      paddingLeft:   T.spacing.paddingX,
      paddingRight:  T.spacing.paddingX,
      paddingTop:    T.spacing.paddingYTop,
      paddingBottom: T.spacing.paddingYBottom,
    }}
  >
    <div style={{ ...T.type.eyebrow, color: T.colors.black }}>KPI · Q1 2026</div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      <div style={{ ...T.type.kpiValue, color: T.colors.ink }}>62</div>
      <div style={{ ...T.type.kpiUnit,  color: T.colors.graphite }}>k</div>
    </div>
    <div style={{ ...T.type.kpiKey, color: T.colors.graphite }}>Metric label</div>
  </AbsoluteFill>
);
```

## Hard rules (match the PPTX template)

- **Accent is an accent, never a background for body text.** Use `ink` or `graphite`.
- **Eyebrow text is always mono + uppercase + 0.12em tracking.** The `eyebrow` preset bakes this in.
- **KPI values + units render as two runs** — value at `kpiValue` size, unit at `kpiUnit` size, baseline-aligned. Mirrors the PPTX KPI layout.
- **Line length:** max 60 characters for body, 8 words for titles. Empty space is intentional.

## Component patterns (TSX — not yet shipped)

The `.tsx` implementations of KPI card, slide frame, chip, and rule divider
are planned for a follow-up PR once a concrete remotion project needs
them. Until then, author compositions directly from the theme object above.
