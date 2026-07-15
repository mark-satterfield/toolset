---
kind: component
name: template-gallery-card
page_family: app
aliases: [template entry, example card, prompt template card, template gallery entry]
status: stable
slots:
  - { name: head, required: true, accepts: [eyebrow, title] }
  - { name: preview, required: true, accepts: [live-canvas] }
  - { name: control-panel, required: true, accepts: [fieldsets] }
  - { name: cta-card, required: true, accepts: [title, description, primary-button] }
  - { name: trailer, required: false, accepts: [caption] }
sizing:
  entry: "full canvas-track width; preview left, control panel right, sticky CTA card far right"
behavior:
  - "control-panel controls live-bind to the preview"
  - "CTA card is sticky within its entry"
accessibility:
  - "dimension groups are <fieldset> + <legend>; segment options aria-pressed"
token_bindings: [--accent-primary, --text-primary, --text-tertiary]
shell_component: false
composite: false
---

# Template gallery card

One repeating entry in a template gallery: a large live preview canvas on the left, a control-panel descriptor of the template's parameter dimensions beside it, and a sticky right-side CTA card carrying the entry title, a short quoted description (the prompt the user would use), and a primary "Use this prompt" action. A small file-version trailer sits below the entry. Each entry is a self-contained advert-plus-demo.

## Slots

- `head` (required): a small title row (e.g., "Calculator Kit") above the preview, with an eyebrow naming the construction and dimension count (e.g., "CONSTRUCTION / 13 DIMENSIONS").
- `preview` (required): a large live preview canvas (e.g., a fully styled calculator).
- `control-panel` (required): each parameter dimension as a labelled control-group preview — segmented choices (e.g., SHELL STYLE — default/flat/brutal/soft/glass; KEY SHAPE — sharp/standard/round/pill/circle; LAYOUT — standard 4×4/scientific 5×6/compact 4×4), sliders and toggles (e.g., DISPLAY — font, size slider, align toggle, show-history toggle; KEY LABELS — face choice, weight slider, size slider).
- `cta-card` (required): a sticky descriptor block at the far right carrying the entry title, a 2–4-line description in quotes, and a primary CTA ("Use this prompt") painted in the mapped accent (`--accent-primary`).
- `trailer` (optional): a small file-version caption below the entry, optionally carrying a trailing caret-marked hover-disclosure affordance (e.g., "calculator-kit / v1 — hover: everything ▾"). The caption text is content; the hover-disclosure affordance is part of the trailer's contract.

## Behavior

- Control-panel controls are interactive and live-bind to the preview: changing a dimension control re-renders the preview canvas for that entry in place, so the user can explore the parameter space before committing. The "Use this prompt" CTA captures the current configuration.
- The right-side CTA card is sticky within its entry: `position: sticky; top: <header offset>`, pinned for the height of the entry so it stays in view while the user scrolls the preview and controls, then releases at the entry boundary.
- When the trailer carries the hover-disclosure affordance ("hover: everything ▾"), hovering it reveals the entry's full state/detail set inline; the trailing caret (`▾`) marks the trailer as hover-expandable. The disclosure is pointer-hover-triggered, so keyboard hosts expose the same disclosure on focus.

## Accessibility

- Each dimension group is a `<fieldset>` with a `<legend>` naming the dimension; segmented options carry `aria-pressed` state.
- The CTA is a standard primary button (`libraries/components/button.md`) with the foundation focus-ring contract.

## Structural skeleton

```html
<section class="template-gallery-card">
  <header class="template-gallery-card__head">
    <span class="template-gallery-card__eyebrow">CONSTRUCTION / 13 DIMENSIONS</span>
    <h2>Calculator Kit</h2>
  </header>
  <div class="template-gallery-card__body">
    <div class="template-gallery-card__preview"><!-- live preview canvas --></div>
    <div class="template-gallery-card__control-panel">
      <fieldset>
        <legend>SHELL STYLE</legend>
        <div class="seg"><button aria-pressed="true">Default</button>…</div>
      </fieldset>
      <fieldset>
        <legend>KEY SHAPE</legend>
        <div class="seg">…</div>
      </fieldset>
      …
    </div>
  </div>
  <aside class="template-gallery-card__cta-card"><!-- sticky -->
    <h3>Calculator construction kit</h3>
    <p>"Create a 'Calculator construction kit' — a simple calculator UI with a LOT of tweaks…"</p>
    <button class="btn-primary btn-primary--accent">Use this prompt</button>
  </aside>
  <footer class="template-gallery-card__trailer">calculator-kit / v1 — <span class="template-gallery-card__trailer-disclosure">hover: everything ▾</span></footer>
</section>
```

Suits prompt-library / template-gallery surfaces where each template carries both a previewable surface and a parameter set the user can explore before choosing it. The vertical stack of entries and the tab strip above them belong to the hosting gallery Shape, not to this Component.
