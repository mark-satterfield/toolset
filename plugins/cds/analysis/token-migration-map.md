# Token Migration Map — App-Surface Capture Vocabulary → Semantic Roles (Ruling 7)

Companion to `model-mapping.md` §5 ruling 7. Every captured token, CSS variable, and raw Tailwind class used by the app-surface components in `reference/components.md` and the cross-context compositions in `skills/compose-app-surface/reference/app-shapes.md` is re-expressed here against the semantic role set (colors) or the geometry/motion token vocabulary (dimensions, curves). The new library entries under `reference/libraries/components/` bind only the right-hand column. Captured tokens with no defensible semantic equivalent are NOT mapped — they are listed under **Role gaps** at the end, for a YAML-level decision.

Calibration values (the pixel/color measurements of the captured product) are recorded in each component entry's body as "calibrates to …" notes, per the FORMAT dimension rule.

## Map

| Captured token / class | Semantic role or geometry/motion token | Components using it |
|---|---|---|
| `--bg-000` / `bg-bg-000` | `--surface-raised` | list-filter (wrapper ground), editor-card (card ground), account-row (avatar ground) |
| `--bg-200` | `--surface-raised` | field-group-form (input ground) |
| `--bg-300` / `bg-bg-300` | `--surface-raised` (per ruling 17: stat card already binds `--surface-raised`; the tile's `--bg-300` names the same ground) | stat-card (tile ground) |
| `--bg-400` / `hover:bg-bg-400` | `--surface-tertiary` (hover-step ground; see Role gaps: hover step) | left-rail (inactive-row hover), account-row (hover) |
| `--bg-500` | `--surface-tertiary` | left-rail (active-row pill, stated in both vocabularies at source) |
| `bg-fill-field` | `--surface-raised` as the control-field fill (see Role gaps: translucent field fill) | filter-chip, period-picker |
| `bg-surface-popover` | `--surface-raised` (see Role gaps: popover-surface step) | filter-chip (focus ground), period-picker (focus ground) |
| `--text-100` / `text-text-100` | `--text-primary` | filter-chip, period-picker, stepper, list-filter, identifier-row, editor-card, setting-card, workspace-switcher, account-row, left-rail |
| `--text-200` / `text-text-200` | `--text-secondary` | identifier-row (label), field-group-form (field label), account-row (avatar ink), left-rail (inactive ink) |
| `--text-300` / `text-text-300` | `--text-tertiary` (see Role gaps: two-step muting) | editor-card (role badge), setting-card (body), left-rail (section headers), account-row (caret) |
| `--text-500` / `text-text-500` / `placeholder:text-text-500` | `--text-tertiary` (see Role gaps: two-step muting) | filter-chip (label), period-picker (label), stepper (meta, pending ink), list-filter (placeholder), editor-card (placeholder, helper), grouped-checkbox-tree (code identifier), workspace-switcher (caret), account-row (role line) |
| `--border-200` / `hover:border-border-200` | `--border-strong` (hover/emphasis border step) | list-filter (hover border), project-picker-gallery (card hover border) |
| `--border-300` / `border-border-300` / `text-border-300` | `--border-subtle` | filter-chip, period-picker (divider spans), stepper (pending circle, connector), list-filter, editor-card, setting-card, field-group-form, destructive-zone, setting-card-with-destructive-sub-row, workspace-switcher, account-row, project-picker-gallery (card rest border) |
| `--border-danger` | `--error-text` (invalid-field border, per the standard text-input error contract) | field-group-form |
| `shadow-field-ring` | hairline box-shadow ring in `--border-subtle` (ring mechanism, border role) | filter-chip |
| `shadow-field-hover` | box-shadow ring in `--border-strong` | filter-chip |
| `shadow-field-invalid` | box-shadow ring in `--error-text` | filter-chip |
| `shadow-focus` | `--focus-ring` (foundation focus-ring contract, accessibility.md §18.2) | filter-chip, setting-card (switch focus) |
| `accent-pro` (list-filter focus ring pairing) | `--focus-ring` | list-filter |
| `--accent-100` / `focus:border-accent-100` | `--focus-ring` (input-focus signal, expressed as a border-color shift in the entry) | editor-card |
| `--brand-000` / `[&_a]:text-brand-000` | `--accent-primary` (inline-link accent) | setting-card (body links) |
| `--danger-100` | `--button-destructive-bg` (the destructive fill role, which the destructive-button entry declares as its binding) | kebab-menu (destructive item ink), destructive-button, destructive-zone, setting-card-with-destructive-sub-row |
| `--success-100` | `--status-positive-bg` (complete-state fill) | stepper (complete circle) |
| white checkmark glyph over `--success-100` | `--text-inverse` (nearest ink role — no dedicated on-status ink role exists; calibrates to white over the positive fill) | stepper (complete-state checkmark) |
| `--switch-track` | `--surface-tertiary` (switch OFF track, per the canonical switch spec) | toggle-switch, setting-card |
| `--switch-track-hover` | `--surface-tertiary` theme-bound hover shade (see Role gaps: hover step) | toggle-switch, setting-card |
| `--fill-accent` / `data-[checked]:bg-fill-accent` | `--switch-active-bg` | toggle-switch, setting-card |
| `--fill-accent-hover` | `--switch-active-bg` theme-bound hover shade (see Role gaps: hover step) | toggle-switch, setting-card |
| `bg-switch-knob` | `--surface-raised` (thumb fill, per the canonical switch spec) | toggle-switch, setting-card |
| `--cds-switch-h` / `h-switch` / `w-[calc(var(--cds-switch-h)*1.8)]` / `size-[calc(var(--cds-switch-h)-4px)]` / `translate-x-[calc(var(--cds-switch-h)*0.8)]` | `--switch-height` geometry token with derivations: track width = 1.8 × h; thumb = h − 4px; travel = 0.8 × h; 2px inset padding. Size variants `compact` (calibrates 18–20px) and `regular` (calibrates 24px → 43×24 track); render proof is the final arbiter per ruling 16 | toggle-switch, setting-card |
| `h-control` (32px) | `--control-height-compact` geometry token (calibrates to 32px) | filter-chip, period-picker, destructive-button (`destructive-inline` variant), setting-card-with-destructive-sub-row |
| `h-9` (36px wrapper) | `--control-height` geometry token (calibrates to 36px; the destructive button's 36px primary height is the same step) | list-filter, destructive-button |
| 44px group-summary row / 40px tool row / 40px dropdown-item min-height / 36px rail row (`h-9`) | list-row density tokens (layout.md §11.11): `--list-row-standard` (40px), `--list-row-compact` (36px); comfortable calibrates 44px | approval-mode-permission-control, kebab-menu (menu items), dropdown-panel, left-rail |
| `rounded` / `rounded-lg` (8px) | `--radius-sm` (8px) | filter-chip, period-picker, list-filter, editor-card, account-row, button base (body-2 size), destructive-button, inverted-pill-badge |
| `rounded-md` (6px) | `--radius-xs` (calibrates to 6px; see Role gaps: 6px radius step) | kebab-menu (trigger), identifier-row (copy button), workspace-switcher, account-row (avatar), editor-card (trailing actions) |
| `rounded-xl` (12px) | `--radius-md` (12px) | stat-card, setting-card, code-block |
| `rounded-[0.6rem]` (9.6px) | `--radius-md` (calibrates to 9.6px at the captured surface; ladder default 12px) | field-group-form (input radius), auth-primary-cta, button base (body-3 size), text-input |
| 16px card radius | `--radius-lg` (16px) | dialog |
| `rounded-full` | fully-rounded pill (shape statement, no token needed) | toggle-switch, stepper (circles) |
| `border-0.5` (0.5px borders) | hairline: `1px solid --border-subtle` with alpha thinned in the role binding (layout.md §11.9 — `1px solid rgba(ink, 0.15–0.3)` instead of literal sub-pixel) | editor-card, setting-card, setting-card-with-destructive-sub-row, account-row (avatar border), editorial-featured-card (bottom border) |
| `border-1.5` (1.5px current-step border) | emphasis border in `--text-primary` (calibrates to 1.5px; see Role gaps: emphasis border weight) | stepper |
| `p-4` (16px), `p-8` (32px), `p-3 pt-9` (12/36px), `px-3 py-2` (12/8px), `pl-sm`/`pr-sm` (8px), `gap-1.5` (6px), `gap-2` (8px), `gap-3` (12px), `gap-x-5` (20px), `gap-6` (24px), `gap-12` (48px), `mt-1` (4px), `pt-6` (24px) | spacing-scale references where a step exists (`--sp-2` = 32px, `--sp-1-5` = 24px, `--sp-1` = 16px, `--sp-0-75` = 12px, `--sp-0-5` = 8px, `--sp-0-25` = 4px — the fixed sub-`--sp-2` steps per layout.md §11.4); remaining small intra-component values are component geometry with calibration values (6, 20, 36, 48px — 48px is not a fixed step; `--sp-3` is a 40–48px clamp) | filter-chip, period-picker, stepper, list-filter, identifier-row, editor-card, setting-card, stat-card, kebab-menu, destructive-zone, grouped-checkbox-tree, field-group-form |
| `mr-[3px]` (trigger caret trailing margin) | derivation `calc(0.75 × var(--sp-0-25))` (calibrates to 3px) | workspace-switcher (trigger caret) |
| `max-w-lg` / `max-width: 32rem` (2-col row cap) | `--column-field-measure` (geometry.columns.field-measure, 512px; layout.md §11.2) | field-group-form, identifier-row (value truncation cap), settings-form (2-col row cap) |
| 208×72px field cells / 96px postal basis | natural flex sizing (no fixed basis); cell height derives from input + label + gap; calibrates to 208×72px and 96px at the reference viewport (audit §3.1) | field-group-form |
| 254×176 / 242×176 / 210×144, `max-w-[500px]`, `flex-1`, `min-w-30` | natural flex sizing: `flex-1` up to a max-width cap (calibrates to 500px); frames calibrate to the listed W×H at the reference viewport (audit §3.1) | stat-card |
| 69px / 81px+ editor-card heights | derivation: top pad + n × line-height + bottom pad (calibrates to 69px single-line, 81px+ multi-line) | editor-card |
| `--modal-width` (520px) | `--modal-width` geometry token (kept; calibrates to 520px), cap re-expressed as `calc(100vw - 2 × --sp-1)` | modal-with-form |
| 256px rail / 56px icon rail / 320px info panel / 280px list column / 320px form sidebar / 64px bottom strip (app-shell pane widths) | `--app-shell-rail-width`, `--app-shell-mini-rail`, `--app-shell-info-panel`, `--app-shell-list-column`, `--app-shell-form-sidebar`, `--app-shell-bottom-strip` — geometry tokens (YAML `geometry.components.app-shell-rail` / `geometry.components.app-shell`; layout.md §11.10) | shells A1–A5, left-rail |
| 16px mini-rail icons / 24px vertical icon gap | `--icon-size-app-rail` (imagery.md §16.1 icon scale) + `--sp-1-5` gap | A4 (outer rail) |
| detail-viewport inner-card cap 960–1100px | floor is `--column-medium`; the 1100px upper bound is A4's own determination (calibration value in the entry) | A4 (detail viewport) |
| `text-body` / `text-sm` (14px) | body compact scale (type-scale reference; calibrates to 14px) | filter-chip, period-picker, stepper, identifier-row, editor-card, setting-card body, field-group-form labels |
| `text-xs` (12px) | caption scale (calibrates to 12px) | stepper (number, meta), list-filter (input), editor-card (helper), workspace-switcher, account-row, grouped-checkbox-tree (code id) |
| `text-lg font-medium` (18px / 510) | heading scale step + variable-axis weight per implementation.md §6.4 (calibrates to 18px / weight 510) | setting-card (title) |
| weight 460 (destructive label) | variable-axis weight per implementation.md §6.4 (calibrates to 460) | destructive-button |
| `font-sans` / `font-ui` | `--typeface-sans` | filter-chip, period-picker, stepper, list-filter, editor-card, field-group-form |
| `font-mono` | `--font-mono` | stepper (meta), identifier-row (value), grouped-checkbox-tree (code identifier) |
| `size-4` (16px glyph), `size-5`/20×20 glyph, 32×32 icon button (`w-8 h-8`) | icon scale (imagery.md §16.1): 20×20 glyphs are the `--icon-viewbox-md` drawing grid; 16px glyphs and 32×32 icon buttons remain component geometry with calibration values (≥44×44 for WCAG 2.5.5 AAA hosts) | kebab-menu, identifier-row, editor-card, list-filter, workspace-switcher, account-row |
| 30×30 read-more SVG arrow | `--icon-viewbox-lg` drawing grid (imagery.md §16.1), rendered at grid size (calibrates to 30×30px) | related-rail |
| kebab glyph dots (2px diameter, 4px between centers) | ratios of the `--icon-viewbox-md` drawing grid: dot diameter 1/10 of the grid, dot-center spacing 1/5 (calibrate to 2px and 4px on the 20-unit grid) | kebab-menu (trigger glyph) |
| `duration-fast` | `--duration-200` interaction-scale step (calibrates to the fast transition) | filter-chip |
| `duration-snap` | `--duration-200` (the canonical 200ms switch thumb slide) | toggle-switch, setting-card |
| `transition-colors` (150ms `cubic-bezier(0.4, 0, 0.2, 1)`) | color transition over 150ms `--ease-in-out` (calibrates to that curve) | list-filter, editor-card, left-rail, workspace-switcher, account-row |
| `ease-overshoot` | no mapping — see Role gaps | setting-card switch (thumb slide) |
| `min-[1400px]` / `2xl` (1536px) label/meta reveal thresholds | very-wide viewport thresholds outside the responsive.md §17.1 ladder; kept as calibration values (1400px, 1536px) in the entry | stepper |
| `can-focus` | the foundation focus-ring application mechanism (`:focus-visible` → `outline: 2px solid var(--focus-ring); outline-offset: 2px`) | list-filter, kebab-menu |
| `hide-focus-ring` (+ wrapper `outline-offset: 2px`) | focus-ring delegation: suppress the inner control's ring, paint the foundation ring on the wrapper | workspace-switcher |
| `outline-none` (inner trigger button) | focus-ring delegation: suppress the inner trigger's own `:focus-visible` outline, paint the focus treatment (ground step + `--focus-ring`) on the wrapper — stated as an explicit behavior contract in the entry because `cds-reset` deliberately does not set `outline: none` | filter-chip |
| `motion-reduce:transition-none` | the global `prefers-reduced-motion: reduce` gate (motion.md §15.5) | toggle-switch, setting-card |
| `data-[disabled]` / `disabled:opacity-50 disabled:pointer-events-none` | shared disabled contract: HTML `disabled` + `opacity: 0.5`, `cursor: not-allowed`, `pointer-events: none` | filter-chip, period-picker, list-filter, editor-card, toggle-switch, kebab-menu (trigger) |
| `data-[checked]` / `data-state="true|false"` / `data-[state=open]` | state mirrors of `aria-checked` / `aria-expanded` (kept as host styling hooks; ARIA is authoritative) | toggle-switch, setting-card, account-row |
| `cds-reset` | defined as a utility component: `libraries/components/cds-reset.md` (see below) | filter-chip, period-picker, toggle-switch, setting-card (switch), app-surface skeletons generally |

## cds-reset decision

The capture used `cds-reset` without ever defining it (audit, ref-components). Chosen resolution: **define it properly as a utility component entry** (`reference/libraries/components/cds-reset.md`) rather than mapping it to an existing mechanism — no existing foundation mechanism performs host-cascade neutralization. The entry fixes its declaration (box/ground/type neutralization via `all`-scoped properties, `appearance: none`, no `outline: none` so the foundation focus ring survives) and states that `generate-stylesheets` emits it once in `components.css`.

## Role gaps

Captured tokens whose distinction the semantic role set cannot express. Each is mapped above to its nearest role for migration continuity, but the lost distinction needs a YAML-level decision — no new roles are invented here.

| Gap | Captured evidence | Nearest role used meanwhile |
|---|---|---|
| **Translucent control-field fill.** The capture paints control grounds as a translucent wash (`color(srgb 1 1 1 / 0.1)` over the dark sub-surface) — an overlay fill, not an opaque surface. `--surface-raised` is opaque by definition. | `bg-fill-field` (filter-chip, period-picker) | `--surface-raised` with a calibration note |
| **Popover-surface step.** The capture distinguishes the rest-state field fill from a focus/open-state opaque popover surface. Mapping both to `--surface-raised` collapses the step. | `bg-surface-popover` vs `bg-fill-field` (filter-chip, period-picker) | `--surface-raised` |
| **Hover-step grounds.** The capture has dedicated hover shades one step off the rest ground (`--bg-400` vs `--bg-500`; `--switch-track-hover`; `--fill-accent-hover`). The semantic set has no "hover shade of role X" convention; entries currently say "steps one shade within the same role's theme binding". | `hover:bg-bg-400`, `--switch-track-hover`, `--fill-accent-hover` | `--surface-tertiary` / `--switch-active-bg` with a theme-binding note |
| **Two-step text muting.** The capture distinguishes body-muted ink (`--text-300`) from placeholder/faint ink (`--text-500`); the semantic set ends at `--text-tertiary`, collapsing both. | `--text-300` vs `--text-500` (editor-card, setting-card, filter-chip labels, placeholders) | `--text-tertiary` for both |
| **Overshoot easing.** The setting-card switch thumb uses an overshoot curve; the motion foundation ships no overshoot easing (§15.1's set is in/out power and expo curves). The canonical switch spec's 200ms slide carries no curve requirement, so entries use `--duration-200` with the default ease. | `ease-overshoot` | none (default ease) |
| **6px radius step.** Icon buttons and avatar boxes sit at 6px, between `--radius-xs` (4px) and `--radius-sm` (8px). | `rounded-md` on kebab trigger, copy button, workspace switcher, avatars | `--radius-xs` with a 6px calibration note |
| **Emphasis border weight.** The stepper's current-step circle uses a 1.5px border; layout.md §11.9's weight ladder is 0.5px (as alpha-thinned 1px) and 1px only. | `border-1.5` (stepper) | stated as an emphasis-weight border with a 1.5px calibration |
| **Very-wide reveal breakpoints.** 1400px and 1536px thresholds sit outside the responsive.md §17.1 breakpoint ladder (480/700/1024). | `min-[1400px]`, `2xl` (stepper) | kept as calibration values in the entry |

## Page-types migration decisions

Token decisions made while re-expressing `reference/page-types.md` into the library entries for the landing, editorial, docs, and auth families.

| Source value | Semantic role or token expression | Entries binding it |
|---|---|---|
| Auth-card type specs (headline 56px/330, button label 16px/500, OR divider 12px/400, legal blurb 14px/400, input label / required asterisk) | The typography.md §13.6 Authentication-card-scale role names (Marketing-headline-outside-card, Button-label, OR-divider, Legal-blurb, Input-label, Required-asterisk); `conversion-auth.md` declares `register.type_scale: authentication-card` | conversion-auth, x2-conversion-card |
| Docs ordered list `Editorial Serif 17px / 400 / 23.8px` (page-types.md:384) | Declared role departure: Body 2 size, weight 400, line-height `--lh-140` (calibrates to 23.8px) — no §13.5 role defines 400-weight serif list text; minting a role is a YAML-level decision | documentation, d2-doc-body |
| Docs outer gutter 316px per side | `--docs-outer-offset` intrinsic geometry token (layout.md §11.2) | docs shell, documentation |
| Docs h2 margin `32px 0 8px` | `calc(2 * var(--sp-1)) 0 var(--sp-0-5)` per layout.md §11.5 | documentation |
| Editorial h2 margin `1.5rem/2rem 0 0.5rem 0` | `var(--sp-1-5)`/`calc(2 * var(--sp-1))` 0 `var(--sp-0-5)` 0 (calibrates to 24px/32px 0 8px 0) | editorial-detail |
| Required-asterisk 4px left margin; provider-logo 8px label gap | `--sp-0-25` / `--sp-0-5` with calibration notes | conversion-auth, x2-conversion-card |
| Column-header `letter-spacing: 0.15px` | Carried by the §13.5 Caption role itself; no per-entry restatement | resource-index, e8-publication-list |
| Editorial eyebrow weight 500–700 | Body 3 with the `.bold` modifier (the role documents the `.bold`→700 path and the 500–700 eyebrow range) | editorial-detail, e1-article-header |
