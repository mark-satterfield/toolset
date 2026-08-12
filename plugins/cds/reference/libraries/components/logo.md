---
kind: component
name: logo
aliases: [brand mark, wordmark, logotype, mark, brand logo]
status: stable
slots:
  - { name: mark, required: true, accepts: [svg-glyph, asset-pair] }
sizing:
  height: "intrinsic — the mark takes the mark height of the Section hosting it (that Section's sizing.mark-height). This entry fixes no height of its own."
  width: "auto, from the height, so the mark's aspect ratio is never distorted"
behavior:
  - "static; the mark never animates"
  - "an asset-pair mark swaps by colour-mode in CSS, with no JavaScript"
accessibility:
  - "the mark links to the site root and carries an accessible name naming the brand"
  - "a single-glyph mark paints via currentColor and inherits --text-primary"
  - "foundation focus ring on :focus-visible"
token_bindings: [--text-primary, --focus-ring]
composite: false
---

# Logo

The brand mark as a placeable unit. By default a single SVG glyph painting via `fill="currentColor"` on its inner paths and `fill="none"` on the outer `<svg>`, so it inherits `--text-primary` and recolours with the surrounding theme.

A multi-colour brand mark MAY instead declare an `assets.logo` light/dark image pair (`mode: asset-pair`): both images are emitted and the active one is selected by colour-mode in CSS with no JavaScript (`compliance.md` §23 #15).

## Determinations

- This entry fixes no height. The mark renders at `width: auto` from whatever height it is given, so its aspect ratio is never distorted, and nothing else about its size is decided here.
- How big the mark is belongs to the Section hosting it, which declares a `mark-height` in its own `sizing` and scopes it to the marks it holds. A bar, a rail, and a footer island therefore size their marks independently: a rail is not a bar and has no reason to inherit a bar's measurements.
- Where the mark sits is the contract of the Shape placing it, never this entry's.
- The mark is static: no scroll transition, no hover treatment, no entrance animation.

## Accessibility

- The mark links to the site root and carries an accessible name naming the brand (an `aria-label` on the link, or `alt` text on the image). On a surface that offers no other navigation, this link is the only exit.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
