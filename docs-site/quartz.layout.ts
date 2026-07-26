import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"

/**
 * Layout for agentic-toolkit's docs site. Copied over quartz's own
 * quartz.layout.ts at build time (see .github/workflows/docs.yml).
 *
 * Graph view is thematically load-bearing here (a knowledge-graph toolkit
 * documented as a knowledge graph), so both the per-page local graph and the
 * global graph it expands into are left on rather than trimmed for minimalism.
 */

// components shared across all pages
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  afterBody: [],
  footer: Component.Footer({
    links: {
      "agentic-toolkit on GitHub": "https://github.com/marsmike/agentic-toolkit",
      Quartz: "https://github.com/jackyzha0/quartz",
    },
  }),
}

// PARA folders keep their vault-schema names (00_Memory, 02_Projects, ...) on
// disk so contract/VAULT_SCHEMA.md and the folder-naming guide stay accurate,
// but the numeric prefix is just sort-order scaffolding — strip it for the
// Explorer's display labels only.
const stripNumericPrefix = (name: string) => name.replace(/^\d+_/, "")

// components for pages that display a single page (e.g. a single note)
export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => page.fileData.slug !== "index",
    }),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
        { Component: Component.ReaderMode() },
      ],
    }),
    Component.Explorer({
      folderDefaultState: "open",
      mapFn: (node) => {
        if (node.isFolder) {
          node.displayName = stripNumericPrefix(node.displayName)
        }
      },
    }),
  ],
  right: [
    Component.Graph({
      localGraph: {
        depth: 1,
      },
      globalGraph: {
        depth: -1,
        enableRadial: true,
      },
    }),
    Component.DesktopOnly(Component.TableOfContents()),
    Component.Backlinks(),
  ],
}

// components for pages that display lists of pages (e.g. tags or folders)
export const defaultListPageLayout: PageLayout = {
  beforeBody: [Component.Breadcrumbs(), Component.ArticleTitle(), Component.ContentMeta()],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
      ],
    }),
    Component.Explorer({
      folderDefaultState: "open",
      mapFn: (node) => {
        if (node.isFolder) {
          node.displayName = stripNumericPrefix(node.displayName)
        }
      },
    }),
  ],
  right: [],
}
