# CDS — Customizable Design System

A brand-neutral design system you install in any project. CDS gives you a stylesheet set, a way to mock pages, sections, and components, a way to ship framework-native in-app surfaces, a way to package an approved mock into a hand-off bundle, a DESIGN.md export, and an audit tool — all derived from one YAML file of design choices you supply.

---

## What's in the box

- **8 slash commands** for direct invocation: `/cds:setup`, `/cds:generate-stylesheets`, `/cds:compose-page`, `/cds:compose-app-surface`, `/cds:apply-design-system`, `/cds:audit-against-system`, `/cds:export-design`, `/cds:package-change`.
- **8 skills** the commands invoke. Seven also auto-route from natural-language phrasing (the model recognizes "build me a landing page", "audit this UI", "regenerate the CSS", "export the design system", "package this change", etc.). The `setup` skill carries `disable-model-invocation: true` and fires only from `/cds:setup`.
- **2 sub-agents** that bundle the right skills with an identity: `cds-ui-author` (for UI work), `cds-code-companion` (for non-UI code that touches UI).
- **A reference tree** of every fixed design decision — the Building Blocks catalog (`reference/libraries/`), the composition rules (`reference/rules/`), the foundations (spacing, motion, type scales, accessibility, imagery), the shared build pipeline, the artwork contract, and the compliance rules — that the skills consult deterministically.
- **A schema** (2.0) for the one file you customize (`customizable-design-elements.yaml`).

What you supply: the YAML. Optionally, environment variables for default paths.

---

## The Building Blocks model

Everything the catalog holds is one of five kinds, plus two rule kinds. The skills translate your everyday words onto these at the boundary (`reference/aliases.md`) and use the internal vocabulary from there.

- **Component** — the smallest CDS-aware unit (button, text input, footer, topbar). Carries five contracts: slots, sizing, behavior, accessibility, token bindings.
- **Shape** — a content-free slot arrangement for one Section. An abstract layout contract.
- **Section** — a themable content container. `deterministic` (its layout is fixed at definition) or `dynamic` (its Shape is chosen at build by the rule engine).
- **Section Container** — an ordered list of Sections forming a page region or a whole page. **User-facing alias: "page type."**
- **Shell** — the outermost frame: it wraps a Section Container with persistent furniture (topbar/footer for marketing, rail/panes for app).

Plus the rules the composer runs: a **shape-selection rule** per dynamic Section (content signals → an ordered list of eligible Shapes) and **page-constraint** entries (post-selection validators over the accumulating page — the Variety Principle, alternation schedule, eyebrow deny-by-default, etc.).

Each Building Block is one `.md` file (typed YAML frontmatter + body) under `reference/libraries/{components,shapes,sections,section-containers,shells}/` and `reference/rules/{shape-selection,page-constraints}/`. Entry format is `reference/libraries/FORMAT.md`.

---

## Install

1. Install the plugin from its marketplace location (or `--plugin-dir ./cds` during development).
2. Choose how to scope it:
   - **Global** — one design system across all your projects.
   - **Project** — design system scoped to this project; does not bleed into others.
3. Set up your environment variables (next section) — by hand using this README, or by running `/cds:setup` for a guided walkthrough.

---

## Configure: environment variables

CDS reads its configuration from environment variables in your `settings.json`'s `env` block. All are optional — when one is unset, the relevant skill asks you for the value at call time (or halts with the matching code if you decline).

Prefix: `CUSTOMIZABLE_DESIGN_SYSTEM_` (underscores; not hyphens — POSIX env-var rules).

| Variable | Required? | Resolves | Consumed by |
|---|---|---|---|
| `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` | Recommended | Path to your populated `customizable-design-elements.yaml` | All skills |
| `CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE` | Recommended | `global` or `project` — gates where per-skill state is stored | composers, `package-change` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR` | Optional | Output directory for the generated CSS files | `generate-stylesheets`, composers, `export-design`, `package-change` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` | Optional | Default output directory for HTML mocks | `compose-page` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR` | Optional | Default output directory for framework-native component code | `compose-app-surface` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` | Required for `compose-app-surface` | Framework target (e.g., `react`, `vue`, `svelte`, `plain-html`) | `compose-app-surface` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` | Optional | Project extensions dir — mirrors `reference/libraries/` + `reference/rules/`, read alongside and overriding the plugin catalog by name | composers, `export-design`, `generate-stylesheets` (fingerprint) |
| `CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` | Optional | Directory holding brand assets + the `artwork-manifest.yaml` | composers, `package-change` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_DESIGN_MD_PATH` | Optional | Default output path for the `DESIGN.md` export | `export-design` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR` | Optional | Default output root for `package-change` hand-off bundles | `package-change` |

When a variable is unset, the relevant skill asks for the value at call time. If you decline, the skill halts with the appropriate `STOP:` code (e.g., `ELEMENTS_YAML_UNSET`, `FRAMEWORK_UNSET`, `OUTPUT_PATH_UNRESOLVABLE`).

### Settings file location

- Global install → `~/.claude/settings.json`
- Project install → `<project-root>/.claude/settings.local.json` (gitignored — env vars often contain user-specific paths)

### Configure by hand

Edit the chosen settings file directly. Example for a global install:

```json
{
  "env": {
    "CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS": "/Users/you/.claude/customizable-design-system/customizable-design-elements.yaml",
    "CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE": "global",
    "CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR": "/Users/you/projects/my-app/src/styles/design-system",
    "CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR": "/Users/you/projects/my-app/design-mocks",
    "CUSTOMIZABLE_DESIGN_SYSTEM_APP_SURFACE_DIR": "/Users/you/projects/my-app/src/components/cds",
    "CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK": "react"
  }
}
```

### Configure with `/cds:setup`

Type `/cds:setup` in Claude Code. It asks whether you already have a populated YAML (and captures the path), or bootstraps one from the shipped template (global → `~/.claude/customizable-design-system/customizable-design-elements.yaml`, project → `<project-root>/.customizable-design-elements.yaml`), then captures the optional defaults and writes them to the right `settings.json` `env` block, preserving your other keys. It is idempotent — re-running reads current values and offers them as defaults. Setup is never required; this README is a complete substitute.

---

## Populate `customizable-design-elements.yaml`

This is the only file you really customize. It carries:

- **Color catalog**: common colors + named palettes (Ramp type for stepwise progressions, Discrete type for named-color sets). Each color has a hex value and optional display name.
- **Typefaces / fonts**: variable + static fonts with their axes, and semantic font roles (`sans`, `serif`, `mono`) → typeface assignments with CSS fallback chains.
- **Roles**: semantic CSS roles (surface/text/border/accent families) + component roles. Each has a type, a scope, a description, and an optional fallback.
- **Themes**: named theme classes. Each defines `light` and `dark` mode bindings — what color each role resolves to. `dark: mirror` says "the dark bindings equal this theme's light bindings" (schema 2.0, below).
- **Optional `geometry:` / `motion:` override blocks**: the reference ships the geometry and motion *values*; a YAML row overrides one key. Omitting these blocks is valid — the reference values are used unchanged.

The schema at `validation/customizable-design-elements.schema.json` is the authoritative shape. The shipped `setup/customizable-design-elements.yaml` is a worked example you copy and edit.

What you do NOT put in this YAML: the default spacing / type scale / motion / radius values (reference-sourced, YAML-overridable per key), and output paths / framework / install mode (env vars).

---

## Core workflows

### Regenerate the stylesheet set

> "Regenerate the design-system CSS."

`generate-stylesheets` reads your YAML + the reference and writes `tokens.css`, `components.css`, `themes.css`, and a `manifest.json` of semantic fingerprints to your stylesheets directory. You rarely run this by hand: the composers, `export-design`, and `package-change` detect a stale set (by comparing the **semantic** hashes of your YAML, the reference tree, and any extensions against the manifest) and **regenerate it themselves** before proceeding. The hash is semantic — a comment- or `description:`-only YAML edit does not trigger a regeneration.

### Mock a page, a section, or a component

> "Build a landing page for our launch."

`compose-page` runs the shared build pipeline (`reference/pipeline.md`) and produces one self-contained HTML file you can open in a browser, attach to a spec, or send for review. It inlines the stylesheet set and a light/dark color-mode toggle. Two content modes: **drafted** (the skill generates a fill-in scaffold from the resolved Sections' slots) or **supplied** ("render this blog post: docs/announcements/launch.md" — the skill parses your content into the chosen page type). Isolated section/component requests wrap the piece in a minimal page so the browser can render it.

### Build an in-app surface

> "Build the settings page in the app."

`compose-app-surface` runs the same pipeline to framework-native component code (per `CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK`) at your `APP_SURFACE_DIR`, plus the wiring diffs (nav entry, route table, parent component) that make the surface reachable. The emitted code **links** the stylesheet set (inlining is mock-only) and never emits theme controllers, color-mode resolvers, or routing — your host project owns those. Trigger it only with an explicit app-embedding signal ("in the app", "to the app", or a live route name); standalone-mock requests route to `compose-page`.

### Render targets

Both composers render the one pipeline; they differ in output form (mock HTML vs. app code) and which targets each offers.

| Target | What renders | Composer |
|---|---|---|
| `assembled` (default) | Shell furniture + the Section Container — "the full page" | both |
| `container-only` | The Section Container alone — no nav, no footer | both |
| `shell-only` | The Shell with a labeled, unfilled content slot — "the frame / the chrome" | `compose-page` |
| `spa` | One Shell, N Section Containers, a client-side switcher showing one at a time (same mechanism as the color-mode toggle; no routing code) | `compose-page` |
| isolated section / component | The piece in a minimal wrapper (`--container-marketing-primary` width, `--sp-4` padding, light mode + toggle) | `compose-page` |

### The sidecars (every run, both composers)

Beside the metadata-free deliverable, the pipeline writes two sidecars on **every** run of **both** composers:

- `<basename>.wireframe.txt` — one block per Section (`ID · section · shape · ground`) with an ASCII arrangement sketch.
- `<basename>.decisions.md` — per Section: the chosen shape, the rule row that fired, alternates rejected and by which constraint, the ground assignment, width, motion notes, and the fallback-generated flag.

The deliverable itself stays clean — the reasoning lives in the sidecars, never in the artifact. The pipeline also writes a deterministic **state record** (the `brief_snapshot` + resolved `sections`) that `package-change` consumes.

### Artwork

Artwork arrives bound to a brief slot — a slot name paired with a file path (read in place) or a URL (fetched into `CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`). When a needed slot is unsupplied, the composer resolves it in a fixed order and stops at the first that yields the asset: the system glyph set → generation → online sourcing at a free-license floor → locate-and-hand-off (a licensed asset the user must fetch) → halt `ARTWORK_UNRESOLVABLE:{slot}`. Every asset records one entry in `<assets-dir>/artwork-manifest.yaml`, which rides into the `package-change` bundle. Full contract: `reference/artwork.md`.

### Export the design system as DESIGN.md

> "Export the design system."

`export-design` reads the live system (elements YAML + catalog + stylesheet manifest) and emits one `DESIGN.md` — the map of colors (palettes → roles → themes with real values), typography, geometry and motion summaries, the Building Blocks catalog with contracts and aliases, the rule summaries, the compliance essentials, and how to consume the class and token names. It follows the emerging DESIGN.md convention (frontmatter tokens + ordered `##` sections) so any consumer — a human, or a tool that reads DESIGN.md the way AGENTS.md is read — can follow the system without opening the plugin. Regenerated, never hand-edited; deterministic given the same inputs.

### Consult the design system while writing handlers

> "I'm wiring the form-submit for the sign-up page. What classes, tokens, events, and ARIA contracts should I bind to?"

`apply-design-system` loads the relevant catalog content into the calling agent's context as a structured response (`## Class names`, `## Token names`, `## Event hooks`, `## ARIA contracts`, `## Reference pointers`, `## Halt conditions`). No code is generated — your handler stays yours; CDS surfaces the contract you bind against.

### Audit existing UI

> "Audit the search results page."

`audit-against-system` checks a target (file, set of files, rendered URL, or pasted markup/CSS) against `compliance.md`, scoped by the rendering context you declare (app-embedded vs. standalone). Output is inline annotations or a structured report; each violation cites the relevant reference file. This skill IS the compliance gate — the composers run the same rule set before delivery.

### Package an approved change for the app repo

> "This mock is approved — package it for the app repo."

`package-change` bundles everything the change needs to cross the boundary into one directory: the current stylesheet set (regenerated first if stale), the mock HTML (or the framework surface + wiring diffs), a derived `build-spec.md` that cites the catalog entries by path, the wireframe and decision-log sidecars, the artwork manifest and assets, and — for a brownfield change — the original-files snapshot and the region-scoped diff. This is the hand-off from "approved in cds" to "built in the app repo."

### Update an existing page or surface (brownfield)

> "Update the hero on this existing page: src/pages/landing.html"

Supply an existing file (from your repo or a Figma reference) and the composer applies the change to the targeted region only, leaving the rest intact — `compose-page` rewrites the standalone HTML byte-for-byte outside the region; `compose-app-surface` emits a region-scoped diff.

### Extend the catalog without forking

Drop `*.md` entries into `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`, which **mirrors `reference/libraries/` + `reference/rules/` exactly** (`libraries/{components,shapes,sections,section-containers,shells}/`, `rules/{shape-selection,page-constraints}/`). The composers read them alongside the plugin catalog; a project entry whose `kind` + basename match a plugin entry **overrides it wholesale**, and project-only entries extend the catalog. A previously-halting Shell, Section Container, or Section composes once you supply its entry — no plugin release required.

---

## Sub-agent usage patterns

For one-shot operations (regenerate stylesheets, audit one file, one quick mock), call the skill or slash command directly.

For sustained work, spawn the appropriate sub-agent (Task tool, `subagent_type=cds-ui-author` or `cds-code-companion`):

- **`cds-ui-author`** — wraps `compose-page`, `compose-app-surface`, `apply-design-system`, `audit-against-system`, `export-design`, `package-change`. Its system prompt mandates consulting the catalog and self-auditing before declaring done, and forbids hand-rolling markup or CSS. `agents/cds-ui-author.md`.
- **`cds-code-companion`** — wraps `apply-design-system`, `audit-against-system`. Use when an agent writes non-UI code that touches generated UI and you want the design vocabulary loaded up front. `agents/cds-code-companion.md`.

Sub-agents are recommended, not enforcement gates: every skill stays directly callable by its slash command, its natural-language trigger, or an explicit invocation. A caller that bypasses the sub-agents bypasses the system-prompt mandates that come with them.

---

## Iteration model

Mocks are deliverables, not state. To iterate, call `compose-page` again with the change in plain language ("make the hero darker, swap the second feature card"). The pipeline:

1. Resolves the output path you supplied (or the default from `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`).
2. Looks for a prior state record at that exact path.
3. If found, loads the prior `brief_snapshot` + `sections` and applies your change to them.
4. Writes the next version to the same path + a new state record and sidecars.

Matching uses strict `output_path` equality. A fresh output path starts fresh; a continuation phrased against a new path gets one clarifying ask. Iteration (from a prior CDS state record) is distinct from update/brownfield (from external files). The plugin assumes a single user; no file locking.

---

## What CDS will not do

- It will not read your host-project code to infer conventions. Everything comes from the reference tree, your elements YAML, or runtime input you give it.
- It will not emit theme controllers, mode resolvers, or routing for in-app surfaces. Your host project owns those.
- It will not embed metadata inside a deliverable. Mocks and emitted code are clean; reasoning lives in the sidecars.
- It will not invent catalog entries. New colors, roles, or themes are your work in the elements YAML; new Building Blocks go in your extensions dir. An **unknown** Shell, Section Container, or Section id halts (`SHELL_UNKNOWN`, `SECTION_CONTAINER_UNKNOWN`, `SECTION_TYPE_UNKNOWN`) rather than guessing.
- It will **not** halt when a *known* dynamic Section's shape candidates are all rejected by the page constraints. Instead the composer **fallback-generates** a layout that fits the content and satisfies the constraints, and records it as fallback-generated in the decisions sidecar. (This replaces the old shape-rules halt: the "no best guess" principle now lives at the catalog boundary — unknown entries — not at the composition boundary.)

### Halt codes you may see

`WRONG_SKILL` · `SHELL_UNKNOWN` · `SECTION_CONTAINER_UNKNOWN` · `SECTION_TYPE_UNKNOWN` · `MISSING_COMPONENT` · `MISSING_SPEC` · `STYLESHEETS_REGEN_FAILED` · `UPDATE_SOURCE_UNREADABLE` · `UPDATE_TARGET_AMBIGUOUS` · `ARTWORK_UNRESOLVABLE` · `COMPLIANCE_UNSATISFIABLE` · `SHELL_FIT_FAILED` · `FRAMEWORK_UNSET` · `OUTPUT_PATH_UNRESOLVABLE` · `TARGET_UNREADABLE` · `STATE_RECORD_NOT_FOUND` · `ASSETS_UNRESOLVABLE` · `ELEMENTS_YAML_UNSET` · `ELEMENTS_INVALID` · `ELEMENTS_VERSION_MISMATCH`.

---

## Schema 2.0

The elements schema is at `2.0.0`. Changes from 1.x:

- **`dark: mirror` sentinel** — a theme's `dark` mode may be the literal string `mirror`, meaning "the dark bindings equal this theme's light bindings." Replaces the old convention of a fully commented-out duplicate dark block per non-flipping theme, and is visible to the semantic hash (a comment block was not).
- **`geometry.elements` group** — a fixed-element-width scale emitted `--element-{key}`. `conversion-card` (448px) moves here out of `geometry.containers`, so the containers invariant ("width ≥ page width") holds without exception. The generator emits `--container-conversion-card` as a compatibility alias until consumers migrate.
- **Color-mode universes declared** — binding modes are `light | dark` only; the runtime `system` mode resolves at load and is never stored.
- **`$conventions.role` corrected** to the bare `--{role key}` emission (the dead `--role-{role key}` form is retired).

**Migrating a live 1.x file:** run `tools/migrate-elements.py <elements.yaml> --in-place` (backs up to `<elements.yaml>.bak`). It applies only the unambiguously mechanical transforms and preserves comments/formatting; it reports (does not auto-apply) the themes that are `dark: mirror` candidates and any contrast-bug rebindings a human must decide. Validate with `validation/lint-elements.py` (schema 2.x only). Full record: `analysis/schema-2-migration-notes.md`.

---

## Testing

CDS ships a deterministic test suite (pure scripts, no LLM) that proves the design system is internally coherent for **whatever elements YAML is supplied** — nothing is hardcoded.

```bash
test/run-tests.sh                        # uses setup/customizable-design-elements.yaml
test/run-tests.sh /path/to/elements.yaml # or any valid config
```

`run-tests.sh` runs `test/check-plugin.py` (which discovers and runs every `checks/check_*.py` — schema, structure, internal links, semantic hash, token coverage, shape alignment, and more), the property-based linter `validation/lint-elements.py` over your live YAML, and a browsable visual render proof so you can see the system render and re-skin. See `test/README.md` for the full plan.

---

## Troubleshooting

**"The skill said it regenerated my stylesheets."** Expected — when your YAML, reference, or extensions change, the pipeline regenerates the set itself before composing. A comment- or `description:`-only YAML edit does not trigger one (the hash is semantic). If an auto-regeneration fails you'll see `STYLESHEETS_REGEN_FAILED` with the inner cause.

**"The skill stopped with `SECTION_CONTAINER_UNKNOWN:editorial-detail`."** Neither the plugin catalog nor your extensions carry that Section Container. The composer halts rather than guess — add the entry to `reference/libraries/section-containers/` or to your `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/libraries/section-containers/`.

**"A section's layout says it was fallback-generated."** That is not an error. A known dynamic Section whose shape candidates were all rejected by the page constraints gets a composer-generated layout that fits — the decisions sidecar records exactly which candidates were rejected and why.

**"The skill stopped with `MISSING_COMPONENT:approval-mode-tool-control`."** The requested component is not in the catalog. Add its entry under `reference/libraries/components/` (or your extensions dir) to enable it.

**"My sub-agent is generating UI code by hand instead of using `compose-page`."** The sub-agent's system prompt mandates the skills, but Claude can drift. Re-spawn it, or remind it to invoke `compose-page` / `compose-app-surface` rather than emit markup directly.

**"`/cds:setup` overwrote a value I had hand-edited."** It should not — the merge preserves unrelated keys and offers current values as defaults. If a known value changed, that is a bug; surface it.

---

## Where things live (cheat sheet)

| Looking for | Where |
|---|---|
| Your design choices (palettes, typefaces, themes) | `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` |
| The schema for your design choices | `validation/customizable-design-elements.schema.json` |
| The Building Blocks catalog | `reference/libraries/{components,shapes,sections,section-containers,shells}/` + `reference/libraries/FORMAT.md` |
| Composition rules (shape-selection, page constraints) | `reference/rules/{shape-selection,page-constraints}/` |
| The shared build pipeline (both composers) | `reference/pipeline.md` |
| User-facing word → internal term map | `reference/aliases.md` |
| Fixed design rules (spacing, motion, type scales, accessibility, imagery) | `reference/foundations/*.md` |
| The artwork contract | `reference/artwork.md` |
| Compliance rules | `reference/compliance.md` |
| Sub-agent system prompts | `agents/cds-ui-author.md`, `agents/cds-code-companion.md` |
| Slash commands | `commands/{setup,generate-stylesheets,compose-page,compose-app-surface,apply-design-system,audit-against-system,export-design,package-change}.md` |
| Skills | `skills/{setup,generate-stylesheets,compose-page,compose-app-surface,apply-design-system,audit-against-system,export-design,package-change}/SKILL.md` |
| Schema 2.0 migration record + tooling | `analysis/schema-2-migration-notes.md`, `tools/migrate-elements.py` |
| Your per-run skill state | `~/.claude/customizable-design-system/state/{skill}/` (global) or `<project>/.claude/customizable-design-system/state/{skill}/` (project) |
| The plugin manifest | `.claude-plugin/plugin.json` |
