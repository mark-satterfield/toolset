---
name: apply-design-system
description: Answers informational questions about this design system's class names, token names, event hooks, and ARIA contracts — for developers writing non-UI code (event handlers, state, data-fetching, business logic, glue) that must bind against plugin-generated surfaces. Returns a structured reference response; never emits code, HTML, CSS, JSX, or file changes. Trigger on "what does the design system say about X?", "what token/class names should my handler use?", "what ARIA contracts apply to modals / drawers / forms / tables?", "what events must my code bind against?", "what should I know about this surface before I wire it up?", "what's the compliance gate for my handler?". Do NOT trigger when the user asks to generate, write, update, or change any code or UI (route to compose-page or compose-app-surface). Do NOT trigger on stylesheet regeneration (generate-stylesheets) or audits (audit-against-system).
allowed-tools: Read, Glob, Grep
---

## What this skill does

Loads the reference content the author needs to write non-UI code (handlers, data layer, state, business logic) that interacts cleanly with surfaces the plugin generates. Returns a structured markdown response — never a code artifact. The author writes the code; this skill makes sure they bind against the right class names, token names, event hooks, and ARIA contracts.

## Inputs

- **From caller (runtime):** what is being built or changed (one sentence); which generated surface (page, section, or component) the author's code interacts with; rendering context (app-embedded or standalone); UI category (navigation, shell, modal, form, table, card grid, hero, footer, etc.); any motion or interaction requirements beyond defaults.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML — used to surface accurate token names back to the author.
- **From shared reference (`../../reference/`):** always `page-types.md`, `foundations/overview.md`, `foundations/layout.md`, `foundations/typography.md`, `foundations/accessibility.md`; plus category-specific files (`components.md`, `foundations/motion.md`, `foundations/imagery.md`, `foundations/responsive.md`, the shared `shapes.md` catalog, and relevant shape-rules content from sibling skills' reference trees when needed).
- **From `../compose-app-surface/reference/`:** `app-shapes.md` for shell-surface and modal-context questions.

This skill does **not** consume any `CUSTOMIZABLE_DESIGN_SYSTEM_*` env var that points at host-project code or stylesheets. It surfaces token names from `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`; it never emits CSS or HTML.

## Discovery checklist

1. **One sentence.** What is the author building or changing?
2. **Which surface.** Which page, section, or component does the non-UI code interact with?
3. **Rendering context.** App-embedded or standalone? Some contracts differ.
4. **UI category.** Navigation, shell, modal, form, table, card grid, hero, footer, list, etc.
5. **Motion / interaction.** Anything beyond defaults that the handler must coordinate with (open/close transitions, optimistic state, focus management, dismissal semantics)?

## Pipeline

1. **Confirm rendering context.** App-embedded code must not assume a theme controller is present; standalone surfaces have one inlined.
2. **Identify page-type context** from `../../reference/page-types.md`. If the surface is in-app, also load the Application Shell section.
3. **Load the reference set for the category.** Always: `page-types.md`, `foundations/layout.md`, `foundations/typography.md`, `foundations/accessibility.md`, and `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`. Plus category-specific files:
   - **Shell surfaces** → `../compose-app-surface/reference/app-shapes.md` + `../../reference/components.md`.
   - **Modals / drawers / side panels** → `../../reference/components.md` (Centered Dialog, Drawer, Side Panel sections) + `foundations/accessibility.md` (focus trap, dismissal, ARIA).
   - **Forms** → `../../reference/components.md` (input families) + `foundations/accessibility.md` (label / error / live-region contracts).
   - **Tables / card grids** → `../../reference/components.md` + the relevant `shapes.md` content from `../compose-page/reference/` or `../compose-app-surface/reference/` depending on context.
   - **Motion-coupled handlers** → `../../reference/foundations/motion.md`.
4. **Surface the loaded content** to the caller as a structured markdown response with these named sections (each section may be empty if not applicable for the category):

   ```
   ## Class names
   ## Token names
   ## Event hooks
   ## ARIA contracts
   ## Reference pointers
   ## Halt conditions
   ```

   Class names are the kebab-case identifiers from `components.css` (`.button-primary`, `.surface-secondary`, `.text-tertiary`, etc.). Token names are the CSS custom properties from `tokens.css` (`--color-{palette}-{shade}`, `--role-{key}`, etc.). Event hooks and ARIA contracts come verbatim from `components.md` and `foundations/accessibility.md`. Reference pointers are file-and-section citations so the author can read deeper.

5. **Point the author at `../../reference/compliance.md`** for their completion gate — that is where they verify their non-UI code keeps the surface on-system.

## Halt conditions

- `MISSING_SPEC` — the reference does not cover the author's category. Surface the gap explicitly. Do not direct the author at host-project code as a substitute for missing reference.

Halt surface format:

```
STOP: apply-design-system: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## What this skill does NOT do

- Does not generate HTML, JSX, CSS, framework-native components, or Figma instructions.
- Does not author code changes on the caller's behalf.
- Does not direct the author to inspect host-project code as a substitute for the reference.
- Does not modify UI surfaces — those are owned by `compose-page` and `compose-app-surface`.
- Does not write any artifact file. Output is a structured markdown response surfaced to the caller's context.

## Boundary — does not

- Does not produce mocks (`compose-page`).
- Does not produce in-app code (`compose-app-surface`).
- Does not regenerate stylesheets (`generate-stylesheets`).
- Does not audit existing UI (`audit-against-system`).
- Never invents class names, token names, event hooks, or ARIA contracts — every value surfaced has a reference citation.
