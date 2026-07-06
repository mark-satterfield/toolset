---
kind: shape
name: setting-card-stack
family: app
aliases: [stacked setting cards, preference cards, privacy settings stack]
status: stable
slots:
  - { name: cards, required: true, accepts: [title, pill, body-paragraphs, toggle-switch, button, value-with-link, destructive-sub-row] }
variants: []
self_contained: false
content_defaults:
  cards:
    - { title: "Data retention period", control: "read-only value + link action" }
    - { title: "Allow user feedback", control: "toggle" }
    - { title: "Join our Development Partner Program", pill: "NEW", control: "primary button" }
    - { title: "Allow product metrics logging", control: "toggle + destructive sub-row" }
---

# setting-card-stack — Stacked setting cards with toggles + inline destructive rows

A vertical stack of setting cards, each carrying a section title (with an optional "NEW" pill), a 1–2-paragraph explanation (inline links allowed), and one or more controls: a toggle-switch component, a button, or a read-only value with a link action. Destructive actions live **inside** the cards they belong to as an inline sub-row (explanatory sentence + destructive button), not in a separate zone at the bottom.

Each card is full-width of the main pane. Cards are visually separated by spacing, not dividers.

## HTML skeleton

```html
<article class="setting-card">
  <h2>Data retention period</h2>
  <p>The data retention period only applies to inputs and outputs sent via the host API…</p>
  <div class="setting-card__control-row">
    <span>30 day retention period</span>
    <a class="link">Contact support ›</a>
  </div>
</article>
<article class="setting-card">
  <header>
    <h2>Allow product metrics logging</h2>
    <input type="checkbox" role="switch" class="setting-card__toggle" checked>
  </header>
  <p>Enable metrics collection to track product usage…</p>
  <div class="setting-card__destructive-sub-row">
    <span>Delete all collected metrics data. This action cannot be undone.</span>
    <button class="btn-destructive">Delete data</button>
  </div>
</article>
```

## Determinations

- Card treatment: a hairline border (1px alpha-thinned `--border-subtle`, `foundations/layout.md` §11.9) on the page surface — no tint, no shadow — at radius `--radius-xl`, with `--sp-2` inner padding. The hairline does the figure/ground work per `foundations/layout.md` §11.8.
- Toggle alignment: the toggle pins to the top-right of the card, vertically aligned with the card title (grid `[1fr_auto]`), so the control sits in a consistent position across all cards regardless of body length.

Suits privacy, security, and feature-flag screens where each setting is independently scoped and needs its own explanation.
