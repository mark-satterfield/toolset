---
name: compose-shell
description: Composes a Shell — the repeating portions of a site that do not change as pages change (menus pinned to canvas edges, a common footer) — from the user's content and instructions, then emits the Shell HTML, shows it, and stores it named-per-Shell in the shells output area for reuse by compose-view. Trigger on "compose my site's shell", "build the shell", "top nav with these links and a footer", "site frame with menu and footer", or edits to an existing stored Shell ("change the footer links in the shell"). Do NOT trigger on composing a Page (compose-page) or a View (compose-view). Composing a Shell and composing a Page are the same act — the user provides input, content, and instructions; the output is a visual mockup as HTML. The only asymmetry is downstream reuse — Shell + Page HTML = View.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Composes a **Shell** per the shared build pipeline (`../../reference/pipeline.md`). The **ShellDefinition** is the transient blueprint assembled from the user's content and instructions — the actual menu items, the specific logo, the specific colors; it carries real content, it is not content-free configuration. What persists for reuse is the generated **Shell** output: one self-contained HTML file, shown to the user and stored **named per Shell** in `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` so `compose-view` can resolve it by name later. Done once per site, edited rarely.

A ShellDefinition is a Frame (entity model: `../../reference/model/entity-catalog.md`): it contains Sections — a menu or menus pinned to one or more edges of the canvas, and perhaps a common footer or status pinned to the bottom — around the **vacant space** a Page nests into. Each of the Shell's Sections is assigned a Shape like any Frame, and is typically realized by catalog Components (the `shell_component: true` entries: topbar, footer, left-rail, mobile-drawer, skip-links, sticky-header, dropdown-panel, account-row, workspace-switcher).

## Inputs

- **From caller (runtime):** plain-language request naming the Shell and describing its content (menu items, links, logo, footer content); a name for the Shell (asked for if not supplied — the name is the reuse key); optional edits to an existing stored Shell.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json`.
- **From the catalog** — `../../reference/libraries/{components,shapes,sections}/` overlaid by `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR`, resolved per `../../reference/pipeline.md` (Catalog resolution). The `shell_component: true` Component entries carry the contracts for the pieces Shells are typically composed from; the `--app-shell-*` geometry tokens (`../../reference/foundations/layout.md` §11.10) size an application Shell's Sections.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`:** the shells output area. When unset, it defaults to a `shells/` directory that is a **sibling of the mocks directory** (`$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`). No ask at compose time — the default applies silently.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`:** decides whether state records go to `~/.claude/customizable-design-system/state/compose-shell/` (global) or `<project-root>/.claude/customizable-design-system/state/compose-shell/` (project).
- **From `../../reference/compliance.md`:** the rule set the compliance pass runs.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, used by the pipeline's stylesheet-freshness stage.

## Discovery checklist

1. **Routing check.** A whole page of content ("landing page with hero and pricing") → STOP `WRONG_SKILL:compose-page`. A Page inside a Shell → STOP `WRONG_SKILL:compose-view`.
2. **Run-mode detection.** If a stored Shell of the given name already exists in the shells area (or a state record matches), treat the request as **iteration**: load the prior ShellDefinition from the state record, apply the change, overwrite the stored file. Otherwise **generate**.
3. **Shell name.** The reuse key and the stored filename. If the user did not name it, ask once ("what should this shell be called?") — a name is required because `compose-view` resolves Shells by name.
4. **Content.** The Shell's Sections and their real content: which edges carry menus, the menu items and links, the logo, the footer content. Drafted scaffolding applies as in `compose-page` when the user asks for a shell but leaves slots open.
5. **Output area.** Resolve `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`; unset → the `shells/` sibling of the mocks directory (create it if absent). STOP `OUTPUT_PATH_UNRESOLVABLE` only if neither resolves.

## Pipeline

Execute the shared build pipeline (`../../reference/pipeline.md`): catalog resolution, per-Section Shape assignment (eager or lazy) for the Shell's Sections, the silent stylesheet-freshness stage, assembly, sidecars, and the state record. This skill adds only the Shell render specifics:

- **Assembly.** Emit one self-contained HTML file: the Shell's Sections realized around a clearly labeled **vacant space** placeholder (where a Page will nest). The `<head>` inlines the stylesheet set and the theming + color-mode scripts, so the stored Shell opens in a browser on its own.
- **Show it.** Open or surface the emitted Shell for the user to look at, exactly as a composed Page is shown.
- **Store it.** Write the file to the shells area as `<shell-name>.html` — one file per Shell, named per Shell. Editing later is the same command: the stored file is overwritten in place, and Views regenerated afterward inherit the change.
- **State record** (pipeline schema) for iteration; sidecars as the pipeline defines.

The compliance pass runs `[scope: standalone]` + `[scope: both]`.

## Halt conditions

- `WRONG_SKILL:{name}` — the request belongs to `compose-page` or `compose-view`.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the freshness stage's auto-invoked `generate-css` halted; inner code surfaced verbatim.
- `MISSING_COMPONENT:{name}` — a required Component is defined in neither reference nor extensions.
- `MISSING_SPEC` — a required spec is too thin to render (name the gap).
- `OUTPUT_PATH_UNRESOLVABLE` — no shells area resolvable (env var unset AND no mocks directory to sibling from AND the caller declined to supply one).
- `ARTWORK_UNRESOLVABLE:{slot}` — a needed artwork slot (e.g. the logo) yields no asset through `../../reference/artwork.md`.
- `COMPLIANCE_UNSATISFIABLE` — a compliance rule cannot be satisfied without violating a reference spec.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: compose-shell: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance gate

The emitted Shell must satisfy every rule tagged `[scope: standalone]` and `[scope: both]` in `../../reference/compliance.md`, and stays metadata-free (reasoning lives in the sidecars).

## Boundary — does not

- Does not compose Pages (`compose-page`) or Views (`compose-view`).
- Does not ship or pre-define any Shell — every Shell is composed here, from the user's content. The plugin catalog contains no shells.
- Does not inspect host-project code.
- Does not itself author stylesheet CSS; the freshness stage INVOKES `generate-css` silently when inputs move.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
