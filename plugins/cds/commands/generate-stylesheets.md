---
description: Regenerate the Configurable Design System stylesheet set — tokens.css, components.css, themes.css, and manifest.json — from the elements YAML and reference tree.
argument-hint: "[--full | --incremental]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:generate-stylesheets

Invoke the `generate-stylesheets` skill in this plugin. Load and execute `skills/generate-stylesheets/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and compliance gate exactly.

## Process

1. Load `skills/generate-stylesheets/SKILL.md`.
2. Parse `$ARGUMENTS` for `--full` (explicit full regenerate) or `--incremental` (skip-on-no-change). Default is incremental.
3. Run the discovery checklist (resolve `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`; resolve output directory from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR` or ask once; surface prior `manifest.json` if present).
4. Validate the elements YAML against `validation/customizable-design-elements.schema.json` and check the `$schema_version` against the schema's `$id` major version.
5. Compose `tokens.css`, `components.css`, `themes.css`, and `manifest.json` per the skill's pipeline.

## Notes

- Determinism contract: for the same `(elements YAML semantic content, reference tree bytes)` pair, the emitted CSS is byte-identical. Comments and `description:` prose are excluded from the YAML fingerprint, so they do not affect the output.
- After this command, `compose-page` and `compose-app-surface` pass their stale-detection checks against the new `manifest.json`.
- Halt codes the user may see: `ELEMENTS_YAML_UNSET`, `OUTPUT_PATH_UNRESOLVABLE`, `ELEMENTS_INVALID`, `ELEMENTS_VERSION_MISMATCH`, `MISSING_SPEC`.
