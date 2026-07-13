---
kind: shape
name: accordion
family: landing
aliases: [FAQ list, expandable list, collapsible list]
status: stable
slots:
  - { name: items, required: true, accepts: [header, body] }
variants: [single-open, multi-open, first-item-open, all-closed]
self_contained: true
content_defaults: {}
---

# accordion — Accordion list

A vertical stack of collapsible rows; each item's header expands to reveal its body.

## Determinations

- Default behavior is multi-open (each item toggles independently) with all items closed at load. Item count is content-driven, 2 or more.
- Items are separated by a 1px hairline (`--border-subtle`) rather than card framing; the stack is capped at a `--column-medium` reading column inside the page-width section.
- Headers carry `aria-expanded` and `aria-controls` per `foundations/accessibility.md` §18.3, and the expand/collapse uses a max-height transition gated by reduced motion.

## Self-containment

Expand/collapse is Shape-level behavior, not provided by the generated component stylesheet or any shared script. The fragment carries its own scoped `<style>` and a scoped IIFE `<script>` that scopes itself to its own instance(s) so multiple accordions on one page never collide; it implements the `aria-expanded` toggling and keyboard contract per `foundations/accessibility.md`, with the max-height transition gated behind reduced motion and an instant-toggle fallback.
