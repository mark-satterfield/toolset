---
kind: component
name: marginalia-row
page_family: editorial
aliases: [marginalia row, marginalia, TOC row pattern]
status: stable
slots:
  - { name: left-rail, required: false, accepts: [italic-serif-toc] }
  - { name: icon, required: true, accepts: [icon] }
  - { name: content, required: true, accepts: [content-stack] }
sizing:
  row_gap: "64px (≥ tablet breakpoint); --sp-2-5 (32–40px clamp) below"
  row_padding_top: "32px"
  row_border_top: "1px"
  icon: "24px square"
  content_max_width: "35ch"
  rail_width: "grid-derived: the columns left of the reading column on the 12-column editorial grid; calibrates to 216px at the reference viewport"
behavior: [rail-active-selection]
accessibility: [aria-current-on-active-toc-entry]
token_bindings:
  - --border-subtle
  - --text-tertiary
  - --text-primary
shell_component: false
composite: false
---

# Marginalia row

An editorial row pattern with an icon, a content stack at 35ch, and an optional left-rail TOC. Static at rest.

## Determinations

- Row gap 64px. Each row: 32px top padding, 1px top border (`--border-subtle`).
- Header-row icon at 24px square; content at `max-width: 35ch`.
- The optional left rail carries an italic-serif TOC. Its width is grid-derived — the rail occupies the columns left of the reading column on the 12-column editorial grid, not a fixed width; calibrates to 216px at the reference viewport.

## Left-rail active selection

The rail TOC marks the entry whose row is currently scrolled into the viewport's upper third as active (driven by an `IntersectionObserver`, `foundations/motion.md` §15.4). The active entry carries `aria-current="true"` and paints at `--text-primary`; inactive entries sit at `--text-tertiary`.

## Responsive behavior

The left rail shows only at the tablet breakpoint and above (≥700px, `foundations/responsive.md` §17.1) where the 12-column grid is active; below 700px the rail is `display: none` and rows fall to a single column at full reading width. The row gap reduces from 64px to `--sp-2-5` (32–40px clamp) below the tablet breakpoint.
