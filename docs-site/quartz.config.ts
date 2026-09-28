import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 configuration for agentic-toolkit's docs site.
 *
 * This file is copied over quartz's own quartz.config.ts at build time (see
 * .github/workflows/docs.yml) — it is NOT part of the vendored quartz checkout.
 * The vault (./vault) is copied into quartz's content/ directory and built
 * as-is: the vault IS the documentation, this config just skins it.
 *
 * Theme: docs/BRAND.md's palette and typography (see that file for the full
 * rationale, the "decent Hamilton homage" rules, and the one attribution
 * line). Every color below is a brand token, not a new choice — the mapping
 * from Quartz's nine color slots to the brand's tokens, and the measured
 * contrast ratio for every text pairing, are recorded next to each value.
 * Names are a nod to Peter F. Hamilton's Commonwealth novels; this project is
 * not affiliated with him or his publishers.
 *
 * Link color: the two candidates were the Guides group teal (`#0c8a7d`/`#2fd4c0`) and the
 * `wormhole` gradient (`#6b46c1`->`#a81f57` light, `#9b87ff`->`#ff7ab6` dark). Teal fails AA
 * on the light background (3.93:1, need 4.5:1); wormhole clears AA on both backgrounds in
 * both modes, and BRAND.md's own glossary already names a link "a wormhole" — so links use
 * the wormhole gradient's two stops (violet for the link color, magenta for hover/visited),
 * not teal.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "unisphere · agentic-toolkit",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    // No analytics account exists for this project; disabling avoids a
    // config that silently points at someone else's dashboard.
    analytics: null,
    locale: "en-US",
    // GitHub Pages project site (not a custom domain): the URL is the
    // repo owner's pages domain plus the repo name as a path prefix.
    baseUrl: "marsmike.github.io/agentic-toolkit",
    // 00_Memory (agent self-memory) and 01_Capture (inbox) are excluded from
    // the content copy itself in docs.yml, not just ignored here — this list
    // only needs to cover things that DO land in content/ but shouldn't be
    // built as pages (Obsidian's own config folder, if ever present).
    ignorePatterns: ["private", "Templates", ".obsidian"],
    defaultDateType: "modified",
    theme: {
      // BRAND.md: "No web fonts in shipped SVGs ... system stacks only" — that rule was
      // scoped to images GitHub rasterizes, but the reasoning (match the explainer video
      // and cheat sheet, which both use `-apple-system, "SF Pro Display", ...` / mono
      // system stacks, never a Google Fonts family) applies here too: the docs site should
      // read as the same brand as those images, not gain a fourth, unrelated typeface set.
      // "local" skips Quartz's Google Fonts fetch/`<link rel=preconnect>` entirely for the
      // site itself; the real multi-font stacks (a single name here is just the local
      // fallback if custom.scss ever fails to load) are set as `!important` on the
      // generated `--headerFont`/`--bodyFont`/`--codeFont` custom properties in
      // custom.scss, which is required because Quartz's own generated `:root`
      // font-variable block is emitted *after* custom.scss in the same stylesheet (see
      // quartz/util/theme.ts `joinStyles`), so a same-specificity override would
      // otherwise lose the cascade.
      //
      // header/body stay a real Google Fonts name ("Inter", visually the closest thing on
      // Google Fonts to San Francisco/system-ui) rather than "-apple-system", for one
      // narrow reason unrelated to site CSS: `Plugin.CustomOgImages()` below (unchanged,
      // part of the existing plugin list) rasterizes each page's social-preview image with
      // satori, which always fetches `theme.typography.header`/`body` from Google Fonts by
      // name to do that — regardless of `fontOrigin` — and errors the whole build
      // ("No fonts are loaded") on a non-Google name like "-apple-system". This value is
      // therefore only visible in the auto-generated per-page OG/social-card image, never
      // on the site itself, which custom.scss pins to the system stack unconditionally.
      fontOrigin: "local",
      cdnCaching: true,
      typography: {
        header: "Inter",
        body: "Inter",
        code: "ui-monospace",
      },
      // Token mapping (brand token -> Quartz slot), both modes, with the WCAG contrast
      // ratio computed for every text pairing (formula: relative luminance, (L1+0.05)/
      // (L2+0.05); AA threshold for body text is 4.5:1). `lightgray`/`gray` are borders and
      // graph-link strokes, not text, so — like `accent` and the group colors in
      // BRAND.md's own palette table — they're picked for clarity against the background
      // rather than held to the text ratio.
      colors: {
        lightMode: {
          light: "#f5f6fb", // brand `bg` — page background
          lightgray: "#e9ebf7", // brand `bg2` — raised surface, used for subtle borders
          gray: "#c7cbea", // brand `line` — structural lines: graph links, heavier borders
          darkgray: "#4b5178", // brand `dim` — body text; dim vs bg = 7.08:1 (AA pass)
          dark: "#141833", // brand `ink` — header text & icons; ink vs bg = 16.10:1 (AA pass)
          secondary: "#6b46c1", // brand `wormhole1` — links = wormholes; vs bg = 5.95:1 (AA pass)
          tertiary: "#a81f57", // brand `wormhole2` — hover/visited; vs bg = 6.49:1 (AA pass)
          highlight: "rgba(107, 70, 193, 0.15)", // faint wormhole1 tint (internal-link bg)
          textHighlight: "#d9820a33", // faint `accent` tint (~20% alpha); dim-on-it = 5.85:1
        },
        darkMode: {
          light: "#0a0e1c", // brand `bg`
          lightgray: "#141a33", // brand `bg2`
          gray: "#3c4270", // brand `line`
          darkgray: "#8d94b8", // brand `dim`; dim vs bg = 6.46:1 (AA pass)
          dark: "#eef1ff", // brand `ink`; ink vs bg = 17.08:1 (AA pass)
          secondary: "#9b87ff", // brand `wormhole1`; vs bg = 6.69:1 (AA pass)
          tertiary: "#ff7ab6", // brand `wormhole2`; vs bg = 7.97:1 (AA pass)
          highlight: "rgba(155, 135, 255, 0.15)", // faint wormhole1 tint
          textHighlight: "#ffcf5c26", // faint `accent` tint (~15% alpha); dim-on-it = 4.73:1
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      // No "git" priority: the workflow rsyncs vault/ into a fresh quartz
      // checkout rather than committing it there, so every file is
      // permanently untracked from git's point of view and this plugin
      // would warn on (and misdate) every single page. Vault notes carry
      // their own `created` frontmatter; `modified` falls back to
      // filesystem mtime (effectively "last built"), which is honest given
      // the real edit history lives in the agentic-toolkit repo, not here.
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      // "shortest" mirrors how Obsidian itself resolves wikilinks (by
      // basename, not full path) — required for the vault's wikilinks to
      // resolve without every link needing a full relative path.
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      Plugin.CustomOgImages(),
    ],
  },
}

export default config
