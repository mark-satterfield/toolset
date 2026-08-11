---
kind: shape
name: editor-card-stack
aliases: [composition surface, prompt builder, message-flow composer]
status: stable
slots:
  - { name: title-row, required: true, accepts: [editable-title, saved-stamp, save-link, mode-tabs, primary-actions] }
  - { name: config-row, required: true, accepts: [model-picker, variables-hint, examples-picker, templates-link] }
  - { name: cards, required: true, accepts: [role-label, helper-text, editable-body, generate-action, delete-action] }
  - { name: action-row, required: true, accepts: [prefill-toggle, add-pair-action] }
variants: []
self_contained: false
content_defaults:
  card_sequence: [system, user, assistant, user]
---

# editor-card-stack — Role-tagged composition surface

A vertical stack of editor cards forming a composition surface, each card representing one role or slot in the composition, with an action row of secondary affordances beneath. Top to bottom:

1. Title row: editable document name (`Untitled ▾`) + "Last saved" timestamp + "Save changes" link, with a right-aligned mode segment (tablist) and primary actions ("Get Code", "▶ Run ⌘↵").
2. Configuration row: a model-picker pill, a variables hint (`{ }`), an examples picker, and a right-aligned templates link.
3. The card stack: a system card (label + one-line helper + info glyph + expand caret), user cards (label + a "✦ Generate" tertiary action + inline input affordance), and assistant cards (label + response placeholder + trailing delete glyph).
4. Action row beneath the cards: a "Pre-fill response" toggle + a "+ Add message pair" link.

## HTML skeleton

```html
<header class="composer-title-row">
  <button class="composer-title">Untitled ▾</button>
  <span class="composer-saved">Last saved Mar 24, 11:29 PM</span>
  <a class="composer-save-link">Save changes</a>
  <nav class="composer-mode-tabs" role="tablist">
    <button role="tab" aria-selected="true">Prompt</button>
    <button role="tab">Evaluate</button>
  </nav>
  <div class="composer-actions">
    <button class="btn-secondary">Get Code</button>
    <button class="btn-primary">▶ Run ⌘↵</button>
  </div>
</header>
<div class="composer-config-row">
  <button class="model-picker">☆ model-name</button>
  <button class="variables-hint">{ }</button>
  <button class="examples-picker">⚲ Examples</button>
  <a class="templates-link">◇ Templates</a>
</div>
<section class="composer-card composer-card--collapsed">
  <h2>System Prompt <span class="composer-card__helper">Define a role, tone or context (optional)</span></h2>
  <button class="composer-card__expand" aria-label="expand">›</button>
</section>
<section class="composer-card">
  <h2>User</h2>
  <button class="btn-tertiary">✦ Generate Prompt</button>
  <span class="composer-card__helper">or enter instructions or prompt for the model…</span>
</section>
<section class="composer-card">
  <h2>Assistant</h2>
  <p class="composer-card__placeholder">Enter the model's response…</p>
  <button class="composer-card__delete" aria-label="delete">🗑</button>
</section>
<footer class="composer-action-row">
  <label><input type="checkbox"> Pre-fill response</label>
  <button class="btn-tertiary">+ Add message pair</button>
</footer>
```

## Determinations

- Card expand/collapse: each card has a caret toggle (`aria-expanded`, `aria-controls`); collapsed cards show title + helper only, expanded cards reveal the editable body. "+ Add message pair" appends a new user/assistant card pair at the bottom; each card's trailing trash glyph removes that card. Cards cannot be removed below a single remaining card.
- Drag-to-reorder: cards are reorderable by a drag handle on the left edge; a keyboard alternative moves the focused card with the handle focused and Up/Down arrows. Reordering animates with the standard cross-fade (`foundations/motion.md` §15.3, application-shell register), suppressed under reduced-motion.
- Model picker: a dropdown trigger listing the host project's available models; the selection persists per document and restores on reopen.

Suits prompt builders, message-flow composers, conversation scripters, and script editors. Suits an application Shell with a rail Section and a right info-panel Section (the info panel hosts the welcome/help guide).
