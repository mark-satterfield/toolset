# Layout

The values in this file are authoritative and fixed. They are not configurable per project. Every surface — marketing, editorial, application, conversion, documentation — resolves layout against the same scaling rules, container widths, spacing scale, grid, radii, shadows, and border weights defined below.

## §11.1 Viewport scaling

The layout system is built on **linear interpolation between two viewport-width anchors.** Do not change values in discrete breakpoint jumps. Interpolate type sizes, container widths, and spacing values linearly between two viewport-width anchors:

- Lower anchor: **20rem (320px)** — values resolve to their minimum at and below this width.
- Upper anchor: **90rem (1440px)** — values resolve to their maximum at and above this width.

Between the two anchors, every responsive token interpolates linearly with viewport width. Implement with a single CSS `clamp()` per token, deriving the middle term mathematically from the token's Min and Max:

```css
/* For a token with Min M and Max X, anchors 320 → 1440 (span 1120): */
clamp(M, calc(M + (X - M) * (100vw - 320px) / 1120), X)
```

Do not hand-pick `vw` middle terms. Do not author per-breakpoint values for spacing or type. Fixed-value tokens (the small steps of the spacing scale, the fixed body-font sizes, the small radius values) declare their value directly without `clamp()`. Discrete `@media` overrides exist only for the explicit mobile-floor cases called out in this section (see §11.3).

## §11.2 Container widths

| Surface Class | Max Width | Inner Reading Column | Side Gutter |
|---|---:|---:|---:|
| Marketing primary container | 1440px | full container | 32–64px clamp |
| Marketing medium container | 1192px | full container | 32–64px clamp |
| Marketing small container | 960px | full container | 32–64px clamp |
| Editorial container | 1400px | **640px**, centered within | 32 / 48 / 64px responsive |
| Documentation or long-form container | viewport minus 316px each side at wide viewports | **640px**, centered | 316px outer offset at the widest breakpoint |
| Conversion card | 448px | n/a | n/a |
| Application shell pane | three-pane: 64px icon rail, 280–320px list column, fluid detail viewport | n/a | 24–32px inner card padding |

Use the 640px reading column for any long-form body type. Body sans on marketing pages may exceed this width if it remains under the full container.

## §11.3 Section padding scale

Apply a clamped section padding system that scales with the viewport. Use the spacing token closest to the role of the section.

| Token | Min | Max | Use For |
|---|---:|---:|---|
| `--section-pad-small` | 64px | 96px | Compact interior sections, marginalia rails. |
| `--section-pad-main` | 96px | 128px | Default desktop section padding. |
| `--section-pad-large` | 128px | 200px | Feature heroes, page-end conversion sections. |
| `--section-pad-page-top` | 192px | 240px | Above-the-fold hero only. |

The Min and Max columns above are the values at the 320px and 1440px viewport anchors. The clamp min is the 320px-anchor floor; any mobile reduction is a separate `@media` override, not a relaxation of the clamp min. The correct implementation for `--section-pad-main`:

```css
:root {
  --section-pad-main: clamp(96px, calc(96px + 32 * (100vw - 320px) / 1120), 128px);
}
@media (max-width: 480px) {
  :root { --section-pad-main: 56px; }
}
```

Apply the same `clamp()` pattern (per §11) to `--section-pad-small`, `--section-pad-large`, and `--section-pad-page-top`. Use the mobile-floor `@media` override only on major section-padding tokens, and only when the 320px-anchor floor is too generous for the narrow-mobile content density.

## §11.4 Spacing scale

Use a single shared spacing scale across the system. Express in rems; convert to pixels with a 16px root.

| Token | Value | Usage |
|---|---:|---|
| `--sp-0-25` | 4px | Hairline gaps, icon-to-label spacing. |
| `--sp-0-5` | 8px | Inline icon spacing, badge padding-x. |
| `--sp-0-75` | 12px | Compact card padding, list-item gap. |
| `--sp-1` | 16px | Paragraph margin-block, default gap. |
| `--sp-1-5` | 24px | Card inner gap, marginalia row padding-top. |
| `--sp-2` | 28–32px clamp | Card padding default. |
| `--sp-2-5` | 32–40px clamp | Section-internal gap. |
| `--sp-3` | 40–48px clamp | Heading-to-body gap on major headings. |
| `--sp-4` | 52–64px clamp | Marginalia row gap, hero header-to-tile gap. |
| `--sp-5` | 64–80px clamp | Hero-to-first-section gap. |
| `--sp-6` | 72–96px clamp | Cross-section breathing room. |

## §11.5 Editorial vertical rhythm

Use exact pixel margins for long-form prose. Do not vary these per page.

| Element | Margin |
|---|---|
| h1 (page title) | `96px 0 48px` |
| Metadata row to body | `24px` bottom on metadata, `24px` top on body |
| Paragraph to paragraph | `16px 0` |
| h2 (section) | `32px 0 8px` |
| Ordered-list item | `12px` bottom |

## §11.6 Grid

Use a 12-column grid above 700px viewport. Drop to 2 columns below 700px. Default gutter is 32px on both axes.

| Layout Pattern | Column Span |
|---|---|
| Editorial header H1 | 1–6 |
| Editorial body | 7–12 (or centered 640px within the full row) |
| Featured grid hero | 1–9 |
| Featured grid side stack | 10–13 |
| Documentation content | 1–10 |
| Documentation sticky sidebar | 11–13 (hidden below 700px) |

## §11.7 Border-radius scale

| Token | Value | Used For |
|---|---:|---|
| `--radius-xs` | 4px | Tags, badge corners, dropdown-item highlight. |
| `--radius-sm` | 8px | Buttons, small inputs, hairline-pill tags. |
| `--radius-md` | 12px | Pill-tab inner button, card-illustration tiles, modal cards. |
| `--radius-lg` | 16px | Pill-tab outer strip, card outer, editorial illustration tile. |
| `--radius-xl` | 16–24px clamp | Major card outer; primary card promo. |
| `--radius-2xl` | 16–32px clamp | Largest hero panels, conversion card. |

Reserve `--radius-2xl` at its top of the clamp (32px) for the conversion card only.

Long-form legal and documentation pages use **zero radius**. Structure relies on whitespace and hairlines instead of boxes.

## §11.8 Shadows

Use shadows sparingly. The default state of every card is `box-shadow: none` with a 1px hairline border doing the figure/ground work.

| Pattern | Shadow Stack | Use For |
|---|---|---|
| Soft floating card | 4-layer low-opacity stack | Conversion card on principal light ground. |
| Hover "shoulder" ring | `0 0 0 1px <button-bg>` on hover only | Button hover state. |
| Faint elevation | `0 1px 2px color-mix(in srgb, var(--role-text-primary) 4%, transparent), 0 1px 1px color-mix(in srgb, var(--role-text-primary) 2%, transparent)` | Application-shell stat cards. |
| Modal lift | `0 12px 24px color-mix(in srgb, var(--role-text-primary) 15%, transparent)` | Centered dialog. |

The conversion-card 4-layer stack:

```css
.card-floating {
  box-shadow:
    0 4px  24px 0 color-mix(in srgb, var(--role-text-primary) 1.57%, transparent),
    0 4px  32px 0 color-mix(in srgb, var(--role-text-primary) 1.57%, transparent),
    0 2px  64px 0 color-mix(in srgb, var(--role-text-primary) 1.18%, transparent),
    0 16px 32px 0 color-mix(in srgb, var(--role-text-primary) 1.18%, transparent);
}
```

Long-form pages use no shadows. Editorial and documentation surfaces rely on a single hard 1px rule between the metadata row and the body to mark figure/ground.

## §11.9 Border weights

| Weight | Use For |
|---|---|
| `0.5px` | Conversion-card outer border at low alpha; secondary-button border at low alpha; editorial side-item bottom hairlines. |
| `1px` | Default card hairline; list-row separator; metadata-to-body hard rule; form-field border. |

Use the 0.5px weight via `1px solid rgba(<ink>, 0.15–0.3)` rather than `0.5px solid`. Browsers paint the alpha-thinned 1px more consistently than a literal subpixel border.

## Known gaps

- §11.3 mobile-floor `@media` override is illustrated only for `--section-pad-main` (56px at `max-width: 480px`). The mobile floor for `--section-pad-small`, `--section-pad-large`, and `--section-pad-page-top` is not specified — apply the same `clamp()` pattern, but explicit floor values for those tokens are undefined.
- §11.4 spacing tokens `--sp-2` through `--sp-6` are listed with clamped ranges (e.g., "28–32px clamp") but the viewport anchors for those clamps are not specified; readers should apply the §11.1 320 → 1440 anchors by default.
- §11.8 shadow patterns reference `<button-bg>` and `<ink>` as placeholders not pinned to specific role tokens. The mapping to `--button-primary-bg` / `--text-primary` (or equivalents) is implied but not stated.
- §11.9 alpha range "0.15–0.3" leaves the exact alpha unstated per use case.
