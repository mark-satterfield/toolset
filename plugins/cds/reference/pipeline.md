# The Build Pipeline

The one composition pipeline both composers execute. `compose-page` renders it to a standalone mock; `compose-app-surface` renders it to framework-native code. Skill files describe discovery and their render target; the pipeline itself is defined here and only here.

## Catalog resolution

The working catalog is the plugin's `reference/libraries/` + `reference/rules/` trees overlaid with the project's `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same tree structure). A project entry whose `kind` and basename match a plugin entry replaces it wholesale; project-only entries extend the catalog. `reference/aliases.md` (plus any project `aliases.md`) translates user-facing names to internal ones before lookup.

## Stages

1. **Resolve the Shell.** Named by the user, or the Section Container's `default_shell`. Halt `SHELL_UNKNOWN:{name}` only when a named Shell exists in neither source.
2. **Resolve the Section Container.** Halt `SECTION_CONTAINER_UNKNOWN:{name}` when it exists in neither source.
3. **Resolve each Section in order.**
   - `deterministic` → populate its fixed layout with the content.
   - `dynamic` → run its Shape Selection Rule (`shape-selection-rule`) over the content contract signals + `page_meta`; take candidates in order (primary, alternates, default); validate each against the container's Page-Level Aesthetic Constraints (`page-constraint` entries) in the post-selection rejection loop; apply the first survivor.
   - All candidates rejected → **fallback generation**: the composer constructs a layout that fits the content and satisfies the constraints, and the decisions sidecar records the layout as fallback-generated. Halt `SECTION_TYPE_UNKNOWN:{id}` only when the Section id itself exists in neither source.
4. **Assemble** per the render target (below). Stylesheet freshness first: compare the `cds_hash.py` semantic fingerprints (elements YAML, reference tree, extensions tree) against `manifest.json`; on mismatch invoke `generate-stylesheets` and proceed — never halt for staleness; halt `STYLESHEETS_REGEN_FAILED:{inner}` only if that regeneration itself fails.
5. **Emit sidecars and the state record** — both composers, every run:
   - `<basename>.wireframe.txt` — one block per Section: `ID · section · shape · ground`, ASCII arrangement sketch.
   - `<basename>.decisions.md` — per Section: chosen shape, rule row that fired, alternates rejected and by which constraint, ground assignment, width, motion notes, fallback-generated flag.
   - State record (shared schema, unchanged): brief_snapshot, sections, sidecar paths, run-mode `generate|update`, update_source, per-section preserved flags; last 10 retained; consumed by `package-change`.
   - The deliverable itself stays metadata-free — reasoning lives in the sidecars, never in the artifact.

## Render targets

| Target | What renders | Who uses it |
|---|---|---|
| `assembled` (default) | the Shell's persistent Sections + the Section Container | both composers |
| `container-only` | The Section Container alone — without the Shell's persistent Sections | both composers |
| `shell-only` | The Shell with a labeled placeholder in its content slot | compose-page |
| `spa` | One Shell, N Section Containers, a client-side switcher showing one at a time (same mechanism as the color-mode toggle; no routing code) | compose-page |
| isolated section / component | The piece in a minimal wrapper (width `--container-marketing-primary`, padding `--sp-4`, light color-mode default + toggle) | compose-page |

Mock output inlines the stylesheet set and theming scripts. App output links the stylesheet set, emits framework-native code plus a wiring diff citing the reference, and never emits theme controllers, mode resolvers, or routing.

## Run-modes

- **generate** — fresh composition.
- **iteration** — a state record exists at the resolved output path: load its brief + decisions, apply the requested change, write the next version. Strict output-path match; a continuation phrased against a new path gets one clarifying ask.
- **update (brownfield)** — the starting point is external files (repo artifacts or a Figma reference): parse into a region map, localize the request (halt `UPDATE_TARGET_AMBIGUOUS` if impossible), recompose only the targeted regions, splice back byte-for-byte (mock) or emit a region-scoped diff (app). Halt `UPDATE_SOURCE_UNREADABLE` when the source cannot be parsed.

## Artwork

Artwork intake and the resolution order for a needed image or glyph are the Artwork contract's (`artwork.md`). Both composers consult it during asset discovery: supplied paths and URLs bind to brief slots, URLs fetch into `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`, and an unsupplied slot resolves through the system glyph set, then generation, then free-license sourcing, then locate-and-hand-off, halting `ARTWORK_UNRESOLVABLE:{slot}` only when no source yields the asset. Every asset records one entry in the artwork manifest beside the assets (`<assets-dir>/artwork-manifest.yaml`), which rides into the `package-change` bundle.

## Compliance

Every run ends with the compliance pass: `[scope: standalone]`+`[scope: both]` for mocks, `[scope: app-embedded]`+`[scope: both]` for app surfaces. `audit-against-system` is the gate; the composers run the same rule set pre-delivery.
