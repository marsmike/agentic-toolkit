---
name: extend
description: Add a new layout to the active brand's catalog from a screenshot, brief, HTML, or existing .pptx. In v2 this is a thin wrapper over /compile — invoke /compile directly with the appropriate --from-* flag.
---

# extend — superseded by /compile

`/extend`'s v1 contract was "regenerate one component + one layout from a
screenshot, append to build.py's demo deck". After PR-2 there is no
`build.py`, no `components/`, no `layouts/` — templates are the unit, and
`/compile` is the per-template authoring path.

For the four `/extend` use cases that v1 supported, the v2 equivalents are:

| v1 invocation                          | v2 invocation                                        |
|----------------------------------------|------------------------------------------------------|
| `/extend ./shot.png`                   | `/compile --from-screenshot ./shot.png --renderer pptx --id <new-id>` |
| `/extend ./brief.md`                   | `/compile --from-brief ./brief.md --renderer pptx --id <new-id>` |
| `/extend ./design.html`                | `/compile --from-html ./design.html --renderer pptx --id <new-id>` |
| `/extend ./adopted.pptx`               | `/compile --from-pptx ./adopted.pptx --renderer pptx --id <new-id>` |

See [`../compile/SKILL.md`](../compile/SKILL.md) for the per-template authoring
flow and visual-verification contract.

If you have a brand-pack-extension scenario `/compile` does not cover (e.g.
authoring multiple related layouts in one shot, or extending the brand's
master/theme rather than adding a layout), open an issue rather than reaching
for the deprecated v1 `/extend` body.
