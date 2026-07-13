# Aliases — user-facing names → internal vocabulary

Skills translate the user's words at the boundary; entry bodies and pipeline logic use internal vocabulary only. Library entries add their own `aliases` frontmatter; a project extends this table with an `aliases.md` in its extensions dir.

| User says | Internal |
|---|---|
| page type, kind of page | Section Container |
| landing page, product page, marketing page | section-container: primary-landing |
| page, full page, whole page | Shell + Section Container (`assembled` render target) |
| just the content, no nav, no footer | `container-only` render target |
| the frame, the chrome, nav and footer | Shell (`shell-only` render target) |
| single-page app, SPA | `spa` render target |
| nav, nav bar, top nav, menu bar, header | the Shell's topbar Component |
| footer | the Shell's footer Component |
| section, band, stripe, block, row of the page | Section |
| hero, hero section | Section (hero) |
| layout, arrangement, template | Shape |
| app screen, app page, dashboard | app Shell + Section Container |
| sidebar, rail, left nav | app Shell pane |
| drawer | the Shell's mobile-drawer Component |
| canvas, stage, main content area | Shell content slot (the Section Container region) |
| widget, control, element (user sense) | Component — internal "Element" (a bare DOM node) is concept-only and never configured |
| card, tile, panel | Component |
| modal, dialog, sheet, popover, tooltip, toast, snackbar, banner | Component |
| CTA, call to action | Component (button) |
| chip, tag, badge, pill, avatar, toggle, stepper, skeleton, breadcrumb, tab bar | Component |
| wireframe, layout map | wireframe sidecar |
| the reasoning, why it chose | decisions sidecar |
| theme, skin, color scheme | theme |
| light mode, dark mode | color-mode |
| mockup, mock, comp | compose-page deliverable |
| in the app, live page, real component | compose-app-surface deliverable |
