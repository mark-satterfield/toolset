---
name: compose-app-surface
description: Builds and wires a surface — page route, in-app section, or shell component (modal, drawer, side panel) — into the host's live application. Emits framework-native code (target from $CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK) derived from the deterministic reference, plus the navigation, route-table, or shell diffs to make the surface reachable. Trigger ONLY when the request carries an explicit app-embedding signal — phrases like "in the app", "in-app", "to the app", "ship to the app", "add to the app"; a named live route as build target ("/settings", "/profile", "/billing/history"); or wiring verbs paired with a destination ("wire X into the checkout flow", "register a route at /Y", "add a drawer to /Z"). Do NOT trigger when the request lacks both app-embedding language and a live route (route to compose-page). Do NOT trigger when "for the app" describes non-UI work (tests, docs, audits, copy). Do NOT trigger on stylesheet regeneration, informational queries, or audits.
allowed-tools: Read, Write, Edit, Bash, Glob
---

## What this skill does

Resolves the requested surface — shell layout, page shape, components, navigation entry, route registration — entirely against the deterministic reference tree, then emits framework-native code (per `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`) plus the diffs needed to wire that surface into the host application's nav, side rail, route table, or parent component. The emitted code links to the generated stylesheet set (it does not inline it — inlining is a mock-packaging concern owned by `compose-page`). Host-owned concerns (theming, mode resolution, routing, the navigation shell, token bindings, build infrastructure) are never re-emitted.

## Inputs

- **From caller (runtime):** plain-language request; optional supplied content (file path, attached document, pasted text); the feature name; the kind of surface; where it lives in the codebase; how it is reached; runtime data dependencies.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML, used indirectly through the generated stylesheet set.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, `manifest.json` for stale detection.
- **From shared reference (`../../reference/`):** `page-types.md` (Application Shell rules), `section-types.md`, `components.md`, `compliance.md`, and the foundations files — `foundations/overview.md`, `foundations/layout.md`, `foundations/typography.md`, `foundations/accessibility.md`, `foundations/motion.md`, `foundations/imagery.md`, `foundations/responsive.md`, `foundations/implementation.md`.
- **From skill-local reference (`./reference/`):** `app-shapes.md` (shell layouts + page shapes for in-app surfaces).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`:** the target framework (e.g., `react`, `vue`, `svelte`, `solid`). If unset → STOP `FRAMEWORK_UNSET`.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR`:** default output directory inside the host project for emitted surfaces; otherwise asked at call time.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-app-surface/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-app-surface/` (project).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`:** the project extensions directory (`shapes/`, `page-types/`, `section-types/`, each holding `*.md` definitions), read **alongside** the plugin reference and **overriding it by name**, so a project grows the catalog without waiting on a plugin release.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used to detect a stale stylesheet set (the same hashes `generate-stylesheets` writes into `manifest.json`).

## Discovery checklist

1. **State-directory check (iteration).** Read the state directory for prior runs whose `output_path` matches the resolved candidate path or whose feature name matches the caller's request. If matched and the request reads as modification → load prior `brief_snapshot` and `sections` and treat as iteration. If matched but reads as fresh start → ask.
   - **Update (brownfield) source check.** Distinct from iteration: if the caller supplies EXISTING files to start FROM — on-disk framework file(s)/route, an existing stylesheet, or a Figma reference/export — or uses update phrasing ("update the existing X", "from the repo", "from Figma", a Figma URL), enter the **UPDATE path** (see Pipeline): the existing file(s) are the starting point and the change is applied as a region-scoped diff, not a from-scratch rebuild.
2. **Content mode.** Drafted or supplied. If supplied, read the source before proceeding. If drafted, generate a fill-in markdown scaffold dynamically once the surface kind is known — asking only for slots the chosen section types and component types require, derived from `section-types.md` and `components.md`.
3. **The feature.** One-sentence description of what the surface does.
4. **Kind of surface.** Page, section inside an existing in-app page, or component (modal / drawer / side panel) bound for the live app.
5. **Where it lives.** Resolve via `$CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR` if set; otherwise ask for an absolute output directory inside the host project.
6. **How it is reached.** Route path, nav entry, side rail entry, parent component invocation — whatever the wiring diff must express.
7. **Shell / page shape / components.** Map every part of the requested surface to a deterministic reference entry: shell layout → `./reference/app-shapes.md`; page shape → `./reference/app-shapes.md`; component → `../../reference/components.md`.
8. **Inputs and state.** Runtime data dependencies — independent of any supplied static content.
9. **Framework target.** Read `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`. If absent, ask once. If still unset → STOP `FRAMEWORK_UNSET`.
10. **Stylesheet freshness (auto-regenerate, never halt for staleness).** Compute the live input fingerprints — `python3 ../../lib/cds_hash.py inputs <$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS> ../../reference <$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR|NONE>` — and read `manifest.json`. If missing, or any of `elements_semantic_sha256` / `reference_tree_sha256` / `extensions_tree_sha256` differs → **invoke `generate-stylesheets` yourself** (`../generate-stylesheets/SKILL.md`), then proceed; do not stop and ask the caller to regenerate by hand. A comment- or `description:`-only YAML edit does not trigger a regeneration. If that regen halts, STOP `STYLESHEETS_REGEN_FAILED:{inner-code}` surfacing the inner halt verbatim.

## Pipeline

1. **Confirm host context.** Validate the request against `../../reference/page-types.md` Application Shell rules — the request must describe a surface that fits inside the host application's shell.
2. **Resolve every part to the reference (plugin + project extensions).** Build the working catalog as plugin-reference ∪ `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (a project definition whose name matches a plugin entry replaces it; project-only names extend it). Shell layout and page shape resolve against `./reference/app-shapes.md` overlaid with `extensions/shapes/`. Each component resolves against `../../reference/components.md`; a component defined in NEITHER reference NOR extensions → STOP `MISSING_COMPONENT:{name}` and name the gap (do not invent it). **For section-level shape decisions inside an app surface (which section type sits where, which shape it takes): STOP `APP_SECTION_RULES_PENDING:{section-type}` only when those rules are present in neither the plugin reference nor the project extensions** (`extensions/section-types/`).
3. **Load foundations and components.** Read `../../reference/foundations/layout.md`, `typography.md`, `accessibility.md`, `motion.md` plus every component family relevant to the resolved surface from `../../reference/components.md`.
4. **Generate framework-native code.** Per `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`, emit component code that implements the resolved spec exactly. The emitted code **links to or imports** the generated stylesheet set from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`; it does NOT inline that CSS. Class names match the kebab-case identifiers in `components.css`. ARIA contracts, keyboard semantics, and focus rules come from `foundations/accessibility.md` and the component entries — they are not invented.
5. **Generate the wiring diff.** Produce the unified diff for the navigation entry, side rail entry, route table change, or parent component update needed to make the new surface reachable. Each diff cites the file it modifies and the existing pattern it follows from the reference (not from inspected host code).
**Update path (brownfield).** When discovery selected the UPDATE path, do not emit a fresh file. Instead: (a) read and parse the supplied existing file(s) — framework component(s), an existing stylesheet, or a Figma reference resolved to markup — into a region map by component boundary; if unreadable or unparseable → STOP `UPDATE_SOURCE_UNREADABLE`; (b) localize the target region(s) the change touches — if it cannot be localized → STOP `UPDATE_TARGET_AMBIGUOUS`; (c) recompose ONLY the target region(s) through Steps 2–4 using the merged plugin+extension catalog; (d) emit a **region-scoped diff** against the existing file rather than a new file, leaving all non-targeted code byte-for-byte intact.

6. **Write the state record.** Append one YAML file named `{ISO-timestamp}-{output-basename}.yaml` to the resolved state directory using the shared state-record schema, including `mode` (`generate` | `update`) and — for updates — `update_source` (the path or Figma ref the change started from) and a per-section `preserved` flag (the `package-change` skill reads these). Retain the last 10. **Do NOT embed agent-side metadata in any emitted code.**

## Halt conditions

- `FRAMEWORK_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` not set and not supplied.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the stylesheet set was stale or missing and the auto-invoked `generate-stylesheets` itself halted; the inner halt code is surfaced verbatim.
- `MISSING_COMPONENT:{name}` — component defined in neither `../../reference/components.md` nor the project extensions.
- `APP_SECTION_RULES_PENDING:{section-type}` — section-level shape rules for in-app sections are present in neither the plugin reference nor the project extensions.
- `MISSING_SPEC` — a required spec is too thin to emit code and is absent from both reference and extensions (name the gap).
- `UPDATE_SOURCE_UNREADABLE` — the existing file(s) supplied for a brownfield update cannot be read or parsed.
- `UPDATE_TARGET_AMBIGUOUS` — an update request cannot be localized to a specific region.
- `OUTPUT_PATH_UNRESOLVABLE` — no host-project output directory provided and none discoverable.
- `PRECONDITION_FAILED` — request does not fit Application Shell rules from `page-types.md`.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: compose-app-surface: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

Emitted code must satisfy every rule tagged `[scope: app-embedded]` and every rule tagged `[scope: both]` in `../../reference/compliance.md`. Explicit negative checks: the output must NOT include theme controllers, mode resolvers, inlined stylesheets, route-table bootstrapping, or any other host-owned concern; it must NOT contain agent-side metadata; it must link to (not inline) the generated stylesheet set.

## Boundary — does not

- Does not generate standalone mocks — `compose-page` owns those.
- Does not emit theming, mode-resolution, routing, navigation-shell, or token-binding code — all host-owned.
- Does not inline the stylesheet set in emitted code.
- Does not inspect host-project code for naming, conventions, tokens, or patterns. Reference is the only source of truth.
- Does not run the host project's build, tests, or deploy.
- Does not write copy on the caller's behalf (drafted-mode scaffolds capture caller-provided copy; supplied content is rendered as-is).
- Does not itself author stylesheet CSS; when the inputs have moved it INVOKES `generate-stylesheets` to refresh the set, then proceeds — `generate-stylesheets` still owns CSS authoring.
- Does not embed agent-side metadata in any emitted file.
