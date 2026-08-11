---
kind: shape
name: tabbed-panels
aliases: [tabs, tabbed showcase, feature tabs]
status: stable
slots:
  - { name: tab-strip, required: true, accepts: [tab-label] }
  - { name: panels, required: true, accepts: [visual, copy] }
  - { name: panel-caption, required: false, accepts: [heading, text] }
variants: [visual-only-panels, visual-plus-text-panels, caption-inside-panel, caption-below-split]
self_contained: true
content_defaults: {}
---

# tabbed-panels — Tabs with one panel per tab

A horizontal tab strip above a single full-width panel that swaps on selection; each tab gets a full visual plus accompanying copy.

## Determinations

- Tabs are top-oriented and horizontal. Tab count is 2–5; beyond 5 the strip becomes a horizontal scroll row rather than wrapping.
- The first tab is selected by default. The strip uses the Pill-tab strip component from the components library (`role="tablist"` + `role="tab"` + `aria-selected` + `aria-controls`), with each panel as `role="tabpanel"`.
- A tab label may carry a leading glyph before its text. Either every tab carries one or none does, so the labels sit at one inline offset across the strip.
- Caption placement: `caption-inside-panel` sets the copy within the panel beside or beneath its visual. `caption-below-split` sets the panel as a tinted full-width plate holding the visual alone, with the caption beneath it as a two-column split — the panel's heading in the start columns, its description in the end columns — collapsing to one column below the tablet breakpoint (`foundations/responsive.md` §17.1). The caption swaps with its panel, so heading and visual always describe the same tab.
- The panel plate holds one height across every tab, sized to the tallest visual, so selecting a tab never reflows the page beneath it.
- Panel swaps use the standard cross-fade; under `prefers-reduced-motion: reduce` the swap is instant.

## Self-containment

Tab switching is Shape-level behavior, not a component-family style, so the generated component stylesheet does not provide it. The fragment carries its own scoped `<style>` and a scoped `<script>` written as an IIFE that scopes itself to its own instance(s) so multiple copies on one page never collide. The script implements the tablist keyboard contract (arrow-key navigation, `aria-selected` management) per `foundations/accessibility.md`; the cross-fade is gated by reduced motion with an instant-swap fallback.
