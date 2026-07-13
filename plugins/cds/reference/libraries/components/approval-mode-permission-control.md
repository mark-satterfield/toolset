---
kind: component
name: approval-mode-permission-control
family: app
aliases: [tool permissions, permission editor, policy control, approval-mode control]
status: stable
slots:
  - { name: group, required: true, accepts: [details] }
  - { name: group-summary, required: true, accepts: [label, count-badge, default-policy-chip] }
  - { name: tool-row, required: true, accepts: [description, segment-control] }
sizing:
  group-summary-row: "list-row density token, comfortable"
  tool-row: "list-row density token, standard"
behavior:
  - "group state: expanded (default) | collapsed"
  - "row state: inherits-default | overridden-allow | overridden-approve | overridden-deny"
accessibility:
  - "per-row controls: role=radiogroup with labelled role=radio glyph buttons"
  - "group collapse via <summary> (aria-expanded, aria-controls)"
token_bindings: [--text-primary, --text-tertiary, --surface-tertiary]
shell_component: false
composite: true
---

# Approval-mode permission control

A two-level permission editor where each group has a default policy (Always allow / Needs approval / Never allow) and each row inside the group can override the group's policy via per-row glyph buttons (allow / approve / deny). The canonical instance is a connector with a Read-only tools group ("Always allow" default, 8 tools) and a Write/delete tools group ("Needs approval" default, 9 tools), each row carrying per-row policy glyph buttons. The composition assembles collapsible groups around segment-control Components.

## Component references

Segment control (`libraries/components/pill-tab-strip.md` in radiogroup mode — the three Read / Write / Don't allow segments are one instance), count-badge primitive (`libraries/components/inverted-pill-badge.md`), filter chip / dropdown trigger (`libraries/components/filter-chip.md`) for the default-policy chip.

## Slots

- `group` (repeating): a collapsible section (`<details>`).
- `group-summary` (required per group): group label + count badge + right-aligned default-policy chip.
- `tool-row` (repeating per group): tool description + per-row segment-control instance for policy override.

State props per group: `expanded` (default) | `collapsed`. Per row: `inherits-default` | `overridden-allow` | `overridden-approve` | `overridden-deny`.

## Sizing

- Group summary row height: the list-row density token at its comfortable step (calibrates to 44px).
- Tool row height: the list-row density token at its standard step (calibrates to 40px).
- The per-row segment control sits at the right edge of the row, three small icon buttons in a row.
- The count badge is a small pill containing a digit (e.g., "8", "9").
- The default-policy chip is a pill-shaped picker (the filter-chip geometry).

## Structural skeleton

```html
<details class="tool-permissions__group" open>
  <summary class="tool-permissions__summary">
    <span class="tool-permissions__group-label">Read-only tools</span>
    <span class="count-badge">8</span>
    <button class="default-policy-chip" aria-haspopup="menu" aria-expanded="false">
      <span aria-hidden="true">⊘</span> Always allow <span aria-hidden="true">▾</span>
    </button>
  </summary>
  <ul class="tool-permissions__rows">
    <li class="tool-row">
      <p class="tool-row__description">Retrieves a specific record from the connected account.</p>
      <div class="tool-row__controls" role="radiogroup" aria-label="policy">
        <button role="radio" aria-checked="true" aria-label="allow">⊘</button>
        <button role="radio" aria-checked="false" aria-label="approve each call">⊕</button>
        <button role="radio" aria-checked="false" aria-label="deny">⊗</button>
      </div>
    </li>
    …
  </ul>
</details>
<details class="tool-permissions__group" open>
  <summary>
    <span class="tool-permissions__group-label">Write/delete tools</span>
    <span class="count-badge">9</span>
    <button class="default-policy-chip">👁 Needs approval ▾</button>
  </summary>
  <ul>…</ul>
</details>
```

## Interaction contracts

- The three per-row glyphs map to allow (call runs without prompting), approve (call prompts for approval each time), and deny (call is blocked), in that left-to-right order; each carries an explicit `aria-label` and the group uses the `role="radiogroup"` pattern (one policy selected per row at a time).
- The default-policy chip is a dropdown trigger opening a single-select menu (Always allow / Needs approval / Never allow).
- A row whose policy differs from its group default carries a small "overridden" dot marker before its controls so the divergence is visible at a glance.
- Expand/collapse uses the standard cross-fade (`foundations/motion.md` §15.3 application-shell register) and reduces to an instant toggle under `prefers-reduced-motion: reduce`.

Any connector, integration, OAuth-scope, or RBAC capability editor benefits from this stable two-level policy contract; without it, each connector page tends to invent a different control idiom.
