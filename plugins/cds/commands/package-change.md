---
description: Bundle an approved CDS change into one hand-off package for the app repo — the stylesheet set, the composer's HTML artifact (Page HTML, Shell, or View), a derived build spec, the wireframe and decision-log sidecars, and ancillary assets.
argument-hint: "[output_path of a prior composer output — a Page HTML, a Shell, or a View]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:package-change

Invoke the `package-change` skill in this plugin. Load and execute `skills/package-change/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and bundle layout exactly.

## Process

1. Load `skills/package-change/SKILL.md`.
2. Treat `$ARGUMENTS` as the target — the `output_path` of a prior composer output (a Page HTML, a Shell, or a View). If empty, ask which approved change to package.
3. Run discovery: resolve the target's state record (searching all three state directories), determine the artifact kind (Page HTML, Shell, or View), resolve the bundle output root.
4. Apply the pipeline: load the state record, run the silent stylesheet-freshness stage, synthesize the build spec, copy the artifacts, add the `update/` folder for brownfield changes, and write the bundle README.

## Notes

- This is the boundary from "approved in cds" to "built in the app repo": the bundle is everything the app-repo developer (or developer agent) needs, and nothing is injected back into the source artifacts.
- The bundle carries the composer's HTML artifact only — never a `.review.html` file, which is the review skill's harness artifact and stays behind as a working file.
- The bundle always ships a CURRENT stylesheet set; the skill guarantees this internally and never presents it to the user as something to run.
- For a brownfield (update-mode) change the bundle also carries the original-files snapshot and the region-scoped change diff.
- When the assets directory holds an `artwork-manifest.yaml` (the artwork provenance record from `reference/artwork.md`), the bundle ships it in `assets/` alongside the icon/image files.
- Halt codes the user may see: `STATE_RECORD_NOT_FOUND`, `OUTPUT_PATH_UNRESOLVABLE`, `STYLESHEETS_REGEN_FAILED`, `ASSETS_UNRESOLVABLE`, `ELEMENTS_YAML_UNSET`.
