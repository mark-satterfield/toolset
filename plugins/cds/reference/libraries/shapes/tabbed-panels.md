---
kind: shape
name: tabbed-panels
family: landing
aliases: [tabs, tabbed showcase, feature tabs]
status: stable
slots:
  - { name: tab-strip, required: true, accepts: [tab-label] }
  - { name: panels, required: true, accepts: [visual, copy] }
variants: [visual-only-panels, visual-plus-text-panels]
self_contained: true
content_defaults: {}
---

# tabbed-panels — Tabs with one panel per tab

A horizontal tab strip above a single full-width panel that swaps on selection; each tab gets a full visual plus accompanying copy.

## Determinations

- Tabs are top-oriented and horizontal. Tab count is 2–5; beyond 5 the strip becomes a horizontal scroll row rather than wrapping.
- The first tab is selected by default. The strip uses the Pill-tab strip component from the components library (`role="tablist"` + `role="tab"` + `aria-selected` + `aria-controls`), with each panel as `role="tabpanel"`.
- Panel swaps use the standard cross-fade; under `prefers-reduced-motion: reduce` the swap is instant.

## Self-containment

Tab switching is shape-level behavior, not a component-family style, so the generated component stylesheet does not provide it. The fragment carries its own scoped `<style>` and a scoped `<script>` written as an IIFE that scopes itself to its own instance(s) so multiple copies on one page never collide. The script implements the tablist keyboard contract (arrow-key navigation, `aria-selected` management) per `foundations/accessibility.md`; the cross-fade is gated by reduced motion with an instant-swap fallback.
