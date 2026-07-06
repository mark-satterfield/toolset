---
kind: component
name: pricing-card
family: landing
aliases: [pricing card, tier card, plan card]
status: stable
slots:
  - { name: title, required: true, accepts: [heading] }
  - { name: feature-list, required: true, accepts: [list] }
  - { name: cta, required: false, accepts: [button] }
sizing:
  padding: "24px"
  feature_list_divider: "1px top border with 24px top padding"
behavior: []
accessibility: []
token_bindings:
  - --surface-raised
  - --border-subtle
  - --border-strong
shell_furniture: false
composite: false
---

# Pricing card

A tier card with a title, a feature list, and (typically) a CTA at the bottom. Static at rest.

## Determinations

- 24px padding. The feature list is separated by a 1px top border with 24px top padding.

## Tier variants

- `default` — `--surface-raised` ground with a `1px solid --border-subtle` hairline.
- `featured` — paints a `1px solid --border-strong` outline plus the `foundations/layout.md` §11.8 "faint elevation" shadow, lifting the emphasized tier one step above its peers; the rest of the geometry is unchanged so tiers align in a row.

## CTA slot

The bottom CTA is a primary button (`libraries/components/button.md`) on the `featured` tier and a secondary button on `default` tiers, so the emphasized tier carries the dominant action.
