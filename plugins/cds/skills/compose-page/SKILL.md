---
name: compose-page
description: Composes a Page — one or more Sections in sequence — and emits a self-contained Page HTML mock, plus isolated single-Section and single-Component renders. Two content modes — drafted (skill generates fill-in slots) or supplied (caller provides a file, attachment, or pasted text). Also owns iteration on a prior output — "v2", "iterate on the hero", "tweak the mock", "change X", "update the layout". Trigger on mock / design / draft / sketch / prototype / render / show me what X looks like — applied to a page, section, or component. Do NOT trigger on composing a Shell (compose-shell) or on nesting a Page inside a Shell (compose-view — "see it in the shell", "the full site view"). Do NOT trigger on audits or informational queries. Halts at the catalog boundary when a named Page, Section, or Component resolves in neither the reference nor the extensions, rather than guessing.
allowed-tools: Read, Write, Bash, Glob
---

## Read the model first

Read `../../reference/model/entity-catalog.md` **in full** before anything else in this skill — every row and every column of both tables, plus its "How to read this catalog" rules. It is normative and it is not skimmable: `Type`, `Extends`, `Construct`, and `Contains` carry meaning the descriptions alone do not; inheritance is transitive; `Contains` never implies "is a container"; `Abstract` and `Concrete` are deliberate; and `can` / `may` / `typically` never mean `must`. Do not proceed from a remembered or summarized version of it, and do not resolve any Building Blocks term — Element, Component, Shape, Frame, Section, Page, ShellDefinition, View, page family — until it has been read this run.

## What this skill does

Composes a **Page** per the shared build pipeline (`../../reference/pipeline.md`) and emits **Page HTML** at a resolved output path: the Page's realized Frames, without any shell. The output inlines the generated stylesheet set and the theming + color-mode scripts so it opens in any browser with no external assets. This skill owns Page composition and its discovery; catalog resolution, the resolution stages, run-modes, sidecars, and compliance are defined once in the pipeline and cited here — never restated.

A Page is one or more Sections in sequence (entity model: `../../reference/model/entity-catalog.md`). Each Section's Shape is assigned **eagerly** (named up front — by the Section entry's `shape:` frontmatter or by the caller) or **lazily** (the Rule Engine resolves it at build time from the Section's content via its ShapeSelectionRule, then the PageLevelAestheticConstraints rejection loop validates it). To see the Page inside a Shell afterward, the caller runs `compose-view`.

## Vocabulary

All internal terms are the Building Blocks entities (`../../reference/model/entity-catalog.md`): Page, Section, Shape, Component, Shell, View, page family. The caller's everyday words resolve against catalog entry names and their `aliases:` frontmatter in context; a word that resolves to nothing is asked about, never guessed.

## Render targets

- **Page HTML** (default) — the whole Page: its Sections in sequence, no shell.
- **isolated Section** — one Section in a minimal wrapper (width `--container-marketing-primary`, padding `--sp-4`, light color-mode default + toggle).
- **isolated Component** — one Component in the same minimal wrapper.

## Inputs

- **From caller (runtime):** plain-language request; optional supplied content (file path, attached document, pasted text); optional output path override; optional asset paths.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML — used indirectly through the generated stylesheet set; this skill does not re-read role bindings.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json`.
- **From the catalog** — the `../../reference/libraries/` + `../../reference/rules/` trees overlaid by `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same structure), resolved per `../../reference/pipeline.md` (Catalog resolution). The composer consults `libraries/pages/`, `libraries/sections/`, `libraries/shapes/`, `libraries/components/`, `rules/shape-selection/`, and `rules/page-constraints/`; entry format is `../../reference/libraries/FORMAT.md`.
- **From `../../reference/compliance.md`:** the rule set the compliance pass runs.
- **From `../../reference/foundations/`:** the emission specifics the stylesheet set already encodes; this skill re-reads none of these except for the theming + color-mode scripts inlined into the output head (`foundations/implementation.md`).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`:** default output directory.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`:** default asset path when the caller does not supply one.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-page/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-page/` (project).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`:** the project extensions directory, mirroring `libraries/` + `rules/` (Catalog resolution, `../../reference/pipeline.md`).
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used by the pipeline's stylesheet-freshness stage.

## Discovery checklist

Runs in this exact order.

1. **Routing check (FIRST).** Is the request actually a Shell composition ("compose my site's shell", nav/footer-only work) → STOP `WRONG_SKILL:compose-shell`. Is it a View ("see it in the shell", "the page inside the site") → STOP `WRONG_SKILL:compose-view`. Requests to build UI inside a running application are not composer work at all — the app repo builds directly with the design system in force (consult `apply-design-system`, audit before done); say so instead of composing.
2. **Run-mode detection (iteration vs update vs generate).** Resolve the candidate output path (from `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`, caller input, or default). Detect **iteration** (a state record exists at strict-equality `output_path` and the request reads as modification), **update/brownfield** (the caller supplies an existing artifact — on-disk HTML, an existing stylesheet, or a Figma reference/export — or uses update phrasing), or **generate** (neither), then hand the pipeline's Run-modes stage the resolved mode. A new `output_path` supplied against a request phrased as continuation of an older path gets one clarifying ask. Iteration starts from a prior CDS state record; update starts from external files.
3. **Page and page family.** Resolve the Page: a named catalog Page entry (e.g. `primary-landing`, `documentation`), or an ad-hoc Page the caller describes Section by Section. Every Page carries a **page family** (landing, app, editorial, docs, auth): take it when stated plainly or obvious from the prompt (a named catalog Page carries its own `page_family:`); otherwise ASK — never infer silently. The page family selects the typography and motion register and scopes the PageLevelAestheticConstraints.
4. **Render target.** The whole Page (default), an isolated Section, or an isolated Component, from the caller's words.
5. **Content mode.** Drafted (skill generates a fill-in markdown scaffold dynamically — asking only for the slots the resolved Sections and Components actually require, taken from their `libraries/` entries) OR supplied (caller provides a file path, attached document, or pasted text; read before composing).
6. **Asset paths.** Accept supplied artwork as file paths AND URLs bound to brief slots; URLs fetch into `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`. A slot with no supplied asset resolves through the Artwork contract's resolution order (`../../reference/artwork.md`), which records every asset in `<assets-dir>/artwork-manifest.yaml`. Default the assets directory from `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` if set, else ask.
7. **Mandatory / forbidden / leading elements.** Per the resolved Page's `sections` list and the page-constraint entries it references (`rules/page-constraints/`), plus any caller overrides.
8. **Output path.** Resolve to a concrete file path; if none is provided and none is discoverable → STOP `OUTPUT_PATH_UNRESOLVABLE`.

## Pipeline

Execute the shared build pipeline (`../../reference/pipeline.md`) with the resolved render target. The pipeline defines catalog resolution, the Page → per-Section resolution stages (eager and lazy Shape assignment, the PageLevelAestheticConstraints rejection loop, and the four-rung Shape-assignment waterfall that searches the rest of the ShapeLibrary — unmodified, then adapted — before anything is generated from scratch), the silent stylesheet-freshness stage, run-modes, sidecar emission, and the state record. This skill adds only the Page HTML render specifics:

- **Assembly.** Emit a single self-contained HTML file at the resolved output path. The `<head>` inlines `tokens.css`, `components.css`, `themes.css` (from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`) inside one `<style>` block, then inlines the theming + color-mode scripts from `../../reference/foundations/implementation.md`. Asset references in supplied content inline as a `data:` URI when readable from disk; an absolute URL or unreadable path is used verbatim with a warning to the caller. The HTML carries no agent-side metadata — no decision logs, provenance comments, or structural maps (the reasoning lives in the sidecars).
- **Build every Component to its `libraries/components/<name>.md` entry.** Layout, sizing, spacing, radius, and container width resolve from the generated tokens the entry's `token_bindings` name; the page block consumes them and declares no geometry of its own. A page-block override of a system geometry token is an `audit-against-system` finding (`../../reference/compliance.md`). A section wrapper's `max-width` is a `--container-*` width (`≥` the page width), never a `--column-*` reading width. If a needed dimension has no token, the gap belongs in the YAML `geometry:` block (STOP `MISSING_SPEC` and surface it), not in a page override.
- **Apply entrance motion through the generated classes only** (`.reveal-word`, `.card-stagger`, `.content-fade`, `.content-fade-up`), animating in the base rule and disabled only inside `@media (prefers-reduced-motion: reduce)`. Never author entrance `@keyframes` in a page block and never wrap an entrance in `@media (prefers-reduced-motion: no-preference)` (`../../reference/compliance.md`; `../../reference/foundations/motion.md`).
- **Isolated render targets** wrap the piece in a minimal HTML page container: viewport meta, `<html>`/`<body>`, light color-mode default with a top-right mode toggle, content width `--container-marketing-primary`, padding `--sp-4`.

Sidecars (`<basename>.wireframe.txt`, `<basename>.decisions.md`), the state record schema, and the compliance pass are the pipeline's — this skill triggers them, it does not redefine them. The compliance pass runs `[scope: standalone]` + `[scope: both]`.

## Change routing ("change the color of that button")

When an iteration request targets a value, determine what actually holds it: **this Page** (a content or per-page choice) or **the system** (a token, role, or theme in the elements YAML). Ask one clarifying question only when genuinely ambiguous ("just this page, or everywhere the system uses it?"). Edit whatever holds the value, let the silent freshness stage regenerate whatever that invalidates, re-render, and show the result. Never mention CSS, manifests, hashes, or staleness to the human.

## Halt conditions

- `WRONG_SKILL:{name}` — the request belongs to a different skill (`compose-shell` for Shell composition, `compose-view` for a Page inside a Shell); the caller must re-invoke the correct skill or slash command.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the pipeline's freshness stage found the set stale or missing and the auto-invoked `generate-css` itself halted; the inner code is surfaced verbatim.
- `PAGE_UNKNOWN:{name}` — the requested named Page resolves in neither the reference nor the extensions.
- `SECTION_TYPE_UNKNOWN:{id}` — a Section id in the Page sequence resolves in neither the reference nor the extensions. (A *known* Section whose rule candidates are all rejected is not a halt — the pipeline descends the Shape-assignment waterfall, reusing a library Shape where one fits and generating only as a last resort, and records the rung it landed on in the decisions sidecar.)
- `MISSING_SPEC` — a required spec is too thin to render and is absent from both the reference and the extensions (name the gap).
- `MISSING_COMPONENT:{name}` — a required Component is defined in neither reference nor extensions.
- `UPDATE_SOURCE_UNREADABLE` — the existing artifact supplied for a brownfield update cannot be read or parsed.
- `UPDATE_TARGET_AMBIGUOUS` — an update request cannot be localized to a specific region.
- `OUTPUT_PATH_UNRESOLVABLE` — no output path provided and none discoverable.
- `ARTWORK_UNRESOLVABLE:{slot}` — a needed artwork slot yields no asset through the resolution order in `../../reference/artwork.md` (system glyph set, generation, free-license sourcing, locate-and-hand-off).
- `COMPLIANCE_UNSATISFIABLE` — a compliance rule cannot be satisfied without violating a reference spec.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: compose-page: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

Iteration with an unreadable prior state record → STOP and ask the caller whether this is a fresh start or to supply the prior brief. Supplied content unreadable or unparseable → STOP and ask for an alternate path or paste.

## Compliance gate

The emitted Page HTML must satisfy every rule tagged `[scope: standalone]` and every rule tagged `[scope: both]` in `../../reference/compliance.md`, and must NOT contain agent-side metadata (no decision logs, provenance comments, or structural maps — those live in the sidecars).

## Boundary — does not

- Does not compose Shells (`compose-shell`) or Views (`compose-view`).
- Does not emit production-app code — the plugin never pivots into app work; designed changes travel via `package-change`.
- Does not inspect host-project code, naming, tokens, or patterns.
- Does not itself author stylesheet CSS; the pipeline's freshness stage INVOKES `generate-css` when inputs move, then proceeds — silently, never as an instruction to the human.
- Does not embed agent-side metadata in the emitted HTML; the wireframe and decisions sidecars are SEPARATE files.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
- Does not certify compliance after the fact — that is `audit-against-system`.
