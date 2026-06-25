# Foundations — Overview

## §1 What the design system is

Build an editorial, type-led interface whose visual character is established by three mapped substrates:

1. A **default light ground** mapped to the system's principal light surface token. The starting setup uses a warm ivory value.
2. A **dominant foreground ink** mapped to the system's primary text token. The starting setup uses a near-black value.
3. A **single restrained accent family** mapped to the system's primary accent tokens. The starting setup uses a saturated burnt-orange family.

Layer on top of this substrate:

- A **dual-family type system** pairing a humanist Primary Sans with a literary Editorial Serif, plus a Mono family reserved for code. Each role is mapped to a font family of the implementer's choice.
- A small set of **saturated panel grounds** reserved for theme-state interjections — feature panels, illustration tiles, badge fills. The shipped setup uses ten named tones (oat, peach, coral, fig, olive, mineral, cactus, sky, heather, plum); implementers map their own set into the same slot structure.
- A **role-and-theme architecture** in which every paintable element names a role; the surrounding theme wrapper defines what that role resolves to.

The system is conservative on long-form reading and editorial surfaces, lively on marketing and product surfaces. Motion is quiet on legal, editorial, and authentication; livelier on hero and feature sections. Across all surfaces, the same primary ink, the same selection tint, and the same reading-column width recur.

Build every surface from a single shared token vocabulary. Do not let any component bypass that vocabulary by hardcoding a hex value, a font name, or a font weight.

---

## §2 Architecture: roles, palette, themes, modes, page types

The architecture rests on roles, not colors.

```
An element names a role.
The palette names colors.
A theme is the contract between them.

The palette contains named swatches.
A theme assigns palette swatches to semantic roles.
Mode selects the light or dark resolution of the active theme.
Page type determines which themes wrap which sections.
Elements do not know about palettes, themes, modes, or page types.
Elements only request semantic roles.
```

The seven layers, in resolution order:

1. **Palette** — a flat dictionary of named swatches. Each swatch is a single hex value with no role. The values are implementer-mapped; the swatch names form a stable contract.
2. **Semantic role slots** — named CSS custom properties (`--surface-primary`, `--text-primary`, `--accent-primary`, etc.) that components request.
3. **Themes** — named wrapper classes (`editorial`, `deep`, etc.) that bind each role slot to a palette swatch.
4. **Mode** — a single document-root marker (`data-mode="light"` or `data-mode="dark"`) that re-binds the roles of every active theme to its dark-mode swatches when set to dark.
5. **Page type** — a high-level surface classification (marketing, editorial, legal, authentication, application shell) that determines which themes wrap which sections and how dense the visual rhythm is.
6. **Section wrappers** — block-level containers that carry a theme class and define the section's vertical rhythm and grid.
7. **Element / component** — leaves of the tree that paint themselves using only the role variables resolved by their nearest theme ancestor.

Adjacent layers:

- **Motion behavior** is bound to interaction state (rest, hover, focus, active, in-viewport) and respects the user's `prefers-reduced-motion` preference. It does not consume role variables; it consumes **motion tokens** (durations, easing curves, and entrance-pattern parameters) — a configurable element set defined in the elements YAML `motion:` block and emitted globally, peer to color and geometry.
- **Responsive behavior** scales typographic size, container width, section padding, and grid column count by viewport range. These are **geometry tokens** — a configurable element set defined in the elements YAML `geometry:` block (spacing, radius, section padding, container widths, and component sizing), emitted globally. Role variables do not change at breakpoints; geometry tokens interpolate with the viewport (`foundations/layout.md` §11.1).

### How one element gets painted

The full rendering sequence:

1. The browser exposes the operating-system color-scheme preference.
2. A small initialization script reads the OS preference.
3. The script reads any manual user override saved in local storage.
4. The script chooses the active mode: `light` or `dark`.
5. The script writes the active mode as `data-mode="light"` or `data-mode="dark"` on the document root.
6. The HTML contains section wrappers tagged with theme classes (`editorial`, `deep`, etc.).
7. CSS binds semantic role variables under each theme wrapper.
8. Light-mode rules bind roles to light-mode swatches.
9. Dark-mode rules rebind the same roles to dark-mode swatches when the root marker indicates dark mode.
10. Components request role variables only.
11. The browser resolves the closest applicable role value from the DOM ancestor chain.
12. The component paints using the resolved swatch.

```
The element never reads the palette.
The element never reads the theme.
The element never reads the mode.
The element never reads the page type.
The element only reads its role.
```

---

## §3 Brand input mapping

Before applying the rest of this document, decide how your brand's color and type vocabulary maps into the role-based contract. The actual values live in `customizable-design-elements.yaml`, resolved at the path held by the environment variable `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`. The shipped starting point lives at `../../setup/customizable-design-elements.yaml` — copy or symlink that file into your project, then edit it to match your brand. This narrative explains *what* you are deciding when you edit that file.

### §3.1 Brand input mapping — what each row represents

The YAML file enumerates a fixed set of input areas. Each row is a single mapping decision: a brand value going into a named role. The input areas are:

- **Default light surface** — used for the principal page ground.
- **Dominant foreground** — used for primary text and high-contrast controls.
- **Primary accent family** — used for selection, emphasis, and brand/action moments. Maps to four slots: primary, interactive, hover, and dark-mode variant.
- **Saturated panel colors** — used for panels, illustration tiles, and badges.
- **Primary Sans** — used for UI, nav, body sans, and application surfaces.
- **Editorial Serif** — used for editorial prose and expressive headings.
- **System Mono** — used for code and technical labels.
- **Geometry** — the `geometry:` block: spacing scale, radius scale, section-padding scale, container widths per surface, and component-level sizing (e.g. topbar bar/logo height). Each entry maps a length/clamp/keyword to a system token the components consume.
- **Motion** — the `motion:` block: easing curves, durations, and entrance-pattern parameters (reveal, card stagger, fade). Each entry maps a curve/time/parameter to a system token; the entrance patterns are emitted as keyframes + classes (`foundations/motion.md`).

Geometry and motion are **first-class configurable element sets**, peers to color and type. They are emitted as global tokens (not theme-bound roles — they do not change on the light/dark flip), so a component reads `var(--topbar-height)` or `var(--ease-in-out)` the same way it reads a role, and the design system — never a page — owns those values.

Optional compatibility aliases for brand-specific naming (e.g., `--p-burnt-orange` aliased to `--color-accent-primary`) may be kept in YAML if existing component code references them. These aliases are pure conveniences. Components consume **roles** (e.g., `--accent-primary`); themes bind those roles to the `accent` semantic palette; the `accent` palette aliases the `burnt-orange` primitive. Components never name a swatch.

### §3.2 Keep-or-replace decisions

| Decision | Keep Same | Replace With Your Own | Notes |
|---|---:|---:|---|
| Token names | Yes | Optional | Keep token names for easiest implementation. |
| Role names | Yes | No | Role names are the architecture contract. |
| Theme structure | Yes | No | Preserve the light/dark theme contract. |
| Color hex values | No | Yes | Replace with your palette. |
| Font families | No | Yes | Replace with mapped font roles. |
| Spacing scale | Yes | Optional | Preserve unless adapting to a materially different density. |
| Motion timing | Yes | Optional | Preserve unless adapting for a stricter accessibility or product context. |
| Component structure | Yes | Optional | Preserve for closest visual match. |

### §3.3 Mapping guidance

- Preserve the **relative contrast progression** of every ramp. If the reference ramp moves from white through twenty steps to absolute black, your mapped ramp should also progress in stable steps from your lightest neutral to your darkest neutral.
- Preserve the **role of each swatch**, not its specific tone. The "principal light ground" role exists regardless of whether your ground is ivory, warm gray, or cool gray.
- Preserve the **accent's restraint**. The reference accent is a single chromatic family. Your accent family should be similarly restrained — one hue family with rest, interactive, hover, and dark variants.
- Preserve the **panel-ground concept**. Saturated grounds carry feature panels and illustration tiles. The hues you choose should be muted enough to host near-black or near-white ink at full strength.

---

## §4 Palette philosophy

The palette is a flat dictionary of named swatches. No swatch carries a role. No component reads a swatch directly. Themes are the only consumers. The actual swatch values — every ramp step, every accent slot, every panel ground, every state swatch — live in `customizable-design-elements.yaml` (path resolved via `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`). This section explains *what* the palette is composed of and *why* each grouping exists.

### §4.1 Color ramps — twenty-one steps per ramp

The spine of the system is a set of four 21-step ramps: a neutral ramp plus three colored ramps (the shipped setup uses blue, green, red — implementers may swap the colored ramps, but should retain three of them). Every neutral surface, every neutral foreground, and every hairline draws from the neutral ramp; the colored ramps supply step-locked alternatives that themes and components can bind into role slots.

Each ramp progresses from pure white at step `000` to absolute black at step `1000`, with twenty named steps between. The contrast progression is the load-bearing property — preserve it even when hue choices change. Step names are stable (`000`, `050`, `100`, … `950`, `1000`); the hex value at each step is the implementer's choice, recorded in YAML.

### §4.2 Accent swatches

Use one restrained accent family for the system's primary chromatic emphasis. Map your accent family into four slots:

- **Primary accent** — drives text-selection tint at 50% mix and decorative emphasis.
- **Interactive accent** — brand-button fill across themes, AA contrast on the light ground.
- **Hover accent** — brand-button hover variant on dark mode.
- **Dark-mode accent** — substitutes for the primary accent in dark mode so the accent reads quieter on dark grounds.

Reserve every other saturated swatch for panel grounds and decorative tiles — accents are not panel paint.

### §4.3 Saturated panel grounds

Saturated panel grounds are **panel grounds only** — for theme-state feature blocks, illustration tiles, and badge fills. Never use them for body type, navigation paint, or default surfaces. Each panel ground declares a foreground binding (near-black ink or light ink) that fixes which ink contrast tier paints on top of it. On any saturated panel ground, the foreground inherits ink at full strength. Tertiary copy is rare on panel surfaces and uses a `35ch` max-width body-sans paragraph when it appears.

### §4.4 State swatches

State colors are their own palette swatches. They are used only inside the components that need them. The shipped setup defines:

- **Error-light** — inline error text on light themes.
- **Error-dark** — inline error text on dark themes.
- **Error-fill** — destructive-action button fill.
- **Required** — required-field asterisk ink. Reserved for this single purpose.
- **Focus-blue** — switch active-state fill and chromatic focus ring on input fields. The system's only chromatic blue.

The system has **no success-green swatch** and **no warning-yellow swatch** by design. Do not introduce them. Communicate success and warning states with copy, iconography, or layout, not with color.

### §4.5 Selection tint

Use the `selection-bg` role to define the global selection tint. The shipped setup defines its value (a 50% mix of the primary accent) in the role's fallback in the elements YAML; the CSS names no swatch. The selection tint should become a recognizable system signature.

```css
::selection {
  background-color: var(--selection-bg);
}
```

Do not override the selection tint per surface or per theme.

---

## §5 Semantic role slots — the philosophy

Roles exist so that components never know the color they paint. A component asks for `--text-primary`; the surrounding theme wrapper decides what color resolves under the cascade. This indirection is the entire reason themes and modes are cheap to swap — components do not change when the palette changes, when the theme changes, or when the mode flips from light to dark.

The shipped role inventory (defined in `customizable-design-elements.yaml`) covers every paintable surface in the system: page grounds, secondary and tertiary surfaces, raised and muted surfaces, primary/secondary/tertiary/inverse text, subtle and strong borders, the primary/interactive/heroes accents, selection tint, focus ring, navigation ground and text, footer ground and text, hero ground and text, the three button variants (primary, secondary, brand, tertiary) with their fill and label slots, the switch active fill, and error text and fill.

Every component requests these role slots by `var(--name)` only. **Never reference a `--p-*` palette swatch directly inside a component class.** The palette is for themes; roles are for components. The contract is one-directional: palette → role → component. Breaking it (by reading the palette from a component) collapses the indirection that makes the rest of the system work.

---

## Known gaps

- §3 narrates the input categories that live in YAML but does not enumerate the YAML's literal schema (key names, nesting, expected types). Implementers building tooling against the YAML must consult `customizable-design-elements.yaml` directly for the schema.
- §3 references `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` as the path resolver but does not specify the resolution algorithm (search order, fallback, error behavior when unset). The resolver contract is undefined.
- §4.5's selection tint consumes the `selection-bg` role (`var(--selection-bg)`); the accent-mix value lives in that role's fallback in the YAML. No palette swatch appears in the CSS — the global selection rule is now role-based like everything else.
- §4 narrative does not specify how to choose the colored-ramp hue families when an implementer wants to substitute different ramps (e.g., teal/amber/violet instead of blue/green/red), only that three colored ramps should exist.
- §5 narrative refers to a "shipped role inventory" enumerated in the YAML; the full role-slot table lives in the YAML, so the prose count of slots here is not independently verifiable from this document alone.
