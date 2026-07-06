---
kind: shape
name: comparison-fork
family: landing
aliases: [comparison columns, attribute fork, side-by-side path compare]
status: stable
slots:
  - { name: path-columns, required: true, accepts: [headline, attribute-list, cta] }
variants: [cta-foot, cta-head]
self_contained: false
content_defaults: {}
---

# comparison-fork — Attribute-comparison fork

Two columns representing exclusive paths, each a headline over a vertical list of contrasted attributes with its own CTA, aligned so attributes read across.

## Determinations

- Count is fixed at exactly two columns, a 50/50 split on the 12-column grid (each spans 6); the grid gutter (`foundations/layout.md` §11.6) separates them.
- Each column stacks a headline, then a vertical list of attribute rows, then a CTA. The two columns share a row grid so the nth attribute of each path sits on the same row baseline, letting the paths contrast attribute by attribute.
- Attribute rows within a column render in the order the content supplies them (no automatic re-sort), each separated from the next by a 1px hairline (`--border-subtle`) at the card-hairline weight (`foundations/layout.md` §11.9).
- The columns sit in the left register; headings and attribute rows align to the reading axis of their content.
- The `cta-foot` variant anchors each column's CTA below its attribute list; the `cta-head` variant places it directly under the headline, above the attributes.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the columns stack to a single column in source order — the first-listed path on top — and the shared row grid releases, each path reading as a self-contained block.
