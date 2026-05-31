## §21 Token Mapping Checklist

Use this checklist when you adopt the template for a new brand or product. Walk through every item before integrating components.

- [ ] All four color ramps mapped — neutral, blue, green, red (21 steps each, contrast progression preserved per ramp). [scope: both]
- [ ] Accent family mapped (primary, interactive, hover, dark variants). [scope: both]
- [ ] Panel colors mapped (saturated grounds for tiles, panels, badges). [scope: both]
- [ ] State colors mapped (error light, error dark, error fill, required, focus blue). [scope: both]
- [ ] Text role contrast checked against every theme's surface (`--role-text-primary` vs `--role-surface-primary`, etc.) at WCAG AAA for body and AA for tertiary. [scope: both]
- [ ] Light themes resolved for every theme class (`clarity`, `default`, `editorial`, `punctuation`, `statement`, `feature-dark`, `code`, `deep`). [scope: both]
- [ ] Dark themes resolved for every light-leaning theme class (`default`, `clarity`, `editorial`). [scope: both]
- [ ] Button slot bindings resolved (primary, secondary, brand) for both light and dark mode. [scope: both]
- [ ] Focus ring color checked against every theme's surface for visibility. [scope: both]
- [ ] Selection tint checked: mapped accent at 50% mix renders legibly over text. [scope: both]
- [ ] Primary Sans mapped, fallback stack documented. [scope: both]
- [ ] Editorial Serif mapped, fallback stack documented. [scope: both]
- [ ] System Mono mapped, fallback stack documented. [scope: both]
- [ ] Non-variable font fallback documented (weight substitution table per `foundations/typography.md` §13.2). [scope: both]
- [ ] CSS `:root` palette block generated from the `foundations/overview.md` §4 tables per the `foundations/implementation.md` §8.1 pattern (no hand-edited hex values inside the CSS). [scope: both]
- [ ] Theme-wrapper CSS classes generated from the `foundations/implementation.md` §6 tables per the `foundations/implementation.md` §8.2 pattern (no hand-edited role-to-swatch bindings inside the CSS). [scope: both]
- [ ] Sample pages visually reviewed in light mode for every page type. [scope: standalone]
- [ ] Sample pages visually reviewed in dark mode for every light-leaning page type. [scope: standalone]
- [ ] Sample pages visually reviewed with `prefers-reduced-motion: reduce` enabled. [scope: standalone]
- [ ] Keyboard focus states checked on every interactive element across every theme. [scope: both]
- [ ] Code-block fixed dark values reviewed and updated to mapped near-black neutrals. [scope: both]

---

## §22 Implementation Checklist

Use this checklist to verify any new page or component before merging.

1. Palette is defined as a flat dictionary of named swatches in a single `:root` selector, generated from the `foundations/overview.md` §4 tables per the `foundations/implementation.md` §8.1 pattern. [scope: both]
2. **No color identity ever appears outside the elements YAML.** Component CSS, foundations CSS, and any other implementation consume **role** variables only (`--surface-primary`, `--accent-primary`, `--tile-ground-1`, `--switch-active-bg`, …). A hex literal, a ramp step (`--color-neutral-950`), or a named swatch (`--color-panels-oat`) appearing in implementation is a violation — naming `oat` is identical in sin to writing `#E3DACC`. The only legitimate consumers of `--color-*` tokens are: (a) the `:root` palette emit (§8.1), and (b) theme wrappers (§8.2), which bind roles to semantic tokens. A role that may draw only from a specific palette declares it with `from_palette` in the YAML; the elements linter resolves every theme binding and fails if it lands outside the allowed palette. [scope: both]
3. Every section is wrapped in a theme class (`default`, `clarity`, etc.). [scope: both]
4. The document root carries `data-mode="light" | dark | system"` at first paint. [scope: standalone]
5. The CSS `color-scheme` property is declared on the root per mode. [scope: standalone]
6. Themes that need to invert in dark mode have their dark-mode bindings inside both `[data-mode="dark"]` and `[data-mode="system"] @media (prefers-color-scheme: dark)` selectors. [scope: both]
7. All inline SVGs use `fill="currentColor"` on inner paths and `fill="none"` on the outer `<svg>`. [scope: both]
8. Text-selection background is the 50% mapped-accent mix applied globally. [scope: both]
9. The hero h1 does not end in a period. [scope: both]
10. Body type is at least 17px on every breakpoint. [scope: both]
11. Every interactive element has a `:focus-visible` ring per `foundations/accessibility.md` §18.2. [scope: both]
12. Every keyframe animation has a `@media (prefers-reduced-motion: reduce)` override. [scope: both]
13. Skip links exist at the top of `<body>`. [scope: standalone]
14. The topbar background matches the page ground exactly. No border. No shadow. [scope: both]
15. Footer columns include language selector and any cookie/consent trigger — not in the topbar. [scope: both]
16. Code blocks render dark in light mode and continue dark in dark mode. [scope: both]
17. The conversion-card 4-layer shadow stack is reserved for the conversion card only. [scope: both]
18. Reading columns on long-form pages are exactly 640px wide. [scope: both]
19. Card padding clamps between 24px and 48px. [scope: both]
20. Section padding clamps between 64px and 200px depending on the section role. [scope: both]

---

## §23 Design Compliance Rules

These rules are non-negotiable. Treat any violation as a build-blocking error.

1. **No component reads a palette swatch directly.** All component CSS reads role variables. Palette references appear only inside theme wrappers. [scope: both]
2. **No component hardcodes a font family.** All `font-family` declarations reference `--font-sans`, `--font-serif`, or `--font-mono`. [scope: both]
3. **No component hardcodes a font size.** All `font-size` declarations reference typography role tokens. [scope: both]
4. **No standalone duration or easing curve.** All transitions reference motion tokens. [scope: both]
5. **No success-green and no warning-yellow swatches.** The palette excludes these by design. [scope: both]
6. **Every keyframe animation has a reduced-motion override.** [scope: both]
7. **Every interactive element exposes a visible focus ring on `:focus-visible`.** [scope: both]
8. **The 640px reading column is the only acceptable body width on long-form editorial and documentation pages.** [scope: both]
9. **Long-form pages contain no shadows, no boxes, and a single hard 1px rule between metadata and body.** [scope: both]
10. **Code blocks declare fixed dark hex values outside the theme system. They do not consume `--role-surface-primary`.** [scope: both]
11. **All decorative SVGs inherit color via `currentColor` from the surrounding theme.** [scope: both]
12. **Mobile narrow sections reduce major section padding to 56px. No exceptions.** [scope: both]
13. **Components consume the `--accent-primary` role; the theme rebinds it to a softer accent in dark mode automatically. Components do not author dark-mode accent overrides and never reference an accent swatch directly.** [scope: both]
14. **Every modal that is not a video or lightbox dialog uses a flat 50% black wash with no backdrop filter.** [scope: both]
15. **Logos, icons, and mascot art are never authored as separate light-mode and dark-mode assets.** [scope: both]
16. **Topbar height is consistent across a page type. Do not vary it per section.** [scope: both]
17. **A theme wrapper is the only mechanism that repaints a section. Do not introduce ad-hoc `background-color` rules on sections.** [scope: both]

---

## Scope ambiguities

- §21 "CSS `:root` palette block generated from the §4 tables per the §8.1 pattern (no hand-edited hex values inside the CSS)." — tagged `[scope: both]`. Ambiguity: the `:root` block lives in the design-system stylesheet, which standalone mocks inline and app-embedded surfaces import. The generation rule applies to the source CSS regardless of how it is delivered, but readers may interpret `:root` as a mock-only concern.
- §21 "Theme-wrapper CSS classes generated from the §6 tables per the §8.2 pattern (no hand-edited role-to-swatch bindings inside the CSS)." — tagged `[scope: both]`. Same ambiguity as the `:root` palette rule: the theme-wrapper classes are part of the shared stylesheet, but the prose can read as page-level.
- §22 #1 "Palette is defined as a flat dictionary of named swatches in a single `:root` selector, generated from the §4 tables per the §8.1 pattern." — tagged `[scope: both]`. Ambiguity: the rule describes the design-system stylesheet structure, which both contexts consume; an app-embedded surface does not author its own `:root` palette block but does depend on the shared one being correct.
- §22 #6 "Themes that need to invert in dark mode have their dark-mode bindings inside both `[data-mode="dark"]` and `[data-mode="system"] @media (prefers-color-scheme: dark)` selectors." — tagged `[scope: both]`. Ambiguity: the selector pattern targets `data-mode` on the document root (a standalone mock concern), but the dark-mode binding rule itself governs the shared stylesheet that both contexts use.
- §23 #10 "Code blocks declare fixed dark hex values outside the theme system. They do not consume `--role-surface-primary`." — tagged `[scope: both]`. Ambiguity: this rule sanctions raw hex values in one specific component, which conflicts with the general "no hand-edited hex" posture; the carve-out applies regardless of rendering context but may need a clearer policy statement.

## Known gaps

- §21–§23 contain no brand identifiers. If these sections are extended later, re-audit for brand references in both prose and any added code blocks.
- §21–§23 contain no fenced code blocks.
- CSS variable references use the `--role-*` and `--color-*` convention throughout: role tokens (`--role-text-primary`, `--role-surface-primary`, etc.) carry the `--role-` prefix; palette swatches (`--color-accent-primary`, `--color-accent-dark`, etc.) carry the `--color-` prefix. Font-family references (`--font-sans`, `--font-serif`, `--font-mono` in §23 #2) follow the YAML's `font_var_pattern: "--font-{font key}"` convention and match `foundations/typography.md §13.1` — no `--role-` prefix.
- Section cross-references (§4, §6, §8.1, §8.2, §13.2, §18.2) resolve to specific files: §4 → `foundations/overview.md`; §6, §8.1, §8.2 → `foundations/implementation.md`; §13.2 → `foundations/typography.md`; §18.2 → `foundations/accessibility.md`. Any further additions to §21–§23 should follow the same `<file>.md §N.M` form.
