# Foundations — Implementation

## §6 Theme contracts — narrative

Themes are CSS classes that wrap a section. Each theme is the structural binding between role slots and palette swatches: when a section carries the theme class, the role variables inside that section resolve to the swatches the theme declares. Themes do not nest meaningfully — a child theme overrides the parent theme cleanly. The set of named themes shipped in `customizable-design-elements.yaml` is `clarity` (high-clarity light, card-heavy interiors, pricing, dense content), `default` (the principal warm light page theme), `editorial` (a direct alias of `default` for editorial and legal pages), `punctuation` (light punctuation between light and dark blocks), `statement` (high-contrast neutral feature panels that push ink to absolute black), `feature-dark` (mid dark feature panels with mascot in light tone), `code` (deeper dark for code blocks and second-tier dark interjections), and `deep` (near-black dark for the footer and principal story-panel reveal).

### Why theme contracts exist

The role-to-swatch binding is the load-bearing decoupling in the whole system. Components ask for `--text-primary`; the theme wrapper says what `--text-primary` resolves to in this section, in this mode. Without theme contracts, every component would have to know its surface — and the system would collapse into per-component color logic. The YAML's binding rows are exhaustive: every theme lists every role explicitly, so each theme class is fully self-contained and resolves without depending on another theme's declarations.

### Light vs. dark theme binding narrative

Light themes come in two kinds. Themes that change between modes (`default`, `clarity`, and its alias `editorial`) bind their role slots to light-mode swatches in their default class declaration; when the document root carries `data-mode="dark"`, those same theme classes are rebound — every role slot the theme paints is reassigned to its dark-mode swatch under a `:root[data-mode="dark"] .{theme}` selector. The primary accent softens to its dark-mode variant; surfaces invert; ink flips. Themes that do not change between modes (`punctuation`, `statement`) declare no live `dark` mode — they render their single expression in both UI modes, and the YAML keeps their dark mapping as a commented-out template for a maintainer who later wants them to diverge. Dark themes (`feature-dark`, `code`, `deep`) likewise require no dark-mode rebinding — they are already dark and continue to render dark in either mode. The literal swatch values for the light bindings and any dark-mode overrides live in `customizable-design-elements.yaml`; this document does not duplicate them.

There is one cross-mode invariant: the chromatic signal (`--color-signals-focus`, consumed via the `switch-active-bg` and `input-focus-ring` roles) used for the switch active-fill and the conversion-input focus ring stays constant across every theme and every mode. It is the only signal the system treats as mode-invariant.

### Button slot binding narrative

Buttons resolve through their own slot family (`--button-primary-bg`, `--button-primary-text`, `--button-secondary-bg`, `--button-secondary-text`, `--button-brand-bg`, `--button-brand-text`, plus the tertiary-button border). The binding rule is mode-driven, not theme-driven: across every light theme in light mode, the primary-button ground sits at the visual opposite of the page ground (dark fill, light label). When the page goes dark, the primary button inverts in lockstep (light fill, dark label). The brand button does not invert — it stays accent-grounded regardless of mode. Secondary buttons shift between a soft neutral fill on light and a darker neutral fill in dark mode. The exact swatches at each slot in each mode are in the YAML.

### §6.1 Light-mode theme bindings

The light-mode theme bindings (which color each role resolves to when the theme runs in light mode) are project-customizable. The full binding tables for every theme class live in the file at `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`, under each theme's `light` block. This file documents only the role-binding contract — the values themselves are not duplicated here. See `customizable-design-elements.schema.json` for the canonical shape.

### §6.2 Dark-mode theme bindings

The dark-mode bindings follow the same role-binding contract as §6.1 but supply different color values per role. Same source-of-truth principle: values live in the elements YAML's `dark` block per theme — present as a live block only for concrete themes that actually change between modes (`default`, `clarity`; `editorial` carries no block of its own — it is an alias that mirrors `default`). A theme with no live `dark` block is taken at face value: it has a single expression that renders in both UI modes. For a theme that does not change between modes, the YAML keeps the full dark mapping as a commented-out template (uncomment and edit to make it diverge), so the binding stays on record without emitting a redundant override.

### §6.3 Button slot bindings

Button slot bindings (the background, label, hover, focus, and disabled colors for every button variant under every theme) live in the elements YAML's role definitions for the button family. See §6.4 below for the weight-oscillation behavior that pairs with the slot bindings.

### §6.4 Button label weight oscillation

Button label weight oscillates between modes to compensate for the perceptual weight shift between dark-ink-on-light and light-ink-on-dark. Apply a deliberate weight compensation: heavier weight on grounds where dark text reads heavier; lighter weight on grounds where inverted-light text reads thinner. The shipped weights are:

| Button Variant | Light Mode | Dark Mode |
|---|---:|---:|
| Primary | 480 | 500 |
| Secondary | 500 | 480 |
| Brand | 500 | 480 |

The pattern: the primary button reads dark-on-light in light mode (label = light text on dark fill), which perceptually thickens — so the weight is held back at 480. In dark mode, the primary button inverts to light-on-dark (label = dark text on light fill), which perceptually thins — so the weight steps up to 500. Secondary and brand buttons are not full-contrast inversions; they oscillate in the opposite direction to keep the visual weight aligned with the rest of the system.

Use a variable-axis weight family. If you map a non-variable font into the system, approximate `480` to `500` and document the substitution in the font mapping instructions.

---

## §7 Color-mode resolution

The color-mode marker is a single attribute on the document root: `data-mode="light"` or `data-mode="dark"`. A third value, `data-mode="system"`, defers to the OS preference.

The CSS reads the color-mode marker in three branches:

1. `:root[data-mode="light"]` — bind light-mode palette swatches.
2. `:root[data-mode="dark"]` — bind dark-mode palette swatches.
3. `:root[data-mode="system"]` plus `@media (prefers-color-scheme: dark)` — bind dark-mode palette swatches.

Declare the CSS `color-scheme` property on the root so that native form controls and scrollbars adapt to the active mode.

```css
:root[data-mode="light"] { color-scheme: light; }
:root[data-mode="dark"]  { color-scheme: dark; }
:root[data-mode="system"] { color-scheme: light dark; }
```

Surfaces that intentionally do not invert (long-form editorial, legal, public authentication card) carry an explicit local `data-mode="light"` on a wrapping element that overrides the root. Surfaces that intentionally stay dark (the deepest footer, code blocks) carry an explicit `data-mode="dark"` on the local wrapper.

Logos and inline SVGs use `fill="currentColor"` on the inner path and `fill="none"` on the outer `<svg>` so they recolor automatically when the surrounding theme's `--text-primary` flips. Single-glyph marks, icons, and mascot art are never authored as separate light/dark assets. The one exception: a multi-color brand logo MAY declare an `assets.logo` light/dark pair (`compliance.md` §23 #15), selected by mode in CSS.

Code blocks declare their fixed dark hex values directly. They render dark in light mode and continue dark in dark mode.

---

## §8 CSS variable implementation

Define the palette, role slots, themes, and component classes in this order. Loading order matters; later rules override earlier ones.

### §8.1 Palette and root

The palette (defined by `customizable-design-elements.yaml`, resolved via `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`) is the canonical source of color values. §8.1 holds only the **pattern** for emitting it as CSS — the YAML rows are the source of truth. The catalog has two tiers and they emit differently:

1. **Primitive palettes** (every ramp + every discrete palette whose rows carry a `hex`): emit `<token>: <hex>;`.
2. **Semantic palettes** (every discrete palette whose rows are aliases — a `{ var: ... }` value): emit `<token>: var(<referenced token>);`. Emit these **after** the primitives so the referenced tokens already exist.

The generator must **not** hardcode the list of palette names — walk every palette under `color_catalog.palettes` (plus `common_colors`) in file order and branch on whether each row is a hex (tier 1) or a `var` alias (tier 2). Token names follow `$conventions.color_var_pattern` (`--color-{palette key}-{color key}`).

Worked example (one primitive ramp, one primitive discrete, the semantic palettes):

```css
:root {
  /* TIER 1 — PRIMITIVES (emit the hex from the YAML row) */

  /* Neutral ramp — one declaration per row */
  --color-neutral-000: <hex from YAML neutral.000>;
  /* ...neutral, blue, green, red ramps; then the discrete primitives: */
  --color-burnt-orange-primary: <hex from YAML burnt-orange.primary>;
  --color-pastel-oat:           <hex from YAML pastel.oat>;
  --color-stronger-indigo:      <hex from YAML stronger.indigo>;
  --color-saturated-focus-blue: <hex from YAML saturated.focus-blue>;
  /* ...continue for every primitive row */

  /* TIER 2 — SEMANTIC (emit a var() alias to the referenced primitive) */

  --color-accent-primary:            var(--color-burnt-orange-primary);
  --color-panels-oat:                var(--color-pastel-oat);
  --color-buttons-primary-bg-brand:  var(--color-blue-750);
  --color-backgrounds-ivory:         var(--color-neutral-050);
  --color-text-ink:                  var(--color-neutral-950);
  --color-borders-warm-gray:         var(--color-neutral-400);
  --color-signals-focus:             var(--color-saturated-focus-blue);
  --color-status-positive:           var(--color-pastel-mineral);
  /* ...continue for every semantic row, in every semantic palette */
}
```

Optional compatibility aliases. Keep only if existing component code references brand-specific accent names.

Reference example (clay accent family):

```css
:root {
  --p-clay: var(--color-accent-primary);
  --p-clay-interactive: var(--color-accent-interactive);
  --p-clay-hover: var(--color-accent-hover);
  --p-clay-dark: var(--color-accent-dark);
}
```

Mapped example (burnt-orange accent family):

````css
:root {
  --p-burnt-orange: var(--color-accent-primary);
  --p-burnt-orange-interactive: var(--color-accent-interactive);
  --p-burnt-orange-hover: var(--color-accent-hover);
  --p-burnt-orange-dark: var(--color-accent-dark);
}
````

Color-mode declarations on the root (global; not derived from the palette):

```css
:root { color-scheme: light; }
:root[data-mode="dark"] { color-scheme: dark; }
```

**Drift rule:** if a swatch value changes, change it in `customizable-design-elements.yaml` and regenerate this block from the YAML. Never edit hex values inside this CSS pattern directly.

### §8.2 Theme wrappers

The theme bindings (light, dark, and button slot) live in `customizable-design-elements.yaml`. §8.2 holds only the **pattern** for emitting them as CSS — the (Theme, Role Slot, Palette Swatch) tuples in the YAML are the source of truth.

**Light-mode pattern.** For each theme listed in the YAML's light-mode bindings, emit a class selector containing one `--<role>: var(--<semantic-token>);` declaration per row bound to that theme.

Worked example — `default`, built from light bindings + button bindings:

```css
.default {
  --surface-primary: var(--color-backgrounds-ivory);
  --surface-secondary: var(--color-backgrounds-linen);
  --surface-tertiary: var(--color-backgrounds-cream);
  --text-primary: var(--color-text-ink);
  --text-secondary: var(--color-text-graphite);
  --text-tertiary: var(--color-text-dim);
  --border-subtle: var(--color-borders-warm-gray);
  --accent-primary: var(--color-accent-primary);
  --button-primary-bg: var(--color-buttons-primary-bg-brand);
  --button-primary-text: var(--color-buttons-primary-txt-frost);
  /* ...emit one declaration per role slot bound to this theme in the YAML.
     Every value is a SEMANTIC token (never a raw ramp step) — the role's
     from_palette constraint is what guarantees that. */
}
```

Repeat the same structure for every theme in the YAML (`clarity`, `editorial`, `punctuation`, `statement`, `feature-dark`, `code`, `deep`). Each theme binds every role explicitly in the YAML, so each generated class is self-contained — it lists a declaration for every role and never relies on inheriting an unlisted role from another theme.

**Dark-mode override pattern.** A theme that changes between modes must rebind its roles when the document root carries `data-mode="dark"`. Only themes that declare a live `dark` mode in the YAML (`default`, `clarity`, and its alias `editorial`) emit an override block; use the YAML's dark-mode binding rows for the override values. A theme whose YAML has no live `dark` mode emits no override block — it renders its single (light) expression in both UI modes.

Worked example — `default` dark-mode override:

```css
:root[data-mode="dark"] .default {
  --surface-primary: var(--color-backgrounds-brand-ink);
  --text-primary: var(--color-text-frost);
  --accent-primary: var(--color-accent-dark);
  /* ...emit one declaration per dark-mode row in the YAML for this theme */
}
```

**System-preference mirror pattern.** Mirror every dark-mode override inside a `[data-mode="system"] @media (prefers-color-scheme: dark)` block so the system path resolves the same values:

```css
@media (prefers-color-scheme: dark) {
  :root[data-mode="system"] .default {
    --surface-primary: var(--color-backgrounds-brand-ink);
    --text-primary: var(--color-text-frost);
    --accent-primary: var(--color-accent-dark);
    /* ...mirror the [data-mode="dark"] block above */
  }
}
```

Apply this pattern for every theme that declares a live `dark` mode in the YAML (`default`, `clarity`; `editorial` inherits `default`'s via the alias mechanism below). Themes that do not change between modes (`punctuation`, `statement`) need no override — their `dark` mode is intentionally absent, carried only as a commented-out template in the YAML. Dark themes (`feature-dark`, `code`, `deep`) also need no override — they are already dark.

**Alias-theme emission pattern.** An alias theme — declared in the YAML as `{ alias: <target> }` (e.g. `editorial: { alias: default }`) — has no bindings of its own. The generator emits it by adding the alias selector to **every** rule it generates for the target theme (the base class and each mode override) as a grouped selector. It never emits a standalone block for the alias and never re-derives values. **Resolution of the share-vs-declare question: an alias shares 100% of its target's rules in every mode — it does not declare its own override block.**

Worked example — `editorial` aliasing `default`:

```css
.default,
.editorial {
  --surface-primary: var(--color-backgrounds-ivory);
  /* ...every role the target binds, emitted once for both selectors... */
}

:root[data-mode="dark"] .default,
:root[data-mode="dark"] .editorial {
  --surface-primary: var(--color-backgrounds-brand-ink);
  /* ...every dark-mode row the target declares... */
}
```

Because the alias is grafted onto the target's selector list, it automatically tracks the target's mode behavior: if the target changes between modes, so does the alias; if the target does not, neither does the alias. The generator reads the `alias` field from data — it must not hardcode the alias map. Aliases do not chain (an alias must point at a concrete theme); the elements linter enforces this.

**Drift rule:** if a theme binding changes, change it in `customizable-design-elements.yaml` and regenerate the relevant block here. Never edit role-to-swatch bindings directly inside this CSS pattern.

### §8.3 Component class pattern

Components consume **role variables** (for color) and **geometry / motion tokens** (for sizing, spacing, radius, easing, duration) only. Raw palette hexes, raw lengths a scale already names, and brand-specific palette names never appear inside a component class. Sizing a component is the design system's job, not a page's: a component class reads `var(--sp-*)`, `var(--radius-*)`, `var(--section-pad-*)`, `var(--container-*)`, and component-level tokens like `var(--topbar-height)` — it does not bake in a literal a scale token already carries, and a page never re-declares those tokens to resize a component (see `compliance.md` §23).

```css
.card {
  background: var(--surface-raised);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--sp-2-5);
}

.button-primary {
  background: var(--button-primary-bg);
  color: var(--button-primary-text);
  border-radius: var(--radius-sm);
  font-weight: var(--fw-480);
  transition: color var(--duration-100) var(--ease-in-out),
              background-color var(--duration-200) var(--ease-in-out),
              box-shadow var(--duration-200) var(--ease-in-out);
}

.button-primary:hover {
  box-shadow: 0 0 0 1px var(--button-primary-bg);
}
```

Component-level geometry resolves the same way — the topbar bar and its logo both read system tokens, so the logo scales with the bar and no page hardcodes a height:

```css
.topbar { height: var(--topbar-height); }
.topbar-logo,
.topbar-logo img,
.topbar-logo svg { height: var(--topbar-logo-height); width: auto; }
```

---

### §8.4 Geometry and motion token emission

Geometry and motion are configurable element sets in the elements YAML (`geometry:`, `motion:`), peers to the color catalog. §8.4 holds only the **pattern** for emitting them; the **reference ships the values** (`foundations/layout.md §11` for spacing/radius/section-padding/containers, `foundations/motion.md §15` for easing/durations/patterns, `libraries/components/topbar.md` for component geometry such as the 84px topbar and 40px logo height), and an optional `geometry:`/`motion:` YAML row overrides the reference value for its key. The generator must not hardcode token lists — it emits the reference set and applies any YAML overrides per the `$conventions` patterns.

**Geometry tokens.** For every entry under `geometry.spacing` / `radius` / `section_padding` / `containers` / `columns`, emit one `:root` custom property using the matching `$conventions` pattern (`--sp-{key}`, `--radius-{key}`, `--section-pad-{key}`, `--container-{key}`, `--column-{key}`) with the row's `value` verbatim. For every `geometry.components.<component>.<property>`, emit `--{component}-{property}`. When a token carries a `mobile_floor`, emit a re-declaration at `:root` inside `@media (max-width: <max_width>)`:

```css
:root {
  --sp-2: clamp(28px, calc(28px + 4 * (100vw - 320px) / 1120), 32px);
  --radius-lg: 16px;
  --section-pad-main: clamp(96px, calc(96px + 32 * (100vw - 320px) / 1120), 128px);
  --column-wide: 1192px;
  --topbar-height: 84px;
  --topbar-logo-height: 40px;
}
@media (max-width: 480px) {
  :root { --section-pad-main: 56px; --topbar-height: 64px; }  /* from each token's mobile_floor */
}
```

**Motion tokens.** For every entry under `motion.easing` and `motion.duration`, emit one `:root` property (`--ease-{key}`, `--duration-{key}`). For every `motion.patterns.<pattern>.<property>`, emit `--{pattern}-{property}` (e.g. `--reveal-stagger`, `--card-duration`, `--fade-delay`).

**Motion pattern classes + keyframes.** Emit the entrance-pattern `@keyframes` and classes exactly as `foundations/motion.md` §15.4 specifies — parameterized by the `--{pattern}-*` tokens, animating in the base rule, resetting to the visible final state only inside `@media (prefers-reduced-motion: reduce)` — plus the global reduced-motion gate (§15.5). Entrance motion is **never** wrapped in `@media (prefers-reduced-motion: no-preference)`.

**Drift rule:** if a geometry or motion value changes, change it in `customizable-design-elements.yaml` and regenerate this block. Never edit a length, duration, or curve directly inside the generated CSS, and never re-declare a system token in a page's style block to resize a component.

---

## §9 JavaScript color-mode controller

Initialize the color-mode marker before the page paints. Run the controller from a small, render-blocking inline script in the document head so that the user does not see a flash of the wrong mode.

```html
<script>
  (function () {
    var STORAGE_KEY = 'site-mode';
    var stored = null;
    try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    var mode = stored || 'system';
    document.documentElement.setAttribute('data-mode', mode);
  })();
</script>
```

Expose a runtime controller that updates the marker, persists the user's choice, and listens for OS changes when in system mode.

```js
const STORAGE_KEY = 'site-mode';

export function setMode(mode) {
  document.documentElement.setAttribute('data-mode', mode);
  try {
    if (mode === 'system') {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, mode);
    }
  } catch (e) {}
}

export function getMode() {
  return document.documentElement.getAttribute('data-mode') || 'system';
}

const systemQuery = window.matchMedia('(prefers-color-scheme: dark)');
systemQuery.addEventListener('change', () => {
  if (getMode() === 'system') {
    // No-op — the CSS @media rule handles the visual flip automatically.
    // Dispatch a custom event for any components that need to react.
    window.dispatchEvent(new CustomEvent('site-mode-resolved'));
  }
});
```

Provide three controls in the user-facing preferences surface: `Light`, `Dark`, `System`. Selecting `System` clears the stored override and returns the surface to OS preference.

Surfaces that must lock to light (the public unauthenticated card, long-form legal pages) set `data-mode="light"` on the closest wrapper, overriding the root marker for their subtree only.
