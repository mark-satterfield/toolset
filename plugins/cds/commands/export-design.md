---
description: Export the live Configurable Design System as a single DESIGN.md file — the map of colors, typography, geometry, motion, the Building Blocks catalog, rules, and compliance, written to the DESIGN.md convention for humans and tools alike.
argument-hint: "[output-path]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:export-design

Invoke the `export-design` skill in this plugin. Load and execute `skills/export-design/SKILL.md` and follow its discovery checklist, pipeline, halt conditions, and determinism contract exactly.

## Process

1. Load `skills/export-design/SKILL.md`.
2. Resolve the output path: `$ARGUMENTS` if given, else `$CUSTOMIZABLE_DESIGN_SYSTEM_DESIGN_MD_PATH`, else ask once for an absolute path.
3. Run the discovery checklist (resolve `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`; resolve the working catalog).
4. Run the freshness stage silently — regenerate the stylesheet set if the `cds_hash.py` fingerprints have moved, without surfacing anything about it to the user — so the generation stamp matches the current inputs.
5. Compose and write `DESIGN.md` per the skill's pipeline.

## Notes

- The emitted `DESIGN.md` follows Google Labs' `design.md` convention (frontmatter tokens + ordered `##` sections), extended with a generation stamp, a Building Blocks catalog (Components, Shapes, Sections, Pages — plus the statement that Shells are user-composed via `compose-shell` and never shipped), a Rules section, and a How-to-consume section for the CDS model.
- Regenerated, never hand-edited: the emitted header says so. Deterministic — the same elements-YAML meaning + catalog bytes produce a byte-identical file.
- Halt codes the user may see: `ELEMENTS_YAML_UNSET`, `OUTPUT_PATH_UNRESOLVABLE`, `STYLESHEETS_REGEN_FAILED`, `MISSING_SPEC`.
