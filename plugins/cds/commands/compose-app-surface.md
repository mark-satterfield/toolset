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
- Section-level shape decisions inside an app surface halt with `APP_SECTION_RULES_PENDING:{section-type}` until those rules are present in the reference. Shell-layout and page-shape composition from `app-shapes.md` is supported.
- Halt codes the user may see: `FRAMEWORK_UNSET`, `STYLESHEETS_MISSING`, `STYLESHEETS_STALE`, `MISSING_COMPONENT`, `APP_SECTION_RULES_PENDING`, `MISSING_SPEC`, `OUTPUT_PATH_UNRESOLVABLE`, `PRECONDITION_FAILED`, `ELEMENTS_YAML_UNSET`.
