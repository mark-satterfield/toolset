# The Build Pipeline

The one composition pipeline every composer executes. `compose-page` renders a **Page HTML** mock (or an isolated Section or Component), `compose-shell` renders and stores a **Shell**, `compose-view` renders a **View** (a Page HTML nested inside a stored Shell). The fourth output, **CSS**, is regenerated silently by the freshness stage. Skill files describe discovery and their output; the pipeline itself is defined here and only here.

## Catalog resolution

The working catalog is the plugin's `reference/libraries/` + `reference/rules/` trees overlaid with the project's `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same tree structure: `libraries/{components,shapes,sections,pages}/`, `rules/{shape-selection,page-constraints}/`). A project entry whose `kind` and basename match a plugin entry replaces it wholesale; project-only entries extend the catalog. User-facing words resolve against entry names and their `aliases:` frontmatter in context; a word that resolves to nothing is asked about, never guessed.

**Where the catalog boundary sits.** An unknown name halts only where composing past it would mean fabricating a contract: a **Component** (its markup, sizing, ARIA, and token bindings) and a **stored Shell** (a file that exists or does not). Pages and Sections are Frames — a Page is Sections in sequence, a Section is a surface plus a Shape — so an unrecognised one is composed from its attributes and the Shape-assignment waterfall rather than halted on.

## Stages

1. **Resolve the Page.** A named Page entry when the catalog carries one, or an ad-hoc Page the user describes Section by Section. A Page the catalog has never seen is composed from the Sections named for it — a Page entry is a preset, not a required type, and an unrecognised Page name never halts. Every Page carries a **page family** (landing, app, editorial, docs, auth): stated plainly, obvious from the prompt, or the skill asks. The page family selects the typography and motion register and scopes the Page-Level Aesthetic Constraints.
2. **Resolve each Section in order.**
   - **Eager** — the Section names its Shape (`shape:` frontmatter, or the user names one): populate that Shape from the ShapeLibrary with the content.
   - **Lazy** — no Shape named: run the Shape-assignment waterfall below.
   - A Section the catalog has never seen is composed from its own attributes — where it pins, its extent, its theme — and resolves its Shape through the waterfall below. It never halts. Section entries are pre-configured Sections, not a closed set of permitted ones (`libraries/FORMAT.md`).

### The Shape-assignment waterfall

Four rungs, tried in order. **A rung is reached only when every rung above it produced nothing**, and a survivor from a higher rung is never displaced by a lower one — the rule is the Section's own declared intent, and the library is the accumulated intent of the whole system. Building from scratch is the last resort, not the fallback for mild inconvenience.

**Rung 1 — the Section's own rule.** Run the Section's Shape Selection Rule (`shape-selection-rule`) over its content-contract signals + `page_meta`; take candidates in order (primary, alternates, default); validate each against the Page's Page-Level Aesthetic Constraints (`page-constraint` entries) in the post-selection rejection loop. The first survivor is applied and the waterfall ends.

**Rung 2 — any other Shape in the library, unmodified.** The rule's candidates are all rejected, but the ShapeLibrary is larger than any one rule's table. Consider every remaining Shape in the resolved library (plugin ∪ extensions) — every Shape, on every Page, because a Shape is an arrangement and carries no page family of its own (`libraries/FORMAT.md`). A Shape is **eligible** when all three hold:

- every slot it declares `required: true` has content to fill;
- every piece of the Section's content lands in one of its slots — an arrangement that drops content is not a fit;
- it survives the same Page-Level Aesthetic Constraints rejection loop.

Among the eligible Shapes, apply the **closest fit**: fewest unfilled optional slots first, then fewest slots overall (the simplest arrangement that still holds everything), then the earliest name alphabetically so the choice is deterministic. Record the outcome as **library-sourced**, naming the Shape and what made it fit.

**Rung 3 — the closest library Shape, adapted.** No Shape fits unmodified. Take the closest-fitting eligible-but-for-one-thing Shape and apply the smallest modification that makes it fit. A modification is bounded:

- It **may** select a declared `variant`, leave an optional slot unfilled, or set a value the Shape's Determinations leave open.
- It **may not** change the Shape's arrangement contract — its slot set, the relative positions of those slots, or any Determination stated as definitive. A change that crosses that line is not that Shape any more, and claiming it is misreports what was built.

Record the outcome as **library-adapted**, naming the base Shape, the modification, and why that base was closest. When the needed change crosses the line, do not stretch the record to fit: that change is a new Shape belonging in `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`, and the run drops to rung 4 while the sidecar says so.

**Rung 4 — fallback generation.** Nothing in the library fits, modified or not. The composer constructs a layout that fits the content and satisfies the constraints. Record the outcome as **fallback-generated**, listing the rungs already tried and why each produced nothing.

Rung 3 and rung 4 outcomes are the system reporting a gap in itself. A Section that keeps landing there wants a Shape the library does not carry yet; the decisions sidecar is where that pattern becomes visible.
3. **Resolve the Shell** (View composition only). A stored Shell is resolved **by name** from `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` (unset → a `shells/` directory that is a sibling of the mocks directory). Unnamed with exactly one stored Shell → use it; unnamed with several → one clarifying ask. Halt `SHELL_UNKNOWN:{name}` only when a named Shell exists nowhere in that area.
4. **Stylesheet freshness (silent).** Compare the `cds_hash.py` semantic fingerprints (elements YAML, reference tree, extensions tree) against `manifest.json`; on mismatch invoke the internal `generate-css` machinery and proceed — never halt for staleness, never mention staleness or regeneration to the human, never instruct the human to run anything. Halt `STYLESHEETS_REGEN_FAILED:{inner}` only if that regeneration itself fails. The human-facing guarantee: what you see is always built from the current system.
5. **Assemble** per the output (below).
6. **Emit sidecars and the state record** — every composer, every run:
   - `<basename>.wireframe.txt` — one block per Section: `ID · section · shape · ground`, ASCII arrangement sketch.
   - `<basename>.decisions.md` — per Section: chosen shape, the **resolution rung** that produced it (`eager` | `rule-candidate` | `library-sourced` | `library-adapted` | `fallback-generated`), the rule row that fired, alternates rejected and by which constraint, ground assignment, width, and motion notes. A `library-sourced` record names the Shape and what made it fit; a `library-adapted` record additionally names the base Shape and the modification applied; a `fallback-generated` record lists the rungs already tried and why each produced nothing.
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
