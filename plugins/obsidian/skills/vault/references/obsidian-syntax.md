# Obsidian syntax, the parts that differ from plain Markdown

**Links and embeds.** `[[Note]]`, `[[path/Note|Shown text]]`, `[[Note#Heading]]`,
`[[Note#^block-id]]` (define with ` ^block-id` at a paragraph's end). A link resolves by file
name, so prefer the vault-relative path when names repeat. `!` embeds: `![[Note]]`,
`![[Note#Heading]]`, `![[image.png|300]]`, `![[file.pdf#page=3]]`, `![[View.base#View name]]`.

**Callouts.** `> [!note] Title` then `> ` lines; types include note, info, tip, success,
warning, danger, abstract, quote. `> [!tip]-` starts folded, `+` starts open.

**Properties** (frontmatter). YAML between `---` lines at the very top. Lists as YAML lists;
`tags` without `#`; `aliases` for alternative names; `cssclasses` for per-note CSS. Nested
objects are valid YAML but Obsidian's editor shows them poorly.

**Tags** `#tag` or `#domain/value` in the body; the same values in `tags:` without `#`.

**Tasks** `- [ ]` / `- [x]`. **Comments** `%% hidden %%`. **Highlight** `==text==`. **Math**
`$x$`, `$$…$$`. **Footnotes** `[^1]` … `[^1]: text`.

**Canvas** (`.canvas`, JSON Canvas 1.0): `{"nodes": [...], "edges": [...]}`. Every node has
`id` (unique, 16 hex chars by convention), `type`, `x`, `y`, `width`, `height`. Types:
`text` (`text`), `file` (`file`: vault path with extension, optional `subpath`), `link` (`url`),
`group` (`label`). Edges: `id`, `fromNode`, `toNode`, optional `fromSide`/`toSide`
(top/right/bottom/left) and `label`. Array order is z-order. After writing, check every edge
references an existing node id and every file node an existing file.

**Bases** (`.base`, YAML): top-level `filters`, `formulas`, `properties` (display names),
`views`. A view: `type` (table, cards, list), `name`, optional `filters`, `order` (columns),
`sort` (`property`, `direction`), `groupBy`, `limit`. Filters are expressions combined with
`and:`/`or:`/`not:` lists:

```yaml
filters:
  and:
    - file.inFolder("04_Resources")
    - note.status == "distilled"
    - '!file.inFolder("05_Archive")'
formulas:
  domain: 'tags.filter(value.startsWith("domain/")).join(", ")'
```

`file.*` are file facts (name, folder, ext, ctime, mtime, tags, links); `note.*` or a bare name
is a frontmatter property; `formula.*` a formula. Quote an expression that starts with `!`.

**The Obsidian desktop CLI** (optional; everything above works with no Obsidian running). With
Settings → General → Advanced → Command line interface on, `obsidian read file="Note"`,
`obsidian search query="…" limit=10`, `obsidian backlinks file="Note"`,
`obsidian property:set name=status value=active file="Note"`, `obsidian daily:append content="…"`.
**Trap: when the interface is off it exits 0 and prints an error string to stdout.** Never trust
the exit code; check the output for "Command line interface is not enabled" (or "not found")
before using a result, and fall back to the files.
