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
| nav, nav bar, top nav, menu bar, header | shell furniture: topbar component |
| footer | shell furniture: footer component |
| section, band, stripe, block, row of the page | Section |
| layout, arrangement, template | Shape |
| app screen, app page, dashboard | app Shell + Section Container |
| sidebar, rail, left nav | app Shell pane |
| widget, control, element | Component |
| wireframe, layout map | wireframe sidecar |
| the reasoning, why it chose | decisions sidecar |
| theme, skin, color scheme | theme |
| light mode, dark mode | color-mode |
| mockup, mock, comp | compose-page deliverable |
| in the app, live page, real component | compose-app-surface deliverable |
