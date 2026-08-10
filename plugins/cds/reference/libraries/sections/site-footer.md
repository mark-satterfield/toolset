---
kind: section
name: site-footer
page_family: shared
aliases: [footer, site footer, footer grid, footer navigation, page footer]
status: stable
shell_edge: block-end
content_contract:
  column_count: "integer — the number of nav columns the frame offers"
  carries_brand_island: "true | false — a mark and its line presented as their own block"
  carries_social: "true | false"
theme: default
composition_notes: []
variants: [ground]
sizing:
  legal-row-separation: "var(--sp-4); calibrates to a 52–64px clamp"
  mark-height: "var(--topbar-logo-height) when the received Shape places a mark, so the mark reads at one size wherever it appears"
  column-heading-type: "smallest body-sans size (12–14px), weight 700"
behavior:
  - "hover on a footer link shifts color toward --text-primary over 100ms"
  - "social-icon hover shifts the currentColor glyph from --text-tertiary toward --text-primary over 100ms — one hover vocabulary with the links"
accessibility:
  - "landmark: <footer role=\"contentinfo\"> (the explicit role is required when the footer is nested inside another sectioning element)"
  - "column headings are <h3>-level; never nested deeper"
  - "each social icon link carries an aria-label naming the destination service; the SVG glyph is aria-hidden"
  - "foundation focus ring on :focus-visible for every link"
token_bindings: [--footer-bg, --footer-text, --text-primary, --text-tertiary, --topbar-logo-height, --focus-ring, --sp-4]
---

# Site footer

The Shell Section pinned to the block-end edge of the frame: the secondary navigation, legal, and social affordances that repeat under every Page. It is a named theme island, outside the Page's ground alternation.

**This entry fixes the surface; the Shape fixes the arrangement.** Ground, link ink, heading type, legal-row separation, hover vocabulary, and landmark are the footer's own properties and live here. How many columns there are, whether a brand island sits beside or above them, and whether a social row is present are the contract of the Shape this Section receives from the ShapeLibrary (`libraries/shapes/`, the `footer-*` arrangements). A footer with different contents is a different Shape over this one Section, never an optional slot on a Component.

## Shape assignment

Lazy by default: the Shape resolves at build time from `column_count`, `carries_brand_island`, and `carries_social` via `rules/shape-selection/site-footer.md`. A ShellDefinition that names a `footer-*` Shape up front is assigned eagerly and the rule does not run.

## Variants

- `ground`: `editorial` (default — `--footer-bg` resolved through the editorial theme: a near-black neutral) | `marketing` (binds to the `deep` theme; deepest dark neutral with mid-tone links) | `authentication` (explicit `data-mode="dark"` wrapper that resolves `--surface-primary` to absolute black).

## Determinations

- Footer link color = `var(--footer-text)`. The ground variants resolve this role to a brighter neutral on the absolute-black variant and a step deeper on the standard dark variant.
- No underline at rest.
- Column heading: smallest body-sans size (12–14px), weight 700, ink at `var(--text-tertiary)` (low-contrast cool gray). Semantically `<h3>`; never nested deeper.
- The legal/copyright row sits full-width beneath whatever the Shape places above it, separated by `var(--sp-4)` (calibrates to a 52–64px clamp).
- Hover on a footer link shifts color toward `--text-primary` over 100ms.
- A mark placed in the footer renders at `var(--topbar-logo-height)`, the one mark height across the build.
- A locale/language selector and a legal trigger (e.g. "Cookie Settings") are footer content and are placed by the received Shape. Neither is ever placed in the top-nav Section.

## Accessibility

- Landmark: the footer host element is `<footer role="contentinfo">` — `<footer>` only resolves to the `contentinfo` landmark when it is a direct child of `<body>`; when the footer is nested inside another sectioning element, the explicit `role="contentinfo"` is required. (WAI-ARIA landmark guidance.)
- Social icon accessible names: each social icon link carries an `aria-label` naming the destination service (e.g. `aria-label="{Brand} on LinkedIn"` — the host project supplies the brand name). The SVG glyph itself carries `aria-hidden="true"` because the link's accessible name carries the semantic. (WAI-ARIA APG link pattern.)
- Focus styling: footer links use the foundation focus ring (`outline: 2px solid var(--focus-ring); outline-offset: 2px`) on `:focus-visible`. Hover-only-style affordances do not satisfy WCAG 2.4.7. (WCAG 2.4.7, 2.4.11.)
