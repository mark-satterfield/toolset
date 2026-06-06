---
name: compose-page
description: Produces a self-contained standalone HTML mock (not production app code) for a full page (landing, marketing, blog, doc, sign-in, announcement), a section in isolation, or a single UI component. Two content modes — drafted (skill generates fill-in slots) or supplied (caller provides a file, attachment, or pasted text). Also owns iteration on a prior mock — "v2", "iterate on the hero", "tweak the mock", "change X", "update the layout". Trigger on mock / design / draft / sketch / prototype / render / show me what X looks like — applied to a page, section, or component — when there is no signal the output should ship inside a running application. Do NOT trigger when the request contains "in the app", "for the app", "in-app", "add to the site", or names a live route (those route to compose-app-surface). Do NOT trigger on stylesheet regeneration or auditing. Composes any page type whose shape rules are present in the reference; if a requested type's rules are absent it halts with SHAPE_RULES_PENDING rather than guess.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Renders a single self-contained HTML file at a resolved output path. The mock inlines the generated stylesheet set and the theming + mode-resolution scripts so it opens correctly in any browser without external assets. Sections in isolation and components in isolation are wrapped in a minimal HTML page container so they render the same way. Iteration on a prior mock is handled in discovery — if a state record exists at the resolved output path, the prior `brief_snapshot` and `sections` are loaded and treated as the starting point.

## Inputs

- **From caller (runtime):** plain-language request; optional supplied content (file path, attached document, pasted text); optional output path override; optional asset paths.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML — used indirectly through the generated stylesheet set; this skill does not re-read role bindings.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json` for stale detection.
- **From shared reference (`../../reference/`):** `page-types.md`, `section-types.md`, `shapes.md` (S0–S28 catalog), `components.md`, `compliance.md`, and the foundations files — `foundations/overview.md`, `foundations/typography.md`, `foundations/layout.md`, `foundations/accessibility.md`, `foundations/motion.md`, `foundations/imagery.md`, `foundations/responsive.md`, `foundations/implementation.md` (§9 carries the theming + mode-resolution scripts inlined into the mock head).
- **From skill-local reference (`./reference/`):** `landing-sections-shape-rules.md` (defines `pick_shape`, variety principle, adjacency rules for landing pages).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`:** default output directory for mocks.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`:** default asset path when caller does not supply one.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-page/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-page/` (project).

## Discovery checklist

The checklist runs in this exact order. Step 1 is the routing gate.

1. **Handoff check (FIRST).** Does the request include "in the app", "for the app", "to the app", "in-app", or name a live route? If yes → STOP `WRONG_SKILL:compose-app-surface` and instruct the caller (user or agent) to re-invoke as `/cds:compose-app-surface`. For requests without app language but where embedding is genuinely ambiguous, ask one question: "Is this a standalone mock or should it ship inside the live app?"
2. **State-directory check.** Resolve the candidate output path (from `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` or caller input or default). Look for a prior state record at strict-equality `output_path`. If found and the request reads as modification → load `brief_snapshot` and `sections` and treat as iteration. If found but the request reads as a fresh start → ask explicitly. If a new `output_path` is supplied but the request reads as iteration of an older path → ask: "There's no prior run at this output_path; I see a prior run at `{older-path}` — is this a fresh start, or a continuation with a new filename?"
3. **Page type.** For drafted content, ASK — do not infer. For supplied content, ASK with a suggested default based on observable signals (article-only content → editorial detail; landing-typical mix → landing) but let the caller pick.
4. **Surface kind.** Page, section, or component. Section and component get wrapped in a minimal HTML page container.
5. **Content mode.** Drafted (skill generates a fill-in markdown scaffold dynamically — asking only for slots the relevant section types and component types actually require, derived from `section-types.md` and `components.md`) OR supplied (caller provides a file path, attached document, or pasted text; skill reads it before composing).
6. **Asset paths.** Default from `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` if set, else ask.
7. **Mandatory / forbidden / leading elements.** Per `page-types.md` for the chosen page type, plus any caller overrides.
8. **Stylesheet staleness.** Compute SHA-256 of the current `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` file. Compare to `manifest.json`'s `elements_yaml_sha256`. If mismatched, or the manifest is missing → ask the caller to run `generate-stylesheets` first; STOP `STYLESHEETS_MISSING` or `STYLESHEETS_STALE` accordingly.

## Pipeline

1. **Load page-type rules.** Read `../../reference/page-types.md` and `../../reference/section-types.md`. Identify the page-type entry for the chosen type and its mandatory / forbidden / leading constraints.
2. **Section sequence + shape derivation.** For **landing-page requests**, consult `./reference/landing-sections-shape-rules.md` and derive the ordered section sequence + a shape per section using its `pick_shape` rules, variety principle, and adjacency rules. **For any page type whose shape rules are not present in the reference, STOP `SHAPE_RULES_PENDING:{page-type}` and surface the gap — do not guess.**
3. **Content resolution.** For supplied content, parse it into section candidates per `./reference/landing-sections-shape-rules.md` (or STOP per Step 2 for non-landing). For drafted content, generate the fill-in markdown scaffold dynamically — asking only for the slots the chosen section types and component types actually need, with slot definitions taken from `section-types.md` and `components.md`. Present the scaffold to the caller; wait for filled values before continuing.
4. **Render the mock.** Emit a single self-contained HTML file at the resolved output path. The `<head>` inlines `tokens.css`, `components.css`, `themes.css` (read from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`) inside a single `<style>` block, then inlines the theming + mode-resolution scripts from `../../reference/foundations/implementation.md` §9. For asset references in supplied content: inline as a `data:` URI when the file is readable from disk; if the reference is an absolute URL or an unreadable path, emit a warning to the caller but use the reference verbatim. **Do NOT embed agent-side metadata in the HTML** — no decision logs, no provenance comments, no structural maps.
5. **Component- or section-in-isolation wrapping.** Wrap the isolated piece in a minimal HTML page container: viewport meta tag, `<html>` / `<body>`, light-mode default with a top-right mode toggle, 1440px viewport content width, 64px outer padding.
6. **Compliance pass.** Validate against `../../reference/compliance.md` rules tagged `[scope: standalone]` and `[scope: both]`. Any failure → fix in place; if a rule cannot be satisfied without violating a reference spec → STOP `PRECONDITION_FAILED` with the rule citation.
7. **Write the state record.** Append one YAML file named `{ISO-timestamp}-{output-basename}.yaml` to the resolved state directory using the shared state-record schema. Retain the last 10; delete older records after writing.

## Halt conditions

- `STYLESHEETS_MISSING` — `manifest.json` not found at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`.
- `STYLESHEETS_STALE` — elements-YAML SHA does not match `manifest.json`'s `elements_yaml_sha256`.
- `SHAPE_RULES_PENDING:{page-type}` — the requested page type's shape rules are not present in the reference.
- `MISSING_SPEC` — any required reference spec is too thin to render (name the gap).
- `MISSING_COMPONENT:{name}` — a required component is not defined in `../../reference/components.md`.
- `OUTPUT_PATH_UNRESOLVABLE` — no output path provided and none discoverable.
- `PRECONDITION_FAILED` — compliance rule cannot be satisfied against the resolved reference.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.
- `WRONG_SKILL:{name}` — the request belongs to a different skill (e.g., `compose-app-surface` when app-embedding language is present); the caller must re-invoke the correct skill or slash command.

Halt surface format:

```
STOP: compose-page: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

Iteration with an unreadable prior state record → STOP and ask the caller whether this is a fresh start or supply the prior brief.

Supplied content unreadable or unparseable → STOP and ask the caller for an alternate path or paste.

## Compliance gate

The emitted mock must satisfy every rule tagged `[scope: standalone]` and every rule tagged `[scope: both]` in `../../reference/compliance.md`. The mock must NOT contain agent-side metadata (no decision logs, no provenance comments, no structural maps).

## Boundary — does not

- Does not emit production-app code, framework-native components, or app shell wiring — `compose-app-surface` owns that.
- Does not inspect host-project code, naming, tokens, or patterns.
- Does not regenerate the stylesheet set — `generate-stylesheets` owns that.
- Does not embed agent-side metadata in the emitted HTML.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
- Does not certify compliance after the fact — that is `audit-against-system`.
