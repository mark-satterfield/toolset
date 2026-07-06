---
description: Generate a new surface inside the host application — page route, in-app section, or in-app component (modal / drawer / side panel) — plus the wiring diffs (nav, route table, parent component) to make it reachable.
argument-hint: "[plain-language request naming an app route, surface, or feature]"
allowed-tools: Read, Write, Edit, Bash, Glob, AskUserQuestion
---

# /cds:compose-app-surface

Invoke the `compose-app-surface` skill in this plugin. Load and execute `skills/compose-app-surface/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and compliance gate exactly.

## Process

1. Load `skills/compose-app-surface/SKILL.md`.
2. Treat `$ARGUMENTS` as the caller's plain-language request. If empty, ask what surface they want to ship inside the app.
3. Run the discovery checklist (run-mode detection → content mode → feature → kind of surface → where it lives → how it is reached → Shell / Section Container / Sections / Components → inputs and state → framework target).
4. Execute the shared build pipeline (`reference/pipeline.md`) with render target `assembled` (or `container-only` for a section/component bound into an existing page): confirm host fit, resolve every part to the catalog, emit framework-native code per `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`, emit the wiring diff. The pipeline emits the wireframe + decisions sidecars and writes the state record.

## Notes

- Trigger condition: the user must explicitly signal app-embedding (`in the app`, `to the app`, `in-app`, or a live route name). Standalone-mock requests route to `/cds:compose-page` instead.
- Render targets: `assembled` (app Shell + Section Container) and `container-only` (a Section or Component bound into an existing in-app page).
- The emitted code LINKS to the stylesheet set; it does NOT inline CSS (inlining is the mock render target).
- The skill does NOT emit theme controllers, color-mode resolvers, or routing — those are host-owned.
- Catalog resolution is plugin ∪ extensions: `*.md` entries under `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/libraries/{components,shapes,sections,section-containers,shells}/` and `/rules/{shape-selection,page-constraints}/` are read alongside the plugin reference and override it by name. App-family Shells (A1–A5 and extensions) and app-family Section Containers compose here; a known Section whose shape candidates are all rejected is fallback-generated (recorded in the decisions sidecar), not halted; only an unknown catalog entry halts.
- Stylesheet freshness is automatic (pipeline stage): if the YAML / reference / extensions have moved, the pipeline invokes `generate-stylesheets` and proceeds (no manual regen; a comment- or description-only YAML edit does not trigger one).
- Update mode: supply existing files (from the repo or Figma) to apply the change as a region-scoped diff instead of a from-scratch rebuild.
- Halt codes the user may see: `FRAMEWORK_UNSET`, `STYLESHEETS_REGEN_FAILED`, `SHELL_UNKNOWN`, `SECTION_CONTAINER_UNKNOWN`, `SECTION_TYPE_UNKNOWN`, `MISSING_COMPONENT`, `MISSING_SPEC`, `UPDATE_SOURCE_UNREADABLE`, `UPDATE_TARGET_AMBIGUOUS`, `OUTPUT_PATH_UNRESOLVABLE`, `ARTWORK_UNRESOLVABLE`, `SHELL_FIT_FAILED`, `ELEMENTS_YAML_UNSET`.
