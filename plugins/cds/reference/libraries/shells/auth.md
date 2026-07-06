---
kind: shell
name: auth
family: auth
aliases: [authentication frame, sign-in frame, conversion frame, minimal frame]
status: stable
furniture:
  - { component: topbar, placement: top, notes: "minimal: one secondary link + one primary CTA; background = --nav-bg matching the page ground exactly; no border, no shadow, no animation" }
  - { component: footer, placement: bottom, notes: "local data-mode=\"dark\" wrapper resolving --surface-primary to the mapped absolute-black neutral — the only place in the system that uses it" }
panes: []
content_slot: { kinds: [section-container], families: [auth] }
---

# Auth shell

The minimal frame for conversion and authentication pages: a stripped topbar above the content region, a dark footer below it.

The topbar is fixed at `--topbar-height` (calibrates to 84px / 5.25rem) and carries exactly one secondary link and one primary CTA. Its background is `--nav-bg`, matching the page ground exactly — no border, no shadow, no nav animation. On narrow viewports it collapses to a compact row.

The footer sits in a local `data-mode="dark"` wrapper that resolves `--surface-primary` to the mapped absolute-black neutral; no other surface in the system paints with that neutral.

Furniture components own their contracts (`libraries/components/topbar.md`, `libraries/components/footer.md`); the shell declares placement, the topbar's minimal slot fill, and the footer's color-mode wrapper.
