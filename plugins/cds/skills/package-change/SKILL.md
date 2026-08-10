---
name: package-change
description: Bundles an approved CDS change into a single hand-off package the app-repo developer (or developer agent) builds from — the generated stylesheet set, the composer's HTML artifact (a Page HTML, a Shell, or a View), a derived build spec, the wireframe and decision-log sidecars, and any ancillary assets. Trigger on "package this change", "package the mock", "give me the hand-off bundle", "bundle this for the app repo", "prepare the change for the developer", or any request to take an approved cds output across the boundary from "approved in cds" to "built in the app repo". Do NOT trigger on composing or iterating an output (compose-page, compose-shell, compose-view), on opening an output in the visual harness (review), or on auditing.
allowed-tools: Read, Write, Bash, Glob
---

## Read the model first

Read `../../reference/model/entity-catalog.md` **in full** before anything else in this skill — every row and every column of both tables, plus its "How to read this catalog" rules. It is normative and it is not skimmable: `Type`, `Extends`, `Construct`, and `Contains` carry meaning the descriptions alone do not; inheritance is transitive; `Contains` never implies "is a container"; `Abstract` and `Concrete` are deliberate; and `can` / `may` / `typically` never mean `must`. Do not proceed from a remembered or summarized version of it, and do not resolve any Building Blocks term — Element, Component, Shape, Frame, Section, Page, ShellDefinition, View, page family — until it has been read this run.

## What this skill does

Assembles everything an approved change needs to reach the application repository into one self-describing bundle directory. It generates nothing new about the design — it reads the state record a prior composer run (`compose-page`, `compose-shell`, `compose-view`) wrote (the deterministic spine), confirms the stylesheet set is current, derives a build spec from the recorded sections, and copies the artifacts together with a `README` index. This is the hand-off boundary: after this skill runs, the app-repo developer agent builds from the bundle alone.

## Inputs

- **From caller (runtime):** a target — the `output_path` of a prior composer output (a Page HTML, a Shell, or a View); an optional bundle output directory override.
- **From the matching state record** (in `~/.claude/customizable-design-system/state/{compose-page|compose-shell|compose-view}/` or the project-local equivalent, per `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`): the resolved `sections` (shapes, themes, components, grounds), the `brief_snapshot`, the sidecar paths, `mode` (`generate` | `update`) and any `update_source`, and the referenced asset paths.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json`.
- **From the artifact:** the composer's HTML output — a Page HTML, a Shell, or a View.
- **From the sidecars:** the `wireframe.txt` and `decisions.md` files the pipeline writes beside every composer output.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`** (and the asset paths in the state record): ancillary icon/image files that must ship on the same server as the page, plus the `artwork-manifest.yaml` provenance manifest (`../../reference/artwork.md`) when the assets directory holds one.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR`:** the default root under which bundles are written; if unset, asked once.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, to confirm the stylesheet set is current before bundling.

## Discovery checklist

1. **Resolve the target.** From the caller's pointer, find the state record whose `output_path` matches strictly, searching all three state directories. If none is found → STOP `STATE_RECORD_NOT_FOUND`.
2. **Determine the artifact kind** from which state directory matched — a Page HTML (`compose-page`), a Shell (`compose-shell`), or a View (`compose-view`). The bundle carries that one HTML artifact.
3. **Resolve the bundle output root** from `$CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR`, else ask once. If still unresolved → STOP `OUTPUT_PATH_UNRESOLVABLE`.

## Pipeline

1. **Load the state record** for the resolved target — it is the build spec's spine.
2. **Confirm stylesheet freshness (silent).** Compute the live fingerprints with `python3 ../../lib/cds_hash.py inputs <$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS> ../../reference <$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR|NONE>` and compare to `manifest.json`. If stale or missing, invoke the internal `../generate-css/SKILL.md` machinery and proceed, so the bundle ships current CSS — never mention this stage to the human or present it as something for them to run. If that regeneration itself halts, STOP `STYLESHEETS_REGEN_FAILED:{inner-code}`.
3. **Synthesize the build spec** from the state record — the composed artifact (the Page with its page family, the ShellDefinition a Shell realizes, or both for a View), its ordered Sections (each with Shape, Components, grounds, token/class contract), and the accessibility contracts the chosen Components carry. For a View, the spec also names the stored Shell (from `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`) the Page nests inside. This is reference-anchored, not invented: it cites the catalog entries by path — `../../reference/libraries/{components,shapes,sections,pages}/<name>.md` and the `../../reference/rules/{shape-selection,page-constraints}/<name>.md` entries the composition applied — plus `../../reference/compliance.md`, rather than restating them.
4. **Copy the artifacts** into the bundle (layout below): the stylesheet set + manifest, the composer's HTML artifact, the wireframe and decision-log sidecars, the resolved ancillary assets (including `artwork-manifest.yaml` when the assets directory holds one), and the state record. Never include a `.review.html` file — that is the review skill's harness artifact, a working file, not a deliverable. If an asset path recorded in the state record cannot be resolved → STOP `ASSETS_UNRESOLVABLE` and name it.
5. **For an update (brownfield) change** (`mode == update` in the state record), add an `update` folder: a snapshot of the original files the change started from (`update_source`) plus the region-scoped change diff, so the app-repo agent applies a scoped change rather than a from-scratch rebuild.
6. **Write the bundle README** — the index plus a short "how the app-repo agent builds this" note. Emit nothing back into the source artifacts (no metadata injected into the HTML artifact or the stylesheets).

## Output bundle layout

A timestamped bundle directory under the package root. The `design/` payload is the composer's self-contained HTML artifact, named for its kind — `page.html` from `compose-page`, `shell.html` from `compose-shell`, `view.html` from `compose-view` (a View already embeds its Shell, so it ships as one file). The `spec/` sidecars come from the same composer run, whichever composer that was:

```
PACKAGE_ROOT/
  <change-slug>-<timestamp>/
    README.md              index + how-to-build note
    spec/
      build-spec.md        the developer-agent spec, derived from the state record
      decisions.md         copy of the composer's decision log
      wireframe.txt        copy of the composer's wireframe
    design/
      page.html | shell.html | view.html
                           the composer's self-contained HTML artifact
                           (never the .review.html harness file)
    styles/
      tokens.css  components.css  themes.css  manifest.json
    assets/                ancillary icon/image files for the same server
      artwork-manifest.yaml  the artwork provenance manifest, copied when present
    state/
      <state-record>.yaml
    update/                present only when mode == update
      original/            snapshot of the existing files the change started from
      change.diff          the region-scoped diff applied by the update path
```

## Halt conditions

- `STATE_RECORD_NOT_FOUND` — no state record matches the target; nothing to package.
- `OUTPUT_PATH_UNRESOLVABLE` — no bundle output directory provided and none discoverable.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the stylesheet set was stale and the auto-invoked `generate-css` halted; the inner code is surfaced verbatim.
- `ASSETS_UNRESOLVABLE` — an ancillary asset recorded in the state record cannot be found.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: package-change: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Boundary — does not

- Does not compose or iterate outputs — the composers own that; this skill only collects their approved output.
- Does not author stylesheet CSS — it invokes `generate-css` to refresh a stale set, nothing more.
- Does not inject any metadata into the HTML artifact or the stylesheets — the build spec and the sidecars are separate files in the bundle.
- Does not build, run, or deploy anything in the app repository — it produces the hand-off bundle only.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
