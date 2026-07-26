import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 configuration for agentic-toolkit's docs site.
 *
 * This file is copied over quartz's own quartz.config.ts at build time (see
 * .github/workflows/docs.yml) — it is NOT part of the vendored quartz checkout.
 * The vault (./vault) is copied into quartz's content/ directory and built
 * as-is: the vault IS the documentation, this config just skins it.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "agentic-toolkit",
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
    ignorePatterns: ["private", "templates", ".obsidian"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Schibsted Grotesk",
        body: "Source Sans Pro",
        code: "IBM Plex Mono",
      },
      colors: {
        lightMode: {
          light: "#faf8f8",
          lightgray: "#e5e5e5",
          gray: "#b8b8b8",
          darkgray: "#4e4e4e",
          dark: "#2b2b2b",
          secondary: "#284b63",
          tertiary: "#84a59d",
          highlight: "rgba(143, 159, 169, 0.15)",
          textHighlight: "#fff23688",
        },
        darkMode: {
          light: "#161618",
          lightgray: "#393639",
          gray: "#646464",
          darkgray: "#d4d4d4",
          dark: "#ebebec",
          secondary: "#7b97aa",
          tertiary: "#84a59d",
          highlight: "rgba(143, 159, 169, 0.15)",
          textHighlight: "#b3aa0288",
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
