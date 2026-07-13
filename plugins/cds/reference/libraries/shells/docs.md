---
kind: shell
name: docs
family: docs
aliases: [documentation frame, docs frame, legal page frame]
status: stable
sections:
  - { component: topbar, placement: top, notes: "sticky; no transition" }
  - { component: footer, placement: bottom, notes: "named theme island: deep; footer link colors carry the shell's only motion, a 200ms color transition" }
panes: []
content_slot: { kinds: [section-container], families: [docs] }
---

# Docs shell

The frame for long-form documentation and reference pages: a sticky topbar above an inset content region, the site footer below it.

The content region is inset by a symmetric outer offset on each side — the `--docs-outer-offset` geometry token (`foundations/layout.md` §11.2; calibrates to 316px per side at the widest viewport). Below the desktop breakpoint the offset reduces to the standard page gutter.

The root carries smooth scrolling (`html { scroll-behavior: smooth; }`), which in-page anchor links honor.

The topbar has no transition and no hide-on-scroll. The Components realizing these persistent Sections own their contracts (`libraries/components/topbar.md`, `libraries/components/footer.md`); the shell declares placement, the offset, and the footer's theme island. Each persistent Section of the Shell is deterministic, realized by the named Component.
