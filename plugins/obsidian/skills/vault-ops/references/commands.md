# Optional: Obsidian Desktop CLI

Everything in `vault-ops` works via the filesystem with zero Obsidian process running.
This reference is for the optional enhancement path: if the user has Obsidian open with
*Settings → General → Advanced → Command line interface* enabled, its `obsidian` binary
adds a few conveniences (daily notes, live backlink queries, plugin dev tools) on top of
the same underlying files.

## The one hard trap — read this before using the CLI at all

**The CLI exits 0 and prints an error string on stdout when the interface is disabled**,
rather than failing:

```
Command line interface is not enabled. Please turn it on in Settings > General > Advanced.
```

Never trust the exit code. Probe once per session with a real read and check the output
against that string (and `not found`/`no such`/`cannot find`) before relying on any
further `obsidian` command — otherwise `obsidian read` "succeeds" while returning the
error string as note content, and `obsidian delete`/`property:set` silently no-op.
If it fails, fall back to the filesystem — that is not a degraded path, it's the default.

## Syntax

Parameters take a value with `=`; quote values with spaces. Flags are boolean switches:

```bash
obsidian read file="My Note"
obsidian create name="New Note" content="# Hello" silent
obsidian search query="search term" limit=10
obsidian daily:append content="- [ ] New task"
obsidian property:set name="status" value="active" file="My Note"
obsidian backlinks file="My Note"
```

Use `\n`/`\t` for multiline content. `file=<name>` resolves like a wikilink (no path or
extension needed); `path=<path>` is exact from the vault root. `vault=<name>` as the
first parameter targets a non-default vault. `--copy` copies output to the clipboard;
`silent` suppresses opening the file; `total` on list commands returns a count.

## Common patterns

```bash
# Create with properties
obsidian create name="Note Title" content="# Note Title\n\nBody." silent
obsidian property:set name="status" value="active" file="Note Title"
obsidian property:set name="tags" value="ai,learning" file="Note Title"

# Append to the daily note
obsidian daily:append content="- [[Note Title]]"

# Safe (trash-based) delete
obsidian delete file="Note Title"

# Tag-filtered search
obsidian search query="[tag:ai]" limit=20
```

## Plugin development

```bash
obsidian plugin:reload id=my-plugin
obsidian dev:errors
obsidian dev:screenshot path=screenshot.png
obsidian dev:console level=error
obsidian eval code="app.vault.getFiles().length"
```

Run `obsidian help` for the full command list, including CDP/debugger controls.
