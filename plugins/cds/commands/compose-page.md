---
description: Compose a Page — one or more Sections in sequence — as a self-contained Page HTML mock, or render a single Section or Component in isolation. Also handles iteration on prior outputs.
argument-hint: "[plain-language request, content path, or output_path of a prior run]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:compose-page

Invoke the `compose-page` skill in this plugin. Load and execute `skills/compose-page/SKILL.md` and follow its discovery checklist (routing check → run-mode detection → Page and page family → render target → content mode → asset paths → mandatory/forbidden/leading elements → output path), the shared build pipeline (`reference/pipeline.md`), halt conditions, and compliance gate exactly.

## Process

1. Load `skills/compose-page/SKILL.md`.
2. Treat `$ARGUMENTS` as the caller's plain-language request, supplied-content pointer, or output-path target. If `$ARGUMENTS` is empty, ask the user what page they want composed.
3. Run the discovery checklist in the exact order defined in the skill — step 1 (routing check) sends Shell composition to `/cds:compose-shell` and View requests to `/cds:compose-view`.
4. Execute the shared build pipeline (`reference/pipeline.md`) with the resolved render target, then the compliance pass; the pipeline emits the wireframe + decisions sidecars and writes the state record.

## Notes

- Render targets: **Page HTML** (default — the Page's Sections in sequence, no shell) and **isolated Section / Component** (wrapped at `--container-marketing-primary` width, `--sp-4` padding, light color-mode default with a top-right toggle).
- Every Page carries a **page family** (landing, app, editorial, docs, auth). If it is not stated plainly or obvious from the request, the skill asks.
- Each Section's Shape is assigned eagerly (named up front) or lazily (resolved at build by the Rule Engine via its ShapeSelectionRule, validated by the PageLevelAestheticConstraints rejection loop).
- Iteration: if a state record exists at the resolved `output_path`, the pipeline loads the prior `brief_snapshot` and `sections` and treats the request as a modification. Matching uses strict `output_path` equality.
- Library resolution is plugin ∪ extensions: a project grows the library via `*.md` entries under `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/libraries/{components,shapes,sections,pages}/` and `/rules/{shape-selection,page-constraints}/`, which override the plugin reference by name. A known Section whose rule candidates are all rejected descends the Shape-assignment waterfall — another library Shape, then an adapted one, then generation from scratch — and the rung it lands on is recorded in the decisions sidecar; it is never halted. Only an unknown Component or an unknown stored Shell halts (`reference/pipeline.md`, Library resolution).
- Stylesheet freshness is automatic and silent (pipeline stage): if the YAML / reference / extensions have moved, the pipeline regenerates the CSS itself and proceeds. The user is never told to run anything.
- Beside the HTML the pipeline writes two sidecars — `<basename>.wireframe.txt` and `<basename>.decisions.md`. The emitted HTML inlines the stylesheet set and stays metadata-free.
- Update mode: supply an existing HTML file (or a Figma reference) to apply the change to it as a region-scoped edit instead of regenerating from scratch.
- To see the composed Page inside a Shell, follow with `/cds:compose-view`.
- Halt codes the user may see: `WRONG_SKILL`, `STYLESHEETS_REGEN_FAILED`, `MISSING_SPEC`, `MISSING_COMPONENT`, `UPDATE_SOURCE_UNREADABLE`, `UPDATE_TARGET_AMBIGUOUS`, `OUTPUT_PATH_UNRESOLVABLE`, `ARTWORK_UNRESOLVABLE`, `COMPLIANCE_UNSATISFIABLE`, `ELEMENTS_YAML_UNSET`.
