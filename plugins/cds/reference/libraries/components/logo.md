---
kind: component
name: logo
page_family: shared
aliases: [brand mark, wordmark, logotype, mark, brand logo]
status: stable
slots:
  - { name: mark, required: true, accepts: [svg-glyph, asset-pair] }
sizing:
  height: "--topbar-logo-height; width auto. One height wherever the mark appears — a bar, a rail, a footer island — so the brand reads at one size across the build."
behavior:
  - "static; the mark never animates"
  - "an asset-pair mark swaps by colour-mode in CSS, with no JavaScript"
accessibility:
  - "the mark links to the site root and carries an accessible name naming the brand"
  - "a single-glyph mark paints via currentColor and inherits --text-primary"
  - "foundation focus ring on :focus-visible"
token_bindings: [--text-primary, --topbar-logo-height, --focus-ring]
composite: false
---

# Logo

The brand mark as a placeable unit. By default a single SVG glyph painting via `fill="currentColor"` on its inner paths and `fill="none"` on the outer `<svg>`, so it inherits `--text-primary` and recolours with the surrounding theme.

A multi-colour brand mark MAY instead declare an `assets.logo` light/dark image pair (`mode: asset-pair`): both images are emitted and the active one is selected by colour-mode in CSS with no JavaScript (`compliance.md` §23 #15).

## Determinations

- Renders at `height: var(--topbar-logo-height); width: auto`, so the mark holds one size wherever it is placed. The design system owns that height — a composed page never hardcodes it, and a page-block `<style>` re-declaring it is an audit violation.
- Where the mark sits is the contract of the Shape placing it, never this entry's.
- The mark is static: no scroll transition, no hover treatment, no entrance animation.

## Accessibility

- The mark links to the site root and carries an accessible name naming the brand (an `aria-label` on the link, or `alt` text on the image). On a surface that offers no other navigation, this link is the only exit.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
