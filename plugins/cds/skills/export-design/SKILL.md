---
name: export-design
description: Produces one DESIGN.md file — the map of the live Configurable Design System, written to the emerging DESIGN.md convention so any consumer (a human, or a tool that reads DESIGN.md the way AGENTS.md is read for agent instructions) can follow the system without opening the plugin. Emits the color system (palettes → roles → themes with real values), typography, geometry and motion summaries, the Building Blocks catalog (Components, Shapes, Sections, and Pages with their contracts and per-entry aliases, plus the statement that Shells are user-composed via compose-shell and never shipped), the rule summaries, the compliance essentials, and how to consume the class and token names. Trigger on "export the design system", "generate DESIGN.md", "give me the design doc", "write the design system file", or "produce a DESIGN.md". The file is regenerated, never hand-edited. Must NOT trigger on composing pages, shells, or views (compose-page, compose-shell, compose-view), on auditing (audit-against-system), or on any stylesheet request — stylesheet freshness is handled silently inside this skill's own pipeline.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Reads the live design system — the elements YAML, the catalog (reference trees overlaid by project extensions), and the generated stylesheet manifest — and emits a single `DESIGN.md` file that describes the whole system in one place. DESIGN.md is the map, not a copy of everything: it states the color/typography/geometry/motion values and enumerates the Building Blocks with one-line purposes and their contracts, and it cites each library entry by path for the depth. It is written to the DESIGN.md convention (below) so a tool that consumes DESIGN.md the way AGENTS.md is consumed can follow the design system without loading the plugin.

The file is **regenerated, never hand-edited** — the emitted header says so — and is **deterministic** given the same inputs (same elements YAML meaning, same reference tree, same extensions tree).

## The DESIGN.md convention followed

Structure follows Google Labs' design.md specification ([google-labs-code/design.md](https://github.com/google-labs-code/design.md), April 2026 — the design-system analogue of AGENTS.md), extended for the CDS Building Blocks model where the base spec's flat `Components` section is too thin. The spec defines: an optional YAML frontmatter of machine-readable tokens (`version`, `name`, `description`, `colors`, `typography`, `rounded`, `spacing`, `components`) followed by a markdown body whose `##` sections keep a fixed order (`Overview`, `Colors`, `Typography`, `Layout`, `Elevation`, `Shapes`, `Components`, `Do's and Don'ts`); token references use `{path.to.token}` dot notation; sections may be omitted but present sections keep the order. The extensions here — a generation stamp in frontmatter, a `Motion` section (the Better Stack DESIGN.md variant carries one), a `Building Blocks` catalog that replaces the flat `Components` section for the five-layer CDS model, a `Rules` section, and a `How to consume` section — are additive and recorded in the emitted body. (Convention identified via web search: "DESIGN.md convention", "DESIGN.md AI agents design system file", Google Labs design.md spec and the Better Stack / VoltAgent DESIGN.md guides.)

## Inputs

- **From caller (runtime):** an optional output path argument; nothing else is required.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`:** the absolute path to the elements YAML — palette swatch values, typeface set, role bindings, `themes:` block, `$conventions`, `$schema_version`, and the optional `geometry:`/`motion:`/`assets:` blocks. If unset or the file is missing → STOP `ELEMENTS_YAML_UNSET`.
- **From the catalog** — the `../../reference/libraries/` + `../../reference/rules/` trees overlaid by `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` (same tree structure), resolved by the same catalog-overlay rule the composers use (Catalog resolution, `../../reference/pipeline.md` — a project entry whose `kind` + basename match replaces the plugin entry wholesale; project-only entries extend). Entry format is `../../reference/libraries/FORMAT.md`; user-facing names resolve against each entry's `name` and `aliases:` frontmatter.
- **From `../../reference/foundations/`:** the value sources DESIGN.md summarizes — `overview.md` (palette philosophy, role inventory), `typography.md`, `layout.md` (geometry §11), `motion.md` (§15), `accessibility.md`, `implementation.md` (theme contracts). These are the authoritative value sources; DESIGN.md summarizes them and cites them, it does not restate every line.
- **From `../../reference/compliance.md`:** the compliance rules the "Compliance" section distills.
- **From the generated stylesheet manifest** (`$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR/manifest.json`): the semantic-hash fingerprints, `generated_at`, and `cds_plugin_version` that become the generation stamp. Regenerate-if-stale first (below) so the stamp reflects the current inputs.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool — used only through the freshness stage, never recomputed here.
- **From `../../.claude-plugin/plugin.json`:** the plugin version recorded in the stamp.

## Discovery checklist

1. Is `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` set and does the file exist? If not → STOP `ELEMENTS_YAML_UNSET`.
2. **Resolve the output path**, in order: (a) the caller's path argument; (b) `$CUSTOMIZABLE_DESIGN_SYSTEM_DESIGN_MD_PATH`; (c) ask the caller once for an absolute output path. If still unresolved → STOP `OUTPUT_PATH_UNRESOLVABLE`. A path naming a directory resolves to `<dir>/DESIGN.md`.
3. Resolve the working catalog (reference ∪ extensions) per `../../reference/pipeline.md` Catalog resolution.

## Pipeline

1. **Refresh the stylesheet set (freshness stage, cited not restated).** Run the same stylesheet-freshness step the composers run — compare the `cds_hash.py` semantic fingerprints (elements YAML, reference tree, extensions tree) against `manifest.json`; on mismatch invoke `generate-css` and proceed; **never halt for staleness**; halt `STYLESHEETS_REGEN_FAILED:{inner}` only if that regeneration itself halts, surfacing the inner code verbatim (`../../reference/pipeline.md`, stage 4 — Stylesheet freshness). The whole step is silent: nothing about freshness or regeneration is surfaced to the human. This guarantees the manifest fingerprints written into the stamp match the current inputs.
2. **Read the value sources.** Parse the elements YAML (palette, typefaces, fonts, role bindings, `themes:`, optional `geometry:`/`motion:` overrides). Read the foundations files that hold the reference geometry/motion values and the theme contract (`layout.md §11`, `motion.md §15`, `implementation.md §6`, `overview.md §5`). If a value a DESIGN.md section must state is absent from both the elements YAML and the reference (e.g. no palette in the YAML, no geometry scale in the reference) → STOP `MISSING_SPEC`, naming the gap.
3. **Read the manifest** at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR/manifest.json` for `generated_at`, `elements_semantic_sha256`, `reference_tree_sha256`, `extensions_tree_sha256`, and `cds_plugin_version` — the generation-stamp fingerprints (staleness in any consumer is detectable by comparing these).
4. **Enumerate the catalog.** Walk `libraries/components/`, `libraries/shapes/`, `libraries/sections/`, `libraries/pages/`, `rules/shape-selection/`, `rules/page-constraints/` (reference ∪ extensions, overlay applied). For each entry read its frontmatter for `name`, `page_family`, `aliases`, `status`, and its per-kind contract fields. Hardcode no counts or names — walk what the catalog declares. There is no shells directory to walk: the catalog contains no Shells — every Shell is user-composed via `compose-shell` and stored outside the catalog in `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`.
5. **Compose `DESIGN.md`** with this exact shape:

   **Frontmatter** (machine-readable tokens, DESIGN.md spec + the generation-stamp extension):
   ```yaml
   ---
   version: alpha
   name: <design system name from the elements YAML>
   description: <one-line identity for the system>
   generated:
     by: cds:export-design
     at: <manifest generated_at>
     cds_plugin_version: <plugin.json version>
     fingerprints:
       elements_semantic_sha256: <manifest value>
       reference_tree_sha256: <manifest value>
       extensions_tree_sha256: <manifest value>
   colors:        # primitives then semantic roles, values from the elements YAML
     <token>: <css color value>
   typography:    # per named text style: fontFamily, fontSize, fontWeight, lineHeight, letterSpacing
     <token>: { ... }
   rounded:       # radius scale, values from layout.md §11 (YAML geometry override wins)
     <level>: <dimension>
   spacing:       # spacing scale, same source
     <level>: <dimension>
   motion:        # easing + durations from motion.md §15 (YAML motion override wins)
     <token>: <value>
   components:    # one entry per Component Definition, its bound role tokens + sizing token refs
     <name>: { ... }
   ---
   ```

   **Body** — first line a banner, then the sections in this order:

   - Banner: `> **Generated by `cds:export-design` — do not hand-edit.** Regenerate with `/cds:export-design`. This file is a map of the live design system; edit the elements YAML or the catalog, then regenerate.`
   - `## Overview` — the identity line, one paragraph on what the system is, and the generation stamp restated in human form (generated-at, plugin version, the three fingerprints) so staleness is visible without parsing frontmatter.
   - `## Colors` — the color system as palettes → roles → themes: the primitive palette with real swatch values, the semantic role set (`--surface-*`, `--text-*`, `--button-*`, ground/ink pairs, …) and what each role means, and each declared theme (light, dark, aliases) with the role→value bindings it resolves. Cites `foundations/overview.md §5` and `foundations/implementation.md §6`.
   - `## Typography` — the typefaces and font stacks (real values), and the type scale (weights, line-heights, tracking) with the non-configurable ladder noted. Cites `foundations/typography.md`.
   - `## Layout & Spacing` — geometry summary: spacing scale, radius scale, section padding, container widths, reading columns, the `--app-shell-*` and `--pane-*` dimension tokens, control/row heights, with values and token names. Cites `foundations/layout.md §11`.
   - `## Motion` — easing curves, durations, and the entrance patterns (`.reveal-word`, `.card-stagger`, `.content-fade`, `.content-fade-up`) with the reduced-motion rule. Cites `foundations/motion.md §15`.
   - `## Building Blocks` — the CDS catalog, one subsection per cataloged kind (`### Components`, `### Shapes`, `### Sections`, `### Pages`) followed by a `### Shells` note. The section opens with one intro line noting that Elements are the concept-only DOM baseline beneath Components — never configured, never cataloged. Each entry is one row: name, a purpose one-liner, its page family, its `aliases:` frontmatter, and the load-bearing contract — for Components the five contracts in brief (slots, sizing, behavior, accessibility, token bindings), the `### Components` rows being Component Definitions (an on-page Component is an instance of its Definition); for Shapes the slots and `self_contained` flag; for Sections the Shape-assignment mode (eager `shape:` or lazy via its Shape Selection Rule) and content contract; for Pages the ordered Section list and referenced constraints. Each row cites its entry path (e.g. `reference/libraries/components/button.md`) for depth — DESIGN.md names and locates, it does not inline every contract. `### Shells` enumerates no catalog entries, because the plugin ships none: it states that every Shell is user-composed via `compose-shell`, stored by name in `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` (default: a `shells/` directory that is a sibling of the mocks directory), and paired with a Page at view time by `compose-view`.
   - `## Rules` — `### Shape selection` (per-Section: the signals consulted and that a rule chooses an ordered candidate set, citing `rules/shape-selection/`) and `### Page-Level Aesthetic Constraints` (directory: `rules/page-constraints/`) (the post-selection validators — ground alternation and the Variety Principle — citing `rules/page-constraints/`). Summaries, not rule tables.
   - `## Compliance` — the compliance essentials a consumer must honor (drawn from `reference/compliance.md`): consume system tokens/classes rather than hardcoding geometry; section wrappers take a `--container-*` width, never a `--column-*`; entrance motion only through the generated classes; deliverables carry no agent-side metadata; contrast obligations. This section fills the DESIGN.md spec's `Do's and Don'ts` slot.
   - `## How to consume` — the practical handles: the generated stylesheet files (`tokens.css`, `components.css`, `themes.css`) and how they are loaded; the class-name convention (kebab-case mirroring role/component names, `.ground--N`/`.feature-tile--N`, the `.u-container`/`.u-reading` utilities); the token-name convention (`var(--sp-*)`, `--container-*`, `--surface-*`, …); and how user-facing words resolve — against catalog entry names and each entry's `aliases:` frontmatter, which the Building Blocks rows above list per entry.

6. **Write `DESIGN.md`** to the resolved output path, replacing any existing file of that name. Emit nothing else — no sidecars, no state record; this skill has no run-modes.

## Halt conditions

- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set, or the file does not exist.
- `OUTPUT_PATH_UNRESOLVABLE` — no path argument, `$CUSTOMIZABLE_DESIGN_SYSTEM_DESIGN_MD_PATH` unset, and the caller supplied none after one ask.
- `STYLESHEETS_REGEN_FAILED:{inner}` — the freshness stage found the stylesheet set stale or missing and the auto-invoked `generate-css` itself halted; the inner halt code is surfaced verbatim.
- `MISSING_SPEC` — a value a DESIGN.md section must state is absent from BOTH the elements YAML and the reference (name the specific gap — e.g., "foundations/layout.md §11: no spacing scale"). An omitted YAML `geometry:`/`motion:` override block is never a `MISSING_SPEC` — the reference values are used unchanged.

Halt surface format:

```
STOP: export-design: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Compliance & determinism

For the same (elements YAML semantic content, reference tree bytes, extensions tree bytes) the emitted `DESIGN.md` is byte-identical — the same inputs that fingerprint identically in the manifest produce the same document. The catalog enumeration is ordered (kind, then entry name) so ordering never drifts. The file is a description of the current state only: no change history, no decision narration, no known-gaps commentary, no deferred-work notes (the DESIGN.md prose rule mirrors the reference prose rule in `../../reference/libraries/FORMAT.md`).

## Boundary — does not

- Does not generate the stylesheet set — it INVOKES `generate-css` through the freshness stage when inputs have moved, then reads the manifest. It never authors CSS.
- Does not compose Pages, Shells, or Views, and emits no sidecars or state record.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`, any file under `../../reference/`, or any extensions entry — it reads them and writes only `DESIGN.md`.
- Does not inspect host-project code; the catalog and elements YAML are the only sources.
- Does not certify compliance — it distills the compliance rules into the document; `audit-against-system` is the gate that certifies emitted UI.
