# CDS — Configurable Design System

A brand-neutral design system you install in any project. CDS gives you a stylesheet set, a way to compose Shells, Pages, and Views you can open in a browser, a visual review harness, a way to package an approved output into a hand-off bundle, a DESIGN.md export, and an audit tool — all derived from one YAML file of design choices you supply.

---

## What's in the box

- **9 slash commands** for direct invocation: `/cds:setup`, `/cds:compose-shell`, `/cds:compose-page`, `/cds:compose-view`, `/cds:review`, `/cds:apply-design-system`, `/cds:audit-against-system`, `/cds:export-design`, `/cds:package-change`.
- **The same-named skills** the commands invoke. Eight also auto-route from natural-language phrasing (the model recognizes "compose my site's shell", "build me a landing page", "let me see it in the shell", "open it so I can comment", "audit this UI", "export the design system", "package this change", etc.). The `setup` skill carries `disable-model-invocation: true` and fires only from `/cds:setup`.
- **One internal skill**, `generate-css` — the machinery that produces the CSS output (`tokens.css`, `components.css`, `themes.css`, `manifest.json`). It has no command and no natural-language trigger: every user-facing skill runs a silent stylesheet-freshness stage that invokes it when the inputs have moved, then proceeds. You never run it, and no agent will ever tell you to — what you see is always built from the current system.
- **2 sub-agents** that bundle the right skills with an identity: `cds-ui-author` (for UI work), `cds-code-companion` (for non-UI code that touches UI).
- **A reference tree** of every fixed design decision — the Building Blocks catalog (`reference/libraries/`), the composition rules (`reference/rules/`), the foundations (spacing, motion, type scales, accessibility, imagery), the shared build pipeline, the artwork contract, and the compliance rules — that the skills consult deterministically.
- **A schema** (2.0) for the one file you customize (`customizable-design-elements.yaml`).

What you supply: the YAML. Optionally, environment variables for default paths.

---

## The Building Blocks model

The model is defined normatively in `reference/model/entity-catalog.md` and `reference/model/data-model.mermaid` — the only authority on its vocabulary. In brief:

- **Component** — the smallest CDS-aware unit, built from Elements (raw HTML tags — a concept only, never configured). Carries sizing rules, behavior contracts, accessibility contracts, and token bindings. A catalog entry is a Component Definition; realized on a page it becomes HTML, CSS, and TypeScript. Lives in the **ComponentLibrary**.
- **Shape** — a template layout for positioning and the proportional and other geospatial properties of Components and Elements. Shapes have no dimensions of their own; variability is handled by selecting a different Shape, never by leaving positions open. Lives in the **ShapeLibrary** — Sections point to Shapes so every layout is shareable.
- **Frame** — the abstract container: themeable, and assigned a Shape either **eagerly** (a predefined Shape supplied up front) or **lazily** (resolved at build time by the Rule Engine from the content). **Section**, **Page**, and **ShellDefinition** are the concrete Frames. A Frame contains Frames, so a Section can contain a Section:
  - **Section** — a single region. It owns its own surface (dimensions, ground, pinning, landmark); its layout is always a Shape in the ShapeLibrary (`shape:` frontmatter = eager; absent = lazy via its ShapeSelectionRule).
  - **Page** — one or more Sections in sequence; nests inside the vacant space of a Shell. Every Page carries a **page family** (landing, app, editorial, docs, auth) that selects its typography and motion register and scopes its constraints — stated plainly, obvious from the prompt, or the skill asks.
  - **ShellDefinition** — the blueprint of a site's repeating portions. **It is defined in terms of Frames, not Components:** its regions are the Section entries that declare a `shell_edge:` — `top-nav` (block-start), `left-rail` (inline-start), `site-footer` (block-end) — each pinned to a canvas edge around the vacant space. It carries real content. Its stored output is the **Shell**. The plugin ships no shells — every Shell is composed by you.

**A region of a frame is a Section; what fills it is a Shape.** A top bar carrying a mark alone, one carrying a mark and a menu, and one carrying a mark, a menu, and a sign-in button are three Shapes over the one `top-nav` Section — never one Component with optional slots, and never three near-identical nav Components. The same holds for `rail-*` over `left-rail` and `footer-*` over `site-footer`. Components (`logo`, `horizontal-menu`, `vertical-menu`, `account-row`, `dropdown-panel`, `mobile-drawer`, …) appear only where a Shape places them. `test/checks/check_frame_regions.py` enforces this.
- **Rules** — a **ShapeSelectionRule** per lazily-assigned Section (content signals → an ordered list of eligible Shapes) and **PageLevelAestheticConstraint** entries (post-selection validators run as a rejection loop over the accumulating page).

**The Shape-assignment waterfall.** When a lazily-assigned Section's Shape is resolved, four rungs are tried in order, and a rung is reached only when everything above it produced nothing:

1. **The Section's own rule** — its candidates (primary, alternates, default), each validated against the page constraints.
2. **Any other library Shape, unmodified** — the ShapeLibrary is larger than one rule's table, so every remaining Shape whose slots fit the content and that survives the constraints is considered, and the closest fit is applied.
3. **The closest library Shape, adapted** — used with the smallest stated modification, bounded to what its variants and open values allow. A change that would alter the Shape's arrangement contract is not an adaptation; that is a new Shape for your extensions dir.
4. **Generated from scratch** — only when nothing in the library fits, modified or not.

The decisions sidecar records which rung produced each Section's layout. Full definition: `reference/pipeline.md`.
- **Outputs** — **CSS** (the stylesheet set), **Page HTML** (the content region on its own), **Shell** (stored for reuse), **View** (the Page HTML nested inside the Shell — the thing a visitor would see).

Each Building Block is one `.md` file (typed YAML frontmatter + body) under `reference/libraries/{components,shapes,sections,pages}/` and `reference/rules/{shape-selection,page-constraints}/`. Entry format is `reference/libraries/FORMAT.md`.

---

## Install

1. Install the plugin from its marketplace location (or `--plugin-dir ./cds` during development).
2. Choose how to scope it:
   - **Global** — one design system across all your projects.
   - **Project** — design system scoped to this project; does not bleed into others.
3. Set up your environment variables (next section) — by hand using this README, or by running `/cds:setup` for a guided walkthrough. Setup is never required; this README is a complete substitute.

---

## Configure: environment variables

CDS reads its configuration from environment variables in your `settings.json`'s `env` block. All are optional — when one is unset, the relevant skill asks you for the value at call time, or applies its documented default.

Prefix: `CUSTOMIZABLE_DESIGN_SYSTEM_` (underscores; not hyphens — POSIX env-var rules). The `CUSTOMIZABLE_DESIGN_SYSTEM_` prefix (and the `customizable-design-elements.yaml` filename) predate the rename to Configurable Design System and are retained verbatim for compatibility.

| Variable | Required? | Resolves | Consumed by |
|---|---|---|---|
| `CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` | Recommended | Path to your populated `customizable-design-elements.yaml` | All skills |
| `CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE` | Recommended | `global` or `project` — gates where per-skill state is stored | composers, `package-change` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR` | Optional | Output directory for the generated CSS files | all skills (via the silent freshness stage) |
| `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` | Optional | Default output directory for composed HTML outputs | `compose-page`, `compose-view` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` | Optional | The shells output area — one file per Shell, named per Shell. Unset → a `shells/` directory that is a sibling of the mocks directory, applied silently | `compose-shell` (stores), `compose-view` (resolves by name) |
| `CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` | Optional | Project extensions dir — mirrors `reference/libraries/` + `reference/rules/`, read alongside and overriding the plugin catalog by name | composers, `export-design`, freshness fingerprint |
| `CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` | Optional | Directory holding brand assets + the `artwork-manifest.yaml` | composers, `package-change` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_DESIGN_MD_PATH` | Optional | Default output path for the `DESIGN.md` export | `export-design` |
| `CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR` | Optional | Default output root for `package-change` hand-off bundles | `package-change` |

When a variable is unset and has no documented default, the relevant skill asks for the value at call time. If you decline, the skill halts with the appropriate `STOP:` code (e.g., `ELEMENTS_YAML_UNSET`, `OUTPUT_PATH_UNRESOLVABLE`).

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
    "CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR": "/Users/you/projects/my-app/design-mocks-shells"
  }
}
```

### Configure with `/cds:setup`

Type `/cds:setup` in Claude Code. It asks whether you already have a populated YAML (and captures the path), or bootstraps one from the shipped template (global → `~/.claude/customizable-design-system/customizable-design-elements.yaml`, project → `<project-root>/.customizable-design-elements.yaml`), then captures the optional defaults — assets, stylesheets, mocks, and shells directories — and writes them to the right `settings.json` `env` block, preserving your other keys. It is idempotent — re-running reads current values and offers them as defaults. Setup is never required; this README is a complete substitute.

---

## Populate `customizable-design-elements.yaml`

This is the only file you really customize. It carries:

- **Color catalog**: common colors + named palettes (Ramp type for stepwise progressions, Discrete type for named-color sets). Each color has a hex value and optional display name.
- **Typefaces / fonts**: variable + static fonts with their axes, and semantic font roles (`sans`, `serif`, `mono`) → typeface assignments with CSS fallback chains.
- **Roles**: semantic CSS roles (surface/text/border/accent groupings) + component roles. Each has a type, a scope, a description, and an optional fallback.
- **Themes**: named theme classes. Each defines `light` and `dark` mode bindings — what color each role resolves to. `dark: mirror` says "the dark bindings equal this theme's light bindings" (schema 2.0, below).
- **Optional `geometry:` / `motion:` override blocks**: the reference ships the geometry and motion *values*; a YAML row overrides one key. Omitting these blocks is valid — the reference values are used unchanged.

The schema at `validation/customizable-design-elements.schema.json` is the authoritative shape. The shipped `setup/customizable-design-elements.yaml` is a worked example you copy and edit.

What you do NOT put in this YAML: the default spacing / type scale / motion / radius values (reference-sourced, YAML-overridable per key), and output paths / install mode (env vars).

---

## Core workflows

### Compose your site's Shell

> "Compose my site's shell: top nav with Home / Pricing / Docs, footer with the legal links."

`/cds:compose-shell` composes a **Shell** from your content and instructions — the ShellDefinition is the transient blueprint carrying your real menu items, logo, and colors. It emits the Shell HTML, shows it, and stores it **named per Shell** in the shells output area for reuse. Done once per site, edited rarely — editing later is the same command, and Views regenerated afterward inherit the change.

### Compose a Page

> "Create a landing page: hero, three feature tiles, pricing, a closing CTA."

`/cds:compose-page` composes a **Page** — one or more Sections in sequence — per the shared build pipeline (`reference/pipeline.md`) and produces one self-contained **Page HTML** file you can open in a browser, attach to a spec, or send for review. Each Section's Shape resolves eagerly (named up front) or lazily (the Rule Engine picks from its ShapeSelectionRule, validated by the PageLevelAestheticConstraints rejection loop). Two content modes: **drafted** (the skill generates a fill-in scaffold from the resolved Sections' slots) or **supplied** ("render this blog post: docs/announcements/launch.md"). Isolated Section/Component requests wrap the piece in a minimal page so the browser can render it.

### See it in the Shell — the View

> "Now let me see it in the shell."

`/cds:compose-view` produces a **View**: the Page HTML nested inside a stored Shell, resolved **by name** from the shells area. One Shell serves many Pages. The **SPA variant** nests N Pages in one Shell with a client-side switcher showing one at a time — the same mechanism as the color-mode toggle; no routing code.

### Review any output visually

> "Open it so I can comment."

`/cds:review` closes the loop between composing and iterating: **compose → review → paste the change request → the owning composer iterates.** It opens ANY generated output — a Shell, a Page HTML, a View, an isolated Section or Component — in a playground-style harness (`<basename>.review.html`, built by `tools/build-review-harness.py`, one self-contained file) in your browser. Hovering shows each region's Building Blocks identity (the Section id and the Shape it received), clicking pins a numbered comment with quick tags (copy, layout, color, spacing, swap-shape, remove, add), and a bottom panel assembles one natural-language change request. Press Copy and paste it back: the request routes to the composer that owns the artifact. The `.review.html` is a review artifact, not a deliverable — `package-change` does not bundle it.

### "Change the color of that button."

Say it in plain language. The agent determines whether that is a change to *this page* or to *the system* (one clarifying question if genuinely ambiguous), edits whatever actually holds the value — the page, or the token/role in your elements YAML — regenerates whatever that invalidates, re-renders, and shows the result. You never hear the words CSS, manifest, hash, or stale.

### Export the design system as DESIGN.md

> "Export the design system."

`/cds:export-design` reads the live system (elements YAML + catalog + stylesheet manifest) and emits one `DESIGN.md` — the map of colors (palettes → roles → themes with real values), typography, geometry and motion summaries, the Building Blocks catalog with contracts and per-entry aliases, the rule summaries, the compliance essentials, and how to consume the class and token names. Any consumer — a human, or a tool that reads DESIGN.md the way AGENTS.md is read — can follow the system without opening the plugin. Regenerated, never hand-edited; deterministic given the same inputs.

### Consult the design system while writing handlers

> "I'm wiring the form-submit for the sign-up page. What classes, tokens, events, and ARIA contracts should I bind to?"

`/cds:apply-design-system` loads the relevant catalog content into the calling agent's context as a structured response (`## Class names`, `## Token names`, `## Event hooks`, `## ARIA contracts`, `## Reference pointers`, `## Halt conditions`). No code is generated — your handler stays yours; CDS surfaces the contract you bind against.

### Audit existing UI

> "Audit the search results page."

`/cds:audit-against-system` checks a target (file, set of files, rendered URL, or pasted markup/CSS) against `compliance.md`, scoped by the rendering context you declare (app-embedded vs. standalone). Output is inline annotations or a structured report; each violation cites the relevant reference file. This skill IS the compliance gate — the composers run the same rule set before delivery.

### Build UI directly in your app repo

> "Create a modal that does x, y, and z." (said to an agent in your application repository)

No composer, no mockup, no CDS command required — the design system is simply *in force*. The building agent consults it (`apply-design-system` or the exported `DESIGN.md`) for colors, fonts, sizes, spacing, and ARIA contracts; links the generated stylesheets; builds with system classes and tokens; and runs `audit-against-system` before saying done.

### Package an approved change for the app repo

> "This is approved — package it for the app repo."

`/cds:package-change` bundles everything the change needs to cross the boundary into one directory: the current stylesheet set, the approved artifact (a Page HTML, a Shell, or a View), a derived `build-spec.md` that cites the catalog entries by path, the wireframe and decision-log sidecars, the artwork manifest and assets, and — for a brownfield change — the original-files snapshot and the region-scoped diff. This is the hand-off from "approved in CDS" to "built in the app repo," and the only bridge outward — the plugin never pivots into app work.

### Update an existing page (brownfield)

> "Update the hero on this existing page: src/pages/landing.html"

Supply an existing file (from your repo or a Figma reference) and `compose-page` applies the change to the targeted region only, rewriting the standalone HTML byte-for-byte outside the region.

### Extend the catalog without forking

Drop `*.md` entries into `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`, which **mirrors `reference/libraries/` + `reference/rules/` exactly** (`libraries/{components,shapes,sections,pages}/`, `rules/{shape-selection,page-constraints}/`). The composers read them alongside the plugin catalog; a project entry whose `kind` + basename match a plugin entry **overrides it wholesale**, and project-only entries extend the catalog. A previously-halting Page or Section composes once you supply its entry — no plugin release required.

### The sidecars (every composer, every run)

Beside the metadata-free deliverable, the pipeline writes two sidecars on **every** run:

- `<basename>.wireframe.txt` — one block per Section (`ID · section · shape · ground`) with an ASCII arrangement sketch.
- `<basename>.decisions.md` — per Section: the chosen shape, the resolution rung that produced it, the rule row that fired, alternates rejected and by which constraint, the ground assignment, width, and motion notes.

The deliverable itself stays clean — the reasoning lives in the sidecars, never in the artifact. The pipeline also writes a deterministic **state record** (the `brief_snapshot` + resolved `sections`) that `package-change` and iteration consume.

### Artwork

Artwork arrives bound to a brief slot — a slot name paired with a file path (read in place) or a URL (fetched into `CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`). When a needed slot is unsupplied, the composer resolves it in a fixed order and stops at the first that yields the asset: the system glyph set → generation → online sourcing at a free-license floor → locate-and-hand-off (a licensed asset the user must fetch) → halt `ARTWORK_UNRESOLVABLE:{slot}`. Every asset records one entry in `<assets-dir>/artwork-manifest.yaml`, which rides into the `package-change` bundle. Full contract: `reference/artwork.md`.

---

## Sub-agent usage patterns

For one-shot operations (audit one file, one quick mock), call the skill or slash command directly.

For sustained work, spawn the appropriate sub-agent (Task tool, `subagent_type=cds-ui-author` or `cds-code-companion`):

- **`cds-ui-author`** — wraps `compose-shell`, `compose-page`, `compose-view`, `review`, `apply-design-system`, `audit-against-system`, `export-design`, `package-change`. In the design studio every line of UI flows through the compose skills; in an app repo it runs the direct-build discipline (consult → build with system tokens/classes → audit before done). `agents/cds-ui-author.md`.
- **`cds-code-companion`** — wraps `apply-design-system`, `audit-against-system`. Use when an agent writes non-UI code that touches generated UI and you want the design vocabulary loaded up front. `agents/cds-code-companion.md`.

Sub-agents are recommended, not enforcement gates: every skill stays directly callable by its slash command, its natural-language trigger, or an explicit invocation.

---

## Iteration model

Outputs are deliverables, not state. To iterate, call the owning composer again with the change in plain language ("make the hero darker, swap the second feature card"). The pipeline:

1. Resolves the output path you supplied (or the default from `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` / the shells area).
2. Looks for a prior state record at that exact path.
3. If found, loads the prior `brief_snapshot` + `sections` and applies your change to them.
4. Writes the next version to the same path + a new state record and sidecars.

Matching uses strict `output_path` equality. A fresh output path starts fresh; a continuation phrased against a new path gets one clarifying ask. Iteration (from a prior CDS state record) is distinct from update/brownfield (from external files). A Shell edit overwrites its stored file; Views regenerated afterward inherit the change. The plugin assumes a single user; no file locking.

---

## What CDS will not do

- It will not read your host-project code to infer conventions. Everything comes from the reference tree, your elements YAML, or runtime input you give it.
- It will not tell you to regenerate CSS or run any maintenance command. Stylesheet freshness is silent machinery: every entry point checks and regenerates before doing its work.
- It will not emit theme controllers, mode resolvers, or routing. The View's SPA switcher is a mock-local visibility mechanism; your host project owns runtime plumbing.
- It will not embed metadata inside a deliverable. Composed HTML is clean; reasoning lives in the sidecars.
- It will not ship shells. Every Shell is composed by you, from your content, via `compose-shell`.
- It will not invent catalog entries. New colors, roles, or themes are your work in the elements YAML; new Building Blocks go in your extensions dir. An **unknown** Page, Section, Component, or stored Shell name halts (`PAGE_UNKNOWN`, `SECTION_TYPE_UNKNOWN`, `MISSING_COMPONENT`, `SHELL_UNKNOWN`) rather than guessing.
- It will **not** halt when a *known* lazily-assigned Section's rule candidates are all rejected by the PageLevelAestheticConstraints. Instead it descends the Shape-assignment waterfall (above) and records the rung it landed on. The "no best guess" principle lives at the catalog boundary — unknown entries — not at the composition boundary.
- It will **not** build a layout from scratch while one in the library would have fitted. Generation is the last rung, not the fallback for mild inconvenience.

### Halt codes you may see

`WRONG_SKILL` · `SHELL_UNKNOWN` · `PAGE_UNKNOWN` · `SECTION_TYPE_UNKNOWN` · `MISSING_COMPONENT` · `MISSING_SPEC` · `STYLESHEETS_REGEN_FAILED` · `UPDATE_SOURCE_UNREADABLE` · `UPDATE_TARGET_AMBIGUOUS` · `ARTWORK_UNRESOLVABLE` · `COMPLIANCE_UNSATISFIABLE` · `OUTPUT_PATH_UNRESOLVABLE` · `TARGET_UNREADABLE` · `REVIEW_HARNESS_FAILED` · `STATE_RECORD_NOT_FOUND` · `ASSETS_UNRESOLVABLE` · `ELEMENTS_YAML_UNSET` · `ELEMENTS_INVALID` · `ELEMENTS_VERSION_MISMATCH`.

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

**"The composer halted with `PAGE_UNKNOWN:editorial-detail`."** Neither the plugin catalog nor your extensions carry that Page. The composer halts rather than guess — add the entry to your `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/libraries/pages/` (the plugin's own catalog ships nine Page entries under `reference/libraries/pages/`).

**"`compose-view` halted with `SHELL_UNKNOWN:main`."** No stored Shell named `main` exists in your shells area. Compose it first: `/cds:compose-shell`.

**"A Section's layout says it was library-sourced / library-adapted / fallback-generated."** None of those is an error — they are the lower rungs of the Shape-assignment waterfall, and the sidecar names which one ran and why. *library-sourced* means the Section's own rule offered nothing that survived, so a Shape from elsewhere in the library was used unmodified. *library-adapted* means the closest library Shape was used with a stated modification. *fallback-generated* means nothing in the library fitted and the layout was built from scratch. A Section that repeatedly lands on the last two is telling you the library is missing an entry — add it to your extensions dir.

**"The skill stopped with `MISSING_COMPONENT:approval-mode-tool-control`."** The requested component is not in the catalog. Add its entry under your extensions dir's `libraries/components/` to enable it.

**"My sub-agent is generating studio UI by hand instead of composing."** The sub-agent's system prompt mandates the compose skills, but Claude can drift. Re-spawn it, or remind it to invoke the compose skills rather than emit markup directly.

**"`/cds:setup` overwrote a value I had hand-edited."** It should not — the merge preserves unrelated keys and offers current values as defaults. If a known value changed, that is a bug; surface it.

---

## Where things live (cheat sheet)

| Looking for | Where |
|---|---|
| The entity model (normative) | `reference/model/entity-catalog.md` + `reference/model/data-model.mermaid` |
| Your design choices (palettes, typefaces, themes) | `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` |
| The schema for your design choices | `validation/customizable-design-elements.schema.json` |
| The Building Blocks catalog | `reference/libraries/{components,shapes,sections,pages}/` + `reference/libraries/FORMAT.md` |
| Composition rules (shape-selection, page constraints) | `reference/rules/{shape-selection,page-constraints}/` |
| The shared build pipeline (all composers) | `reference/pipeline.md` |
| Fixed design rules (spacing, motion, type scales, accessibility, imagery) | `reference/foundations/*.md` |
| The artwork contract | `reference/artwork.md` |
| Compliance rules | `reference/compliance.md` |
| Your composed Shells | `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` (default: the `shells/` sibling of your mocks directory) |
| Sub-agent system prompts | `agents/cds-ui-author.md`, `agents/cds-code-companion.md` |
| Slash commands | `commands/{setup,compose-shell,compose-page,compose-view,review,apply-design-system,audit-against-system,export-design,package-change}.md` |
| Skills | `skills/{setup,generate-css,compose-shell,compose-page,compose-view,review,apply-design-system,audit-against-system,export-design,package-change}/SKILL.md` |
| The review-harness builder | `tools/build-review-harness.py` |
| Schema 2.0 migration record + tooling | `analysis/schema-2-migration-notes.md`, `tools/migrate-elements.py` |
| Your per-run skill state | `~/.claude/customizable-design-system/state/{skill}/` (global) or `<project>/.claude/customizable-design-system/state/{skill}/` (project) |
| The plugin manifest | `.claude-plugin/plugin.json` |
