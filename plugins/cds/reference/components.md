# Components

Component family specifications. Slot definitions, fixed sizing, behavior, and accessibility contracts. Foundational tokens (spacing, motion curves, color roles, type scale) live in `foundations/`; this file references those tokens rather than re-declaring them.

---

## §12.1 Topbar

**Purpose.** A fixed-position desktop topbar that anchors global navigation and conversion CTAs without painting a visible boundary.

**Slot definitions.**
- `logo`: required SVG glyph at the height of the bar; paints via `fill="currentColor"` and inherits `--text-primary`.
- `primary-nav`: required cluster of nav links, right-aligned.
- `conversion-cta`: 1–2 right-aligned conversion actions — typically a tertiary text link followed by a filled primary button.

**Props / variants.**
- `height`: `desktop` (default, 84px) | `mobile-floor` (64px, below 480px viewport).
- `cta-adjacency`: `standalone` (default) | `caret-flush` (asymmetric radius when CTA sits flush against an adjacent dropdown caret).

**Fixed sizing/spacing.**
- `position: fixed; top: 0; z-index: 100`.
- Background = `--nav-bg`, the topbar's dedicated navigation-ground role (a `from_palette: backgrounds` component role). It is bound per theme to the same ground as the section directly beneath it — the page ground, `--surface-primary` — so the nav blends seamlessly into the first section with no seam. The topbar has no standalone color of its own.
- Height = `84px` at desktop widths. Reduce to `64px` below the 480px viewport via a discrete `@media` override (the topbar's only acceptable mobile-floor adjustment). Topbar height is a single value across every surface within a build.
- No bottom border. No drop shadow. The nav blends into the page ground.
- Nav-link type at the small-body sans size (15px), weight 400.
- Primary-action button: 36px height, mapped primary fill, mapped inverse text, 8–10px radius.
- Caret-flush deviation: asymmetric radius `8px 0 0 8px` (left-rounded only) so the right edge meets the caret cleanly.

**Behavior.** Static at rest. The primary-action button uses the same primary button vocabulary as anywhere else on the page (see §14.1).

**Accessibility.**
- Logo: `currentColor` ensures contrast inherits from `--text-primary`.
- Conversion CTAs follow primary button focus contract (see §14.1).
- **Landmark contract:** the topbar host element is a `<header role="banner">` containing a `<nav aria-label="primary">` that wraps `primary-nav` and `conversion-cta`. The logo link sits outside the inner nav so the nav lists only navigational and conversion controls. (WAI-ARIA landmark guidance.)
- **Keyboard contract:** Tab visits the logo, each primary-nav link in source order, then each conversion CTA in source order. Shift+Tab reverses. Nav links and CTAs use the default semantics of `<a>` (Enter activates) and `<button>` (Enter + Space activate). No arrow-key navigation between top-level nav links — the topbar is not a `role="menubar"`; arrow-key cycling is reserved for the dropdown panels that descend from each trigger (§12.2). (WAI-ARIA + HTML spec defaults.)

---

## §12.2 Dropdown panels

**Purpose.** Reveal grouped link lists or grids below a topbar trigger, opened on hover (desktop) or click (touch).

**Slot definitions.**
- `trigger`: required nav link or button carrying `aria-haspopup="menu"` and `aria-expanded`.
- `panel`: required container; structure varies by variant.
- `item`: repeating link or row inside the panel.

**Props / variants.**

| Variant | Panel Width | Use For |
|---|---:|---|
| Flat menu | 200px | 1–4 link lists. |
| Mega panel | 656–864px | Multi-column link grids; centered above multiple trigger columns. |
| Lift-and-scale | 256px | Compact sub-nav menus that need a small entrance affordance. |

**Fixed sizing/spacing.**
- Dropdown items: `min-height: 40px`, `padding: 8px 12px`, `border-radius: 4px`.
- Hover paints the item background `--surface-tertiary` over 100ms.

**Behavior.**
- Flat and mega panels open with `grid-template-rows: 0 → auto` and `opacity: 0 → 1` over 600ms, curve `cubic-bezier(0.16, 1, 0.3, 1)`. The panel grows from zero row-height; do not translate.
- Lift-and-scale panel opens with `transform: scale(0.95) → scale(1)` plus `opacity: 0 → 1` over 200ms, curve `cubic-bezier(0.4, 0, 0.2, 1)`. Set `transform-origin: 50% 0`.
- Item hover background transitions over 100ms.

**Accessibility.**
- Trigger uses `aria-haspopup="menu"` and `aria-expanded` toggling.
- Panel carries `role="menu"`; items carry `role="menuitem"`. (WAI-ARIA APG menu pattern.)
- Tab cycles through visible items.
- Arrow Up / Arrow Down move focus between adjacent menu items; Arrow Down on the last item wraps to the first; Arrow Up on the first wraps to the last. Enter and Space activate the focused item. (WAI-ARIA APG menu pattern.)
- Escape closes the panel and returns focus to the trigger. (WAI-ARIA APG menu pattern.)
- Panel closes on click outside the trigger and the panel itself, on scroll past the trigger, and on Escape. (Common design-system convention.)
- Touch: on touch input the trigger toggles open on first tap and closes on a second tap of the trigger or a tap outside the panel. Hover-to-open is suppressed on touch input (Material / Polaris convention).
- Honor `prefers-reduced-motion: reduce` by replacing the open/close animations with an instant display toggle. (WCAG 2.3.3.)

---

## §12.3 Mobile drawer

**Purpose.** Collapse the desktop topbar into a full-viewport drawer at mobile widths, sharing the same DOM as the topbar.

**Slot definitions.**
- `hamburger`: required trigger button.
- `drawer`: required full-viewport container with masked scrolling content.
- `item`: repeating drawer entry with staggered entrance.

**Props / variants.**
- `state`: `closed` (default) | `open`.
- `motion-mode`: `animated` (default) | `reduced` (instant display toggle under `prefers-reduced-motion: reduce`).

**Fixed sizing/spacing.**
- Drawer: `position: fixed; inset: 0; z-index: 101`.
- Drawer background = `--surface-primary`.
- Hamburger button is 40×40px with a 16×1px top line and an 8×1px bottom line in `currentColor`.
- Hamburger button has an inset 2px focus ring (`outline-offset: -2px`).

**Behavior.**
- Drawer opens with `clip-path: inset(0 0 100%) → inset(0 0 0%)` over 800ms with a `cubic-bezier(<ease-in-out-power3>)` curve, wiping down from the top edge.
- Drawer closes with the reverse animation over 400ms.
- Drawer items stagger in 80ms apart with `animation-delay: calc(320ms + var(--item-index) * 80ms)` to chain after the panel wipe-in.
- Drawer content uses a soft `mask-image: linear-gradient(to bottom, transparent 0%, white var(--container-margin), white calc(100% - var(--container-margin)), transparent 100%)` to fade the top and bottom edges as content scrolls.
- Reduced-motion override: drop all drawer animations to instant display toggle.

**Accessibility.**
- Hamburger button carries an inset 2px focus ring.
- **Hamburger ARIA contract:** `<button type="button" aria-label="Open menu" aria-controls="<drawer-id>" aria-expanded="false">`; `aria-expanded` flips to `"true"` while the drawer is open and `aria-label` updates to `"Close menu"`. (WAI-ARIA APG disclosure pattern.)
- **Drawer role / labelling:** the drawer is a full-viewport takeover, so it is `<div role="dialog" aria-modal="true" aria-label="Site navigation">` wrapping a `<nav>` for the link list. (WAI-ARIA APG modal-dialog pattern.)
- **Focus trap:** when the drawer opens, focus moves to the drawer's first focusable element (typically the close affordance or the first nav item). Tab cycles forward within the drawer; Shift+Tab cycles backward; both wrap at the boundaries. Focus cannot escape to background content. (WAI-ARIA APG modal-dialog pattern.)
- **Keyboard:** Escape closes the drawer and returns focus to the hamburger trigger. Enter and Space on a focused nav item activate the link. (WAI-ARIA APG modal-dialog pattern.)

---

## §12.4 Sticky header

**Purpose.** A header that hides on downward scroll and reappears on upward scroll. Optional. Apply only to editorial surfaces.

**Slot definitions.**
- `header`: required host element carrying the `is-hide-on-scroll` modifier.

**Props / variants.**
- `state`: rest | `is-hidden` (translated off-screen).
- `motion-mode`: `animated` (default) | `reduced` (under `prefers-reduced-motion: reduce`, no transition).

**Fixed sizing/spacing.** Inherits topbar dimensions (see §12.1).

**Behavior.**

```css
.header.is-hide-on-scroll {
  transition: transform 0.3s ease;
}
.header.is-hide-on-scroll.is-hidden {
  transform: translateY(-100%);
}
@media (prefers-reduced-motion: reduce) {
  .header.is-hide-on-scroll { transition: none; }
}
```

The `is-hidden` class is added via JavaScript on downward scroll past the header height and removed on upward scroll.

**Accessibility.** Reduced-motion override drops the transition entirely so the header snaps between states.
- **Focus during hide:** while focus is inside the header (e.g., the user has Tab-walked into a nav link or CTA), the `is-hidden` class is NOT applied — the hide is suppressed until focus leaves the header. This prevents the keyboard user's focused control from being scrolled off-screen, satisfying WCAG 2.4.11 (Focus Not Obscured, AA).
- If the header hides while focus is elsewhere, focus is untouched; the next Tab moves into the next sequential focusable element in the document, which may be off-screen until the user scrolls up to reveal the header. (HTML default focus order.)

**Scroll-direction detection threshold.** Apply a hide threshold of 8px of cumulative downward scroll past the header height before adding `is-hidden`, and reveal on any upward scroll of 4px or more. Debounce scroll handling to one evaluation per animation frame (`requestAnimationFrame`) so the detection cost stays off the main scroll path.

---

## §12.5 App shell left rail

**Purpose.** Three-pane navigation chrome for application-shell page types.

**Slot definitions.**
- `outer-rail`: required column. The icon-rail and list-column collapse into a single 256px column.
- `workspace-switcher`: top of column. See §12.5.1 Workspace switcher for its full spec.
- `section-header`: tertiary-ink labels above grouped rows.
- `item-row`: nav row carrying icon + label.
- `detail-viewport`: required fluid pane filling remaining width.

**Props / variants.**
- `row-state`: rest | `active` (filled-pill selection).

**Fixed sizing/spacing.**
- Rail outer container: `position: fixed; left: 0; top: 0`; `width: 256px`; `height: 100vh` (`h-screen`).
- Rail padding: `12px` on all sides (`px-3 py-3`).
- Rail background: `var(--role-surface-secondary)` (dark elevated rail ground).
- Rail border-right: `0.5px solid var(--role-border-subtle)` (a hairline at low alpha against the dark surface — alpha is encoded in the role binding for dark themes).
- Rail box-shadow: `inset -4px 0px 6px -4px hsl(var(--always-black) / 4%)` at `lg` and above (`lg:shadow-[inset_-4px_0px_6px_-4px_...]`); a plain `shadow-lg` below `lg`.
- Rail `overflow: hidden`.
- Nav-row height: `36px` (`h-9`).
- Nav-row horizontal padding: `8px` (`px-2`). (The active row's left padding inflates to `40px` when an icon slot is reserved — host responsibility, not the component's base.)
- Nav-row gap between icon and label: `12px` (`gap-3`).
- Nav-row border-radius: `8px` (`rounded-lg`).
- Nav-row font: `font-ui`, `font-size: 14px` (`text-sm`), `font-weight: 400`.
- Active-row pill spec: paints the full row at radius `8px` with background `var(--role-surface-tertiary)` (deepest stratification within the theme) and ink `var(--role-text-primary)`. The active row carries `aria-current="page"`.
- Inactive-row rest: transparent ground, ink `hsl(var(--text-200))` (`text-text-200`).
- Inactive-row hover: background `hsl(var(--bg-400))` (`hover:bg-bg-400`), ink `hsl(var(--text-100))` (`hover:text-text-100`).
- Transition on hover (inactive): `transition-colors` — composite of `color`, `background-color`, `border-color`, `text-decoration-color`, `fill`, `stroke` over `150ms cubic-bezier(0.4, 0, 0.2, 1)`.

**Behavior.**
- Active row paints a filled pill at radius `8px` using `bg-bg-500` ground and `text-text-100` ink. No left bar, no border indicator. The fill alone marks the selection.
- Inactive rows are transparent at rest. On hover, the row paints `bg-bg-400` ground and `text-text-100` ink over a 150ms ease transition.
- Active and inactive rows are both `<a>` (anchors) because they navigate — not `<button>`.

**Accessibility.**
- Rail outer is wrapped in `<nav aria-label="Main navigation">`. The nav element carries the landmark; the rail `<div>` it wraps does NOT redeclare a role.
- Active row carries `aria-current="page"`.
- Section headers are visually distinct via tertiary ink (`text-text-300`).
- Focus contract: nav rows expose focus via the foundation focus ring on `:focus-visible` — `outline: 2px solid var(--role-focus-ring); outline-offset: 2px` (foundations/accessibility.md §18.2). The ring paints only for keyboard focus.

**Keyboard.** Rows are `<a>` anchors inside a `<nav>` landmark, not a `role="menu"` — so the contract is standard sequential Tab order, NOT arrow-key navigation. Tab moves to the next focusable row; Shift+Tab to the previous; Enter activates. (WAI-ARIA APG: navigation landmarks do not use arrow-key composite-widget semantics — that pattern is reserved for `role="menu"`, `role="tablist"`, `role="listbox"`, etc.)

**Reduced motion.** Honor `prefers-reduced-motion: reduce` by suppressing the `transition-colors` hover transition; hover state swaps instantly. (WCAG 2.3.3.)

**Icon-slot reservation.** Rows that prefix an icon glyph inflate left padding to `40px` (`pl-[40px]`) to reserve the icon column; the icon-to-label gap stays `12px` (`gap-3`). Rows without an icon use the base `8px` (`px-2`) horizontal padding. The reservation is a per-row modifier, not a change to the base row contract — apply it consistently to every row in a section so the labels align.

---

## §12.6 Skip links

**Purpose.** Keyboard-accessible jump targets at the top of the body that snap into view on focus.

**Slot definitions.**
- `skip-link`: repeating `<a>` element with `class="skip-link"` and an in-page anchor.

**Props / variants.**
- `state`: rest (off-screen) | `:focus` (snapped into view).

**Fixed sizing/spacing.**
- Off-screen position: `top: -1000px; left: 50%; transform: translateX(-50%)`.
- Padding: `12px 24px`.
- Border-radius: `0 0 var(--radius-md) var(--radius-md)`.
- Font-weight: 700.
- Text decoration: none.

**Behavior.**

```html
<a href="#main-content" class="skip-link">Skip to main content</a>
<a href="#footer" class="skip-link">Skip to footer</a>
```

```css
.skip-link {
  position: absolute;
  top: -1000px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  background: var(--surface-primary);
  color: var(--text-primary);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  font-weight: 700;
  text-decoration: none;
}
.skip-link:focus {
  top: 0;
}
```

**Accessibility.**
- Hidden off-screen at rest; snaps to `top: 0` on focus so the first Tab from the document reveals it.
- Uses semantic `<a>` elements with in-page hash anchors.
- **Stacking:** focused skip links use `z-index: 101`, one step above the fixed topbar's `z-index: 100` (§12.1), so the link is never visually occluded when it snaps into view. (WCAG 2.4.1 — Bypass Blocks.)
- **Focus styling:** the skip-link state change is `:focus` (not `:focus-visible`) because keyboard users are the sole population that surfaces this control — the positional snap IS the focus indicator, and it must paint for every focus event regardless of input modality. Pair with the foundation focus ring (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`) so the focused link is visually distinct against any page ground. (WCAG 2.4.7, 2.4.11, 2.4.13.)

---

## §12.7 Footer

**Purpose.** Multi-column site footer providing secondary navigation, legal, and social affordances.

**Slot definitions.**
- `columns`: required set of columns. Default columns: Products / Models / Solutions / Platform / Resources / Help / Company / Terms.
- `column-heading`: required per column; `<h3>` semantically.
- `column-link`: repeating link within a column.
- `social-row`: optional row of social icons, single row at the bottom or as a left-aligned column.
- `language-selector`: optional, placed inside a footer column list.
- `legal-trigger`: optional (e.g., "Cookie Settings"), placed inside a footer column list. Not placed in the topbar.

**Props / variants.**
- `ground`: `editorial` (default — `--role-footer-bg` resolved through the editorial theme: a near-black neutral) | `marketing` (binds to the `deep` theme; deepest dark neutral with mid-tone links) | `authentication` (explicit `data-mode="dark"` wrapper that resolves `--role-surface-primary` to absolute black; used only on the conversion page's footer).

**Fixed sizing/spacing.**
- Footer link color = `var(--role-footer-text)`. The two ground variants resolve this role to a brighter neutral on the absolute-black variant and a step deeper on the standard dark variant.
- No underline at rest.
- Footer column heading: smallest body-sans size (12–14px), weight 700, ink at `var(--role-text-tertiary)` (low-contrast cool gray). Semantically `<h3>`; do not nest deeper.

**Behavior.** Hover on a footer link shifts color toward `--text-primary` over 100ms.

**Accessibility.**
- Column headings are `<h3>`-level; do not nest deeper.
- **Landmark:** the footer host element is `<footer role="contentinfo">` — `<footer>` only resolves to the `contentinfo` landmark when it is a direct child of `<body>`; if the footer is nested inside another sectioning element, the explicit `role="contentinfo"` is required. (WAI-ARIA landmark guidance.)
- **Social icon accessible names:** each social icon link carries an `aria-label` naming the destination service (e.g., `aria-label="{Brand} on LinkedIn"` — host project supplies the brand name). The SVG glyph itself carries `aria-hidden="true"` because the link's accessible name carries the semantic. (WAI-ARIA APG link pattern.)
- **Focus styling:** footer links use the foundation focus ring (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`) on `:focus-visible`. Hover-only-style affordances do not satisfy WCAG 2.4.7. (WCAG 2.4.7, 2.4.11.)
- **Social-icon hover:** the icon's `currentColor` glyph shifts from `--role-text-tertiary` toward `--role-text-primary` over 100ms — matching the footer-link hover treatment so the row reads as one consistent hover vocabulary.

---

## §14 Component catalog

The §14 source table provides one row per component family with four facets — Structure (slot composition), Theme Roles Used (token bindings), Interaction Behavior, and Notes (sizing / padding / radius / special rules). The 32 H2s below carry that row data per component. Variants and shared specs across variant families live in §14.1 (button base), §14.2 (auth CTA bloom), and §14.3 (switch active) further down.

---

## §14 Primary button

**Purpose.** Conversion or commit action; the dominant button on its surrounding surface.

**Structure (slots).** Fill + label.

**Theme Roles Used.** `--button-primary-bg`, `--button-primary-text`.

**Behavior.** Hover paints a 1px outer shoulder ring in the fill color over 200ms.

**Sizing / notes.** 40px min-height; 8px radius. Inverts ground with the page's mode (light theme → dark fill; dark theme → light fill). Inherits the rest of the spec from §14.1 Button base — including focus ring, disabled, loading, and tap-target rules.

---

## §14 Secondary button

**Purpose.** Supporting action peer to a primary button on the same surface.

**Structure (slots).** Fill + label.

**Theme Roles Used.** `--button-secondary-bg`, `--button-secondary-text`.

**Behavior.** Hover shifts fill to `--surface-primary`.

**Sizing / notes.** 40px min-height. Inherits remaining base from §14.1 — focus ring, disabled, loading, and tap-target rules included.

---

## §14 Tertiary button

**Purpose.** Quietest action affordance; used inline or as a link-like control.

**Structure (slots).** Border + label.

**Theme Roles Used.** `--button-tertiary-border`, `--text-tertiary`.

**Behavior.** Hover shifts text color to `--text-primary`; border unchanged.

**Sizing / notes.** Transparent fill; hairline border; link-glyph leading. Inherits remaining base from §14.1 — including focus ring, disabled, and the shared transition (`color 0.1s ease, background-color 0.2s, box-shadow 0.2s`).

---

## §14 Destructive button

**Purpose.** A button variant reserved for destructive actions (delete, remove, revoke, irrevocable resets). Visually distinct from primary / secondary via a destructive (red) fill.

**Structure (slots).** Fill + label. Optional leading-icon slot (a warning or trash glyph preceding the label).

**Theme Roles Used.** `--button-destructive-bg` (binds to `--danger-100`), `--button-destructive-text` (binds to `--role-text-inverse`).

**Behavior.** Hover scales the button (subtle `scale-y-[1.015]` paired with a matching `scale-x` factor) rather than re-coloring the fill. Wrapped in a `transition` (default ≈150ms ease). Suppress the scale transform under `prefers-reduced-motion: reduce`.

**Sizing / notes.** `36px` height; width is content-driven via `inline-flex`. Padding `8px 16px`. Border `0` (visual is fill-based). Border-radius `8px`. Font-size `14px`, font-weight `460` (a custom weight via the variable-axis sans face — NOT 500/600), font-family `var(--typeface-sans)`. Label color `var(--role-text-inverse)`. Display `inline-flex` with `items-center justify-center`. Position `relative`, `isolate` (creates a stacking context for the fill layer). Inherits remaining base from §14.1.

**Variant set.**

- `destructive-primary` — solid destructive fill + light label at `36px` height. Reserved for the highest-stakes irreversible action on a settings surface.
- `destructive-inline` — same fill, used inline beside a helper sentence on a setting card. Steps down to a `32px` compact height (`h-control`) so it reads as a denser inline control beside body text; padding tightens to `6px 12px`.

**Interaction states.** `rest` | `hover` | `disabled` (`disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none disabled:drop-shadow-none`) | `confirming` (the confirm-step contract is not part of the button itself — it lives in the surrounding flow). Focus paints the foundation focus ring on `:focus-visible`, but resolves the ring color to the destructive token (`outline: 2px solid var(--danger-100); outline-offset: 2px`) rather than the brand accent, to maintain semantic consistency. (foundations/accessibility.md §18.2.)

The wrapper-zone pattern (hairline-divider section that hosts a Destructive button) is documented in `skills/compose-app-surface/reference/app-shapes.md` under "Cross-context component compositions § Destructive zone".

---

## §14 Pill-tab strip

**Purpose.** Segmented control where one option is active at a time, painted as an inset pill inside an outer strip.

**Structure (slots).** Outer strip + inner buttons.

**Theme Roles Used.** `--surface-tertiary` (strip), `--text-tertiary` (button at rest), `--text-primary` then `--text-inverse` (button active).

**Behavior.** Active button background paints with `currentColor`; inner label inherits inverse ink. Background transition 200ms; color transition 100ms. Active inner text transitions over 500ms via slow color glide.

**Sizing / notes.** Outer radius 16px, inner radius 12px, 4px inner padding.

**Accessibility.** When the strip selects a filter/view that updates content in place without revealing/hiding distinct panels, use `role="radiogroup"` on the outer strip and `role="radio"` with `aria-checked` on each button. When the strip switches between distinct content panels in the same DOM, use `role="tablist"` + `role="tab"` + `aria-selected` + `aria-controls` pointing at the `role="tabpanel"`. Keyboard contract (both patterns): Tab focuses the group once; Arrow Left / Arrow Right move selection between options and wrap at the boundaries; Space or Enter activate when manual-activation is required (tabs that mount expensive content); selection moves with focus when automatic-activation is acceptable (radiogroup behavior). (WAI-ARIA APG tabs and radio-group patterns.)

---

## §14 Feature card

**Purpose.** Marginalia-style content card with a hairline anchor on the left or top edge.

**Structure (slots).** Left or top hairline anchor + content stack.

**Theme Roles Used.** `--border-subtle`, `--text-primary`.

**Behavior.** None at rest.

**Sizing / notes.** Padding `12/16/24/32px` (small / medium / large / x-large variants). Left border is `1px solid --border-subtle` — the marginalia anchor.

**Variant selection.** Use `small` (12px) for dense list-adjacent cards, `medium` (16px) as the default in-flow card, `large` (24px) for standalone feature callouts, and `x-large` (32px) for hero-adjacent cards that anchor a section. Match the variant to the section padding role in foundations/layout.md §11.3 — denser sections take the smaller paddings.

---

## §14 Full promo card

**Purpose.** Bordered card with a transparent fill used for product or feature callouts on landing surfaces.

**Structure (slots).** 1px outer border, transparent fill, content stack inside.

**Theme Roles Used.** `--border-subtle`, `--surface-primary`.

**Behavior.** None at rest.

**Sizing / notes.** Radius `--radius-xl` (resolved in `foundations/layout.md` §11.7), inner padding 32px.

**Behavior / accessibility.** The card is a non-interactive container — focus and hover live on the controls inside (CTA buttons, links). If a host implementation makes the entire card a single interactive surface, wrap the contents in a single `<a>` or `<button>` and apply the foundation focus ring (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`) to the wrapping interactive element on `:focus-visible`. (WCAG 2.4.7, 2.4.11.)

---

## §14 Link card

**Purpose.** A card that links to another page or asset; emphasis on the title.

**Structure (slots).** Title + body + hairline border.

**Theme Roles Used.** `--text-primary`, `--border-subtle`.

**Behavior.** Hover transitions text color over 300ms.

**Sizing / notes.** Title in Editorial Serif at H6 scale.

**Accessibility.** The entire card wraps in a single `<a>` so the focus ring lights the full card, not a sub-element. On `:focus-visible`, paint the foundation focus ring (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`). Hover transitions the title text from `--role-text-primary` toward `--role-text-secondary` over 300ms (matches the spec's existing 300ms transition; secondary is the conventional next-step ink for the hover target).

---

## §14 Pricing card

**Purpose.** A tier card with title + feature list + (typically) a CTA at the bottom.

**Structure (slots).** Title + feature list.

**Theme Roles Used.** `--surface-raised`, `--border-subtle`.

**Behavior.** None at rest.

**Sizing / notes.** 24px padding. Feature list separated by a 1px top border with 24px top padding.

**Tier variants.** `default` — `--surface-raised` ground with a `1px solid --border-subtle` hairline. `featured` — paints a `1px solid --border-strong` outline plus the §11.8 "faint elevation" shadow to lift the emphasized tier one step above its peers; the rest of the geometry is unchanged so tiers align in a row.

**CTA slot.** The bottom CTA is a Primary button (§14.1) on the `featured` tier and a Secondary button (§14.1) on `default` tiers, so the emphasized tier carries the dominant action.

---

## §14 Catalog card

**Purpose.** Grid-item card carrying a label badge plus title/body/meta.

**Structure (slots).** Badge + title + body + meta.

**Theme Roles Used.** `--surface-raised`, `--border-subtle`.

**Behavior.** None at rest.

**Sizing / notes.** Small label badge in the top-left. Card padding `--sp-2` (28–32px clamp, foundations/layout.md §11.4); border-radius `--radius-lg` (16px, §11.7); internal gap between badge, title, body, and meta is `--sp-0-75` (12px). The badge follows the §14 Outline pill badge spec (`0.5rem 0.75rem` padding, 12px caption type).

---

## §14 Editorial featured card

**Purpose.** A featured editorial item — a tinted illustration tile paired with title, dek, and date.

**Structure (slots).** Tinted illustration tile + title + dek + date.

**Theme Roles Used.** `--text-primary`, saturated panel ground.

**Behavior.** Whole-card opacity dims to 0.6 on hover over 200ms.

**Sizing / notes.** Tile aspect-ratio 1:1 for side items, 16:9 for the lead item. SVG centered with `padding: 48–64px`. Title underline at 0.2em offset. Bottom border `0.5px solid --border-subtle`. Saturated panel ground binds to a feature-tile ground role (`--role-tile-ground-1` / `--role-tile-ground-2` / `--role-tile-ground-3`, `from_palette: panels`) — pick a tile number per the page-type rules, never a color.

**Lead-vs-side selection.** The first item in the collection renders as the `lead` (16:9 tile, larger title scale); every subsequent item renders as a `side` item (1:1 tile). When a section shows a single item, it always uses the `lead` treatment.

---

## §14 Application stat card

**Purpose.** In-app KPI / metric card carrying a caption, a display number, and an optional inline action.

**Structure (slots).** Caption + display number + optional inline action.

**Theme Roles Used.** `--surface-raised`, `--text-primary`, `--text-tertiary`.

**Behavior.** None at rest.

**Sizing / notes.** ~12px radius. Display number at 32–40px Primary Sans weight 600–700.

### Dimensions

Two sizes share the same frame contract:

- **Larger variant**: 254×176px (or 242×176 when peer tile widths shrink to fit the row). `display: inline-flex`; `flex-direction: row`; `align-items: center`; `gap: 48px` (`gap-12`); `padding: 16px` (`p-4`); `border: 0`; `border-radius: 12px` (`rounded-xl`); `box-shadow: none`. Classes: `bg-bg-300 inline-flex flex-row rounded-xl p-4 items-center gap-12 flex-1 max-w-[500px]`.
- **Smaller variant**: 210×144px. `display: inline-flex`; `flex-direction: column`; `gap: 8px` (`gap-2`); `padding: 16px 0` (`p-4 px-0` — vertical-only); `border: 0`; `border-radius: 12px`; `box-shadow: none`. Classes: `bg-bg-300 inline-flex flex-col rounded-xl p-4 min-w-30 grow gap-2 px-0`.
- **Row container**: peer tiles sit in `display: flex; gap: 16px` (`flex gap-4`); each tile uses `flex-1` to grow up to a `max-w-[500px]` cap.
- **Background → `var(--role-surface-raised)`** — theme-context dependent. In a dark sub-section the role resolves to a near-black surface; on a light page main the same role resolves to a light surface. There is NO separate `deep` wrapper attribute around these tiles; the dark rendering is the natural resolution of `--role-surface-raised` at this nesting depth in the active theme context.

**Inline-action slot.** The optional inline action is a Tertiary button (§14.1) — the quietest affordance, so it sits beside the display number without competing with it for emphasis. When the action is a per-tile overflow menu, use the §14 Kebab menu instead.

---

## §14 Hero promo card

**Purpose.** Landing-page hero-adjacent promo with a decorative dark sub-panel inside the card.

**Structure (slots).** Title + body + tertiary CTA + decorative dark sub-panel.

**Theme Roles Used.** `--surface-raised`, `--text-primary`, local `deep` wrapper for the sub-panel.

**Behavior.** None at rest.

**Sizing / notes.** Card padding `--sp-2-5` (32–40px clamp, foundations/layout.md §11.4); card radius `--radius-xl` (16–24px clamp, §11.7). The decorative sub-panel uses a local `deep` wrapper, sits at radius `--radius-lg` (16px), occupies the lower or trailing third of the card, and paints the `--accent-heroes` glyph (foundations/motion.md §15.6) via `currentColor` on the near-black ground. The accent glyph is supplied per theme through the `--accent-heroes` slot — do not author per-theme artwork.

---

## §14 Empty-state card

**Purpose.** A card that occupies the location of an absent list/grid and explains the empty state with a glyph, caption, and action.

**Structure (slots).** Glyph + caption + action.

**Theme Roles Used.** `--surface-raised`, `--text-tertiary`.

**Behavior.** None at rest.

**Sizing / notes.** Card padding `--sp-2-5` (32–40px clamp, foundations/layout.md §11.4), content centered. Glyph is a centered `48×48px` tiny line-art SVG in `--text-tertiary`, sitting `--sp-1-5` (24px) above the caption. Caption in tertiary ink at body-2 size. The action below is a Secondary button (§14.1) — empty states offer a recovery action, not a conversion, so the dominant Primary fill is reserved for the populated surface; the button sits `--sp-1` (16px) below the caption.

---

## §14 Marginalia row

**Purpose.** An editorial row pattern with an icon, a content stack at 35ch, and an optional left rail TOC.

**Structure (slots).** Optional left rail + icon + 35ch content stack.

**Theme Roles Used.** `--border-subtle`, `--text-tertiary`.

**Behavior.** None at rest.

**Sizing / notes.** Row gap 64px. Each row: 32px top padding, 1px top border. Header row icon at 24px square; content at `max-width: 35ch`. Optional left rail at 216px width with italic-serif TOC.

**Left-rail active selection.** The rail TOC marks the entry whose row is currently scrolled into the viewport's upper third as active (driven by an `IntersectionObserver`, foundations/motion.md §15.4); the active entry carries `aria-current="true"` and paints at `--text-primary` while inactive entries sit at `--text-tertiary`.

**Responsive behavior.** The left rail is shown only at the tablet breakpoint and above (≥700px, foundations/responsive.md §17.1) where the 12-column grid is active; below 700px the rail is `display: none` and rows fall to a single column at full reading width. The row gap reduces from 64px to `--sp-2-5` (32–40px clamp) below the tablet breakpoint.

---

## §14 Standard text input

**Purpose.** Single-line text input.

**Structure (slots).** Hairline border + light fill + label-via-placeholder.

**Theme Roles Used.** `--surface-raised`, `--border-subtle`, `--text-primary`.

**Behavior.** Border shifts to `--text-secondary` on hover; outline appears on `:focus-visible` only.

**Sizing / notes.** 44px height, 9.6px radius, 12px horizontal padding. Label hidden in favor of placeholder. The 44px height also satisfies WCAG 2.5.5 (AAA) target size.

**Disabled state.** `opacity: 0.5; cursor: not-allowed; pointer-events: none`. The input also carries the HTML `disabled` attribute so it is excluded from form submission and tab order. (Common DS convention.)

**Focus-visible ring.** `outline: 2px solid var(--role-focus-ring); outline-offset: 2px` per the foundation focus-ring contract. (WCAG 2.4.7, 2.4.11.)

**Error state.** The border shifts to `--error-text`; the input carries `aria-invalid="true"`. A leading or trailing warning glyph in `--error-text` is optional. The error message renders below the input in `--error-text` inside an `aria-live="polite"` container (foundations/accessibility.md §18.6).

**Helper-text slot.** Helper text renders as a caption below the input: tertiary ink (`--text-tertiary`), 13px, weight 400, with `--sp-0-25` (4px) top margin. When both helper text and an error message can appear, the error message replaces the helper text in the same slot.

---

## §14 Search input

**Purpose.** Text input with a leading magnifier icon used in search contexts.

**Structure (slots).** Hairline border + leading magnifier icon + input field.

**Theme Roles Used.** `--surface-raised`, `--border-subtle`.

**Behavior.** Border on focus shifts to the mapped mid-tone neutral. Global `:focus-visible` paints the 2px ring.

**Sizing / notes.** 44px min-height. Padding `8px 16px 8px 40px` (40px left padding for the icon). 44px height satisfies WCAG 2.5.5 (AAA) target size.

**Clear affordance / keyboard.** The input is `<input type="search">`, which provides the browser's native clear control once a value is present and clears the value on Escape when the input has focus (HTML spec / MDN). When the input is inside a `<form>`, Enter submits the form (HTML spec). When used as an inline filter (no form submission), the parent host suppresses default submit and emits change events as the user types (host responsibility).

---

## §14 Textarea

**Purpose.** Multi-line variant of the standard text input.

**Structure (slots).** Same as Standard text input.

**Theme Roles Used.** Same as Standard text input.

**Behavior.** Same as Standard text input.

**Sizing / notes.** Generous padding (16px on all sides). Resize affordance defaults to `resize: vertical` so the user can grow the field downward without breaking horizontal layout. `min-height` ~3 lines (sufficient room for visible context); `max-height` unset by default and capped at the host-feature level when scroll is preferable to growth. (Common DS convention; Tailwind UI / Polaris.)

---

## §14 Outline pill badge

**Purpose.** Lightweight tag with a hairline border, used for categorical or meta labels.

**Structure (slots).** Pill with border + body label.

**Theme Roles Used.** `--border-subtle`, `--surface-secondary`, `--text-tertiary`.

**Behavior.** None at rest.

**Sizing / notes.** `0.5rem 0.75rem` padding, sentence-case label, 12px caption type. No uppercase.

**Interactive vs static.** The default badge is a non-interactive `<span>` — it labels content, it doesn't act. When the host needs the badge to behave as a filter chip or removable tag, wrap or replace the `<span>` with a `<button>` (or `<a>` if it navigates); apply the foundation focus ring on `:focus-visible` and hover-darken the border one role-step toward `--role-border-strong`. (Common DS convention; HTML spec for semantic distinction.)

---

## §14 Inverted pill badge

**Purpose.** A filled pill that inverts ink — used for emphasis labels and counters.

**Structure (slots).** Filled pill with inverse ink.

**Theme Roles Used.** `--text-primary` as background, `--surface-primary` as text.

**Behavior.** None at rest.

**Sizing / notes.** 8px radius, `min-width: 4rem`, `line-height: 1`. Padding and type size default to the sibling Outline pill badge values (`0.5rem 0.75rem` padding, 12px caption) so the two pill variants align vertically when placed side-by-side. Host projects may override.

---

## §14 Status badge

**Purpose.** Indicator badge keyed to a state (e.g., warm coral for "needs attention" / cool sage for "ok").

**Structure (slots).** Mapped warm panel or status fill + label.

**Theme Roles Used.** Ground and ink resolve per state from the status-color mapping below — grounds `--role-status-positive-bg` / `--role-status-caution-bg` / `--role-status-critical-bg` (neutral uses `--role-surface-secondary`); ink `--role-text-primary` / `--role-text-inverse` / `--role-text-tertiary`.

**Behavior.** None at rest.

**Sizing / notes.** 12px caption type. Stored lowercase; rendered uppercase via `text-transform: uppercase` with `0.04em` letter-spacing.

**Status → color mapping.**

| State | Ground | Ink |
|---|---|---|
| `ok` / `success` | `--status-positive-bg` | `--text-primary` |
| `warning` / `needs-attention` | `--status-caution-bg` | `--text-primary` |
| `error` / `failed` | `--status-critical-bg` | `--text-inverse` |
| `neutral` / `info` | `--surface-secondary` | `--text-tertiary` |

Each ground is a role, not a swatch — the `status-*-bg` roles are constrained (`from_palette: status`) and resolve per theme. Every ground meets the §18.5 readable-text floor against its ink at the 12px caption size.

---

## §14 Code block

**Purpose.** Monospaced text block on a dark ground with optional language picker and Copy / View Docs actions.

**Structure (slots).** Mono text body + optional language-picker (top-left) + Copy + View Docs (top-right).

**Theme Roles Used.** `--role-surface-primary` (resolved through the `code` theme to a fixed dark neutral, with `--role-surface-secondary` as the inner stratification); `--role-text-primary` (resolved through the `code` theme to a light text neutral). The `code` theme is mode-invariant — it stays dark in both light and dark mode.

**Behavior.** None at rest.

**Sizing / notes.** 12px radius. Syntax highlighting: muted accent for keywords and strings, light tone for identifiers, dim tone for comments. Language picker top-left; "Copy" and "View Docs" tertiary actions top-right.

**Copy success state.** On copy, the Copy action swaps its label to "Copied" with a checkmark glyph for 1.5s, then reverts — an inline confirmation, not a toast, since the action is local to the block. Announce the result via an `aria-live="polite"` visually-hidden span ("Copied to clipboard"). Suppress any fade/scale on the swap under `prefers-reduced-motion: reduce` (foundations/motion.md §15.5).

**View Docs target.** The "View Docs" action is a Tertiary button that links to the documentation URL supplied by the host's `data-docs-href` attribute on the block; when no target is supplied, the action is omitted rather than rendered inert.

---

## §14 Toggle switch

**Purpose.** Boolean on/off control with a sliding thumb.

**Structure (slots).** Pill body + circular thumb.

**Theme Roles Used.** `--switch-active-bg`, `--surface-tertiary` (OFF), `--surface-raised` (thumb).

**Behavior.** Thumb slides over 200ms.

**Sizing / notes.** ~32×18px to 36×20px. ON state: chromatic blue fill, thumb right. OFF state: gray fill, thumb left.

**Accessibility.** Switch is a `<button role="switch">` carrying `aria-checked="true|false"` reflecting the ON/OFF state. Space and Enter both toggle the switch (WAI-ARIA APG switch pattern + HTML default for `<button>`). Tab focuses the switch as a single control. Focus ring on `:focus-visible` follows the foundation focus ring (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`). When disabled, the switch carries the HTML `disabled` attribute, `opacity: 0.5`, `cursor: not-allowed`, and `pointer-events: none`; `aria-checked` continues to reflect the current state. Honor `prefers-reduced-motion: reduce` by suppressing the 200ms thumb-slide transition; thumb snaps to the new position instead. (WCAG 2.3.3.) See also §14.3 for the switch-active swatch reservation.

---

## §14 Centered dialog

**Purpose.** Modal card centered on a dimmed-light backdrop.

**Structure (slots).** Modal card + dimmed-light backdrop + close glyph.

**Theme Roles Used.** `--surface-raised`, `--text-primary`. Backdrop = mapped absolute-black neutral at 50% opacity.

**Behavior.** Backdrop has no blur. Mount via display toggle; no entrance keyframe.

**Sizing / notes.** ~600px wide, 16px radius. Close glyph upper-right; sticky to the top-left of the scroll container.

**Accessibility.** Dialog renders as `<div role="dialog" aria-modal="true">` with `aria-labelledby` pointing at the dialog title (or `aria-label` when no visible title is present). On open, focus moves to the first focusable element in the dialog (typically the close glyph or first form field). Tab cycles forward within the dialog; Shift+Tab cycles backward; both wrap at the boundaries — focus cannot escape to background content. Escape closes the dialog and returns focus to the element that invoked it. While open, the underlying page is scroll-locked (typically by setting `overflow: hidden` on `<body>` and accounting for scrollbar-width to prevent layout shift). (WAI-ARIA APG modal-dialog pattern.)

**Small-viewport collapse.** Below the mobile-wide breakpoint (`< 700px`, foundations/responsive.md §17.1) the dialog becomes full-screen: `inset: 0`, `width: 100vw`, `height: 100dvh`, `border-radius: 0`, and the close glyph pins to the top-right of the viewport. At and above 700px it renders as the ~600px centered card. The backdrop and focus-trap contract are unchanged across breakpoints.

---

## §14 Video / lightbox dialog

**Purpose.** Modal variant for video and image content with a blurred backdrop.

**Structure (slots).** Modal content panel + blurred near-black backdrop + close glyph.

**Theme Roles Used.** Mapped near-black neutral at 90% opacity; `backdrop-filter: blur(5–10px)`.

**Behavior.** Same mount pattern as Centered dialog.

**Sizing / notes.** The ONLY dialogs that apply backdrop blur. Content panel up to `75rem`, `90vw`, `90vh`.

**Video player chrome.** Use the browser-native `<video controls>` chrome rather than a custom control bar, so the platform's accessible playback controls apply. Keyboard handling follows the native `<video>` contract: Space toggles play/pause when the player is focused, arrow keys seek and adjust volume, and `F` toggles fullscreen. Dialog-level Escape closes the lightbox (and exits fullscreen first if active), returning focus to the invoking element.

**Caption tracks.** Embed captions via `<track kind="captions" srclang="…" label="…">`; default the captions track to showing when the host supplies one. Image content uses descriptive `alt` text on the `<img>` instead.

---

## §14 Consent / cookie banner

**Purpose.** A bottom-right pinned card for cookie or consent disclosures that does NOT block page interaction.

**Structure (slots).** Pinned card + heading + body + accept/reject actions.

**Theme Roles Used.** Local `deep` wrapper, `--text-primary`, `--text-secondary`.

**Behavior.** None at rest. The card is bottom-right pinned, NOT a centered modal. The page underneath remains fully interactive — no backdrop wash.

**Sizing / notes.** 24px radius and 32px desktop / 16px mobile padding.

**Action buttons.** Two actions: an Accept rendered as a Primary button (§14.1) and a Reject rendered as a Secondary button (§14.1), Accept leading. An optional "Manage preferences" Tertiary link sits below the action row.

**Focus order.** When the banner mounts, focus is NOT auto-moved (the banner is non-blocking and the page stays interactive). The banner's controls insert into the natural Tab order immediately after the topbar so a keyboard user reaches them early; the banner is a `role="region"` with `aria-label="Cookie consent"`.

**Persistence semantics.** Both Accept and Reject persist the user's choice (cookie or local-storage flag) so the banner does not reappear on subsequent visits; dismissing without choosing is not offered — the banner stays until an explicit Accept or Reject. "Manage preferences" opens the §14 Centered dialog for granular category toggles.

---

## §14 Article hero

**Purpose.** Editorial detail page's hero — a centered three-line header above a tinted illustration tile.

**Structure (slots).** Eyebrow (Subjects row) + title (Headline 1) + date row + illustration tile.

**Theme Roles Used.** `--text-primary`, saturated panel ground.

**Behavior.** None at rest.

**Sizing / notes.** Title at Headline 1 scale, centered, `text-wrap: balance`. Date row below in tertiary ink. Illustration tile at 16:9 aspect-ratio with inner padding `calc(--card-padding-md * 2)` = 96–128px around the centered SVG.

**Title truncation.** Titles are never truncated — the hero title is the page's primary content and wraps to as many lines as needed with `text-wrap: balance` keeping line lengths even. The illustration tile reflows below the wrapped title rather than the title clipping.

**Multi-author byline.** The date row hosts an optional byline slot: author names join with comma separators and a final "and" (e.g., "By A, B, and C"), rendered inline in the same tertiary ink as the date, separated from the date by a `·` middot. Beyond three authors, show the first two followed by "and N others".

**Illustration tile breakpoint behavior.** The tile holds its 16:9 aspect-ratio at the tablet breakpoint and above; below 700px (foundations/responsive.md §17.1) it relaxes to 4:3 to preserve glyph legibility in the narrower column, and the inner padding drops to the lower bound (96px → `--sp-4`, 52–64px clamp).

---

## §14 Related-content rail

**Purpose.** Sibling-article rail at the bottom of editorial detail pages.

**Structure (slots).** Heading + 3-item link grid (each item: title + dek + "Read more" arrow link).

**Theme Roles Used.** `--text-primary`.

**Behavior.** Item color transitions to `--text-secondary` over 200ms.

**Sizing / notes.** Heading at Headline 4 scale. Each item: Headline 6 title + Body 3 serif dek + tertiary "Read more" arrow link with a 30×30 SVG arrow.

**Item selection.** The rail renders exactly three items supplied by the host's content layer; the component does not choose them. When fewer than three are supplied, the grid renders the available items and collapses unused columns rather than padding with placeholders.

**Responsive collapse.** Three columns at the tablet breakpoint and above (≥700px, foundations/responsive.md §17.1); two columns from 480–700px; a single column below 480px. Inter-item gap follows the §11.6 grid gutter (32px) above tablet and reduces to `--sp-1-5` (24px) when stacked.

---

## §14 Social-share row

**Purpose.** Two-icon share row above a hairline rule, typically at the foot of an editorial article.

**Structure (slots).** Two icon links + 1px top rule.

**Theme Roles Used.** `--border-strong`, `--text-primary`.

**Behavior.** None at rest.

**Sizing / notes.** `margin-top` and `padding-top` both `--sp-3` (resolved in `foundations/layout.md` §11.4). Icon links inherit the product family's icon-button base — `32×32px` touch hit-area with a `20×20` SVG glyph centered. Host-project implementations targeting WCAG 2.5.5 AAA should ship at `≥44×44px` to clear WCAG 2.5.5 (AAA) target size.

**Accessibility.** Each icon link is an `<a>` with an `aria-label` naming the destination service (e.g., `aria-label="Share on LinkedIn"`); the SVG glyph carries `aria-hidden="true"`. Focus paints the foundation focus ring on `:focus-visible` (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`). (WCAG 2.4.7, 2.4.11.)

**Default service pair.** The row ships a "copy link" action and a generic "share" action (the platform Web Share API where available, falling back to copy-link) as its default pair, so the row carries no brand-network dependency. Host projects may substitute named-network icons by replacing the two slots.

---

## §14 Pagination

**Purpose.** Indicator-plus-text-links pagination — explicitly NOT numbered page buttons.

**Structure (slots).** "1 / 3" indicator + Prev/Next text links.

**Theme Roles Used.** `--text-tertiary`.

**Behavior.** None at rest.

**Sizing / notes.** Do NOT use numbered page buttons.

**Accessibility.** Prev/Next are `<a>` when navigating to a distinct URL or `<button>` when re-rendering in place. Wrap the strip in `<nav aria-label="Pagination">` per WAI-ARIA landmark guidance. Disabled Prev (on first page) and disabled Next (on last page) render with `opacity: 0.5; pointer-events: none; cursor: not-allowed` and `aria-disabled="true"` (link variant) or the HTML `disabled` attribute (button variant). The "1 / 3" indicator is decorative — wrap in `<span aria-hidden="true">` and provide an adjacent visually-hidden `<span>` reading "Page 1 of 3" for screen readers. Keyboard contract is the HTML default: Tab visits Prev, indicator (skipped, non-focusable), Next; Enter activates `<a>`; Enter and Space activate `<button>`. (WAI-ARIA APG link/button patterns.)

---

## §14 Three-pane app shell

**Purpose.** In-app shell topology with icon rail + list column + detail viewport. (Also catalogued in `skills/compose-app-surface/reference/app-shapes.md` as shell layout `A4`.)

**Structure (slots).** Icon rail + list column + detail viewport.

**Theme Roles Used.** `--surface-primary`, `--surface-tertiary` (active row pill), `--text-primary`.

**Behavior.** Active row paints with a filled pill.

**Sizing / notes.** See §12.5 for the rail's own spec (width, padding, active-row pill).

**Pane resize rules.** The icon rail is fixed at 64px; the list column is fixed within the 280–320px range (foundations/layout.md §11.2 application-shell pane); the detail viewport is fluid and absorbs all remaining width. The list column may carry a host-provided drag handle on its right edge that constrains resizing to the 280–320px range and persists the chosen width per user.

**Collapse-to-mobile.** Below the desktop breakpoint (`< 1024px`, foundations/responsive.md §17.1) the shell collapses to a single visible pane with the list and detail panes stacked as routes: selecting a list row navigates to the detail pane, and a back affordance returns to the list. Below 700px the icon rail collapses into the §12.3 mobile drawer.

**Cross-pane navigation contract.** Selecting an icon-rail item swaps the list column's contents; selecting a list row updates the detail viewport in place (the list selection persists). The active icon-rail item and active list row both carry `aria-current="page"`; only one row per pane is active at a time.

---

## §14.1 Button base

**Purpose.** The base specification applied across every button variant in the component table (Primary, Secondary, Tertiary, etc.).

**Slot definitions.**
- `leading-icon`: optional icon preceding the label.
- `label`: required text content in Primary Sans.

**Props / variants.** Variant set (Primary, Secondary, Tertiary, etc.) is enumerated in the component table at the top of §14. This section captures the shared base.

| Component | Structure | Theme Roles Used | Interaction Behavior | Notes |
|---|---|---|---|---|
| Primary button | Fill + label | `--button-primary-bg`, `--button-primary-text` | Hover paints a 1px outer shoulder ring in the fill color over 200ms. | 40px min-height, 8px radius. Inverts ground with page mode. |
| Secondary button | Fill + label | `--button-secondary-bg`, `--button-secondary-text` | Hover shifts fill to `--surface-primary`. | 40px min-height. |
| Tertiary button | Border + label | `--button-tertiary-border`, `--text-tertiary` | Hover shifts text to `--text-primary`; border unchanged. | Transparent fill, hairline border, link-glyph leading. |

State props: `rest` | `hover` | `disabled`.

**Fixed sizing/spacing.**
- `min-height: 40px` (2.5rem).
- `display: inline-flex; align-items: center; justify-content: center;` — label and any leading icon centered on both axes; `gap: 8px` when a leading icon is present.
- `padding: 8px 16px` (0.5rem 1rem) horizontal.
- `border-radius: 8px` for body-2 size (17px font), `9.6px` for body-3 size (14–15px font).
- Font: Primary Sans, Body 2 size (17px), weight per the type-weight scale in `foundations/implementation.md` §6.4.
- `line-height: 1`.

**Behavior.**
- Transitions: `color 0.1s ease, background-color 0.2s, box-shadow 0.2s`. The leading icon (if any) uses `color 0.3s ease`.
- Hover: 1px outer box-shadow ring in the button's fill color. Use shadow, not a fill change, as the hover affordance.
- Disabled: 50% opacity, `pointer-events: none`, shadow removed.

**Accessibility.**
- **Disabled-state attribute choice.** Default to the HTML `disabled` attribute on `<button>` so the control is excluded from tab order, form submission, and pointer events at the browser level. Use `aria-disabled="true"` (plus visual styling + a JS click-guard) only when the control must remain focusable so screen reader users can still discover it (e.g., a form-submit button whose disabled state explains *why* on focus). The two forms are mutually exclusive — never set both. (WAI-ARIA + HTML spec.)
- **Focus-visible ring.** `outline: 2px solid var(--role-focus-ring); outline-offset: 2px` per the foundation focus-ring contract — only paints on `:focus-visible` so pointer-input focus does not light the ring. (WCAG 2.4.7, 2.4.11.)
- **Loading / pending state.** Preserve the button's rest-state width and height (avoid layout shift); replace the label with a centered spinner inheriting `currentColor`; set `aria-busy="true"` on the button; click events are ignored while loading. The `disabled` attribute is NOT set during loading so screen readers continue to announce the button. (Common DS convention; Polaris / Material / Carbon.)
- **Icon-only variant.** A button with no visible label MUST carry an `aria-label` describing the action (e.g., `aria-label="Close"`). Icon-only buttons render at the larger of (a) `min-height` 40px and (b) `min-width` 40px so the icon's hit area meets the same target floor as labelled buttons. (WAI-ARIA + WCAG 2.5.5.)
- **Tap target.** 40px min-height meets WCAG 2.5.8 (AA, 24×24). To clear 2.5.5 (AAA, 44×44), variants intended for high-pointer-error contexts (mobile, forms) should ship at `min-height: 44px` — see §14.2 for the conversion-CTA variant at 44px. The 40px base assumes desktop placement with adequate inline spacing satisfying 2.5.8's spacing clause.

---

## §14.2 Authentication primary CTA

**Purpose.** Conversion primary CTA on authentication / sign-up surfaces — richer hover treatment than the standard primary button (the "bloom hover").

**Slot definitions.**
- `host`: required transparent element.
- `::before`: paints the mapped dark fill at full width and height with 9.6px radius.
- `::after`: radial-gradient highlight that fades in on hover.
- `label`: required text content inside the host.

**Props / variants.**
- `state`: `rest` | `hover`.

**Fixed sizing/spacing.**
- `height: 44px`.
- `min-width: 6rem`.
- `padding: 0 20px`.
- `::before` radius: 9.6px.

**Behavior.**
- Default transition: `transform 0.15s cubic-bezier(0.165, 0.85, 0.45, 1)`.
- Hover: `transform: scale(1.005, 1.015)` plus a `::after` radial-gradient highlight whose opacity fades 0 → 1 over 200ms.
- No box-shadow, no outline ring.

**Accessibility.** Inherits primary button keyboard semantics (see §14.1).
- **Focus-visible.** Since the variant suppresses the outline ring at rest, the focus indicator paints on `:focus-visible` ONLY as the foundation focus ring (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`). The bloom hover is decorative — it must not double as the focus indicator. (WCAG 2.4.7, 2.4.11.)
- **Reduced motion.** Honor `prefers-reduced-motion: reduce` by suppressing both the `transform: scale(...)` transition and the `::after` opacity fade; the button paints its rest state on hover instead. (WCAG 2.3.3.)
- **Disabled state.** Inherits the §14.1 button-base disabled contract: HTML `disabled` attribute, `opacity: 0.5`, `cursor: not-allowed`, `pointer-events: none`. The bloom transform and `::after` highlight do not paint while disabled.

**Radial-gradient highlight.** The `::after` highlight is `radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--accent-primary) 40%, transparent) 0%, transparent 70%)` — a soft accent bloom seated at the button's top edge that fades from transparent toward the accent color and back out by 70% of the radius. It binds to the `--accent-primary` role (foundations/motion.md §15.6) so the bloom carries the active theme's accent without per-surface authoring.

---

## §14.3 Switch active

**Purpose.** Specifies the chromatic accent reserved for the toggle switch's active state. The toggle switch is the only place the chromatic blue state swatch paints a control surface.

**Slot definitions.**
- `track`: required pill body.
- `thumb`: required circular thumb element.

**Props / variants.**
- `state`: `off` | `on`.

**Fixed sizing/spacing.**
- Track size: ~32×18px to 36×20px.
- ON: chromatic fill (`--switch-active-bg`), thumb right.
- OFF: gray fill (`--surface-tertiary`), thumb left.
- Thumb fill: `--surface-raised`.

**Behavior.** Thumb slides 200ms between OFF (left) and ON (right) positions. The `--switch-active-bg` and `--focus-ring` roles are reserved for switches and the conversion-input focus ring respectively — both constrained (`from_palette: signals`/`borders`) — so no other control surface paints with these.

**Accessibility.** The `--switch-active-bg` role resolves to the same chromatic signal the focus ring uses on conversion inputs; the switch's ON-state ground must therefore meet contrast against the thumb fill `--surface-raised` to remain perceivable.
- **ARIA contract.** The switch is a `<button role="switch">` carrying `aria-checked="true|false"`. The visual ON/OFF state and the `aria-checked` value are always synchronized. (WAI-ARIA APG switch pattern.)
- **Keyboard.** Space and Enter both toggle the switch (WAI-ARIA APG + HTML default for `<button>`). Tab focuses the switch as a single control.
- **Focus-visible ring.** `outline: 2px solid var(--role-focus-ring); outline-offset: 2px` paints on `:focus-visible` per the foundation focus-ring contract. (WCAG 2.4.7, 2.4.11.)
- **Reduced motion.** Honor `prefers-reduced-motion: reduce` by suppressing the 200ms thumb-slide transition; thumb snaps to the new position. (WCAG 2.3.3.)
- **Disabled state.** HTML `disabled` attribute on the `<button>`, plus `opacity: 0.5`, `cursor: not-allowed`, `pointer-events: none`. `aria-checked` continues to reflect the current state.

---

## §14 Stat tile

**Purpose.** A smaller variant of the application stat card optimized for status-or-progress rendering — a label, an optional value, and a glyph that visualizes the value's state (filled donut for progress, dashed disc for "no data", status pill for "Not enabled", em-dash placeholder).

**Slot definitions.**
- `label` (required): tile label.
- `value` (optional): primary value when one exists.
- `glyph` (required): one of: filled donut, dashed "No data" disc, sparkline, status pill, or em-dash placeholder.
- `action` (optional): inline "Set up" / "Try a prompt" / "Add funds" link or button.

**Props / variants.**
- `state`: `populated` | `empty` | `setup-required`.
- `layout`: `large-horizontal` (KPI row) | `small-vertical` (status/progress row).

**Fixed sizing/spacing.**

Two sizes share the same frame contract:

- **Large-horizontal variant** (KPI row): 254×176px (or 242×176 when peer tile widths shrink). `display: inline-flex; flex-direction: row; align-items: center; gap: 48px; padding: 16px; border: 0; border-radius: 12px; box-shadow: none`. Classes: `bg-bg-300 inline-flex flex-row rounded-xl p-4 items-center gap-12 flex-1 max-w-[500px]`.
- **Small-vertical variant** (status/progress row): 210×144px. `display: inline-flex; flex-direction: column; gap: 8px; padding: 16px 0`. Classes: `bg-bg-300 inline-flex flex-col rounded-xl p-4 min-w-30 grow gap-2 px-0`.
- Row container: `display: flex; gap: 16px` (`flex gap-4`) — peer tiles arrange horizontally; each tile uses `flex-1` to grow up to a `max-w-[500px]` cap.
- Background → `--bg-300` (theme-context dependent; resolves dark in dark sub-sections, light in light contexts).
- Border → none (relies on background contrast against page ground, not a hairline).
- Border-radius → `12px` (`rounded-xl`).

**Behavior.** The tile frame is not interactive (no hover/focus/click handlers on the tile itself). Inline `action` buttons (when present) carry their own button-variant interaction contract.

**Accessibility.** Tile is a non-interactive `<article>`; inline actions follow button accessibility contracts. Glyph SVG should carry `aria-hidden="true"` because the label + value carry the semantic content.

**Structural skeleton.**

```html
<!-- Large horizontal variant -->
<article class="bg-bg-300 inline-flex flex-row rounded-xl p-4 items-center gap-12 flex-1 max-w-[500px]">
  <span class="stat-tile__label-value"><!-- label + optional primary value --></span>
  <span class="stat-tile__glyph" aria-hidden="true"><!-- donut, status pill, em-dash, or sparkline --></span>
</article>

<!-- Small vertical variant -->
<article class="bg-bg-300 inline-flex flex-col rounded-xl p-4 min-w-30 grow gap-2 px-0">
  <span class="stat-tile__label"><!-- label, optionally with trailing ⓘ info button --></span>
  <span class="stat-tile__glyph" aria-hidden="true"><!-- donut, status pill, em-dash --></span>
  <span class="stat-tile__microcopy"><!-- optional caption --></span>
</article>
```

**Glyph mapping.** The glyph slot renders one of: a filled donut for progress (arc length = percent complete), a dashed disc for "no data", a sparkline for trended values, a Status pill for state labels, or an em-dash placeholder for an absent value. The state → glyph mapping is: `populated` → donut/sparkline/value, `empty` → dashed disc or em-dash, `setup-required` → Status pill plus inline action.

**Status-pill ground/ink.** When the glyph slot renders a status pill, it inherits the §14 Status badge status → color mapping (the per-state status grounds and their paired ink roles).

**Variant relationship.** `large-horizontal` and `small-vertical` are two `layout` props of a single component (not separate components); both share the frame contract above and differ only in flex-direction, gap, and padding.

---

## §14 Filter chip

**Purpose.** A compact pill-shaped picker that displays a filter facet's label, the current value, and a trailing caret indicating the picker opens a popover when clicked. Renders as a wrapper `<div>` housing a `<button>` (the label+value trigger) plus a sibling caret region — the wrapper carries the visible pill shape and ground; the button is transparent.

**Slot definitions.**
- `label` (optional): the facet name (e.g., "Group by", "Project", "Range"). Some chips render value-only when context conveys the facet.
- `value` (required): the currently selected value, rendered inline next to the label.
- `caret` (required): a small dropdown caret in the wrapper's right slot.
- `leading-glyph` (optional): a small icon glyph variant — an icon-only chip (e.g., download glyph) without label text.

**Props / variants.**
- `state`: `rest` | `hover` | `focus-visible` | `open` | `disabled` | `invalid`.
- `kind`: `labelled` (default) | `icon-only`.

**Fixed sizing/spacing.**
- Wrapper (the pill): `height: 32px` (`h-control`); padding `0 8px 0 0` (right only via `pr-sm`); border `0`; border-radius `8px` (`rounded`); `display: flex; align-items: center; gap: 6px` (`gap-1.5`); background `bg-fill-field` (translucent — `color(srgb 1 1 1 / 0.1)` on dark sub-section); ring via `shadow-field-ring`.
- Inner button: `height: 32px` (`self-stretch`); padding `0 0 0 8px` (`pl-sm`); border `0`; transparent background; `display: flex; align-items: center; gap: 6px`.
- Wrapper width: content-driven, ranging 105–180px (narrowest at the most concise label+value pair; widest at the longest combined string).
- Type binding: `text-body` size (14px), weight 400, font-sans, color `text-primary`; label sits at `text-text-500`.

**Behavior.**
- `hover`: ring shifts from `shadow-field-ring` to `shadow-field-hover` (only when not focused and not invalid). Transition `transition duration-fast`.
- `focus-visible` (keyboard): wrapper background swaps to `bg-surface-popover`; ring becomes `shadow-focus`.
- `open`: handled at the popover side. Chip carries `aria-expanded` toggle.
- `disabled`: pointer events removed, opacity 50%, cursor default (`data-[disabled]`).
- `invalid`: ring uses `shadow-field-invalid` (`data-[invalid]`).

**Accessibility.**
- Inner button: `aria-haspopup="dialog"` (NOT `menu`) — chip opens a dialog popover for arbitrary controls (radio groups, multi-selects, date pickers).
- Inner button carries `aria-expanded`; host library toggles on open.
- Enter/Space opens the dialog (browser default for `<button>`).
- Tab focuses the inner button; wrapper is non-focusable.

**Structural skeleton.**

```html
<div class="cds-reset inline-flex items-center gap-1.5 h-control rounded font-sans text-body text-primary bg-fill-field shadow-field-ring pr-sm">
  <button aria-haspopup="dialog" aria-expanded="false"
          class="cds-reset flex min-w-0 flex-1 items-center gap-1.5 self-stretch pl-sm text-left border-0 bg-transparent p-0 outline-none">
    <span class="filter-chip__label-value"><!-- label and current value text --></span>
    <span class="filter-chip__caret" aria-hidden="true"><!-- caret SVG --></span>
  </button>
</div>
```

**Popover panel.** The chip opens a `role="dialog"` popover that can hold any control (radio groups, multi-selects, date pickers); the panel contents are supplied by the host. The panel anchors below the chip, left-aligned to the chip's left edge, and follows the §12.2 lift-and-scale open vocabulary.

**Caret animation.** The caret rotates 180° on `aria-expanded="true"` over 150ms using `--ease-in-out` (foundations/motion.md §15.1); suppress the rotation under `prefers-reduced-motion: reduce`.

**Icon-only chip width.** The icon-only variant renders as a 32px square (matching `h-control`), which is also the tap-target floor.

---

## §14 Search field

**Purpose.** A single-line text input with a leading search glyph and a placeholder, used to filter a list rendered elsewhere on the same page. Distinct from §14 Search input (which is a general-purpose search-typed input); the Search field is the in-list filter pattern with a wrapper that owns the chrome and a transparent inner input.

**Slot definitions.**
- `glyph` (required): leading 16×16 SVG magnifying-glass icon, left-aligned inside the wrapper.
- `input` (required): the text-entry field. Renders transparent with zero padding (visual styling lives on the wrapper).
- `placeholder` (required): instructive placeholder text.
- `clear` (optional): a trailing × clear button visible only when the input has a value.

**Props / variants.**
- `state`: `rest` | `hover` | `focus` | `with-value` | `disabled`.

**Fixed sizing/spacing.**
- Wrapper: full container width; `height: 36px` (`h-9`); padding `8px 12px` (`px-3 py-2`); border `1px solid hsl(var(--border-300))`; border-radius `8px` (`rounded-lg`); background `hsl(var(--bg-000))` (`bg-bg-000`); `display: flex; gap: 8px`.
- Glyph: 16×16px SVG (`size-4`).
- Input itself: `flex: 1; background: transparent; padding: 0; border: none; outline: none`; font-family `var(--typeface-sans)`; placeholder color `--text-500`; input text color `--text-100`.

**Behavior.**
- `hover`: border shifts from `--border-300` to `--border-200` via `transition-colors`.
- `focus`: focus ring applied via `can-focus` utility on the wrapper. Pair the ring with the accent-pro token by default; verify against host's focus-ring foundation.
- `disabled`: cursor not-allowed; opacity 50%.
- Reduced-motion: suppress the border-color transition.

**Accessibility.**
- `<input type="search">` provides implicit `role="searchbox"`.
- Pair with a visually-hidden `<label>` or `aria-label` matching the placeholder.
- Wrapper `<div>` carries no role.
- Escape key clears the input when focused (browser default for `type="search"`).
- Tab focuses the input.

**Structural skeleton.**

```html
<div class="bg-bg-000 border border-border-300 hover:border-border-200 transition-colors can-focus h-9 px-3 py-2 flex items-center gap-2 rounded-lg">
  <svg class="size-4 shrink-0" aria-hidden="true"><!-- magnifying-glass path --></svg>
  <input type="search" placeholder="Search templates" aria-label="Search templates"
         class="flex-1 min-w-0 m-0 bg-transparent p-0 outline-none text-xs text-text-100 placeholder:text-text-500 disabled:cursor-not-allowed disabled:opacity-50">
</div>
```

**Clear button mechanics.** Because the input is `<input type="search">`, the browser's native clear control renders automatically once a value is present and clears on Escape when focused (HTML spec). When the host needs a custom clear control (e.g., to match the magnifier glyph's visual weight or to suppress the native browser glyph via `::-webkit-search-cancel-button { display: none }`), the custom clear is a trailing `<button type="button" aria-label="Clear search">`, visible only when the input value is non-empty, positioned at the right edge inside the wrapper. On click: clear the input value, restore focus to the input, and emit a synthetic change event so the host's filter logic re-runs.

**Debounce contract.** Live filtering debounces input at 200ms (matching the foundations/motion.md §15.2 interaction-scale duration): the filter callback fires 200ms after the user stops typing, with a leading-edge fire on the first keystroke so the first character feels immediate. Clearing the field (native or custom clear) fires the filter immediately with an empty query, bypassing the debounce.

---

## §14 Period picker

**Purpose.** A control letting the user select the currently-rendered time period. The default pattern is a dropdown-trigger pill that opens a date-range dialog. Structurally identical to the Filter chip, differing only in the dialog contents it opens.

**Slot definitions.**
- `label` (required): the facet name (e.g., "Range").
- `value` (required): the currently selected value, rendered to the right of the label.
- `popover-trigger` (required): the wrapper itself acts as the dropdown trigger via `aria-haspopup="dialog"`.

**Props / variants.**
- `state`: `rest` | `hover` | `open` | `disabled`.

**Fixed sizing/spacing.**
- Wrapper: `height: 32px` (`h-control`); width sized to content (range 104–201px); padding `0 8px 0 0`; border-radius `8px` (`rounded`); border `0`; background `bg-fill-field`; `display: inline-flex; align-items: center; gap: 6px`.
- Inner button: `flex-1; padding: 0` (right pad handled by wrapper; left pad `8px` via `pl-sm`).
- Inner button children: two `<span>` slots — `label-span` (color `--text-500`), `value-span` (color `--text-100`).
- Row container: `display: flex; gap: 12px` between sibling chips; chips separated by thin `text-border-300` divider spans.
- Type: 14px (`text-sm`), weight 400, color `--text-100`.

**Behavior.**
- `hover` is not declared as a separate visual; chip remains at rest until focused/opened.
- `focus-visible`: wrapper background swaps to `bg-surface-popover`.
- `open`: wrapper retains focus-visible ground; popover panel is a separate component.
- `disabled`: `opacity: 0.5; pointer-events: none`.

**Accessibility.**
- Wrapper is `<div role="combobox">`; inner `<button aria-haspopup="dialog" aria-expanded="false">` is the actual trigger.
- Activation opens a `role="dialog"` popover (NOT `listbox` — this is a date-range picker dialog).
- Disabled gating uses `data-[disabled]` attributes.

**Structural skeleton.**

```html
<div role="combobox"
     class="cds-reset inline-flex items-center gap-1.5 h-control rounded font-sans text-body text-primary bg-fill-field pr-2 focus-visible:bg-surface-popover">
  <button class="cds-reset flex min-w-0 flex-1 items-center gap-1.5 self-stretch pl-sm text-left border-0 bg-transparent p-0 outline-none"
          aria-haspopup="dialog" aria-expanded="false">
    <span class="text-text-500">{label}</span>
    <span class="text-text-100">{value}</span>
  </button>
</div>
```

**Popover panel.** Activation opens a `role="dialog"` date-range picker holding two calendar grids (start and end) plus a column of preset ranges (Today, Last 7 days, Last 30 days, This month, Custom). Selecting a preset or completing a custom range updates the chip's `value` slot and closes the dialog, returning focus to the trigger. The panel follows the §12.2 lift-and-scale open vocabulary and the modal-dialog focus-trap contract.

---

## §14 Stepper

**Purpose.** A horizontal progress indicator showing a numbered sequence of steps in a multi-step flow. The current step is visually emphasized (high-contrast outline, full-strength text token); pending and complete steps drop to a dim-border + muted-text treatment. Optional API-endpoint metadata renders inline at very wide viewports.

**Slot definitions.**
- `step` (repeating, 1 per logical step):
  - `circle` (required): the numbered indicator.
  - `label` (required): the step name.
  - `meta` (optional, current step only by convention): inline secondary text (e.g., the API call this step makes), rendered in a monospace face.
- `connector` (one per step except the first, rendered BEFORE that step's wrapper): a hairline horizontal rule joining adjacent steps. Owned by the step it precedes (inside the same `<li>`).

**Props / variants.**
- `state`: `current` | `pending` | `complete`. Current set via `aria-current="step"`.

**Fixed sizing/spacing.**
- Circle: `20×20px` (`h-5 w-5`); `border-radius: 9999px` (`rounded-full`).
- Current-step circle border: `1.5px solid hsl(var(--text-100))` (`border-1.5 border-text-100`).
- Pending-step circle border: `1px solid hsl(var(--border-300))`.
- Connector: `height: 1px; width: 16px` (`h-px w-4`); `background-color: hsl(var(--border-300))`.
- Gap between circle and label/meta inside a step: `8px` (`gap-2`).
- Gap between adjacent step wrappers (sibling-DIV gap inside the OL): `12px` (`gap-3`).
- Circle number: `12px` (`text-xs`), weight 500, font-family `var(--typeface-sans)`.
- Label: `14px` (`text-sm`); weight 500 for current step, default (400) for pending.
- Meta: `12px` (`text-xs`), `font-mono`, color `--text-500`.

**Responsive collapse.**
- Default viewport: only circles + connectors render. Labels and meta `display: none`.
- Viewport ≥ 1400px: labels become inline (`min-[1400px]:inline`).
- Viewport ≥ 1536px (`2xl`): meta becomes inline (`2xl:inline`).
- Label and meta use `white-space: nowrap`.

**Behavior.** Not interactive by default; the wrapper carries `aria-current="step"` on the current step only. No CSS transitions on the step elements — no reduced-motion fallback required. If a host project's flow needs back-navigation, the pending/complete circle becomes a `<button>` inside the wrapper.

**Accessibility.**
- Wrapper element: `<ol>` (implicit ARIA role `list`).
- Each step: `<li class="contents">` with `display: contents`.
- Current step's inner `<div>` carries `aria-current="step"`.
- Connectors carry `aria-hidden="true"`.
- No `role="navigation"` — it's a status indicator, not a navigation landmark.

**Structural skeleton.**

```html
<ol class="flex min-w-0 items-center gap-3">
  <li class="contents">
    <div aria-current="step" class="flex min-w-0 items-center gap-2">
      <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-medium border-1.5 border-text-100 text-text-100">1</span>
      <span class="hidden whitespace-nowrap text-sm min-[1400px]:inline text-text-100 font-medium">Create project</span>
      <span class="hidden whitespace-nowrap font-mono text-xs text-text-500 2xl:inline">POST /v1/projects</span>
    </div>
  </li>
  <li class="contents">
    <span aria-hidden="true" class="h-px w-4 shrink-0 bg-border-300"></span>
    <div class="flex min-w-0 items-center gap-2">
      <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-medium border border-border-300 text-text-500">2</span>
      <span class="hidden whitespace-nowrap text-sm min-[1400px]:inline text-text-500">Configure environment</span>
    </div>
  </li>
</ol>
```

**Complete-state visual.** A completed step paints a filled circle in `--success-100` containing a centered white checkmark glyph (replacing the step number). The circle border drops in favor of the fill; the label shifts to default weight (400) at `--text-100`, matching pending labels but with the filled circle marking completion.

**Interactive back-navigation.** When a host enables back-navigation, the complete/pending circle's `<span>` is replaced with a `<button>` carrying an `aria-label` of the step name; it paints the foundation focus ring on `:focus-visible` (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`, foundations/accessibility.md §18.2). The current step is never a button (you cannot navigate to where you already are).

---

## §14 Kebab menu

**Purpose.** A 3-dot trigger that opens a small floating menu carrying secondary actions for the current record. Distinct from the dropdown panels in §12.2 — kebab menus are anchored to record headers, not nav triggers.

**Slot definitions.**
- `trigger` (required): a 3-dot icon button (`⋮`).
- `menu` (required): a small floating panel anchored to the trigger.
- `item` (repeating): a row with a label and an optional leading icon; destructive items may render with destructive ink.

**Props / variants.**
- `trigger-state`: `rest` | `hover` | `open`.
- `menu-state`: `closed` | `open`.

**Fixed sizing/spacing.**

Trigger geometry inherits the icon-button base:

- Icon button outer: `32×32px`; host-project implementations targeting WCAG 2.5.5 AAA should ship at `≥44×44px` to clear the WCAG 2.1 AA tap-target floor.
- Padding: `0` (SVG centered via `inline-flex items-center justify-center`).
- Border-radius: `6px` (`rounded-md`).
- Background at rest: `transparent`.
- SVG glyph: `20×20px` centered.
- Class shape: `inline-flex items-center justify-center relative isolate shrink-0 can-focus select-none disabled:pointer-events-none disabled:opacity-50`.

Menu panel: dimensions follow §12.2 Dropdown panels item rules (40px min-height, 8/12px padding, 4px radius). Panel width fits the longest label (roughly 160–200px). Menu anchors below the trigger and right-aligns to the trigger's right edge.

**Behavior.** Click on trigger opens the menu; click outside or Escape closes. Items follow §12.2 hover treatment (background `--surface-tertiary` over 100ms).

**Accessibility.**
- Trigger carries `aria-label` (e.g., "more actions"), `aria-haspopup="menu"`, `aria-expanded`.
- Menu uses `role="menu"`; items use `role="menuitem"`.
- Standard menu keyboard contract (Arrow keys to navigate, Enter to activate, Escape to close).

**Structural skeleton.**

```html
<div class="kebab-menu-wrapper">
  <button class="kebab-trigger" aria-label="more actions" aria-haspopup="menu" aria-expanded="false">⋮</button>
  <ul class="kebab-menu" role="menu" hidden>
    <li role="menuitem"><button>View details</button></li>
    <li role="menuitem"><button>Refresh tools list</button></li>
    <li role="menuitem"><button class="kebab-menu__item--destructive">Remove</button></li>
  </ul>
</div>
```

**Menu open/close motion.** Menu mounts with the §12.2 lift-and-scale dropdown vocabulary: `transform: scale(0.95) → scale(1)` plus `opacity: 0 → 1` over 200ms with `cubic-bezier(0.4, 0, 0.2, 1)`; `transform-origin: 100% 0` so the panel grows from the trigger's anchor corner. Close reverses over 150ms. Honor `prefers-reduced-motion: reduce` by replacing both with an instant display toggle. (WCAG 2.3.3; matches §12.2 motion vocabulary.)

**Kebab glyph.** The trigger glyph is three vertically stacked dots, each a `2px`-diameter filled circle, centered in the `20×20px` glyph slot with `4px` between dot centers, painted in `currentColor`.

**Destructive-item ink.** Destructive menu items render their label in `--danger-100` (matching the §14 Destructive button fill role); on hover the row still paints the §12.2 `--surface-tertiary` background while the label stays destructive.

---

## §14 Read-only identifier row

**Purpose.** A small inline row exposing a system-generated identifier (UUID, slug, key prefix) the user cannot edit but may need to copy. Renders as label + monospaced value + copy icon button.

**Slot definitions.**
- `label` (required): identifier name (e.g., "Organization ID").
- `value` (required): the identifier itself, in a monospaced face for visual distinction from labels and prose.
- `copy` (required): a copy-to-clipboard icon button positioned immediately after the value.

**Props / variants.**
- `state`: `rest` | `copied` (transient confirmation visual).

**Fixed sizing/spacing.**
- Row container: `display: inline-flex; align-items: center; gap: 8px`. No background, no border, no padding — the row inherits the surrounding section's surface.
- Label color: `--text-200` (one step dimmer than primary body text).
- Value: `font-family: ui-monospace, SFMono-Regular, Menlo, monospace` (binds to the brand's `font-mono` utility); `font-size: 14px` (`text-sm`); color `--text-100`; `letter-spacing: 0`.
- Copy button (inherits the product's icon-button base): `32×32px`; padding `0`; border-radius `6px` (`rounded-md`); transparent background; `inline-flex items-center justify-center`; SVG glyph `16×16` (`size-4`). Host-project implementations targeting WCAG 2.5.5 AAA should ship at `≥44×44px` to clear WCAG 2.1 AA.

**Truncation rule.**
- Default: render on a single line at natural width.
- Long IDs (>48 chars): apply `overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 32rem` to the value's container. Copy button always copies the FULL value via the clipboard payload, not the truncated display.
- Never wrap — wrapping a UUID across two lines defeats visual scan/verification.

**Behavior.** Click on copy button writes the full value to the clipboard and triggers the `copied` state — recommend an inline checkmark swap on the same icon button (1.5s timeout) over a toast, since the action is local and the row is small. The swap is an instantaneous icon replacement; if a fade or scale is added at the host level, suppress it under `prefers-reduced-motion: reduce` and show the new icon instantly. (WCAG 2.3.3.) When the copy succeeds, also announce the result via an `aria-live="polite"` region (a visually-hidden `<span>` reading "Copied") so screen-reader users get parity with the visual checkmark.

**Accessibility.**
- Copy button carries `aria-label` joining the action and the identifier name (e.g., `aria-label="Copy Organization ID"`).
- Value element should be `<code>` for semantic distinction.

**Structural skeleton.**

```html
<p class="readonly-id-row inline-flex items-center gap-2">
  <span class="readonly-id-row__label text-text-200">Organization ID:</span>
  <code class="readonly-id-row__value font-mono text-sm text-text-100 overflow-hidden text-ellipsis whitespace-nowrap max-w-[32rem]">7a6d6c1d-ef84-4842-8726-df2db70910f0</code>
  <button class="readonly-id-row__copy inline-flex items-center justify-center w-8 h-8 rounded-md bg-transparent" aria-label="Copy Organization ID">
    <svg class="size-4" aria-hidden="true"><!-- clipboard glyph --></svg>
  </button>
</p>
```

**Value element.** The value MUST be wrapped in `<code>` for semantic distinction from labels and prose; the monospaced face alone is not a substitute for the element.

**Narrow-viewport behavior.** At and above the mobile-wide breakpoint (≥480px, foundations/responsive.md §17.1) the row stays inline (label, value, copy on one line). Below 480px the label moves above the value/copy pair (a two-line stack) so the monospaced value retains its full single-line width without wrapping; the copy button stays on the value's line.

---

## §14 Editor card

**Purpose.** A self-contained card representing one labelled turn in a composed message sequence (system / user / assistant). The role badge is a small label absolutely positioned in the top-left corner of the card's chrome; the content area is a rich-text editor that fills the rest of the card. Optional trailing affordances (delete, info, expand) live in the top-right corner.

**Slot definitions.**
- `role-badge` (required): one of "System Prompt", "User", "Assistant" — rendered as a `<label>` element absolutely positioned in the top-left corner.
- `content` (required): the editable text region, rendered as a rich-text editor (TipTap/ProseMirror). Carries `role="textbox"`. The card's top padding makes room for the badge above the first line of content.
- `leading-action` (optional): a button (e.g., "Generate Prompt") rendered inline at the start of the content row.
- `trailing-action` (optional): a 32×32 icon button (delete / info / expand / reorder) positioned in the top-right corner with ~4px inset.
- `helper` (optional): a one-line guidance sentence accompanying the badge, rendered in tertiary ink (`--text-500`) at 12px below the badge.

**Props / variants.**
- `state`: `rest` | `hover` | `focus` (content has focus — visible as `border-accent-100`) | `disabled` (`opacity-50, cursor-not-allowed`) | `empty` (placeholder shown).
- `role`: `system` | `user` | `assistant`.

**Fixed sizing/spacing.**
- Card outer: width fills the parent track; height grows with content (69px single-line; 81px+ multi-line).
- Card padding: `36px 12px 12px` (`p-3 pt-9`). The 36px top padding accommodates the absolute-positioned role badge (badge sits at top 12px, height 20px).
- Card border: `0.5px solid` at rest (`border-0.5 border-border-300`).
- Card border-radius: `8px` (`rounded-lg`).
- Card background: `--bg-000` (theme-context dependent).
- Card layout: `display: flex; flex-direction: row; align-items: center; gap: 8px`.
- Wrapper (parent of each card): `group relative` — provides the positioning context for the absolute badge.
- Role badge: `<label>` with `for` pointing at the textbox's `id`; `position: absolute; left: 12px; top: 12px`; transparent background; padding `0`; content-sized.
- Content area: `<div role="textbox" contenteditable="true">`; transparent background; border `0`; padding `0` (card's `pt-9` handles vertical offset).
- Trailing-action: `32×32px`; positioned in top-right with ~4px inset; transparent background at rest; glyph `16×16` (`size-4`). Host-project implementations targeting WCAG 2.5.5 AAA should ship at `≥44×44px` for WCAG 2.1 AA.

**Type bindings.**
- Role badge: `14px` (`text-sm`), weight 400, `var(--typeface-sans)`; color `--text-300` (one step dimmer than primary).
- Content text: `14px`, line-height `20px`; color `--text-100`; `var(--typeface-sans)`.
- Placeholder text: same family/size; color `--text-500`.

**Behavior.**
- `hover`: `hover:border-border-300` on the card; transition `transition-colors` (≈150ms ease).
- `focus` (content gains focus): `focus:border-accent-100`; the focus signal is the border color shift only, NOT a focus ring. Verify against host's input-focus foundation.
- `disabled`: `cursor-not-allowed; opacity-50`.
- Reduced-motion: suppress the border-color transition for instant border swap.

**Accessibility.**
- Card wrapper carries no ARIA role — it's a layout container.
- Badge is a `<label>` with `for` pointing at the textbox's `id`, wiring the role announcement to focus.
- Content area carries `role="textbox"` and `contenteditable="true"`.
- Trailing-action button is a standard `<button>`, tab-focusable on its own.

**Structural skeleton.**

```html
<div class="group relative">
  <label for="user__r_13_"
         class="text-text-200 mb-1 block font-base font-normal !text-text-300 absolute left-3 top-3 font-ui">
    User
  </label>
  <div class="flex w-full items-center gap-2 bg-bg-000 border-0.5 leading-5 rounded-lg
              transition-colors hover:border-border-300 placeholder:text-text-500
              focus:border-accent-100 focus:ring-0 focus:outline-none
              disabled:cursor-not-allowed disabled:opacity-50 whitespace-pre-wrap resize-none
              border border-border-300 p-3 font-ui text-sm pt-9 overflow-hidden">
    <div id="user__r_13_" role="textbox" contenteditable="true" class="tiptap ProseMirror">
      <!-- editable rich-text content -->
    </div>
  </div>
</div>
```

**Collapsed state.** A `collapsed` card shows only the role badge and a single-line preview of the content (truncated with ellipsis) at the single-line height (69px); the trailing-action set reduces to an expand affordance that toggles back to the full editor. Toggling between collapsed and expanded animates height over 150ms with `--ease-in-out`, suppressed under `prefers-reduced-motion: reduce`.

**Helper text.** The optional helper sentence sits directly below the absolute-positioned role badge in the top-left zone, in tertiary ink (`--text-500`) at 12px weight 400; the card's `pt-9` top padding accommodates badge plus helper when both are present (top padding inflates to `48px` when a helper line is shown).

**Placeholder text.** The empty editor renders placeholder text via the editor's placeholder extension as a `::before` pseudo-element on the first empty block, in `--text-500` at the content size; it also carries `aria-placeholder` on the `role="textbox"` element so screen readers announce it.

**Trailing-action catalog.** Four trailing actions: Delete, Info, Expand, Reorder — each a 32×32 icon button. Reorder is a drag handle (`cursor: grab`) that initiates row reordering; it carries `aria-label="Reorder turn"` and exposes keyboard reordering via Arrow Up/Down while focused (with `aria-grabbed` toggling).

**Max-height before scroll.** The card uses `overflow: hidden` at the frame; the content editor grows to a `max-height` of `40vh`, after which the editor's own region scrolls internally while the badge and trailing actions stay pinned.

---

## §14 Setting card

**Purpose.** A self-contained card representing a single preference: title, 1–2-paragraph explanation, and an inline toggle (or primary action) on the right.

**Slot definitions.**
- `title` (required): card heading.
- `body` (required): one or more paragraphs explaining the preference.
- `toggle` (optional): a switch on the right edge, vertically centered against the full card height via `row-span-2`.
- `primary-action` (optional): a primary button in the toggle slot's place (mutually exclusive with toggle).
- `pill` (optional): a small tag adjacent to the title (e.g., "NEW"); renders inline inside the title cell via `inline-flex gap-2 items-center`.

**Props / variants.**
- `control-kind`: `toggle` | `primary-action` | `none`.
- Toggle state inherits §14.3 Switch active: `off` | `on`.

**Fixed sizing/spacing.**
- Card outer width: fills the settings main pane.
- Card padding: `32px` on all sides (`p-8`).
- Card border: `0.5px solid hsl(var(--border-300))` (`border-0.5 border-border-300`).
- Card border-radius: `12px` (`rounded-xl`).
- Card background: transparent (sits directly on page ground).
- Card inner layout: `display: flex; flex-direction: column; gap: 24px` (`flex flex-col gap-6`).

**Layout pattern.** The card's single direct child is a 2-column CSS grid: `grid grid-cols-[1fr_auto] gap-x-5 w-full`. Three grid items participate:

1. **Title cell** (`text-text-100 text-lg font-medium inline-flex gap-2 items-center`): 18px text, weight 510, color `--text-100`. Column 1, row 1.
2. **Toggle cell** (`flex items-center row-span-2`): the switch wrapper. Column 2, spans both rows, vertically centered against the full title-plus-body height.
3. **Body cell** (`text-sm [&_a]:text-brand-000 text-text-300 mt-1`): 14px text, weight 400, color `--text-300`; inline links inherit `--brand-000`. Column 1, row 2, with `margin-top: 4px`.

The toggle's `row-span-2` is the key rule: the toggle always centers vertically against the combined title + body block, regardless of how the body wraps.

**Toggle spec.** Switch rendered as `<button role="switch" data-state="true">` containing a `<span>` thumb. Outer 43×24px (with `--cds-switch-h: 20px`), padding `2px`, `rounded-full`, background `--switch-track` at rest / `--fill-accent` when checked. Thumb 20×20px, `bg-switch-knob`, `shadow-sm`, translates `calc(var(--cds-switch-h) * 0.8)` (~16px) right when checked. Transition `duration-snap ease-overshoot`; suppress under `prefers-reduced-motion: reduce` via `motion-reduce:transition-none`.

**Behavior.**
- Title color: `--text-100`.
- Body color: `--text-300`; inline links `--brand-000`.
- Switch track at rest `--switch-track`; on hover `--switch-track-hover`; when on `--fill-accent`; when on + hover `--fill-accent-hover`.
- Focus ring on switch: `shadow-focus` foundation token.

**Accessibility.**
- Switch: `<button role="switch">`; state in both `aria-checked` and `data-state="true|false"`.
- Heading-to-switch relationship via `aria-labelledby` on the switch pointing at the title's `id`.
- Space and Enter toggle the switch.
- Tab focuses the switch.

**Structural skeleton.**

```html
<article class="rounded-xl p-8 flex flex-col gap-6 border-0.5 border-border-300">
  <div class="grid grid-cols-[1fr_auto] gap-x-5 w-full">
    <div class="text-text-100 text-lg font-medium inline-flex gap-2 items-center">
      Allow product metrics logging
      <!-- optional <span class="pill pill--new">NEW</span> sits here -->
    </div>
    <div class="flex items-center row-span-2">
      <button role="switch" data-state="true" aria-checked="true"
              class="cds-reset relative inline-flex shrink-0 rounded-full border-0 outline-none
                     bg-switch-track hover:bg-switch-track-hover
                     data-[checked]:bg-fill-accent data-[checked]:hover:bg-fill-accent-hover
                     disabled:opacity-50 focus-visible:shadow-focus
                     h-switch w-[calc(var(--cds-switch-h,20px)*1.8)] p-[2px]">
        <span class="block rounded-full bg-switch-knob shadow-sm
                     transition-transform duration-snap ease-overshoot motion-reduce:transition-none
                     size-[calc(var(--cds-switch-h,20px)-4px)]
                     data-[checked]:translate-x-[calc(var(--cds-switch-h,20px)*0.8)]"></span>
      </button>
    </div>
    <div class="text-sm [&_a]:text-brand-000 text-text-300 mt-1">
      Enable metrics collection to track product usage across your organization…
    </div>
  </div>
</article>
```

**Multi-card spacing.** When multiple setting cards stack in a column, the inter-card gap is `--sp-1-5` (24px, `gap-6`) — matching the intra-card slot gap so the rhythm reads as one consistent vertical scale.

**Pill placement.** When a pill accompanies the title, it sits inline after the title text inside the title cell's `inline-flex gap-2 items-center` layout (8px gap), vertically centered against the title's cap height.

The composition that adds a destructive sub-row beneath the body is documented in `skills/compose-app-surface/reference/app-shapes.md` § "Cross-context component compositions" § "Setting card with toggle + destructive sub-row" — not a property of this Component.

---

## §12.5.1 Workspace switcher

**Purpose.** A control at the top of the rail letting the user switch between workspaces in the current organization. Extends §12.5 App shell left rail's `workspace-switcher` slot.

**Slot definitions.**
- `wrapper` (required): a `<div>` with a hairline border that hosts both the trigger and an optional sibling collapse-toggle.
- `trigger` (required): a `<button>` rendering the current workspace name plus a trailing caret glyph.
- `name` (required, inside trigger): the workspace name text.
- `caret` (required, inside trigger): a small chevron glyph indicating the trigger is expandable.
- `collapse-toggle` (optional, sibling of trigger inside wrapper): a separate button to collapse the rail.
- `panel` (required when open): a popover listing other workspaces.

**Props / variants.**
- `variant`: `compact` (32×32 icon-only, rail collapsed) | `full` (232×32 named, rail expanded).
- `state`: `closed` | `open`.

**Fixed sizing/spacing (full variant).**
- Wrapper: width `232px`; height `32px` (`h-8`); padding `0px 5px 0px 0px` (`pr-[5px]`); border `1px solid var(--role-border-subtle)` (hairline at low alpha against the dark rail surface); border-radius `6px` (`rounded-md`); background transparent (rail's `--role-surface-secondary` shows through); layout `display: flex; gap: 2px; align-items: center`.
- Trigger: width `225px`; height `30px`; padding `0 0 0 8px` (`pl-2`); gap `4px` (`gap-1`).
- Trigger children:
  - `name` SPAN: `flex-1 min-w-0 truncate`; `font-size: 12px` (`text-xs`); weight 400; color `--text-100`.
  - `caret` DIV: `12×12px`; `shrink-0`; color `--text-500`.

**Fixed sizing/spacing (compact variant).**
- Button: `32×32px` (`h-8 w-8`); padding `0`; border-radius `6px` (`rounded-md`); transparent background; `text-text-500` at rest; `hover:text-text-100`.
- Single child: `16×16` icon glyph; color inherited via `currentColor`.

**Behavior.**
- `closed` (rest): trigger carries `aria-expanded="false"`.
- `open`: trigger carries `aria-expanded="true"`; panel becomes visible.
- `hover` (compact variant): text color transitions from `--text-500` to `--text-100` via `transition-colors`.
- `focus`: trigger uses `hide-focus-ring` on the inner button; wrapper carries `outline-offset: 2px` so the focus indicator paints on the wrapper. Actual focus ring is the host's global `:focus-visible` foundation.
- Compact-variant transition: `duration-300 ease-[cubic-bezier(0.165,0.85,0.45,1)]` plus `transition-colors`.
- Under `prefers-reduced-motion: reduce`, suppress both transitions for instant color swaps.

**Accessibility.**
- Trigger: `<button type="button" role="combobox" aria-haspopup="dialog" aria-expanded="false">`. The combobox role + dialog popup is the live pattern (NOT `<menu>` or `<listbox>`).
- `aria-haspopup="dialog"` means screen readers announce "opens a dialog."
- Wrapper `<div>` carries no ARIA role.
- Keyboard: standard button activation (Space/Enter to open). Arrow keys, Escape, and dialog focus-trap behavior are dialog-pattern responsibilities.

**Structural skeleton (full variant).**

```html
<div class="border border-border-300 transition-colors text-text-100 w-full flex items-center pr-[5px] outline-offset-2 h-8 text-xs rounded-md gap-0.5 [--cbx-pl:theme(spacing.2)]">
  <button type="button" role="combobox" aria-haspopup="dialog" aria-expanded="false"
          class="hide-focus-ring flex flex-1 self-stretch min-w-0 pl-[var(--cbx-pl)] items-center gap-1 text-left">
    <span class="flex-1 min-w-0 truncate">{workspace name}</span>
    <div class="text-text-500 shrink-0 mr-[3px]"><!-- 12×12 caret SVG --></div>
  </button>
  <!-- optional sibling: collapse-rail toggle -->
</div>
```

**Structural skeleton (compact variant).**

```html
<button type="button" aria-label="{open workspace switcher}"
        class="inline-flex items-center justify-center h-8 w-8 rounded-md text-text-500 hover:text-text-100 transition-colors">
  <!-- 16×16 icon glyph -->
</button>
```

**Panel contents.** The popover is a `role="dialog"` listing the organization's workspaces. Its layout, top to bottom: a §14 Search field (shown only when more than ~7 workspaces exist), a list of workspace rows (each row reusing the §12.5 nav-row geometry — 36px height, 8px radius, `aria-current="true"` on the active workspace), and a "Create workspace" row pinned to the bottom rendered as a Tertiary button with a leading plus glyph. The panel follows the §12.2 lift-and-scale open vocabulary and the modal-dialog focus-trap contract.

**Leading workspace-color dot.** An optional `color-dot` slot precedes the workspace name in both trigger and panel rows: an `8px` circle painted in the workspace's identity color, supplied per workspace by the host. When no color is supplied the dot is omitted and the name sits flush left.

**Variant switching.** The `compact` ↔ `full` switch keys off the rail's collapsed/expanded runtime state (the rail's own collapse toggle), not a media query — when the rail collapses, the switcher renders `compact`.

---

## §12.5.2 Account row

**Purpose.** A row anchored to the bottom of the rail (or sidebar) showing the current user's identity, role/org, and an expandable menu trigger for account actions. Extends §12.5 App shell left rail's `account` slot.

**Slot definitions.**
- `avatar` (required): user's avatar — a fixed-size box containing an initial, image, or icon glyph.
- `name` (required): user's display name.
- `role-or-org` (optional): a secondary line showing role or org name; truncates to 2 lines max with line-clamp.
- `caret` (required, `full` variant only): an expand chevron indicating the row opens a menu.

**Props / variants.**
- `variant`: `full` (avatar + name + role + caret, standard rail) | `compact` (avatar only, narrow mini-rail) | `footer-strip` (horizontal strip with link + identity pills at the bottom of an A5 form sidebar).
- `state`: `rest` | `hover` | `menu-open` (`data-state="open"`).

**Fixed sizing/spacing (full variant).**
- Outer button: width fills rail content (232px on 256px-wide rail); height `48px`; padding `6px vertical × 8px horizontal` (`py-1.5 px-2`); border-radius `8px` (`rounded-lg`); background transparent at rest.
- Layout: `display: flex; align-items: center; gap: 12px`.
- Avatar: `32×32px` (`size-8`); border-radius `6px` (`rounded-md` — NOT a circle); border `0.5px solid --border-300`; background `--bg-000` at 60% opacity (`bg-bg-000/60`); icon/text color `--text-200`. Inner SVG icon: `20×20px` centered.
- Name/role stack container: `flex flex-col items-start; min-width: 0; overflow: hidden; padding-right: 16px; flex: 1`.
- Name span: `14px / weight 500` (`text-sm font-medium`); `line-clamp: 2` with `break-words`.
- Role/org line: `12px / weight 400 / --text-500`.
- Caret: `16×16px` SVG chevron in `--text-300` with `aria-hidden="true"`. When the menu opens, the caret rotates 180° over 150ms with `--ease-in-out`; suppress under `prefers-reduced-motion: reduce`.

**Fixed sizing/spacing (compact variant).**
- Button: `32×32px` (`size-8`); padding `0`; border-radius `8px` (`rounded-lg`); transparent background at rest; `hover:bg-bg-400`. Renders the avatar glyph only (no name, role, or caret), centered.
- Avatar inside: same `32×32px` rounded-md avatar spec as the full variant, filling the button.
- Carries an `aria-label` joining the user's name and role so the identity is announced despite the absent visible text.

**Fixed sizing/spacing (footer-strip variant).**
- A horizontal strip at the bottom of a form sidebar: `display: flex; align-items: center; justify-content: space-between; gap: 12px`; height `40px`; padding `0 8px`.
- Left: a small identity pill (avatar `20×20px` + name at 12px/`--text-200`). Right: a Tertiary link (e.g., "Sign out" or "Account") at 12px.
- No caret and no menu trigger — the footer-strip variant exposes its actions inline as links rather than opening a menu.

**Behavior.**
- `hover` (pointer): background fades from transparent to `--bg-400` via `transition-colors`.
- `menu-open` (`data-state="open"`): background stays at `--bg-400`; the caret (if animated) typically rotates 180°.

**Accessibility.**
- Wrapper is a `<button>` carrying `aria-haspopup="menu"` and `aria-expanded`.
- Row should carry an `aria-label` joining avatar + name + role: e.g., `aria-label="Account menu for {name}, {role}"`. Avatar SVG carries `aria-hidden="true"`.
- Keyboard: Tab focuses the button; Enter or Space opens the menu; Escape closes (host's menu logic).

**Structural skeleton (full variant).**

```html
<button class="py-1.5 px-2 flex justify-between items-center gap-3 rounded-lg hover:bg-bg-400 data-[state=open]:bg-bg-400 transition-colors w-full"
        aria-haspopup="menu" aria-expanded="false" aria-label="Account menu for {name}, {role}">
  <div class="flex gap-3 items-center min-w-0 w-full">
    <div class="flex-shrink-0 flex size-8 items-center justify-center rounded-md bg-bg-000/60 border-border-300 border-0.5 text-text-200">
      <svg class="size-5" aria-hidden="true"><!-- avatar glyph (20×20) --></svg>
    </div>
    <div class="flex flex-col items-start min-w-0 font-ui overflow-hidden pr-4 flex-1">
      <span class="text-sm font-medium w-full text-start line-clamp-2 break-words">{name}</span>
      <span class="text-xs text-text-500 w-full text-start truncate">{role-or-org}</span>
    </div>
    <svg class="size-4 shrink-0 text-text-300" aria-hidden="true"><!-- chevron --></svg>
  </div>
</button>
```

**Variant relationship.** `full`, `compact`, and `footer-strip` are three `variant` props of one Account row component. The `footer-strip` variant is the form-sidebar placement; it shares the identity slots (avatar, name) but exposes actions as inline links rather than a menu trigger.

---

## Cross-component foundation references

The following foundation contracts are referenced by components throughout this file; their authoritative values live in `foundations/`:

- **Focus-visible ring.** Every interactive component paints the focus ring on `:focus-visible` per `foundations/accessibility.md` §18.2 (`outline: 2px solid var(--role-focus-ring); outline-offset: 2px`, with the inset `-2px` offset variant for elements with a ≤4px radius). The skip-link snap and the hamburger inset ring are specializations of this contract.
- **Reduced motion.** Reduced-motion fallbacks are specified per-component for the mobile drawer (§12.3), sticky header (§12.4), dropdowns (§12.2), authentication primary CTA bloom (§14.2), toggle switch (§14 Toggle switch + §14.3 Switch active), and kebab menu (§14 Kebab menu), all governed by the global `prefers-reduced-motion: reduce` gate in `foundations/motion.md` §15.5.
- **`--container-margin`** (referenced by the mobile drawer mask, §12.3) resolves in `foundations/layout.md` as the side-gutter clamp (32–64px, §11.2).
- **`--ease-in-out-power3`** (referenced by the mobile drawer open animation, §12.3) resolves to the `--ease-in-out-expo` curve in `foundations/motion.md` §15.1 (`cubic-bezier(1, 0, 0, 1)`), the curve reserved for max-height and panel reveals over longer durations.
