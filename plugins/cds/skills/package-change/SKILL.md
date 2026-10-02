---
name: package-change
description: Bundles an approved CDS change into a single hand-off package the app-repo developer (or developer agent) builds from — the generated stylesheet set, the composer's HTML artifact (a Page HTML, a Shell, or a View), a derived build spec, the wireframe and decision-log sidecars, and any ancillary assets. Trigger on "package this change", "package the mock", "give me the hand-off bundle", "bundle this for the app repo", "prepare the change for the developer", or any request to take an approved cds output across the boundary from "approved in cds" to "built in the app repo". Do NOT trigger on composing or iterating an output (compose-page, compose-shell, compose-view), on opening an output in the visual harness (review), or on auditing.
allowed-tools: Read, Write, Bash, Glob
---

## Read the model first

Before anything else in this run, read `../../reference/model/entity-catalog.md` **in full** — every row and every column of both tables, plus its "How to read this catalog" rules. Those rules are stated in that file and are deliberately not repeated here: the catalog is the only description of the model, and a second copy would be a second thing to keep true. It is normative and it is not skimmable. Resolve no Building Blocks term — Element, Component, Shape, Frame, Section, Page, ShellDefinition, View, page family — from memory, from a summary, or from training data; only from that file, read this run.

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

`../../tools/package-change.py` performs these checks; the skill only resolves the bundle root first when `$CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR` is unset, and passes it as `--package-root`.

1. **Resolve the target.** From the caller's pointer, find the state record whose `output_path` matches strictly, searching all three state directories. If none is found → STOP `STATE_RECORD_NOT_FOUND`.
2. **Determine the artifact kind** from which state directory matched — a Page HTML (`compose-page`), a Shell (`compose-shell`), or a View (`compose-view`). The bundle carries that one HTML artifact.
3. **Resolve the bundle output root** from `$CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR`, else ask once. If still unresolved → STOP `OUTPUT_PATH_UNRESOLVABLE`.

## Pipeline

One bundle holds exactly one artifact — one Page, one Shell, or one View. To hand off several, run this skill once per artifact.

1. **Run the bundler.** `python3 ../../tools/package-change.py <target-output-path> [--package-root <dir>]` does the discovery checklist and writes the whole bundle; the model synthesizes and copies nothing by hand. It:
   - finds the one state record whose `output_path` equals the target, across the three state directories, and reads the artifact kind from the directory it sits in;
   - for a View, reads the Shell from the record's `shell: {name, modified}` field (records written before that format are read from a plain-string `shell` or from `shell_name` / `shell_modified`) and halts `VIEW_SHELL_UNRESOLVED` when no Shell name resolves;
   - confirms the stylesheet set is current with `../../lib/cds_hash.py` (the elements YAML, `../../reference`, and the extensions tree against `manifest.json`, and each sheet against its recorded SHA-256);
   - writes `spec/build-spec.md` from the state record — the artifact, its page family, for a View the stored Shell and whether this View modified it, and the **Sections table** with one row per recorded Section under its stable Section ID (Shape, Components, ground, resolution rung) — citing by path the `reference/libraries/{components,shapes,sections,pages}/` and `reference/rules/{shape-selection,page-constraints}/` entries the composition applied, plus `reference/compliance.md`, rather than restating them;
   - copies the stylesheet set + manifest, the composer's HTML artifact, the wireframe and decision-log sidecars, the record's assets (plus `artwork-manifest.yaml` when the assets directory holds one), and the state record — never a `.review.html` harness file;
   - for `mode == update`, adds `update/` with a snapshot of `update_source` and the diff from it to the artifact;
   - writes `README.md` (index plus a "how the app-repo agent builds this" note) and `bundle.json`, and prints the bundle path.
2. **Act on its exit status.**
   - `0` — done; report the printed bundle path.
   - `1` — a halt; surface the `STOP:` block it printed on stderr verbatim.
   - `3` — the stylesheet set is stale or missing. Invoke the internal `../generate-css/SKILL.md` machinery, then rerun step 1 — never mention this stage to the human or present it as something for them to run. If that regeneration itself halts, STOP `STYLESHEETS_REGEN_FAILED:{inner-code}`.
   - `2` — a usage or IO error; surface stderr.

Nothing is written back into the source artifacts (no metadata injected into the HTML artifact or the stylesheets).

## bundle.json

The machine-readable contract at the bundle root, which the delivery pipeline matches on:

```json
{"kind": "page" | "shell" | "view",
 "slug": "<artifact slug: the artifact file's basename without .html>",
 "shell": {"name": "<stored shell name>", "modified": false} | null,
 "created_at": "<UTC ISO-8601>",
 "build_spec": "spec/build-spec.md"}
```

`shell` is non-null only for a View. The Section IDs in `spec/build-spec.md`'s Sections table are the IDs downstream work cites.

## Output bundle layout

A timestamped bundle directory under the package root. The `design/` payload is the composer's self-contained HTML artifact, named for its kind — `page.html` from `compose-page`, `shell.html` from `compose-shell`, `view.html` from `compose-view` (a View already embeds its Shell, so it ships as one file). The `spec/` sidecars come from the same composer run, whichever composer that was:

```
PACKAGE_ROOT/
  <change-slug>-<timestamp>/
    bundle.json            the machine-readable contract (above)
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
- `STATE_RECORD_AMBIGUOUS` — more than one state record names the target as its `output_path`.
- `STATE_RECORD_UNREADABLE` — the matching state record is not valid YAML.
- `VIEW_SHELL_UNRESOLVED` — the target is a View and its state record names no Shell.
- `SECTIONS_UNRECORDED` — the state record records no Sections, so the build spec has no Sections table.
- `TARGET_UNREADABLE` — the artifact the state record names is not on disk.
- `SIDECAR_UNRESOLVABLE` — the wireframe or decisions sidecar cannot be found.
- `UPDATE_SOURCE_UNRESOLVABLE` — `mode == update` but `update_source` is not a readable file.
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
