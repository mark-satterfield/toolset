---
kind: component
name: outline-pill-badge
aliases: [badge, pill, tag, outline badge, label badge]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
sizing:
  padding: "0.5rem 0.75rem"
  type: "12px caption"
behavior: []
accessibility: [static-span-default, interactive-wrap-option]
token_bindings:
  - --border-subtle
  - --surface-secondary
  - --text-tertiary
  - --border-strong
  - --focus-ring
composite: false
---

# Outline pill badge

A lightweight tag with a hairline border, used for categorical or meta labels: a pill with border + body label. Static at rest.

## Determinations

- `0.5rem 0.75rem` padding, sentence-case label, 12px caption type. No uppercase.

## Interactive vs static

- The default badge is a non-interactive `<span>` — it labels content, it doesn't act.
- When the host needs the badge to behave as a filter chip or removable tag, wrap or replace the `<span>` with a `<button>` (or `<a>` if it navigates); apply the foundation focus ring on `:focus-visible` and hover-darken the border one role-step toward `--border-strong`.
