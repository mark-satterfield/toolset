---
name: compose-view
description: Produces a View — one Page's HTML nested inside a stored Shell — so the user sees the page as a visitor would. Also produces the SPA variant — one stored Shell plus N Pages with a client-side switcher showing one at a time. Trigger on "see it in the shell", "the page inside the site", "the full site view", "put the landing page in the main shell", "SPA mock", "single-page app mock with these screens". Do NOT trigger on composing a Page (compose-page) or composing/editing a Shell (compose-shell). One Shell serves many Pages; a Shell edit re-frames all Views regenerated afterward.
allowed-tools: Read, Write, Bash, Glob
---

## Read the model first

Read `../../reference/model/entity-catalog.md` **in full** before anything else in this skill — every row and every column of both tables, plus its "How to read this catalog" rules. It is normative and it is not skimmable: `Type`, `Extends`, `Construct`, and `Contains` carry meaning the descriptions alone do not; inheritance is transitive; `Contains` never implies "is a container"; `Abstract` and `Concrete` are deliberate; and `can` / `may` / `typically` never mean `must`. Do not proceed from a remembered or summarized version of it, and do not resolve any Building Blocks term — Element, Component, Shape, Frame, Section, Page, ShellDefinition, View, page family — until it has been read this run.

## What this skill does

Produces a **View** per the shared build pipeline (`../../reference/pipeline.md`): the combination of a generated Page HTML nested inside a stored **Shell** — the Page fills the Shell's vacant space. The Shell is resolved **by name** from `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` (the output area `compose-shell` stores into). The View is one self-contained HTML file, the thing a person opens and looks at.

**SPA variant:** one stored Shell + N Pages, with a client-side switcher in the mock that shows one Page at a time in the vacant space — the same mechanism as the color-mode toggle; no routing code.

## Inputs

- **From caller (runtime):** which Page(s) — an existing composed Page HTML (by output path), or a Page to compose first (delegated to `compose-page`); which Shell, by name; optional output path override.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`:** the stored Shells, one file per Shell, named per Shell. Unset → the `shells/` directory that is a sibling of the mocks directory.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`:** default output directory for the View, and where prior Page HTML outputs live.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json`.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-view/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-view/` (project).
- **From `../../reference/compliance.md`:** the rule set the compliance pass runs.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used by the pipeline's stylesheet-freshness stage.

## Discovery checklist

1. **Routing check.** Page-only work ("just the content, no shell") → STOP `WRONG_SKILL:compose-page`. Shell authoring or editing → STOP `WRONG_SKILL:compose-shell`.
2. **Resolve the Shell by name** from the shells area (pipeline Stage: Resolve the Shell). Unnamed with exactly one stored Shell → use it. Unnamed with several → one clarifying ask listing the stored names. Named but absent → STOP `SHELL_UNKNOWN:{name}`. No stored Shells at all → say so and route the user to `compose-shell` first (a View needs a Shell to nest into).
3. **Resolve the Page(s).** An existing Page HTML at a given path is used as-is (its state record supplies the section map for the sidecars). A Page described but not yet composed is composed first via the `compose-page` pipeline, then nested. For the SPA variant, resolve every Page in the requested set the same way.
4. **Run-mode detection.** A state record at the resolved View output path + a modification request = **iteration** (re-nest with the change; a Page-content change routes to `compose-page` iteration first, a Shell change to `compose-shell`). Otherwise **generate**.
5. **Output path.** Default beside the mocks (`$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`); STOP `OUTPUT_PATH_UNRESOLVABLE` if nothing resolves.

## Pipeline

Execute the shared build pipeline (`../../reference/pipeline.md`) — catalog resolution and per-Section stages apply when a Page must be composed fresh; the silent stylesheet-freshness stage always runs. This skill adds the View render specifics:

- **Assembly.** Nest the Page HTML's content into the stored Shell's vacant space and emit one self-contained HTML file: stylesheet set and theming + color-mode scripts inlined once in the `<head>`, no duplicated machinery from the two sources.
- **SPA variant.** Nest N Pages; emit a client-side switcher (same mechanism as the color-mode toggle — a `data-` attribute on the root, a small inline script, CSS visibility rules) showing one Page at a time in the vacant space. No routing code, no URL handling.
- **Freshness of ingredients.** A stored Shell older than the current stylesheet set is re-inlined from the current set during nesting (the stored Shell's structure is reused; the CSS inlined into the View is always current — the invisible-machinery guarantee).
- **State record** (pipeline schema): the Shell name, the Page path(s), and the output path, for iteration; sidecars as the pipeline defines.

The compliance pass runs `[scope: standalone]` + `[scope: both]`.

## Halt conditions

- `WRONG_SKILL:{name}` — the request belongs to `compose-page` or `compose-shell`.
- `SHELL_UNKNOWN:{name}` — no stored Shell of that name exists in the shells area.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the freshness stage's auto-invoked `generate-css` halted; inner code surfaced verbatim.
- `TARGET_UNREADABLE` — a supplied Page HTML path cannot be read.
- `OUTPUT_PATH_UNRESOLVABLE` — no output path provided and none discoverable.
- `COMPLIANCE_UNSATISFIABLE` — a compliance rule cannot be satisfied without violating a reference spec.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: compose-view: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

The emitted View must satisfy every rule tagged `[scope: standalone]` and `[scope: both]` in `../../reference/compliance.md`, and stays metadata-free (reasoning lives in the sidecars).

## Boundary — does not

- Does not compose Pages (`compose-page`) or Shells (`compose-shell`) beyond delegating to their pipelines when an ingredient is missing.
- Does not emit routing code, URL handling, or app wiring — the SPA switcher is a mock-local visibility mechanism only.
- Does not inspect host-project code.
- Does not itself author stylesheet CSS; the freshness stage INVOKES `generate-css` silently when inputs move.
- Does not modify stored Shells (`compose-shell` owns edits) or any file under `../../reference/`.
