---
name: compose-app-surface
description: Builds and wires a surface — page route, in-app section, or in-app Component (modal, drawer, side panel) — into the host's live application. Emits framework-native code (target from $CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK) derived from the deterministic reference, plus the navigation, route-table, or shell diffs to make the surface reachable. Trigger ONLY when the request carries an explicit app-embedding signal — phrases like "in the app", "in-app", "to the app", "ship to the app", "add to the app"; a named live route as build target ("/settings", "/profile", "/billing/history"); or wiring verbs paired with a destination ("wire X into the checkout flow", "register a route at /Y", "add a drawer to /Z"). Do NOT trigger when the request lacks both app-embedding language and a live route (route to compose-page). Do NOT trigger when "for the app" describes non-UI work (tests, docs, audits, copy). Do NOT trigger on stylesheet regeneration, informational queries, or audits.
allowed-tools: Read, Write, Edit, Bash, Glob
---

## What this skill does

Renders the shared build pipeline (`../../reference/pipeline.md`) to framework-native app code (per `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`) plus the diffs that wire the surface into the host application's nav, side rail, route table, or parent component. This skill owns the app render target and its discovery; catalog resolution, the resolution stages, run-modes, sidecars, and compliance are defined once in the pipeline and cited here — never restated. The emitted code links to the generated stylesheet set (it does not inline it — inlining is the mock render target, owned by `compose-page`). Host-owned concerns (theming, color-mode resolution, routing, the host's navigation frame, token bindings, build infrastructure) are never re-emitted.

## Vocabulary

Internal Building Blocks terms, with the user-facing alias on first use: **Shell** (alias: app screen frame / the surrounding chrome) — the app Shell wraps a Section Container with persistent Sections; panes are the layout regions those Sections and the content slot occupy. What callers name a sidebar / rail / left nav is a persistent Section of the app Shell; its layout region is a pane, a geometry concept (`--pane-*` tokens), not a Building Blocks term. **Section Container** (alias: page type), **Section** (alias: in-app region / band), **Shape** (alias: layout / arrangement), **Component** (alias: widget / control). `../../reference/aliases.md` maps every user-facing word onto these; this skill translates the caller's words at the boundary and uses internal vocabulary everywhere after.

## Render targets (from `../../reference/pipeline.md`)

This skill emits the app-side render targets:

- **assembled** (default) — the app Shell's persistent Sections + the Section Container.
- **container-only** — the Section Container alone (a section or component bound into an existing in-app page), without the Shell's persistent Sections.

App output links the stylesheet set, emits framework-native code plus a wiring diff citing the reference, and never emits theme controllers, color-mode resolvers, or routing.

## Inputs

- **From caller (runtime):** plain-language request; optional supplied content (file path, attached document, pasted text); the feature name; the kind of surface; where it lives in the codebase; how it is reached; runtime data dependencies.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML, used indirectly through the generated stylesheet set.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, `manifest.json`.
- **From the catalog** — the `../../reference/libraries/` + `../../reference/rules/` trees overlaid by `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same structure), resolved per `../../reference/pipeline.md` (Catalog resolution). App surfaces resolve against `libraries/shells/` (app-family Shells and extensions), `libraries/section-containers/` (app family), `libraries/sections/`, `libraries/shapes/`, `libraries/components/`, and `rules/`; entry format is `../../reference/libraries/FORMAT.md`.
- **From `../../reference/compliance.md`:** the rule set the compliance pass runs.
- **From `../../reference/foundations/`:** the emission specifics the stylesheet set already encodes (ARIA contracts, keyboard semantics, focus rules come from the Component entries and `foundations/accessibility.md`).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`:** the target framework (e.g. `react`, `vue`, `svelte`, `solid`). If unset → STOP `FRAMEWORK_UNSET`.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR`:** default output directory inside the host project for emitted surfaces; otherwise asked at call time.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-app-surface/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-app-surface/` (project).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`:** the project extensions directory, mirroring `libraries/` + `rules/` (Catalog resolution, `../../reference/pipeline.md`).
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used by the pipeline's stylesheet-freshness stage.

## Discovery checklist

Alias translation (`../../reference/aliases.md`) happens throughout.

1. **Run-mode detection (iteration vs update vs generate).** Read the state directory for a prior run whose `output_path` matches the resolved candidate path or whose feature name matches the request. Detect **iteration** (matched, request reads as modification), **update/brownfield** (the caller supplies existing files to start FROM — on-disk framework file(s)/route, an existing stylesheet, or a Figma reference/export — or uses update phrasing), or **generate** (neither), then hand the pipeline's Run-modes stage the resolved mode. Iteration starts from a prior CDS state record; update starts from external files.
2. **Content mode.** Drafted or supplied. If supplied, read the source before proceeding. If drafted, generate a fill-in markdown scaffold dynamically once the surface kind is known — asking only for the slots the resolved Sections and Components require, taken from their `libraries/` entries.
3. **The feature.** One-sentence description of what the surface does.
4. **Kind of surface.** Page (assembled: app Shell + Section Container), or a Section or Component bound into an existing in-app page (container-only). Translate the caller's words through the alias table.
5. **Where it lives.** Resolve via `$CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR` if set; otherwise ask for an absolute output directory inside the host project. If none is resolvable → STOP `OUTPUT_PATH_UNRESOLVABLE`.
6. **How it is reached.** Route path, nav entry, side rail entry, parent component invocation — whatever the wiring diff must express.
7. **Shell / Section Container / Sections / Components.** Map every part of the requested surface to a catalog entry; the pipeline's resolution stages do the lookup and the halts.
8. **Inputs and state.** Runtime data dependencies — independent of any supplied static content. Static artwork (hero images, logos, glyphs) arrives as file paths AND URLs bound to brief slots; URLs fetch into `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`, and a slot with no supplied asset resolves through the Artwork contract's resolution order (`../../reference/artwork.md`), which records every asset in `<assets-dir>/artwork-manifest.yaml`.
9. **Framework target.** Read `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`. If absent, ask once. If still unset → STOP `FRAMEWORK_UNSET`.

## Pipeline

Execute the shared build pipeline (`../../reference/pipeline.md`) with render target = the target resolved in discovery (default `assembled`, or `container-only` for a section/component bound into an existing page). The pipeline defines catalog resolution, the Shell → Section Container → per-Section resolution stages (including dynamic Shape selection, the page-constraint rejection loop, and fallback generation for a known Section whose candidates are all rejected), the stylesheet-freshness stage, the render targets, run-modes, sidecar emission, and the state record. This skill adds only the app render specifics:

- **Confirm host fit.** The request must describe a surface that fits an app-family Shell. If it fits no app Shell → STOP `SHELL_FIT_FAILED`.
- **Emit framework-native code** per `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` that implements the resolved spec exactly. The code **links to or imports** the generated stylesheet set from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`; it does NOT inline that CSS. Class names match the kebab-case identifiers in `components.css`. ARIA contracts, keyboard semantics, and focus rules come from `../../reference/foundations/accessibility.md` and the Component entries — they are not invented. The code carries no agent-side metadata.
- **Emit the wiring diff.** Produce the unified diff for the navigation entry, side rail entry, route table change, or parent component update that makes the surface reachable. Each diff cites the file it modifies and the existing pattern it follows from the reference (not from inspected host code).

Sidecars (`<basename>.wireframe.txt`, `<basename>.decisions.md`), the state record schema, and the compliance pass are the pipeline's — this skill triggers them, it does not redefine them. The compliance pass runs `[scope: app-embedded]` + `[scope: both]`.

## Halt conditions

- `FRAMEWORK_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` not set and not supplied.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the pipeline's freshness stage found the set stale or missing and the auto-invoked `generate-stylesheets` itself halted; the inner code is surfaced verbatim.
- `SHELL_UNKNOWN:{name}` — a named Shell resolves in neither the reference nor the extensions.
- `SECTION_CONTAINER_UNKNOWN:{name}` — the requested Section Container resolves in neither the reference nor the extensions.
- `SECTION_TYPE_UNKNOWN:{id}` — a Section id in the container sequence resolves in neither the reference nor the extensions. (A *known* Section whose Shape candidates are all rejected is not a halt — the pipeline fallback-generates a fitting layout and records it in the decisions sidecar.)
- `MISSING_COMPONENT:{name}` — a Component is defined in neither reference nor extensions.
- `MISSING_SPEC` — a required spec is too thin to emit code and is absent from both reference and extensions (name the gap).
- `UPDATE_SOURCE_UNREADABLE` — the existing file(s) supplied for a brownfield update cannot be read or parsed.
- `UPDATE_TARGET_AMBIGUOUS` — an update request cannot be localized to a specific region.
- `OUTPUT_PATH_UNRESOLVABLE` — no host-project output directory provided and none discoverable.
- `ARTWORK_UNRESOLVABLE:{slot}` — a needed artwork slot yields no asset through the resolution order in `../../reference/artwork.md` (system glyph set, generation, free-license sourcing, locate-and-hand-off).
- `SHELL_FIT_FAILED` — the request does not fit any app Shell.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: compose-app-surface: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

Emitted code must satisfy every rule tagged `[scope: app-embedded]` and every rule tagged `[scope: both]` in `../../reference/compliance.md`. Explicit negative checks: the output must NOT include theme controllers, color-mode resolvers, inlined stylesheets, route-table bootstrapping, or any other host-owned concern; it must NOT contain agent-side metadata; it must link to (not inline) the generated stylesheet set.

## Boundary — does not

- Does not generate standalone mocks — `compose-page` owns those.
- Does not emit theming, color-mode-resolution, routing, host-navigation-frame, or token-binding code — all host-owned.
- Does not inline the stylesheet set in emitted code.
- Does not inspect host-project code for naming, conventions, tokens, or patterns. The catalog is the only source of truth.
- Does not run the host project's build, tests, or deploy.
- Does not write copy on the caller's behalf (drafted-mode scaffolds capture caller-provided copy; supplied content is rendered as-is).
- Does not itself author stylesheet CSS; the pipeline's freshness stage INVOKES `generate-stylesheets` when inputs move, then proceeds.
- Does not embed agent-side metadata in any emitted file.
