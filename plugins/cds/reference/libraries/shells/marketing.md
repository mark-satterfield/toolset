---
kind: shell
name: marketing
family: landing
aliases: [marketing shell, landing frame, nav and footer]
status: stable
sections:
  - { component: topbar, placement: top, notes: "fixed banner; carries the page ground via --nav-bg" }
  - { component: footer, placement: bottom, notes: "named theme island: deep" }
panes: []
content_slot: { kinds: [section-container], families: [landing, editorial] }
---

# Marketing shell

The outermost frame for marketing and landing pages: a fixed topbar above the content region, the site footer below it. The content region hosts exactly one Section Container (or, in SPA render mode, a set of Section Containers with one active).

The Components realizing these persistent Sections own their contracts (`libraries/components/topbar.md`, `libraries/components/footer.md`); the shell declares placement and the theme islands. Each persistent Section of the Shell is deterministic, realized by the named Component. Neither persistent Section participates in the content container's ground alternation.
