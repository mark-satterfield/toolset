---
name: generate-stylesheets
description: Produces the canonical Customizable Design System stylesheet set — tokens.css, components.css, themes.css, and manifest.json — by reading the elements YAML and the deterministic reference tree. Trigger on requests to generate, regenerate, refresh, rebuild, emit, produce, update, sync, or run an incremental pass on the design-system CSS, design tokens, or stylesheet set — including first-time bootstrapping and post-edit regeneration after changing the elements YAML or palette. Must NOT trigger on composition requests (building pages, mocks, sections, or in-app surfaces — those route to compose-page or compose-app-surface; the stylesheet set this skill emits is an INPUT to those skills, not an output). Must NOT trigger on audit, code review, or informational queries about the design system.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Reads the elements YAML and the plugin's deterministic reference tree, then emits three CSS files (`tokens.css`, `components.css`, `themes.css`) plus a `manifest.json` at a resolved output directory. The emitted CSS is byte-identical for any given (elements YAML, reference tree) pair and is consumed by `compose-page` (inlined into mocks) and `compose-app-surface` (linked from app-embedded code).

## Inputs

- **From caller (runtime):** the resolved output directory (if not supplied by env var); a regenerate-all vs. incremental choice (incremental still produces all three files but only triggers a write when any input SHA differs from `manifest.json`).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the absolute path to the elements YAML — the palette, typeface set, role bindings, conventions, `$schema_version`, and the **optional** `geometry:`/`motion:` override blocks (supplied only to override or extend the reference's geometry/motion values — never the source of those values), plus the optional top-level `assets:` block (logo rendering mode).
- **From shared reference (`../../reference/`):** every file under `foundations/` — `overview.md` (architecture + palette philosophy + role inventory), `typography.md`, `layout.md`, `accessibility.md`, `motion.md`, `imagery.md`, `responsive.md`, `implementation.md` (theme contracts + CSS variable emit patterns) — plus `components.md`. **Geometry values (spacing, radius, section-padding, containers) come from `layout.md §11`; motion values (easing, durations, entrance-pattern params) from `motion.md §15`; component geometry (topbar height, logo height) from `components.md §12.1` + `implementation.md §8.4`. The reference is the authoritative source of these values; the elements YAML only overrides them.**
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`:** the output directory if set; otherwise asked at call time.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`:** the project extensions directory (or unset → treated as `NONE`), read only to record its fingerprint in the manifest so the composers can detect when the input set has advanced.
- **From `../../validation/`:** `customizable-design-elements.schema.json` for elements-YAML validation.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool used for the manifest (so the composers compute identical hashes when checking staleness).

## Discovery checklist

1. Is `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` set and does the file exist? If not → STOP `ELEMENTS_YAML_UNSET`.
2. Is the output directory resolvable from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`? If not, ask the caller once for an absolute output directory. If still unresolved → STOP `OUTPUT_PATH_UNRESOLVABLE`.
3. Does a prior `manifest.json` exist at the output directory? If so, surface its `generated_at` and the SHAs of `elements_semantic_sha256`, `reference_tree_sha256`, and `extensions_tree_sha256` so the caller knows whether a regenerate is a no-op.
4. Is this an explicit full regenerate, or should incremental skip-on-no-change apply?

## Pipeline

1. **Validate the elements YAML** against `../../validation/customizable-design-elements.schema.json`. If invalid → STOP `PRECONDITION_FAILED`, naming the failing path inside the YAML.
2. **Version check.** Compare the YAML's `$schema_version` against the schema's `$id` major version. If majors differ → STOP `ELEMENTS_VERSION_MISMATCH`.
3. **Read the elements YAML** for palette entries, typeface set, role bindings, the `$conventions` block (custom-property naming for every family, including the geometry/motion override patterns), and the **optional** `geometry:`/`motion:` override blocks if present.
4. **Read every foundations file** (`../../reference/foundations/overview.md`, `typography.md`, `layout.md`, `accessibility.md`, `motion.md`, `imagery.md`, `responsive.md`, `implementation.md`) and **`../../reference/components.md`** in full. The palette swatch values live in `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` (not in foundations); the role contract lives in `overview.md §5` and the theme bindings in `implementation.md §6` + the elements YAML's `themes:` block. If any referenced spec is too thin to write declarative CSS (e.g., a component family with no sizing or no state matrix) → STOP `MISSING_SPEC`, naming the gap.
5. **Compose `tokens.css`** — CSS custom properties for the whole design system, one declaration per token (no shorthand). **Colors and fonts are sourced from the elements YAML and named per the `$conventions` block. Geometry and motion are sourced from the reference and emitted with the reference's own token names and values; a matching entry in an optional `geometry:`/`motion:` YAML block overrides the reference value for that key. The generator walks each block in file order and hardcodes no token name or count:**
   - **Colors** — `color_catalog` (primitives, then semantic aliases), per `foundations/implementation.md §8.1`. Naming: `color_var_pattern`.
   - **Fonts / typefaces** — `typefaces` (`typeface_var_pattern`) and `fonts` (`font_var_pattern`).
   - **Geometry** — values sourced from the reference (`foundations/layout.md §11` for spacing/radius/section-padding/containers/columns; `components.md §12.1` + `foundations/implementation.md §8.4` for component geometry such as `--topbar-height` and `--topbar-logo-height`), emitted with the reference's token names and values. An optional `geometry:` block in the elements YAML overrides per key (named per `spacing_var_pattern` `--sp-{key}`, `radius_var_pattern` `--radius-{key}`, `section_padding_var_pattern` `--section-pad-{key}`, `container_var_pattern` `--container-{key}`, `column_var_pattern` `--column-{key}`, `component_size_var_pattern` `--{component}-{property}`) and may add project-specific tokens; a supplied `value` replaces the reference value verbatim. When a token carries a `mobile_floor` (from the reference or an override), emit a re-declaration at `:root` inside `@media (max-width: <max_width>)` so every consumer inherits the floor (the §11.3 `--section-pad-main` pattern — also covers component tokens like `--topbar-height`).
   - **Motion** — values sourced from the reference (`foundations/motion.md §15` for easing curves, durations, and entrance-pattern parameters), emitted with the reference's token names and values. An optional `motion:` block in the elements YAML overrides per key (named per `ease_var_pattern` `--ease-{key}`, `duration_var_pattern` `--duration-{key}`, `motion_pattern_var_pattern` `--{pattern}-{property}`, e.g. `--reveal-stagger`, `--card-duration`) and may add project-specific tokens.

   **The only NON-configurable tokens** are the typography weight / line-height / tracking scale (`--fw-*`, `--lh-*`, `--track-*`), which remain foundation-fixed (`foundations/typography.md §13.3`) and are emitted verbatim. Geometry and motion are no longer "fixed" — they are reference-sourced, YAML-overridable element sets, peers to color (`foundations/overview.md §2`, `foundations/layout.md`, `foundations/motion.md`). A YAML that omits a `geometry:`/`motion:` override block is valid — the reference values are used unchanged. **Never STOP `MISSING_SPEC` for an omitted YAML `geometry:`/`motion:` block;** STOP `MISSING_SPEC` only when the reference itself lacks a value a generated class depends on. Every `var(--token)` referenced in `components.css` must be defined in the emitted set — enforced by `test/checks/check_token_coverage.py`.
6. **Compose `components.css`** — one class per component family per `components.md`, kebab-case identifiers that mirror role and component names (e.g., `.button-primary`, `.topbar`, `.text-tertiary`). Each class declares only what the reference specifies, consuming **role variables** (color) and **geometry tokens** (sizing/spacing/radius/container) — never a literal a token already names. The DESIGN SYSTEM owns component sizing: emit the topbar's geometry as `.topbar { height: var(--topbar-height); }` and `.topbar-logo, .topbar-logo img, .topbar-logo svg { height: var(--topbar-logo-height); width: auto; }` (foundations/implementation.md §8.4, components.md §12.1) — the logo height resolves from config so no page block ever hardcodes it. **Emit the ground / feature-tile variant set data-drivenly:** for every role in the YAML roles map whose key matches `tile-ground-<suffix>`, emit two classes that share the same declarations — `.feature-tile--<suffix>` (the editorial-tile alias) and `.ground--<suffix>` (the shape-agnostic ground any `card-grid` may opt into) — each declaring `background: var(--tile-ground-<suffix>); color: var(--tile-ink-<suffix>);`. If the paired `tile-ink-<suffix>` role is absent, fall back to `color: var(--text-primary)`. Hardcode no count or suffix list — `tile-ground-4..N` declared in the YAML automatically produce `.feature-tile--4..N` and `.ground--4..N`, and the suffix is decoupled from the bound palette key (a theme binds `tile-ground-2` to any `panels-*`). `.editorial-featured-card` consumes a chosen `.feature-tile--N` rather than baking a fixed ground. **Emit the layout utility classes** from `foundations/layout.md §11.2`: `.u-container` (a section wrapper at `max-width: var(--container-marketing-primary)`, centered, with the §11.2 side padding), `.u-container-full` (`max-width: none`, full-bleed), and `.u-reading` (an inner reading column at `max-width: var(--column-reading)`, centered). A section wrapper never takes a `--column-*` width. **Emit the logo mode-swap rules only when `assets.logo.mode == asset-pair`:** select the active logo image by mode in CSS (no JS) — `.topbar-logo .logo-dark { display: none; }`, then under `:root[data-mode="dark"]` and under `:root[data-mode="system"]` inside `@media (prefers-color-scheme: dark)` hide `.logo-light` and show `.logo-dark`. When `assets.logo.mode` is `currentColor` (the default, or when no `assets` block is present) emit no logo CSS — the single glyph recolors via `currentColor`. **Then emit the motion entrance patterns** from `foundations/motion.md §15.4`: the `revealWord` / `cardRaise` `@keyframes` and the `.reveal-word` / `.card-stagger` / `.content-fade` / `.content-fade-up` classes, parameterized by the `--{pattern}-*` tokens, **animating in the base rule and resetting to the visible final state only inside `@media (prefers-reduced-motion: reduce)`**, plus the global reduced-motion gate (§15.5). Never wrap entrance motion in `@media (prefers-reduced-motion: no-preference)`.
7. **Compose `themes.css`** — theme bindings (light, dark, any additional modes the YAML declares) per `foundations/implementation.md`. Selectors and resolution order follow the implementation reference exactly. **Alias themes** (a `themes` entry of the form `{ alias: <target> }`, no `modes` of its own) emit no standalone block — graft the alias selector onto every rule generated for its target theme (base class and each mode override) as a grouped selector, so the alias shares 100% of the target's rules. Read the `alias` field from data; never hardcode the alias map. Aliases do not chain.
8. **Write all three files** to the resolved output directory, replacing any existing file with identical name.
9. **Emit `manifest.json`** in the same directory with this exact shape:

   ```json
   {
     "generated_at": "<ISO-8601 timestamp>",
     "elements_semantic_sha256": "<hex>",
     "reference_tree_sha256": "<hex>",
     "extensions_tree_sha256": "<hex>",
     "extensions_dir": "<absolute path or null>",
     "files": {
       "tokens.css": "<hex>",
       "components.css": "<hex>",
       "themes.css": "<hex>"
     },
     "cds_plugin_version": "<semver from plugin.json>"
   }
   ```

   Compute the three input fingerprints with the shared hasher — `python3 ../../lib/cds_hash.py inputs <elements.yaml> ../../reference <extensions-dir|NONE>`:
   - `elements_semantic_sha256` is the YAML's **meaning** (parsed; comments and every `description:` value excluded), so a comment- or description-only edit does **not** change it — and therefore does not trigger a downstream regeneration.
   - `reference_tree_sha256` is the SHA-256 of the alphabetically-sorted concatenation of every file's relative path plus that file's SHA-256, across the entire `reference/` tree.
   - `extensions_tree_sha256` is the same tree hash over `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`, or the empty-string sentinel when no extensions dir is set. `extensions_dir` records the absolute path used (or `null`).

   Using one shared script guarantees the composers compute byte-identical fingerprints when they decide whether the set is stale.

## Halt conditions

- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set, or the file does not exist.
- `OUTPUT_PATH_UNRESOLVABLE` — output directory not supplied by env var and the caller did not provide one after one ask.
- `PRECONDITION_FAILED` — elements YAML fails schema validation.
- `ELEMENTS_VERSION_MISMATCH` — `$schema_version` major differs from the validation schema's `$id` major.
- `MISSING_SPEC` — a **reference** file is too thin to write declarative CSS — a geometry/motion value or component spec the emitted CSS needs is absent from the reference; an omitted YAML `geometry:`/`motion:` override block is never a `MISSING_SPEC` (name the specific gap — e.g., "components.md: Drawer family has no width tokens").

Halt surface format:

```
STOP: generate-stylesheets: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

The emitted CSS satisfies every rule tagged `[scope: both]` in `../../reference/compliance.md`. Determinism contract: for the same (elements YAML semantic content, reference tree bytes), this skill produces byte-identical `tokens.css`, `components.css`, and `themes.css`. Comments and `description:` prose are not emitted into CSS, so they do not affect the output.

## Boundary — does not

- Does not generate HTML, JSX, component code, or mocks — those are owned by `compose-page` and `compose-app-surface`.
- Does not consume or inspect host-project code for any reason.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
- Does not embed theme controllers, mode resolvers, or runtime JavaScript in the CSS files — those live in `foundations/implementation.md` and are emitted by the composers when needed.
- Does not write any state record (this skill is stateless apart from `manifest.json`).
