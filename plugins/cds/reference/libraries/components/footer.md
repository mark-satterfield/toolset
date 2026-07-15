---
kind: component
name: footer
page_family: shared
aliases: [site footer, footer grid, footer navigation]
status: stable
shell_component: true
composite: false
slots:
  - { name: columns, required: true, accepts: [column-heading, column-link] }
  - { name: column-heading, required: true, accepts: [h3-label] }
  - { name: column-link, required: true, accepts: [link] }
  - { name: social-row, required: false, accepts: [social-icon-link] }
  - { name: language-selector, required: false, accepts: [locale-control] }
  - { name: legal-trigger, required: false, accepts: [link, button] }
sizing:
  column-grid: "4–6 nav columns on the 12-column grid; collapses to 2 columns below 700px and 1 below 480px"
  legal-row-separation: "var(--sp-4); calibrates to a 52–64px clamp"
  column-heading-type: "smallest body-sans size (12–14px), weight 700"
behavior:
  - "hover on a footer link shifts color toward --text-primary over 100ms"
  - "social-icon hover shifts the currentColor glyph from --text-tertiary toward --text-primary over 100ms — one hover vocabulary with the links"
accessibility:
  - "landmark: <footer role=\"contentinfo\"> (explicit role required when the footer is nested inside another sectioning element)"
  - "column headings are <h3>-level; never nested deeper"
  - "each social icon link carries an aria-label naming the destination service; the SVG glyph is aria-hidden"
  - "foundation focus ring on :focus-visible for every link"
token_bindings: [--footer-bg, --footer-text, --text-primary, --text-tertiary, --focus-ring, --sp-4]
content_defaults:
  columns: [Products, Models, Solutions, Platform, Resources, Help, Company, Terms]
---

# Footer

Multi-column site footer providing secondary navigation, legal, and social affordances. It realizes the Shell's footer Section, placed below the content region as a named theme island, outside the Page's ground alternation.

## Slots

- **columns** — the set of nav columns. Default column headings are declared in `content_defaults`; supplied content overrides.
- **column-heading** — required per column; `<h3>` semantically.
- **column-link** — repeating link within a column.
- **social-row** — optional row of social icons, a single row at the bottom or a left-aligned column.
- **language-selector** — optional, placed inside a footer column list.
- **legal-trigger** — optional (e.g., "Cookie Settings"), placed inside a footer column list. Never placed in the topbar.

## Variants

- `ground`: `editorial` (default — `--footer-bg` resolved through the editorial theme: a near-black neutral) | `marketing` (binds to the `deep` theme; deepest dark neutral with mid-tone links) | `authentication` (explicit `data-mode="dark"` wrapper that resolves `--surface-primary` to absolute black; used only on the conversion page's footer).

## Layout

Multi-column nav grid above a legal/copyright row.

- Default is 4–6 nav columns on the 12-column grid, collapsing to 2 columns below 700px and 1 below 480px.
- The legal/copyright row sits full-width beneath the grid, separated by `var(--sp-4)` (calibrates to a 52–64px clamp), and carries the copyright line plus legal links (and a locale/language selector when present) per the slot definitions above.
- The number of nav columns and the presence of a social/utility row are per-instance layout choices.

## Determinations

- Footer link color = `var(--footer-text)`. The ground variants resolve this role to a brighter neutral on the absolute-black variant and a step deeper on the standard dark variant.
- No underline at rest.
- Footer column heading: smallest body-sans size (12–14px), weight 700, ink at `var(--text-tertiary)` (low-contrast cool gray). Semantically `<h3>`; never nested deeper.
- Hover on a footer link shifts color toward `--text-primary` over 100ms.

## Accessibility

- Landmark: the footer host element is `<footer role="contentinfo">` — `<footer>` only resolves to the `contentinfo` landmark when it is a direct child of `<body>`; when the footer is nested inside another sectioning element, the explicit `role="contentinfo"` is required. (WAI-ARIA landmark guidance.)
- Social icon accessible names: each social icon link carries an `aria-label` naming the destination service (e.g., `aria-label="{Brand} on LinkedIn"` — the host project supplies the brand name). The SVG glyph itself carries `aria-hidden="true"` because the link's accessible name carries the semantic. (WAI-ARIA APG link pattern.)
- Focus styling: footer links use the foundation focus ring (`outline: 2px solid var(--focus-ring); outline-offset: 2px`) on `:focus-visible`. Hover-only-style affordances do not satisfy WCAG 2.4.7. (WCAG 2.4.7, 2.4.11.)
- Social-icon hover: the icon's `currentColor` glyph shifts from `--text-tertiary` toward `--text-primary` over 100ms — matching the footer-link hover treatment so the row reads as one consistent hover vocabulary.
