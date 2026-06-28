---
description: Bundle an approved CDS change into one hand-off package for the app repo — the stylesheet set, the mock or surface, a derived build spec, the wireframe and decision-log sidecars, and ancillary assets.
argument-hint: "[output_path of a prior mock, or a prior app-surface feature/output]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:package-change

Invoke the `package-change` skill in this plugin. Load and execute `skills/package-change/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and bundle layout exactly.

## Process

1. Load `skills/package-change/SKILL.md`.
2. Treat `$ARGUMENTS` as the target — the `output_path` of a prior `compose-page` mock, or the feature/output of a prior `compose-app-surface` run. If empty, ask which approved change to package.
3. Run discovery: resolve the target's state record, determine the source kind (mock vs surface), resolve the bundle output root.
4. Apply the pipeline: load the state record, confirm stylesheet freshness (regenerating if stale), synthesize the build spec, copy the artifacts, add the `update/` folder for brownfield changes, and write the bundle README.

## Notes

- This is the boundary from "approved in cds" to "built in the app repo": the bundle is everything the app-repo developer (or developer agent) needs, and nothing is injected back into the source artifacts.
- The bundle ships a CURRENT stylesheet set: if the set is stale the skill regenerates it first (via `generate-stylesheets`) before copying.
- For a brownfield (update-mode) change the bundle also carries the original-files snapshot and the region-scoped change diff.
- Halt codes the user may see: `STATE_RECORD_NOT_FOUND`, `OUTPUT_PATH_UNRESOLVABLE`, `STYLESHEETS_REGEN_FAILED`, `ASSETS_UNRESOLVABLE`, `ELEMENTS_YAML_UNSET`.
