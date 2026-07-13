---
name: compose-page
description: Produces a self-contained standalone HTML mock (not production app code) for a full page (landing, marketing, blog, doc, sign-in, announcement), a section in isolation, or a single UI component. Two content modes — drafted (skill generates fill-in slots) or supplied (caller provides a file, attachment, or pasted text). Also owns iteration on a prior mock — "v2", "iterate on the hero", "tweak the mock", "change X", "update the layout". Trigger on mock / design / draft / sketch / prototype / render / show me what X looks like — applied to a page, section, or component — when there is no signal the output should ship inside a running application. Do NOT trigger when the request contains "in the app", "for the app", "in-app", "add to the site", or names a live route (those route to compose-app-surface). Do NOT trigger on stylesheet regeneration or auditing. Composes any Section Container (the user-facing page type) present in the catalog; halts at the catalog boundary when a named Shell, Section Container, or Section id resolves in neither the reference nor the extensions, rather than guessing.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Renders the shared build pipeline (`../../reference/pipeline.md`) to a standalone HTML mock at a resolved output path. The mock inlines the generated stylesheet set and the theming + color-mode scripts so it opens in any browser with no external assets. This skill owns the mock render target and its discovery; catalog resolution, the resolution stages, run-modes, sidecars, and compliance are defined once in the pipeline and cited here — never restated.

## Vocabulary

Internal Building Blocks terms, with the user-facing alias on first use: **Section Container** (alias: page type), **Shell** (alias: the frame / nav and footer), **Section** (alias: band / stripe / block), **Shape** (alias: layout / arrangement), **Component** (alias: widget / control). `../../reference/aliases.md` maps every user-facing word onto these; this skill translates the caller's words at the boundary and uses internal vocabulary everywhere after.

## Render targets (from `../../reference/pipeline.md`)

This skill emits the mock-side render targets:

- **assembled** (default) — the Shell's persistent Sections + the Section Container. The user's "the page / full page".
- **container-only** — the Section Container alone, without the Shell's persistent Sections. The user's "just the content, no nav, no footer".
- **shell-only** — the Shell alone, its Section Container slot labeled but unfilled (the Shell rendered as its template / Shell Template view). The user's "the frame / the chrome".
- **spa** — one Shell, N Section Containers, a client-side switcher showing one at a time (the same mechanism as the color-mode toggle; no routing code).
- **isolated section / component** — the piece in a minimal wrapper (width `--container-marketing-primary`, padding `--sp-4`, light color-mode default + toggle).

## Inputs

- **From caller (runtime):** plain-language request; optional supplied content (file path, attached document, pasted text); optional output path override; optional asset paths.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the elements YAML — used indirectly through the generated stylesheet set; this skill does not re-read role bindings.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json`.
- **From the catalog** — the `../../reference/libraries/` + `../../reference/rules/` trees overlaid by `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same structure), resolved per `../../reference/pipeline.md` (Catalog resolution). The composer consults `libraries/shells/`, `libraries/section-containers/`, `libraries/sections/`, `libraries/shapes/`, `libraries/components/`, `rules/shape-selection/`, and `rules/page-constraints/`; entry format is `../../reference/libraries/FORMAT.md`.
- **From `../../reference/compliance.md`:** the rule set the compliance pass runs.
- **From `../../reference/foundations/`:** the emission specifics the stylesheet set already encodes; the mock re-reads none of these except for the theming + color-mode scripts inlined into the mock head (`foundations/implementation.md`).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`:** default output directory for mocks.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`:** default asset path when the caller does not supply one.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-page/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-page/` (project).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`:** the project extensions directory, mirroring `libraries/` + `rules/` (Catalog resolution, `../../reference/pipeline.md`).
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used by the pipeline's stylesheet-freshness stage.

## Discovery checklist

Runs in this exact order. Step 1 is the routing gate; alias translation (`../../reference/aliases.md`) happens throughout.

1. **Handoff check (FIRST).** Does the request include "in the app", "for the app", "to the app", "in-app", or name a live route? If yes → STOP `WRONG_SKILL:compose-app-surface` and instruct the caller to re-invoke as `/cds:compose-app-surface`. For requests without app language but where embedding is genuinely ambiguous, ask one question: "Is this a standalone mock or should it ship inside the live app?"
2. **Run-mode detection (iteration vs update vs generate).** Resolve the candidate output path (from `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`, caller input, or default). Detect **iteration** (a state record exists at strict-equality `output_path` and the request reads as modification), **update/brownfield** (the caller supplies an existing artifact — on-disk HTML, an existing stylesheet, or a Figma reference/export — or uses update phrasing), or **generate** (neither), then hand the pipeline's Run-modes stage the resolved mode. A new `output_path` supplied against a request phrased as continuation of an older path gets one clarifying ask. Iteration starts from a prior CDS state record; update starts from external files.
3. **Section Container (alias: page type).** For drafted content, ASK — do not infer. For supplied content, ASK with a suggested default from observable signals (article-only content → `editorial-detail`; landing-typical mix → `primary-landing`) but let the caller pick. Translate the caller's page-type words through `../../reference/aliases.md`.
4. **Render target.** Resolve from the caller's words (assembled / container-only / shell-only / spa / isolated section / isolated component) per the alias table. Default is assembled.
5. **Content mode.** Drafted (skill generates a fill-in markdown scaffold dynamically — asking only for the slots the resolved Sections and Components actually require, taken from their `libraries/` entries) OR supplied (caller provides a file path, attached document, or pasted text; read before composing).
6. **Asset paths.** Accept supplied artwork as file paths AND URLs bound to brief slots; URLs fetch into `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`. A slot with no supplied asset resolves through the Artwork contract's resolution order (`../../reference/artwork.md`), which records every asset in `<assets-dir>/artwork-manifest.yaml`. Default the assets directory from `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` if set, else ask.
7. **Mandatory / forbidden / leading elements.** Per the resolved Section Container's `sections` list and the page-constraint entries it references (`rules/page-constraints/`), plus any caller overrides.
8. **Output path.** Resolve to a concrete file path; if none is provided and none is discoverable → STOP `OUTPUT_PATH_UNRESOLVABLE`.

## Pipeline

Execute the shared build pipeline (`../../reference/pipeline.md`) with render target = the target resolved in discovery (default `assembled`). The pipeline defines catalog resolution, the Shell → Section Container → per-Section resolution stages (including dynamic Shape selection, the page-constraint rejection loop, and fallback generation for a known Section whose candidates are all rejected), the stylesheet-freshness stage, the render targets, run-modes, sidecar emission, and the state record. This skill adds only the mock render specifics:

- **Assembly (mock).** Emit a single self-contained HTML file at the resolved output path. The `<head>` inlines `tokens.css`, `components.css`, `themes.css` (from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`) inside one `<style>` block, then inlines the theming + color-mode scripts from `../../reference/foundations/implementation.md`. Asset references in supplied content inline as a `data:` URI when readable from disk; an absolute URL or unreadable path is used verbatim with a warning to the caller. The HTML carries no agent-side metadata — no decision logs, provenance comments, or structural maps (the reasoning lives in the sidecars).
- **Build every Component to its `libraries/components/<name>.md` entry.** Layout, sizing, spacing, radius, and container width resolve from the generated tokens the entry's `token_bindings` name; the page block consumes them and declares no geometry of its own. A page-block override of a system geometry token is an `audit-against-system` finding (`../../reference/compliance.md`). A section wrapper's `max-width` is a `--container-*` width (`≥` the page width), never a `--column-*` reading width. If a needed dimension has no token, the gap belongs in the YAML `geometry:` block (STOP `MISSING_SPEC` and surface it), not in a page override.
- **Apply entrance motion through the generated classes only** (`.reveal-word`, `.card-stagger`, `.content-fade`, `.content-fade-up`), animating in the base rule and disabled only inside `@media (prefers-reduced-motion: reduce)`. Never author entrance `@keyframes` in a page block and never wrap an entrance in `@media (prefers-reduced-motion: no-preference)` (`../../reference/compliance.md`; `../../reference/foundations/motion.md`).
- **Isolated render targets** wrap the piece in a minimal HTML page container: viewport meta, `<html>`/`<body>`, light color-mode default with a top-right mode toggle, content width `--container-marketing-primary`, padding `--sp-4`.

Sidecars (`<basename>.wireframe.txt`, `<basename>.decisions.md`), the state record schema, and the compliance pass are the pipeline's — this skill triggers them, it does not redefine them. The compliance pass runs `[scope: standalone]` + `[scope: both]`.

## Halt conditions

- `WRONG_SKILL:{name}` — the request belongs to a different skill (e.g. `compose-app-surface` when app-embedding language is present); the caller must re-invoke the correct skill or slash command.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the pipeline's freshness stage found the set stale or missing and the auto-invoked `generate-stylesheets` itself halted; the inner code is surfaced verbatim.
- `SHELL_UNKNOWN:{name}` — a named Shell resolves in neither the reference nor the extensions.
- `SECTION_CONTAINER_UNKNOWN:{name}` — the requested Section Container resolves in neither the reference nor the extensions.
- `SECTION_TYPE_UNKNOWN:{id}` — a Section id in the container sequence resolves in neither the reference nor the extensions. (A *known* Section whose Shape candidates are all rejected is not a halt — the pipeline fallback-generates a fitting layout and records it in the decisions sidecar.)
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

The emitted mock must satisfy every rule tagged `[scope: standalone]` and every rule tagged `[scope: both]` in `../../reference/compliance.md`, and must NOT contain agent-side metadata (no decision logs, provenance comments, or structural maps — those live in the sidecars).

## Boundary — does not

- Does not emit production-app code, framework-native components, or app shell wiring — `compose-app-surface` owns that.
- Does not inspect host-project code, naming, tokens, or patterns.
- Does not itself author stylesheet CSS; the pipeline's freshness stage INVOKES `generate-stylesheets` when inputs move, then proceeds.
- Does not embed agent-side metadata in the emitted HTML; the wireframe and decisions sidecars are SEPARATE files.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
- Does not certify compliance after the fact — that is `audit-against-system`.
