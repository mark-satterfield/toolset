---
kind: shell
name: a5-form-sidebar-canvas
id: A5
family: app
aliases: [generator shell, config sidebar and canvas, design tool shell, template picker]
status: stable
furniture: []
panes:
  - { name: form-sidebar, width: var(--app-shell-form-sidebar), collapse: "between the tablet and desktop breakpoints → narrows to its declared floor (calibrates to 280px); below the tablet breakpoint → top sheet behind a \"Configure\" trigger" }
  - { name: canvas-or-gallery, width: fluid (remaining viewport width), collapse: "fills the viewport when the sidebar collapses" }
content_slot: { kinds: [section-container], families: [app] }
---

# A5 — Form-driven sidebar + canvas/gallery

Left sidebar drives configuration via form controls; the right pane is a canvas or gallery showing the result of the current configuration (or a gallery of templates that, when picked, populate the form).

## Partitioning

- `form-sidebar` (left, fixed width) — labelled form controls grouped into a configuration panel: name input, design-system picker, mode segment (wireframe / high-fidelity), primary Create CTA at the bottom of the panel. Below the form sit project-scope labels ("Only you can see your project by default.") and a docs + identity footer.
- `canvas-or-gallery` (right, fluid) — either a working canvas (live preview of the configured object) or a gallery (Recent / Your designs / Examples / Design systems tab strip with project cards or template cards beneath). The right pane may be a project gallery or an examples gallery with per-template descriptor cards on the right edge.

## Determinations

- Form sidebar width `--app-shell-form-sidebar` (`foundations/layout.md` §11.10; declared floor calibrates to 280px).
- Canvas/gallery is fluid, taking the remaining width, with its own horizontal tab strip ("Recent / Your designs / Examples / Design systems") at the top.
- Sidebar role across modes: in gallery mode the sidebar drives creation — its Create CTA starts a new object; in editing/canvas mode the sidebar's controls bind to the active object so editing a control updates the canvas live. The sidebar keeps one role across modes; only the right pane changes between gallery and canvas.
- Tab-strip routing: the canvas tab strip is URL-routed (each tab is a distinct route segment so a tab is shareable and survives reload), with local state mirroring the active tab for instant paint.
- Collapse ladder: at and above the desktop breakpoint (`foundations/responsive.md` §17.1) both panes show side by side. Between the tablet and desktop breakpoints the sidebar narrows to its floor. Below the tablet breakpoint the sidebar collapses to a top sheet opened by a "Configure" trigger, and the canvas/gallery fills the viewport.

## Structural skeleton

```html
<div class="app-shell app-shell--a5">
  <aside class="app-form-sidebar" aria-label="configuration">
    <header class="app-form-sidebar__brand">Design Tool</header>
    <nav class="app-form-sidebar__mode-tabs" role="tablist">
      <button role="tab" aria-selected="true">Prototype</button>
      <button role="tab">Slide deck</button>
      <button role="tab">From template</button>
      <button role="tab">Other</button>
    </nav>
    <form class="app-form-sidebar__form">
      <label>Project name <input type="text"></label>
      <label>Design system <select>…</select></label>
      <fieldset class="app-form-sidebar__segment">
        <legend class="sr-only">Fidelity</legend>
        <label><input type="radio" name="fidelity" value="wireframe">Wireframe</label>
        <label><input type="radio" name="fidelity" value="high" checked>High fidelity</label>
      </fieldset>
      <button type="submit" class="app-form-sidebar__primary">+ Create</button>
    </form>
    <footer class="app-form-sidebar__footer">
      <span>Docs</span>
      <span>Alex</span>
      <span>Alex's Organization</span>
    </footer>
  </aside>
  <main class="app-canvas">
    <nav class="app-canvas__tabs" role="tablist">
      <button role="tab">Recent</button>
      <button role="tab">Your designs</button>
      <button role="tab" aria-selected="true">Examples</button>
      <button role="tab">Design systems</button>
    </nav>
    <div class="app-canvas__body">
      <!-- gallery cards or live canvas -->
    </div>
  </main>
</div>
```

## Frame register

- Motion is the application register: cross-fades on tab and route changes, 200ms control transitions, dropdown chevron rotation; no hero reveal animations.
- Primary-action emphasis stays reserved — the loudest CTA emphasis belongs to marketing surfaces, never inside the app frame.
- Panes paint `default` theme grounds. Code panels use the local `code` theme wrapper and stay dark in both color-modes.
- Modal dialogs center on a dimmed backdrop without blur.

## Suits

Creative/design tools (prototype builders, slide editors, generator entry screens) where configuration is parametric and the canvas is the work product. The form-driven sidebar earns its width only when the form is doing real work — configuring the canvas or picking a template.

- A5 vs. A2: A5's sidebar drives the canvas; A2's info panel is help, not input. Help-and-tips belongs in A2; configuration-that-renders belongs in A5.
