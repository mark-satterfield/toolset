# Layout

Geometry — the spacing scale, radius scale, section-padding scale, and container widths — is a **configurable element set**, defined in the elements YAML's `geometry:` block (a first-class peer to `color_catalog` and `motion`, resolved at `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`). The values below are the **canonical defaults the shipped YAML encodes**, plus the scaling rules and rationale that govern them. `generate-stylesheets` sources every geometry token from the YAML `geometry:` block — not from this prose — and emits each as a CSS custom property in `tokens.css`; component classes in `components.css` consume those tokens, so the design system (not any page) owns sizing. This file is the source of *meaning* (what each scale step is for, the interpolation law); the YAML is the source of *value*.

What is **structurally fixed** (not a per-project value, but the law the values obey): the §11.1 linear-interpolation form, the two viewport anchors (320 / 1440), the grid column model (§11.6), and the role-not-color discipline. Every surface — marketing, editorial, application, conversion, documentation — resolves layout against the same scales; a surface chooses *which* container/padding token it uses, it does not invent a one-off value in a page style block (see `compliance.md` §23 — page-block overrides of system-defined geometry are an audit violation).

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

## §11.2 Container widths and reading columns

A surface's width comes from one of two distinct token families, and conflating them is what makes a section render narrower than the page:

- **Section wrappers** (`geometry.containers`, emitted `--container-{key}`) are the screen-wide block ground. A section wrapper's `max-width` is **≥ the page width — never below it**: a section either matches the page width or goes full-bleed.
- **Inner reading columns** (`geometry.columns`, emitted `--column-{key}`) cap a **single** content block — one text column, one card — *inside* a page-width section. A reading column is applied to a child element, **never to the section wrapper**.

A surface **chooses a container token** for its wrapper; it does not hardcode a `max-width` in a page style block. Fixed widths belong to individual elements, not to screen-wide containers.

**Section wrappers** (`--container-{key}`)

| Surface class | Token | Width |
|---|---|---:|
| Marketing | `--container-marketing-primary` | 1440px — the page width; the default `.u-container` |
| Editorial / long-form | `--container-editorial` | 1400px |
| Full-bleed | `.u-container-full` | `max-width: none` (≥ page width) |

**Inner reading columns** (`--column-{key}`, applied to one block inside a page-width section — never to the wrapper)

| Token | Width | Use for |
|---|---:|---|
| `--column-wide` | 1192px | the widest single content block |
| `--column-medium` | 960px | a centered single column or quote block |
| `--column-reading` | 640px | long-form body type (the `.u-reading` column) |
| `--column-field-measure` | 512px | a compact field/value measure — a 2-col form row or a truncated identifier value |

**Element widths** (`geometry.elements`, emitted `--element-{key}`) — the fixed width of an individual element. An element width is never applied to a section wrapper.

| Token | Width | Element |
|---|---:|---|
| `--element-conversion-card` | 448px | The conversion card. Fixed on every breakpoint; the surrounding ground reflows. |

`--container-conversion-card` is emitted as a compatibility alias of `--element-conversion-card`; both resolve to the same value, and new consumers use the `--element-` name.

**Documentation outer offset** (`--docs-outer-offset`): the fixed gutter a long-form documentation page holds on each outer side at wide-desktop widths. An intrinsic geometry default — it is a standalone design choice, not a derivation of the container or column scales — calibrated to **316px**. YAML-overridable like every geometry token.

Application-shell pane widths are component-level geometry tokens (§11.10), not containers.

**Utility classes** (emitted into `components.css`):

```css
/* Section wrapper. Default is page width; a wrapper is never narrower. */
.u-container      { max-width: var(--container-marketing-primary); margin-inline: auto;
                    /* Min 32px, Max 64px, middle term per §11.1 */
                    padding-inline: clamp(32px, calc(32px + 32 * (100vw - 320px) / 1120), 64px); }
.u-container-full { max-width: none; }                 /* full-bleed, ≥ page width */
/* Inner reading column — lives on a child, never on the section wrapper. */
.u-reading        { max-width: var(--column-reading); margin-inline: auto; }
```

**The law:** a section-level container's `max-width` is **≥** the page width. `--column-*` measures apply to a single inner content block, never to a section wrapper.

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

The mobile floor is declared in the YAML as the token's `mobile_floor` (e.g. `geometry.section_padding.main.mobile_floor: { max_width: "480px", value: "56px" }`). `generate-stylesheets` emits it by re-declaring the token at `:root` inside `@media (max-width: <max_width>)`, so every consumer of `var(--section-pad-main)` inherits the floor with no per-component media query. Any geometry token may carry a `mobile_floor` the same way (e.g. the topbar bar height, §components).

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

Long-form prose margins derive from the spacing scale (§11.4). Do not vary these per page.

| Element | Margin |
|---|---|
| h1 (page title) | `calc(6 * var(--sp-1)) 0 calc(3 * var(--sp-1))` — calibrates to 96px 0 48px |
| Metadata row to body | `var(--sp-1-5)` bottom on metadata, `var(--sp-1-5)` top on body — calibrates to 24px |
| Paragraph to paragraph | `var(--sp-1) 0` — calibrates to 16px 0 |
| h2 (section) | `calc(2 * var(--sp-1)) 0 var(--sp-0-5)` — calibrates to 32px 0 8px |
| Ordered-list item | `var(--sp-0-75)` bottom — calibrates to 12px |

## §11.6 Grid

Use a 12-column grid at the tablet breakpoint (700px) and above. Drop to 2 columns below the tablet breakpoint. Default gutter is 32px on both axes.

Placements below are inclusive column spans (columns 1–12):

| Layout Pattern | Column Span |
|---|---|
| Editorial header H1 | 1–6 |
| Editorial body | 7–12 (or a centered `--column-reading` column within the full row) |
| Featured grid hero | 1–9 |
| Featured grid side stack | 10–12 |
| Documentation content | 1–10 |
| Documentation sticky sidebar | 11–12 (hidden below the tablet breakpoint) |

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
| Faint elevation | `0 1px 2px color-mix(in srgb, var(--text-primary) 4%, transparent), 0 1px 1px color-mix(in srgb, var(--text-primary) 2%, transparent)` | Application-shell stat cards. |
| Modal lift | `0 12px 24px color-mix(in srgb, var(--text-primary) 15%, transparent)` | Centered dialog. |

The conversion-card 4-layer stack:

```css
.card-floating {
  box-shadow:
    0 4px  24px 0 color-mix(in srgb, var(--text-primary) 1.57%, transparent),
    0 4px  32px 0 color-mix(in srgb, var(--text-primary) 1.57%, transparent),
    0 2px  64px 0 color-mix(in srgb, var(--text-primary) 1.18%, transparent),
    0 16px 32px 0 color-mix(in srgb, var(--text-primary) 1.18%, transparent);
}
```

The 1.57% and 1.18% layer opacities are the shadow scale's intrinsic design choices — the tuned strengths of the stack's four layers, not derivations of any other token.

Long-form pages use no shadows. Editorial and documentation surfaces rely on a single hard 1px rule between the metadata row and the body to mark figure/ground.

## §11.9 Border weights

| Weight | Use For |
|---|---|
| `0.5px` | Conversion-card outer border at low alpha; secondary-button border at low alpha; editorial side-item bottom hairlines. |
| `1px` | Default card hairline; list-row separator; metadata-to-body hard rule; form-field border. |

Use the 0.5px weight via `1px solid rgba(<ink>, 0.15–0.3)` rather than `0.5px solid`. Browsers paint the alpha-thinned 1px more consistently than a literal subpixel border.

## §11.10 Application-shell panes

Application-shell pane geometry is a set of component-level geometry tokens in the YAML `geometry:` block. The values below are the shipped defaults; every token is YAML-overridable.

| Token | Default | Pane |
|---|---:|---|
| `--app-shell-rail-width` | 256px | Primary navigation rail. |
| `--app-shell-mini-rail` | 56px | Icon-only collapsed rail. |
| `--app-shell-info-panel` | 320px | Contextual info/detail panel. |
| `--app-shell-list-column` | 280px | List column of a list-detail layout. Host-resizable between 280px and 320px; the chosen width persists per user. |
| `--app-shell-form-sidebar` | 320px | Form sidebar; compresses to a 280px floor. |
| `--app-shell-bottom-strip` | 64px | Bottom action-strip height. |
| `--app-shell-detail-card-max` | 1100px | Upper bound for inner cards in a detail viewport. |

A pane width applies to the shell pane, never to a section wrapper or content block inside it.

## §11.11 Control and row heights

Interactive-control and list-row heights are component-level geometry tokens in the YAML `geometry:` block. The values below are the shipped defaults; every token is YAML-overridable.

| Token | Default | Use For |
|---|---:|---|
| `--control-height` | 36px | Default inline-control height: toolbar actions, selects, standard-density chips. |
| `--control-height-compact` | 32px | Compact inline controls in dense toolbars and filter strips. |
| `--list-row-standard` | 40px | Default list-row height. |
| `--list-row-compact` | 36px | Dense list rows and rail navigation rows. |
