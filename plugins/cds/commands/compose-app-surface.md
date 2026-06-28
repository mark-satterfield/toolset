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
3. Run the discovery checklist (state-directory check → content mode → feature → kind of surface → where it lives → how it is reached → shell / page shape / components → inputs and state → framework target → stylesheet staleness).
4. Apply the pipeline: validate against `page-types.md` Application Shell rules, resolve every part to the deterministic reference, generate framework-native code per `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`, generate the wiring diff, write the state record.

## Notes

- Trigger condition: the user must explicitly signal app-embedding (`in the app`, `to the app`, `in-app`, or a live route name). Standalone-mock requests route to `/cds:compose-page` instead.
- The emitted code LINKS to the stylesheet set; it does NOT inline CSS (inlining is mock-only).
- The skill does NOT emit theme controllers, mode resolvers, or routing — those are host-owned.
- A project grows the catalog without a plugin release: `*.md` definitions under `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/{shapes,page-types,section-types}/` are read alongside the plugin reference and override it by name. Section-level shape decisions halt with `APP_SECTION_RULES_PENDING:{section-type}` only when present in neither the reference nor the extensions dir. Shell-layout and page-shape composition from `app-shapes.md` is supported.
- Stylesheet freshness is automatic: if the YAML / reference / extensions have moved, the skill invokes `generate-stylesheets` itself and proceeds (no manual regen; a comment- or description-only YAML edit does not trigger one).
- Update mode: supply existing files (from the repo or Figma) to apply the change as a region-scoped diff instead of a from-scratch rebuild.
- Halt codes the user may see: `FRAMEWORK_UNSET`, `STYLESHEETS_REGEN_FAILED`, `MISSING_COMPONENT`, `APP_SECTION_RULES_PENDING`, `MISSING_SPEC`, `UPDATE_SOURCE_UNREADABLE`, `UPDATE_TARGET_AMBIGUOUS`, `OUTPUT_PATH_UNRESOLVABLE`, `PRECONDITION_FAILED`, `ELEMENTS_YAML_UNSET`.
