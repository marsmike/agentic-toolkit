# JSON Canvas

Create and edit JSON Canvas files (.canvas) with nodes, edges, groups, and connections. Use when working with .canvas files, creating visual canvases, mind maps, flowcharts, or when the user mentions Canvas files in Obsidian.

## File Structure

A canvas file (`.canvas`) contains two top-level arrays following the [JSON Canvas Spec 1.0](https://jsoncanvas.org/spec/1.0/):

```json
{
  "nodes": [],
  "edges": []
}
```

## Common Workflows

### Create a New Canvas

1. Create a `.canvas` file with `{"nodes": [], "edges": []}`
2. Generate unique 16-character hex IDs for each node
3. Add nodes with required fields: `id`, `type`, `x`, `y`, `width`, `height`
4. Add edges referencing valid node IDs via `fromNode` and `toNode`
5. **Validate**: Parse JSON, verify all edge references resolve

### Add a Node

1. Read and parse the existing `.canvas` file
2. Generate a unique ID (no collisions)
3. Choose position avoiding overlaps (50-100px spacing)
4. Append node, optionally add edges
5. **Validate**: Confirm all IDs unique, all edge references valid

## Nodes

Array order determines z-index: first = bottom, last = top.

### Generic Attributes

| Attribute | Required | Type | Description |
|-----------|----------|------|-------------|
| `id` | Yes | string | Unique 16-char hex identifier |
| `type` | Yes | string | `text`, `file`, `link`, or `group` |
| `x` | Yes | integer | X position in pixels |
| `y` | Yes | integer | Y position in pixels |
| `width` | Yes | integer | Width in pixels |
| `height` | Yes | integer | Height in pixels |
| `color` | No | canvasColor | Preset `"1"`-`"6"` or hex |

### Text Nodes

```json
{
  "id": "6f0ad84f44ce9c17",
  "type": "text",
  "x": 0, "y": 0,
  "width": 400, "height": 200,
  "text": "# Hello World\n\nThis is **Markdown** content."
}
```

### File Nodes

```json
{
  "id": "a1b2c3d4e5f67890",
  "type": "file",
  "x": 500, "y": 0,
  "width": 400, "height": 300,
  "file": "Attachments/diagram.png"
}
```

Optional: `subpath` for heading/block links (starts with `#`).

### Link Nodes

```json
{
  "id": "c3d4e5f678901234",
  "type": "link",
  "x": 1000, "y": 0,
  "width": 400, "height": 200,
  "url": "https://obsidian.md"
}
```

### Group Nodes

Visual containers. Position child nodes inside the group's bounds.

Optional: `label`, `background` (path to image), `backgroundStyle` (`cover`, `ratio`, `repeat`).

## Edges

| Attribute | Required | Default | Description |
|-----------|----------|---------|-------------|
| `id` | Yes | - | Unique identifier |
| `fromNode` | Yes | - | Source node ID |
| `fromSide` | No | - | `top`, `right`, `bottom`, `left` |
| `fromEnd` | No | `none` | `none` or `arrow` |
| `toNode` | Yes | - | Target node ID |
| `toSide` | No | - | `top`, `right`, `bottom`, `left` |
| `toEnd` | No | `arrow` | `none` or `arrow` |
| `color` | No | - | Line color |
| `label` | No | - | Text label |

## Colors

| Preset | Color |
|--------|-------|
| `"1"` | Red |
| `"2"` | Orange |
| `"3"` | Yellow |
| `"4"` | Green |
| `"5"` | Cyan |
| `"6"` | Purple |

## Layout Guidelines

- Coordinates can be negative (canvas extends infinitely)
- `x` increases right, `y` increases down; position is top-left corner
- Space nodes 50-100px apart; 20-50px padding inside groups
- Align to grid (multiples of 10 or 20)

| Node Type | Width | Height |
|-----------|-------|--------|
| Small text | 200-300 | 80-150 |
| Medium text | 300-450 | 150-300 |
| Large text | 400-600 | 300-500 |
| File preview | 300-500 | 200-400 |
| Link preview | 250-400 | 100-200 |

## Validation Checklist

1. All `id` values unique across nodes and edges
2. Every `fromNode`/`toNode` references existing node ID
3. Required fields present per node type
4. `type` is `text`, `file`, `link`, or `group`
5. Side values are `top`, `right`, `bottom`, `left`
6. End values are `none` or `arrow`
7. Colors are `"1"`-`"6"` or valid hex
8. JSON is valid and parseable

## References

- [JSON Canvas Spec 1.0](https://jsoncanvas.org/spec/1.0/)
- [JSON Canvas GitHub](https://github.com/obsidianmd/jsoncanvas)
