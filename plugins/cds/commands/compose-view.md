---
description: Produce a View — a composed Page nested inside a stored Shell — or an SPA mock (one Shell, N Pages, client-side switcher).
argument-hint: "[page (path or description) + shell name — e.g. \"landing.html in the main shell\"]"
allowed-tools: Read, Write, Bash, Glob, AskUserQuestion
---

# /cds:compose-view

Invoke the `compose-view` skill in this plugin. Load and execute `skills/compose-view/SKILL.md` and follow its discovery checklist (routing check → resolve the Shell by name → resolve the Page(s) → run-mode detection → output path), the shared build pipeline (`reference/pipeline.md`), halt conditions, and compliance gate exactly.

## Process

1. Load `skills/compose-view/SKILL.md`.
2. Treat `$ARGUMENTS` as the Page (path or description) and the Shell name. If `$ARGUMENTS` is empty, ask which Page and which Shell.
3. Run the discovery checklist in order; nest the Page into the Shell's vacant space; emit one self-contained View HTML.

## Notes

- The Shell resolves **by name** from the shells output area (`$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`; default: the `shells/` sibling of the mocks directory). Exactly one stored Shell → used without asking; several → one clarifying ask; none → compose one with `/cds:compose-shell` first.
- One Shell serves many Pages. Editing the Shell (`/cds:compose-shell`) re-frames every View regenerated afterward.
- **SPA variant:** one stored Shell + N Pages with a client-side switcher showing one at a time — the same mechanism as the color-mode toggle; no routing code.
- Stylesheet freshness is automatic and silent; the CSS inlined into the View is always current.
- Halt codes the user may see: `WRONG_SKILL`, `SHELL_UNKNOWN`, `STYLESHEETS_REGEN_FAILED`, `TARGET_UNREADABLE`, `OUTPUT_PATH_UNRESOLVABLE`, `COMPLIANCE_UNSATISFIABLE`, `ELEMENTS_YAML_UNSET`.
