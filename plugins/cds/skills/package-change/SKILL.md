---
name: package-change
description: Bundles an approved CDS change into a single hand-off package the app-repo developer (or developer agent) builds from — the generated stylesheet set, the mock HTML or framework surface, a derived build spec, the wireframe and decision-log sidecars, and any ancillary assets. Trigger on "package this change", "package the mock", "give me the hand-off bundle", "bundle this for the app repo", "prepare the change for the developer", or any request to take an approved cds mock/surface across the boundary from "approved in cds" to "built in the app repo". Do NOT trigger on composing or iterating a mock (compose-page), shipping a live surface (compose-app-surface), regenerating stylesheets (generate-stylesheets), or auditing.
allowed-tools: Read, Write, Bash, Glob
---

## What this skill does

Assembles everything an approved change needs to reach the application repository into one self-describing bundle directory. It generates nothing new about the design — it reads the state record a prior `compose-page` or `compose-app-surface` run wrote (the deterministic spine), confirms the stylesheet set is current, derives a build spec from the recorded sections, and copies the artifacts together with a `README` index. This is the hand-off boundary: after this skill runs, the app-repo developer agent builds from the bundle alone.

## Inputs

- **From caller (runtime):** a target — the `output_path` of a prior `compose-page` mock, or the feature / output of a prior `compose-app-surface` run; an optional bundle output directory override.
- **From the matching state record** (in `~/.claude/customizable-design-system/state/{compose-page|compose-app-surface}/` or the project-local equivalent, per `$CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE`): the resolved `sections` (shapes, themes, components, grounds), the `brief_snapshot`, the sidecar paths, `mode` (`generate` | `update`) and any `update_source`, and the referenced asset paths.
- **From the generated stylesheet set** (at `$CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR`): `tokens.css`, `components.css`, `themes.css`, and `manifest.json`.
- **From the mock or surface:** the `compose-page` HTML mock, or the `compose-app-surface` framework code plus wiring diffs.
- **From the sidecars:** the `wireframe.txt` and `decisions.md` files written beside a mock by `compose-page`.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`** (and the asset paths in the state record): ancillary icon/image files that must ship on the same server as the page.
- **From `$CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR`:** the default root under which bundles are written; if unset, asked once.
- **From `../../lib/cds_hash.py`:** the shared fingerprint tool, to confirm the stylesheet set is current before bundling.

## Discovery checklist

1. **Resolve the target.** From the caller's pointer, find the matching state record (strict `output_path` for a mock; feature/output match for a surface). If none is found → STOP `STATE_RECORD_NOT_FOUND`.
2. **Determine the source kind** from which state directory matched — a `compose-page` mock (bundles the HTML) or a `compose-app-surface` surface (bundles the code + wiring diffs).
3. **Resolve the bundle output root** from `$CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR`, else ask once. If still unresolved → STOP `OUTPUT_PATH_UNRESOLVABLE`.

## Pipeline

1. **Load the state record** for the resolved target — it is the build spec's spine.
2. **Confirm stylesheet freshness.** Compute the live fingerprints with `python3 ../../lib/cds_hash.py inputs <$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS> ../../reference <$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR|NONE>` and compare to `manifest.json`. If stale or missing, invoke `../generate-stylesheets/SKILL.md` first so the bundle ships current CSS; if that regen halts, STOP `STYLESHEETS_REGEN_FAILED:{inner-code}`.
3. **Synthesize the build spec** from the state record — the page/surface, its ordered sections (each with shape, components, grounds, token/class contract), wiring (for a surface), and the accessibility contracts the chosen components carry. This is reference-anchored, not invented: it cites `../../reference/components.md` and `../../reference/compliance.md` rather than restating them.
4. **Copy the artifacts** into the bundle (layout below): the stylesheet set + manifest, the mock HTML or surface code + diffs, the wireframe and decision-log sidecars, the resolved ancillary assets, and the state record. If an asset path recorded in the state record cannot be resolved → STOP `ASSETS_UNRESOLVABLE` and name it.
5. **For an update (brownfield) change** (`mode == update` in the state record), add an `update` folder: a snapshot of the original files the change started from (`update_source`) plus the region-scoped change diff, so the app-repo agent applies a scoped change rather than a from-scratch rebuild.
6. **Write the bundle README** — the index plus a short "how the app-repo agent builds this" note. Emit nothing back into the source artifacts (no metadata injected into the mock, surface, or stylesheets).

## Output bundle layout

A timestamped bundle directory under the package root, shaped like this (file names shown for a `compose-page` source; a surface source replaces the design folder with code + diffs):

```
PACKAGE_ROOT/
  <change-slug>-<timestamp>/
    README.md              index + how-to-build note
    spec/
      build-spec.md        the developer-agent spec, derived from the state record
      decisions.md         copy of the compose-page decision log
      wireframe.txt        copy of the compose-page wireframe
    design/
      mock.html            the self-contained compose-page mock        (page source)
      surface/             framework code + .diff wiring files          (surface source)
    styles/
      tokens.css  components.css  themes.css  manifest.json
    assets/                ancillary icon/image files for the same server
    state/
      <state-record>.yaml
    update/                present only when mode == update
      original/            snapshot of the existing files the change started from
      change.diff          the region-scoped diff applied by the update path
```

## Halt conditions

- `STATE_RECORD_NOT_FOUND` — no state record matches the target; nothing to package.
- `OUTPUT_PATH_UNRESOLVABLE` — no bundle output directory provided and none discoverable.
- `STYLESHEETS_REGEN_FAILED:{inner-code}` — the stylesheet set was stale and the auto-invoked `generate-stylesheets` halted; the inner code is surfaced verbatim.
- `ASSETS_UNRESOLVABLE` — an ancillary asset recorded in the state record cannot be found.
- `ELEMENTS_YAML_UNSET` — `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` not set.

Halt surface format:

```
STOP: package-change: {halt-code}: {one-line summary}

Reference: {file:line or section pointer}
Detail: {one paragraph explaining what is needed to proceed}
```

## Boundary — does not

- Does not compose or iterate mocks or surfaces — `compose-page` and `compose-app-surface` own that; this skill only collects their approved output.
- Does not author stylesheet CSS — it invokes `generate-stylesheets` to refresh a stale set, nothing more.
- Does not inject any metadata into the mock, surface, or stylesheets — the build spec and the sidecars are separate files in the bundle.
- Does not build, run, or deploy anything in the app repository — it produces the hand-off bundle only.
- Does not modify `$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS` or any file under `../../reference/`.
