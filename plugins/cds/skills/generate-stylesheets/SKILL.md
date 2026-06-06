---
name: generate-stylesheets
description: Produces the canonical Customizable Design System stylesheet set — tokens.css, components.css, themes.css, and manifest.json — by reading the elements YAML and the deterministic reference tree. Trigger on requests to generate, regenerate, refresh, rebuild, emit, produce, update, sync, or run an incremental pass on the design-system CSS, design tokens, or stylesheet set — including first-time bootstrapping and post-edit regeneration after changing the elements YAML or palette. Must NOT trigger on composition requests (building pages, mocks, sections, or in-app surfaces — those route to compose-page or compose-app-surface; the stylesheet set this skill emits is an INPUT to those skills, not an output). Must NOT trigger on audit, code review, or informational queries about the design system.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Reads the elements YAML and the plugin's deterministic reference tree, then emits three CSS files (`tokens.css`, `components.css`, `themes.css`) plus a `manifest.json` at a resolved output directory. The emitted CSS is byte-identical for any given (elements YAML, reference tree) pair and is consumed by `compose-page` (inlined into mocks) and `compose-app-surface` (linked from app-embedded code).

## Inputs

- **From caller (runtime):** the resolved output directory (if not supplied by env var); a regenerate-all vs. incremental choice (incremental still produces all three files but only triggers a write when any input SHA differs from `manifest.json`).
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the absolute path to the elements YAML — the palette, typeface set, role bindings, conventions, and `$schema_version`.
- **From shared reference (`../../reference/`):** every file under `foundations/` — `overview.md` (architecture + palette philosophy + role inventory), `typography.md`, `layout.md`, `accessibility.md`, `motion.md`, `imagery.md`, `responsive.md`, `implementation.md` (theme contracts + CSS variable emit patterns) — plus `components.md`.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`:** the output directory if set; otherwise asked at call time.
- **From `../../validation/`:** `customizable-design-elements.schema.json` for elements-YAML validation.

## Discovery checklist

1. Is `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` set and does the file exist? If not → STOP `ELEMENTS_YAML_UNSET`.
2. Is the output directory resolvable from `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`? If not, ask the caller once for an absolute output directory. If still unresolved → STOP `OUTPUT_PATH_UNRESOLVABLE`.
3. Does a prior `manifest.json` exist at the output directory? If so, surface its `generated_at` and the SHAs of `elements_yaml_sha256` and `reference_tree_sha256` so the caller knows whether a regenerate is a no-op.
4. Is this an explicit full regenerate, or should incremental skip-on-no-change apply?

## Pipeline

1. **Validate the elements YAML** against `../../validation/customizable-design-elements.schema.json`. If invalid → STOP `PRECONDITION_FAILED`, naming the failing path inside the YAML.
2. **Version check.** Compare the YAML's `$schema_version` against the schema's `$id` major version. If majors differ → STOP `ELEMENTS_VERSION_MISMATCH`.
3. **Read the elements YAML** for palette entries, typeface set, role bindings, and the `$conventions` block (which fixes custom-property naming).
4. **Read every foundations file** (`../../reference/foundations/overview.md`, `typography.md`, `layout.md`, `accessibility.md`, `motion.md`, `imagery.md`, `responsive.md`, `implementation.md`) and **`../../reference/components.md`** in full. The palette swatch values live in `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` (not in foundations); the role contract lives in `overview.md §5` and the theme bindings in `implementation.md §6` + the elements YAML's `themes:` block. If any referenced spec is too thin to write declarative CSS (e.g., a component family with no sizing or no state matrix) → STOP `MISSING_SPEC`, naming the gap.
5. **Compose `tokens.css`** — CSS custom properties bound to elements-YAML values through the role contract in `foundations/overview.md §5`. Naming follows the YAML's `$conventions` block (e.g., `--color-{palette}-{shade}`, `--role-{key}`, `--type-{key}`, `--space-{key}`). One declaration per token; no shorthand.
6. **Compose `components.css`** — one class per component family per `components.md`, using kebab-case identifiers that mirror role and component names from the reference (e.g., `.button-primary`, `.surface-secondary`, `.text-tertiary`). Each class declares only what the reference specifies — no invented rules.
7. **Compose `themes.css`** — theme bindings (light, dark, any additional modes the YAML declares) per `foundations/implementation.md`. Selectors and resolution order follow the implementation reference exactly. **Alias themes** (a `themes` entry of the form `{ alias: <target> }`, no `modes` of its own) emit no standalone block — graft the alias selector onto every rule generated for its target theme (base class and each mode override) as a grouped selector, so the alias shares 100% of the target's rules. Read the `alias` field from data; never hardcode the alias map. Aliases do not chain.
8. **Write all three files** to the resolved output directory, replacing any existing file with identical name.
9. **Emit `manifest.json`** in the same directory with this exact shape:

   ```json
   {
     "generated_at": "<ISO-8601 timestamp>",
     "elements_yaml_sha256": "<hex>",
     "reference_tree_sha256": "<hex>",
     "files": {
       "tokens.css": "<hex>",
       "components.css": "<hex>",
       "themes.css": "<hex>"
     },
     "cds_plugin_version": "<semver from plugin.json>"
   }
   ```

   `reference_tree_sha256` is the SHA-256 of the alphabetically-sorted concatenation of every file's relative path plus that file's SHA-256, taken across the entire `reference/` tree.

## Halt conditions

- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set, or the file does not exist.
- `OUTPUT_PATH_UNRESOLVABLE` — output directory not supplied by env var and the caller did not provide one after one ask.
- `PRECONDITION_FAILED` — elements YAML fails schema validation.
- `ELEMENTS_VERSION_MISMATCH` — `$schema_version` major differs from the validation schema's `$id` major.
- `MISSING_SPEC` — any reference file is too thin to write declarative CSS (name the specific gap — e.g., "components.md: Drawer family has no width tokens").

Halt surface format:

```
STOP: generate-stylesheets: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

The emitted CSS satisfies every rule tagged `[scope: both]` in `../../reference/compliance.md`. Determinism contract: for the same (elements YAML bytes, reference tree bytes), this skill produces byte-identical `tokens.css`, `components.css`, and `themes.css`.

## Boundary — does not

- Does not generate HTML, JSX, component code, or mocks — those are owned by `compose-page` and `compose-app-surface`.
- Does not consume or inspect host-project code for any reason.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
- Does not embed theme controllers, mode resolvers, or runtime JavaScript in the CSS files — those live in `foundations/implementation.md` and are emitted by the composers when needed.
- Does not write any state record (this skill is stateless apart from `manifest.json`).
