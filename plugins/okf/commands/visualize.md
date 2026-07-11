---
description: Render an OKF bundle as a single self-contained, interactive HTML graph viewer — offline, no CDN. Nodes are concepts colored by type; edges are cross-links.
argument-hint: "[bundle dir] [optional output html path]"
allowed-tools: Read, Bash, Glob
---

# /okf:visualize

Invoke the `visualize-okf-bundle` skill to render a bundle as an interactive
concept graph.

## Process

1. Resolve `$ARGUMENTS` — first token is the bundle directory (default: current
   directory), second (optional) is the output HTML path (default:
   `<bundle>/viz.html`). If the bundle path is missing, ask for it.
2. Load and execute
   `${CLAUDE_PLUGIN_ROOT}/skills/visualize-okf-bundle/SKILL.md`.
3. Run the generator and report the concept count, edge count, and output path;
   offer to open the file.

## Notes

- Output is one self-contained HTML file — Cytoscape, marked, and DOMPurify are
  inlined, so it works offline with no CDN and is safe to open or share.
- Requires Python 3 with PyYAML.
