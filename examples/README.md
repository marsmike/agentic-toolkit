# Examples

Real-world usage examples for plugins in `agentic-toolkit`.

Each subdirectory pairs an **input** (a brief, a DESIGN.md, a screenshot) with the **output** the plugin produced (a `.pptx`, a rendered PNG, a generated layout). Use these as starting points for your own work.

## feinschliff

| Example | What's inside | Plugin command |
|---|---|---|
| [`feinschliff/template-preview/`](feinschliff/template-preview/) | Pre-built `.pptx` for the eponymous Feinschliff brand (gold + navy, Bauhaus) | `build.py` |
| [`feinschliff/template-preview-claude/`](feinschliff/template-preview-claude/) | Pre-built `.pptx` for the Claude brand (coral + cream, editorial serif) | `build.py` |
| [`feinschliff/brief-to-deck/`](feinschliff/brief-to-deck/) | One-paragraph brief → 8-slide branded deck | `/deck "..."` |
| [`feinschliff/design-md-to-tokens/`](feinschliff/design-md-to-tokens/) | A DESIGN.md + the brand pack it expanded into (v0.2 preview) | `/compile` |

*More examples land alongside future plugins.*

## Contributing examples

Examples are PR-friendly — open one with:

1. A new subdirectory under the relevant plugin (`feinschliff/`, etc.)
2. A short `README.md` explaining what's demonstrated
3. The input (brief / DESIGN.md / screenshot) committed
4. The output the plugin produced (`.pptx`, PNG, etc.) committed if useful for visual reference

Match the existing format. Keep examples small, self-contained, and shippable as MIT (no real customer logos or trademarked brands beyond what NOTICE already covers).
