---
description: Compose a standalone HTML mock — full page (landing / blog / doc / sign-in / announcement), a section in isolation, or a single component in isolation. Also handles iteration on prior mocks.
argument-hint: "[plain-language request, content path, or output_path of a prior run]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:compose-page

Invoke the `compose-page` skill in this plugin. Load and execute `skills/compose-page/SKILL.md` and follow its discovery checklist (handoff check → run-mode detection → Section Container [alias: page type] → render target → content mode → asset paths → mandatory/forbidden/leading elements → output path), the shared build pipeline (`reference/pipeline.md`), halt conditions, and compliance gate exactly.

## Process

1. Load `skills/compose-page/SKILL.md`.
2. Treat `$ARGUMENTS` as the caller's plain-language request, supplied-content pointer, or output-path target. If `$ARGUMENTS` is empty, ask the user what they want to mock.
3. Run the discovery checklist in the exact order defined in the skill — step 1 (handoff check) routes app-embedding requests to `/cds:compose-app-surface`.
4. Execute the shared build pipeline (`reference/pipeline.md`) with the resolved render target, then the compliance pass; the pipeline emits the wireframe + decisions sidecars and writes the state record.

## Notes

- Render targets: `assembled` (default, the full page), `container-only` (content without Shell furniture), `shell-only` (the frame with an unfilled content slot), `spa` (one Shell, N Section Containers, a client-side switcher), and isolated section/component (wrapped at `--container-marketing-primary` width, `--sp-4` padding, light color-mode default with a top-right toggle).
- Iteration: if a state record exists at the resolved `output_path`, the pipeline loads the prior `brief_snapshot` and `sections` and treats the request as a modification. Matching uses strict `output_path` equality.
- Catalog resolution is plugin ∪ extensions: a project grows the catalog via `*.md` entries under `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/libraries/{components,shapes,sections,section-containers,shells}/` and `/rules/{shape-selection,page-constraints}/`, which override the plugin reference by name. A known Section whose shape candidates are all rejected is fallback-generated (recorded in the decisions sidecar), not halted; only an unknown catalog entry halts.
- Stylesheet freshness is automatic (pipeline stage): if the YAML / reference / extensions have moved, the pipeline regenerates the stylesheet set and proceeds (a comment- or description-only YAML edit does not trigger a regeneration).
- Beside the HTML the pipeline writes two sidecars — `<mock>.wireframe.txt` and `<mock>.decisions.md`. The emitted HTML inlines the stylesheet set and stays metadata-free.
- Update mode: supply an existing HTML file (or a Figma reference) to apply the change to it as a region-scoped edit instead of regenerating from scratch.
- Halt codes the user may see: `WRONG_SKILL`, `STYLESHEETS_REGEN_FAILED`, `SHELL_UNKNOWN`, `SECTION_CONTAINER_UNKNOWN`, `SECTION_TYPE_UNKNOWN`, `MISSING_SPEC`, `MISSING_COMPONENT`, `UPDATE_SOURCE_UNREADABLE`, `UPDATE_TARGET_AMBIGUOUS`, `OUTPUT_PATH_UNRESOLVABLE`, `ARTWORK_UNRESOLVABLE`, `COMPLIANCE_UNSATISFIABLE`, `ELEMENTS_YAML_UNSET`.
