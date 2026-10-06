# Rendered readability and verification

The owner reads every diagram as a rendered image. A diagram is finished only when its rendered
image is readable: **nothing overlaps anything else**. Mermaid source that parses is not finished;
it is a draft until its PNG has been looked at and found clean.

## The rule

In the rendered image:

- No box overlaps another box, boundary title or label.
- No label (node text, edge label, boundary title, note) overlaps another label, a box or a line.
- No line passes through a box it does not connect to.
- Every edge label sits unambiguously on its own edge.
- No text is clipped, truncated or too small to read at normal zoom.

## How to get there

Apply these in order; most diagrams are clean after the first three.

1. **Short edge labels.** An edge label is a few words: a verb or mechanism (`calls`,
   `publishes OrderPlaced`, `REST`, `reads`). Put the detail (payload, protocol, retry policy,
   condition) in a table or prose beside the diagram, keyed by the label or by a number on the
   edge (`1`, `2`, ...). In a sequence diagram use `autonumber` and key the table by step number.
2. **One question per diagram.** When many edges converge on one node (a table every service
   reads, an event bus everything publishes to), split the diagram: one view per flow or per
   consumer group, or draw the shared node once per subgraph. Link the split views to each other.
3. **Pick the direction that spreads edges.** `LR` for chains and pipelines, `TB` for
   hierarchies and layers. If the render is tall and thin with stacked labels, try the other
   direction. Inside a subgraph, `direction` can differ from the outer one, but
   Mermaid ignores it when a node in the subgraph links to a node outside it.
4. **Use the ELK layout when crowded.** ELK routes edges orthogonally and spaces labels better
   than dagre. Declare it at the top of the diagram:

   ```text
   %%{init: {"flowchart": {"defaultRenderer": "elk"}}}%%
   ```

   or, as Mermaid frontmatter, which also applies to other diagram kinds (`erDiagram`,
   `classDiagram`, `stateDiagram-v2`):

   ```text
   ---
   config:
     layout: elk
   ---
   ```

   Mermaid CLI 12 already lays flowcharts out with ELK by default; a renderer on an older Mermaid
   (as an Obsidian or GitHub build may be) uses dagre unless ELK is declared and available. When
   the reader's renderer may fall back to dagre, also render once with `layout: dagre` in the
   frontmatter and make sure that image is clean too.
5. **Order the source.** Layout follows declaration order. Declare nodes in reading order, group
   related nodes in a `subgraph`, and use an invisible link (`A ~~~ B`) to pull two nodes next to
   each other without drawing a line.
6. **Short node text.** Break long names with `<br/>` in flowchart labels; keep the technology
   tag on its own line. Never put a paragraph in a node.
7. **C4 kinds.** Mermaid's `C4Context` / `C4Container` / `C4Component` / `C4Deployment` place
   elements in a grid and often draw relationship labels on top of each other. Use
   `UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")` to change the grid and
   `UpdateRelStyle(from, to, $offsetX="-40", $offsetY="20")` to move a label off another. When
   the render still overlaps, draw the same C4 view as a `flowchart` with C4 notation (person,
   system, container and external shapes via `classDef`, `[Technology]` on the second line of
   each label, a legend). The C4 semantics, not the Mermaid kind, make it a C4 view.
8. **Split rather than shrink.** If a diagram is still crowded after the steps above, it shows
   too much. Split it by scope, flow or concern, and link the parts.

## Verification (required)

Render every Mermaid block you wrote or changed to PNG, look at each image, and fix until nothing
overlaps. Do this for every diagram, every time it changes.

1. **Render.** For a view file, render all its blocks at once into a scratch directory (never
   into the architecture folders; PNGs are verification evidence, not documentation):

   ```text
   bash <plugin>/skills/architecture-diagramming/scripts/render-check.sh <out-dir> <view.md> [more.md ...]
   ```

   The script runs the Mermaid CLI (`npx -y @mermaid-js/mermaid-cli`) on each file, writes
   `<out-dir>/<file>-<n>.png` for the n-th Mermaid block, prints every PNG path, and exits
   non-zero when a block fails to render. For a single `.mmd` file the direct command is:

   ```text
   npx -y @mermaid-js/mermaid-cli -i x.mmd -o x.png -s 2 -b white
   ```

2. **Look.** Open every PNG with the Read tool and inspect it against the rule above: boxes,
   labels and lines, one by one. A render error is a syntax failure; a clean exit says nothing
   about overlap.
3. **Fix and repeat.** Change the source with the techniques above, render again, look again.
   Repeat until the image is clean. If five passes do not get there, split the diagram.
4. **Report.** For each diagram, report separately: rendered (CLI exit 0), the PNG path you
   inspected, and the readability result (clean, or what still overlaps). If the CLI cannot run
   (no Node, no network for `npx`, the browser fails to start), say so; an unrendered or
   uninspected diagram is reported as unverified, never as passing.

Readability is one of three separate checks. The other two stay as they are: the source renders
(syntax), and the diagram shows exactly the design it was drawn from (semantics).
