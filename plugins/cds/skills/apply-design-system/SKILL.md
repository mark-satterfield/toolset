---
name: apply-design-system
description: Answers informational questions about this design system's class names, token names, event hooks, and ARIA contracts — for developers writing non-UI code (event handlers, state, data-fetching, business logic, glue) that must bind against plugin-generated surfaces. Returns a structured reference response; never emits code, HTML, CSS, JSX, or file changes. Trigger on "what does the design system say about X?", "what token/class names should my handler use?", "what ARIA contracts apply to modals / drawers / forms / tables?", "what events must my code bind against?", "what should I know about this surface before I wire it up?", "what's the compliance gate for my handler?". Do NOT trigger when the user asks to generate, write, update, or change any code or UI (route to the composers — compose-page, compose-shell, compose-view). Do NOT trigger on audits (audit-against-system).
allowed-tools: Read, Glob, Grep
---

## What this skill does

Loads the reference content the author needs to write non-UI code (handlers, data layer, state, business logic) that interacts cleanly with surfaces the plugin generates. Returns a structured markdown response — never a code artifact. The author writes the code; this skill makes sure they bind against the right class names, token names, event hooks, and ARIA contracts.

## Inputs

- **From caller (runtime):** what is being built or changed (one sentence); which generated surface (page, section, or component) the author's code interacts with; rendering context (app-embedded or standalone); UI category (navigation, Shell, modal, form, table, card grid, hero, footer, etc.); any motion or interaction requirements beyond defaults.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML — used to surface accurate token names back to the author.
- **From the catalog (`../../reference/libraries/` + `../../reference/rules/`):** always the `libraries/pages/` entry for the surface's Page, `foundations/overview.md`, `foundations/layout.md`, `foundations/typography.md`, `foundations/accessibility.md`; plus category-specific entries — `libraries/components/*.md`, `libraries/shapes/*.md`, `libraries/sections/*.md`, the `rules/shape-selection/` and `rules/page-constraints/` entries, `foundations/motion.md`, `foundations/imagery.md`, `foundations/responsive.md` — resolved (plugin ∪ extensions) per `../../reference/pipeline.md`. Entry format is `../../reference/libraries/FORMAT.md`; the caller's words resolve against entry names and their `aliases:` frontmatter in context, with the vocabulary itself defined in `../../reference/model/entity-catalog.md`.

This skill does **not** consume any `CUSTOMIZABLE_DESIGN_SYSTEM_*` env var that points at host-project code or stylesheets. It surfaces token names from `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`; it never emits CSS or HTML.

## Discovery checklist

1. **One sentence.** What is the author building or changing?
2. **Which surface.** Which page, section, or component does the non-UI code interact with?
3. **Rendering context.** App-embedded or standalone? Some contracts differ.
4. **UI category.** Navigation, Shell, modal, form, table, card grid, hero, footer, list, etc.
5. **Motion / interaction.** Anything beyond defaults that the handler must coordinate with (open/close transitions, optimistic state, focus management, dismissal semantics)?

## Pipeline

1. **Confirm rendering context.** App-embedded code must not assume a theme controller is present; standalone surfaces have one inlined.
2. **Identify the Page context** from `../../reference/libraries/pages/`. If the surface is in-app, load the matching app-family Page entry. Any Shell around it is user-composed (`compose-shell`) and stored in `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` — the plugin ships no Shell catalog, so Shell contracts are surfaced from the Component entries that realize a Shell's Sections (`shell_component: true` in `../../reference/libraries/components/*.md`), never read off generated HTML.
3. **Load the catalog set for the category** (plugin ∪ extensions, per `../../reference/pipeline.md`). Always: the surface's `libraries/pages/` entry, `foundations/layout.md`, `foundations/typography.md`, `foundations/accessibility.md`, and `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`. Plus category-specific entries:
   - **Shell surfaces** → the `../../reference/libraries/components/*.md` entries marked `shell_component: true` (topbar, footer, left-rail, mobile-drawer, skip-links, workspace-switcher, account-row) — these carry the contracts for a Shell's persistent Sections.
   - **Modals / drawers / side panels** → `../../reference/libraries/components/{dialog,mobile-drawer,modal-with-form,dropdown-panel}.md` (and siblings) + `foundations/accessibility.md` (focus trap, dismissal, ARIA).
   - **Forms** → the input-family entries under `../../reference/libraries/components/` + `foundations/accessibility.md` (label / error / live-region contracts).
   - **Tables / card grids** → `../../reference/libraries/components/*.md` + the relevant `../../reference/libraries/shapes/*.md` entries.
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

   Class names are the kebab-case identifiers from `components.css` (`.button`, `.surface-secondary`, `.text-tertiary`, etc.). Token names are the CSS custom properties from `tokens.css` (`--color-{palette}-{shade}`, `--{key}`, etc.). Event hooks and ARIA contracts come verbatim from the Component entries' `behavior` and `accessibility` frontmatter (`../../reference/libraries/components/*.md`) and `foundations/accessibility.md`. Reference pointers are file-and-section citations so the author can read deeper.

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
- Does not modify UI surfaces — those are owned by the composers (`compose-page`, `compose-shell`, `compose-view`).
- Does not write any artifact file. Output is a structured markdown response surfaced to the caller's context.

## Boundary — does not

- Does not produce mocks (`compose-page`).
- Does not produce in-app code — the plugin never pivots into app work.
- Does not produce or modify the stylesheet set — it only reads token and class names back to the author.
- Does not audit existing UI (`audit-against-system`).
- Never invents class names, token names, event hooks, or ARIA contracts — every value surfaced has a reference citation.
