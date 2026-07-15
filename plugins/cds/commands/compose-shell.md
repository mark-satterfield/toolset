---
description: Compose a Shell — the repeating menus/footer of a site — from your content and instructions; shows it and stores it by name for reuse in Views.
argument-hint: "[shell name and content — e.g. \"main: top nav with Home / Pricing / Docs, footer with the legal links\"]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:compose-shell

Invoke the `compose-shell` skill in this plugin. Load and execute `skills/compose-shell/SKILL.md` and follow its discovery checklist (routing check → run-mode detection → shell name → content → output area), the shared build pipeline (`reference/pipeline.md`), halt conditions, and compliance gate exactly.

## Process

1. Load `skills/compose-shell/SKILL.md`.
2. Treat `$ARGUMENTS` as the Shell's name and content description. If `$ARGUMENTS` is empty, ask what the shell should contain (menus, links, logo, footer) and what to call it.
3. Run the discovery checklist in order; compose per the pipeline; show the emitted Shell; store it named-per-Shell in the shells output area.

## Notes

- The ShellDefinition is the transient blueprint (it carries the real menu items, logo, and colors); the stored **Shell** HTML is what persists for reuse. `compose-view` resolves it by name.
- Shells store in `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`; when unset, a `shells/` directory that is a sibling of the mocks directory is used automatically — no ask at compose time.
- Editing a Shell later is this same command: the stored file is overwritten, and Views regenerated afterward inherit the change.
- Stylesheet freshness is automatic and silent; the user is never told to run anything.
- Halt codes the user may see: `WRONG_SKILL`, `STYLESHEETS_REGEN_FAILED`, `MISSING_COMPONENT`, `MISSING_SPEC`, `OUTPUT_PATH_UNRESOLVABLE`, `ARTWORK_UNRESOLVABLE`, `COMPLIANCE_UNSATISFIABLE`, `ELEMENTS_YAML_UNSET`.
