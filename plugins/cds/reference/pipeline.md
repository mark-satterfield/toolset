# The Build Pipeline

The one composition pipeline every composer executes. `compose-page` renders a **Page HTML** mock (or an isolated Section or Component), `compose-shell` renders and stores a **Shell**, `compose-view` renders a **View** (a Page HTML nested inside a stored Shell). The fourth output, **CSS**, is regenerated silently by the freshness stage. Skill files describe discovery and their output; the pipeline itself is defined here and only here.

## Catalog resolution

The working catalog is the plugin's `reference/libraries/` + `reference/rules/` trees overlaid with the project's `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same tree structure: `libraries/{components,shapes,sections,pages}/`, `rules/{shape-selection,page-constraints}/`). A project entry whose `kind` and basename match a plugin entry replaces it wholesale; project-only entries extend the catalog. User-facing words resolve against entry names and their `aliases:` frontmatter in context; a word that resolves to nothing is asked about, never guessed.

## Stages

1. **Resolve the Page.** A named Page entry (halt `PAGE_UNKNOWN:{name}` only when a named Page exists in neither source), or an ad-hoc Page the user describes Section by Section. Every Page carries a **page family** (landing, app, editorial, docs, auth): stated plainly, obvious from the prompt, or the skill asks. The page family selects the typography and motion register and scopes the Page-Level Aesthetic Constraints.
2. **Resolve each Section in order.**
   - **Eager** — the Section names its Shape (`shape:` frontmatter, or the user names one): populate that Shape from the ShapeLibrary with the content.
   - **Lazy** — no Shape named: run the Section's Shape Selection Rule (`shape-selection-rule`) over the content contract signals + `page_meta`; take candidates in order (primary, alternates, default); validate each against the Page's Page-Level Aesthetic Constraints (`page-constraint` entries) in the post-selection rejection loop; apply the first survivor.
   - All candidates rejected → **fallback generation**: the composer constructs a layout that fits the content and satisfies the constraints, and the decisions sidecar records the layout as fallback-generated. Halt `SECTION_TYPE_UNKNOWN:{id}` only when the Section id itself exists in neither source.
3. **Resolve the Shell** (View composition only). A stored Shell is resolved **by name** from `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` (unset → a `shells/` directory that is a sibling of the mocks directory). Unnamed with exactly one stored Shell → use it; unnamed with several → one clarifying ask. Halt `SHELL_UNKNOWN:{name}` only when a named Shell exists nowhere in that area.
4. **Stylesheet freshness (silent).** Compare the `cds_hash.py` semantic fingerprints (elements YAML, reference tree, extensions tree) against `manifest.json`; on mismatch invoke the internal `generate-css` machinery and proceed — never halt for staleness, never mention staleness or regeneration to the human, never instruct the human to run anything. Halt `STYLESHEETS_REGEN_FAILED:{inner}` only if that regeneration itself fails. The human-facing guarantee: what you see is always built from the current system.
5. **Assemble** per the output (below).
6. **Emit sidecars and the state record** — every composer, every run:
   - `<basename>.wireframe.txt` — one block per Section: `ID · section · shape · ground`, ASCII arrangement sketch.
   - `<basename>.decisions.md` — per Section: chosen shape, rule row that fired, alternates rejected and by which constraint, ground assignment, width, motion notes, fallback-generated flag.
   - State record (shared schema, unchanged): brief_snapshot, sections, sidecar paths, run-mode `generate|update`, update_source, per-section preserved flags; last 10 retained; consumed by `package-change` and by iteration.
   - The deliverable itself stays metadata-free — reasoning lives in the sidecars, never in the artifact.

## Outputs

| Output | What renders | Composer |
|---|---|---|
| Page HTML (default) | the Page's realized Frames, without any shell | `compose-page` |
| isolated Section / Component | the piece in a minimal wrapper (width `--container-marketing-primary`, padding `--sp-4`, light color-mode default + toggle) | `compose-page` |
| Shell | the ShellDefinition rendered to HTML with a labeled vacant space; stored named-per-Shell in `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` for reuse | `compose-shell` |
| View | one Page HTML nested inside a stored Shell | `compose-view` |
| View (SPA variant) | one stored Shell + N Pages with a client-side switcher showing one at a time (same mechanism as the color-mode toggle; no routing code) | `compose-view` |

Every output is a self-contained HTML mock: it inlines the stylesheet set and theming scripts, and opens in a browser as-is.

## Run-modes

- **generate** — fresh composition.
- **iteration** — a state record exists at the resolved output path: load its brief + decisions, apply the requested change, write the next version. Strict output-path match; a continuation phrased against a new path gets one clarifying ask. A Shell edited via `compose-shell` overwrites its stored file; Views regenerated afterward inherit the change.
- **update (brownfield)** — the starting point is external files (repo artifacts or a Figma reference): parse into a region map, localize the request (halt `UPDATE_TARGET_AMBIGUOUS` if impossible), recompose only the targeted regions, splice back byte-for-byte. Halt `UPDATE_SOURCE_UNREADABLE` when the source cannot be parsed.

## Artwork

Artwork intake and the resolution order for a needed image or glyph are the Artwork contract's (`artwork.md`). Composers consult it during asset discovery: supplied paths and URLs bind to brief slots, URLs fetch into `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`, and an unsupplied slot resolves through the system glyph set, then generation, then free-license sourcing, then locate-and-hand-off, halting `ARTWORK_UNRESOLVABLE:{slot}` only when no source yields the asset. Every asset records one entry in the artwork manifest beside the assets (`<assets-dir>/artwork-manifest.yaml`), which rides into the `package-change` bundle.

## Compliance

Every run ends with the compliance pass: `[scope: standalone]`+`[scope: both]` for generated mocks; `[scope: app-embedded]`+`[scope: both]` applies when auditing UI that lives inside an application. `audit-against-system` is the gate; the composers run the same rule set pre-delivery.
