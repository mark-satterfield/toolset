---
kind: shape
name: settings-form
page_family: app
aliases: [organization settings, settings page, two-column settings form]
status: stable
slots:
  - { name: page-header, required: true, accepts: [heading] }
  - { name: meta-row, required: true, accepts: [labelled-values] }
  - { name: field-groups, required: true, accepts: [text-input, select, label] }
  - { name: readonly-identifier, required: false, accepts: [identifier, copy-action] }
  - { name: destructive-zone, required: true, accepts: [destructive-button] }
  - { name: info-card, required: false, accepts: [icon, text, tertiary-cta] }
  - { name: toggle-rows, required: false, accepts: [title, helper-text, toggle-switch] }
variants: []
self_contained: false
content_defaults:
  page_title: "Organization"
  meta: [{ label: "Organization name", value: "Example Org" }, { label: "Members", value: "1" }]
  address: { line1: "123 Example St.", country: "Country", state: "State", city: "City", postal: "00000" }
  destructive_label: "Delete organization"
  info_card: "Collaborate with friends and teammates by setting up an organization"
  toggle_row: "Allow creating new projects in the default workspace"
---

# settings-form — Two-column field groups + destructive zone

A settings screen combining identification, editable fields, a bottom destructive action, and standalone preference toggles, in this vertical order:

1. Page heading (`<h1>`).
2. Top metadata row: labelled values rendered side by side, display-only (no inputs).
3. Address field group: a label + two-column input row (line 1 / line 2).
4. A four-column field row: `<select>` (country) + inputs (state, city, postal code).
5. Inline read-only identifier row (identifier text + a copy glyph).
6. Destructive action row: a destructive button on its own line, no other controls beside it.
7. Info card beneath the form: icon + one sentence + a right-aligned tertiary CTA.
8. Standalone toggle row: title + helper + a toggle-switch component on the right.

## HTML skeleton

```html
<header class="page-header"><h1>Organization</h1></header>
<dl class="settings-meta-row">
  <dt>Organization name</dt><dd>Example Org</dd>
  <dt>Members</dt><dd>1</dd>
</dl>
<section class="settings-field-group">
  <label>Primary business address</label>
  <div class="field-row field-row--2col">
    <input type="text" value="123 Example St.">
    <input type="text" placeholder="Line 2">
  </div>
  <div class="field-row field-row--4col">
    <label>Country <select>…</select></label>
    <label>State or province <input></label>
    <label>City <input></label>
    <label>Postal code <input></label>
  </div>
</section>
<div class="readonly-identifier-row">
  <span>Organization ID: 00000000-0000-0000-0000-000000000000</span>
  <button aria-label="copy">⧉</button>
</div>
<section class="destructive-zone">
  <button class="btn-destructive">Delete organization</button>
</section>
<aside class="info-card">
  <span class="info-card__icon">👥</span>
  <span class="info-card__text">Collaborate with friends and teammates by setting up an organization</span>
  <button class="btn-tertiary">Set up organization</button>
</aside>
<section class="toggle-row">
  <div>
    <h3>Allow creating new projects in the default workspace</h3>
    <p>Allow users to create new projects in the default workspace. Disabling this setting does not affect existing projects.</p>
  </div>
  <input type="checkbox" role="switch">
</section>
```

## Determinations

- Field-group width caps: the two-column row caps at `max-width: var(--column-field-measure)` (`foundations/layout.md` §11.2) — the same measure the `field-group-form` component (`libraries/components/`) declares for its 2-col row; the four-column row spans full width and wraps to two-up below the tablet breakpoint (`foundations/responsive.md` §17.1). Labels sit above their inputs (not beside) at every breakpoint.
- Save model: submit-button save. Edits stage locally and a "Save changes" primary button (disabled until a field is dirty) commits them; there is no save-on-blur. The destructive action and the field edits are two clearly separate commits.

Suits organization-level, profile-level, or workspace-level settings screens. Distinct from `setting-card-stack` — these are editable text fields, not standalone preference cards.
