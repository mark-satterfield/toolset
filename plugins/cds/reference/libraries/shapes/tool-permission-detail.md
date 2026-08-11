---
kind: shape
name: tool-permission-detail
aliases: [connector permissions, integration permission editor, scope editor]
status: stable
slots:
  - { name: header, required: true, accepts: [logo, name, disconnect-action, kebab-menu] }
  - { name: description, required: true, accepts: [paragraph] }
  - { name: permission-groups, required: true, accepts: [group-label, count-badge, default-policy-chip, tool-rows] }
variants: []
self_contained: false
content_defaults:
  groups:
    - { label: "Read-only tools", count: 8, default_policy: "Always allow" }
    - { label: "Write/delete tools", count: 9, default_policy: "Needs approval" }
---

# tool-permission-detail — Read/write groups with per-row policy controls

An integration/connector permission editor filling the vacant space — it suits an application Shell with a rail and list Sections: a connector header — logo + name on the left, a "Disconnect" link and a kebab menu (View details / Refresh tools list / Remove) on the right — a 1–3-sentence description, a "Tool permissions" subhead with a one-line helper, then collapsible permission groups. Each group carries a label, a count badge, and a right-aligned default-policy chip; its rows each carry a one-line tool description on the left and three per-row policy controls on the right (allow / approve / deny glyph buttons).

## HTML skeleton

```html
<header class="connector-detail__header">
  <div class="connector-detail__brand">
    <img class="connector-detail__logo" alt="">
    <h1>Connector name</h1>
  </div>
  <div class="connector-detail__actions">
    <button class="link">Disconnect</button>
    <button class="kebab" aria-label="more">⋮</button>
  </div>
</header>
<p class="connector-detail__description">Connect your account to the integration to quickly access its data…</p>
<section class="tool-permissions">
  <h2>Tool permissions</h2>
  <p>Choose when the integration is allowed to use these tools.</p>
  <details class="tool-group" open>
    <summary>
      <span>Read-only tools <span class="count-badge">8</span></span>
      <button class="default-policy-chip">⊘ Always allow ▾</button>
    </summary>
    <ul>
      <li class="tool-row">
        <p>Retrieves a specific record from the connected account.</p>
        <div class="tool-row__controls">
          <button aria-label="allow">⊘</button>
          <button aria-label="approve each call">⊕</button>
          <button aria-label="deny">⊗</button>
        </div>
      </li>
    </ul>
  </details>
  <details class="tool-group" open>
    <summary>
      <span>Write/delete tools <span class="count-badge">9</span></span>
      <button class="default-policy-chip">👁 Needs approval ▾</button>
    </summary>
    <ul>…</ul>
  </details>
</section>
```

## Determinations

- Per-row policy glyphs: the three controls form a `role="radiogroup"` with one selected at a time — allow (the call runs without prompting), approve (the call prompts for approval each time), and deny (the call is blocked). Each carries an explicit `aria-label` ("allow", "approve each call", "deny") and `aria-checked`; the selected glyph paints filled, the others outline.
- Default-policy chip: a dropdown trigger (`aria-haspopup="menu"`, `aria-expanded`) opening a single-select menu (Always allow / Needs approval / Never allow). Choosing a value sets the group default and updates every row that still inherits the default; rows with an explicit override keep their override.

Suits integration/connector permission screens, OAuth scope editors, and RBAC tool-permission editors — any surface where capabilities group by default policy and each row carries a per-item override.
