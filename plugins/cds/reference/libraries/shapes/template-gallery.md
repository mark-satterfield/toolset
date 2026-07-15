---
kind: shape
name: template-gallery
page_family: app
aliases: [example gallery, prompt library gallery, template showcase]
status: stable
slots:
  - { name: tab-strip, required: true, accepts: [tabs] }
  - { name: entries, required: true, accepts: [eyebrow, title, preview-canvas, control-panel, cta-card, version-trailer, hover-state-picker] }
variants: []
self_contained: false
content_defaults:
  tabs: [Recent, "Your designs", Examples, "Design systems"]
  first_entry:
    eyebrow: "CONSTRUCTION / 13 DIMENSIONS"
    title: "Calculator Kit"
    dimensions: ["SHELL STYLE — default/flat/brutal/soft/glass", "KEY SHAPE — sharp/standard/round/pill/circle", "LAYOUT — standard 4×4/scientific 5×6/compact 4×4", "DISPLAY — font, size slider, align toggle, show-history toggle", "KEY LABELS — sans/mono/serif/oxtech, weight slider, size slider"]
    cta: "Use this prompt"
---

# template-gallery — Example entries with live control panels

A vertical stack of template entries filling the vacant space — it suits an application Shell with a form-sidebar Section, as the Examples-tab view — beneath the tab strip. Each entry is a self-contained advert-plus-demo:

- Left: a large live preview canvas, with a small title row and an eyebrow ("CONSTRUCTION / 13 DIMENSIONS") above it.
- Right: a control-panel descriptor rendering each of the template's dimensions as a labelled control-group preview (segments, sliders, toggles).
- Far right: a sticky descriptor block carrying the entry title, a 2–4-line quoted description (the prompt the user would use), and a primary CTA in mapped accent.
- Beneath the entry: a small file-version trailer ("calculator-kit / v1") with a trailing hover-state picker — a disclosure control labelled with the current hover scope ("hover: everything ▾") that selects which part of the entry's preview responds to hover demonstration.

## HTML skeleton

```html
<section class="template-entry">
  <header class="template-entry__head">
    <span class="template-entry__eyebrow">CONSTRUCTION / 13 DIMENSIONS</span>
    <h2>Calculator Kit</h2>
  </header>
  <div class="template-entry__body">
    <div class="template-entry__preview"><!-- live preview canvas --></div>
    <div class="template-entry__control-panel">
      <fieldset>
        <legend>SHELL STYLE</legend>
        <div class="seg"><button aria-pressed="true">Default</button>…</div>
      </fieldset>
      <fieldset><legend>KEY SHAPE</legend><div class="seg">…</div></fieldset>
    </div>
  </div>
  <aside class="template-entry__cta-card">
    <h3>Calculator construction kit</h3>
    <p>"Create a 'Calculator construction kit' — a simple calculator UI with a LOT of tweaks…"</p>
    <button class="btn-primary btn-primary--accent">Use this prompt</button>
  </aside>
  <footer class="template-entry__trailer">
    calculator-kit / v1 —
    <button class="template-entry__hover-picker" aria-haspopup="listbox" aria-expanded="false">hover: everything ▾</button>
  </footer>
</section>
```

## Determinations

- Control-panel controls are interactive and live-bind to the preview: changing a dimension control re-renders that entry's preview canvas in place, so the user explores the parameter space before committing. The CTA captures the current configuration.
- The right-side CTA card is sticky within its entry: `position: sticky; top: <header offset>`, pinned for the height of the entry so it stays in view while the user scrolls the preview and controls, releasing at the entry boundary.

Suits prompt-library and template-gallery surfaces where each template carries both a previewable surface and a parameter set worth exploring before choosing it.
