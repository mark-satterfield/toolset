---
name: visualize-okf-bundle
description: >-
  Render an OKF bundle as a single self-contained, interactive HTML graph
  viewer — nodes are concepts colored by type, edges are cross-links, with
  search, a type filter, per-node detail, rendered body, and backlinks. Use
  when the user wants to see, view, visualize, explore, or get a graph/map of
  an OKF bundle.
allowed-tools: [Read, Bash, Glob]
---

# Visualize an OKF bundle

Generate one self-contained `viz.html` (Cytoscape + marked + DOMPurify inlined;
no network) that renders the bundle as an interactive concept graph.

## Steps

1. **Ensure PyYAML** is available:
   `python3 -c "import yaml" 2>/dev/null || uv pip install pyyaml || pip install pyyaml`
2. **Generate:**
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/okf_tools/viewer.py <bundle> [--out <path>] [--name <display name>]`
   (default output: `<bundle>/viz.html`).
3. **Report** the concept count, edge count, and output path from the
   generator's summary line; offer to open the file.

## What it renders

- **Nodes** — one per concept, colored by `type` (palette auto-assigned per
  distinct type), sized by body length.
- **Edges** — one directed edge per bundle-relative markdown link between
  concepts (`/path.md` preferred, `./sibling.md` also resolved).
- **Detail panel** — frontmatter (description, resource, tags), the rendered
  concept body, and a "Cited by" backlinks list.
- **Controls** — search (title / id / tag), type filter, layout switch
  (force / concentric / breadth-first / circle / grid).

## Notes

- Reserved files (`index.md`, `log.md`) are excluded — they are not concepts.
- The body is rendered as markdown and **sanitized with DOMPurify**, so the
  viewer is safe even for bundles built from ingested web/PDF content.
- A file whose frontmatter fails to parse as YAML is skipped, not rendered.
- The output is a static file: regenerate it after the bundle changes.
