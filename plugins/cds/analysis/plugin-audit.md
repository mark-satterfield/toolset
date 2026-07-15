# CDS Plugin Audit — conformance to the Building Blocks entity model

An audit of the cds plugin against its two normative model documents — `reference/model/entity-catalog.md` and `reference/model/data-model.mermaid` — which are the only authority on the model's vocabulary and structure. Every claim below is verifiable by the cited check.

---

## 1. The model surface

| Entity (catalog) | Where it lives in the plugin | Conforms |
|---|---|---|
| Component / ComponentLibrary | `reference/libraries/components/` (55 entries; `kind: component`) | yes |
| Shape / ShapeLibrary | `reference/libraries/shapes/` (60 entries + CONVENTIONS.md; `kind: shape`) | yes |
| Section (concrete Frame) | `reference/libraries/sections/` (39 entries; `kind: section`). A Section never contains layout: 22 entries name their Shape eagerly via `shape:`; 17 are lazy (no `shape:` key) and resolve via their ShapeSelectionRule | yes |
| Page (concrete Frame) | `reference/libraries/pages/` (9 entries; `kind: page`; ordered `sections` list + `constraints`) | yes |
| ShellDefinition / Shell | No catalog directory — by design. The plugin pre-develops and delivers no shells. A ShellDefinition exists only transiently inside `compose-shell`; its stored output (the Shell) lives in the user's `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR` | yes |
| PageFamily | `page_family:` frontmatter on every catalog entry; supplied at compose time for ad-hoc pages (stated plainly, obvious from the prompt, or the skill asks); selects the typography/motion register and scopes constraints | yes |
| ShapeSelectionRule(s) | `reference/rules/shape-selection/` (17 entries; one per lazy Section) | yes |
| PageLevelAestheticConstraint(s) | `reference/rules/page-constraints/` (3 entries; `applies_to: {page_families, pages}` scoping; rejection-loop semantics stated in FORMAT.md and pipeline.md) | yes |
| DesignToken / DesignTokenLibrary | The elements YAML (`$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS`) + `reference/foundations/` values; emitted by `generate-css` | yes |
| Outputs: CSS, Page HTML, Shell, View | `generate-css` (internal machinery) emits CSS; `compose-page` emits Page HTML; `compose-shell` emits and stores the Shell; `compose-view` emits the View (and its SPA variant) | yes |

Eager/lazy Shape assignment is the only assignment vocabulary in the plugin. The previous generation's vocabulary — the deterministic/dynamic assignment axis, the removed `arrangement` property, the retired page-container term, the shell-slot and default-shell frontmatter keys, and the shipped-shells catalog — appears nowhere.

## 2. The skill surface

Nine commands, each a thin wrapper over the same-named skill: `setup`, `compose-shell`, `compose-page`, `compose-view`, `review`, `apply-design-system`, `audit-against-system`, `export-design`, `package-change`. One internal skill, `generate-css`, carries `disable-model-invocation: true`, has no command wrapper, and is invoked only by the other skills' silent stylesheet-freshness stages.

The invisible-machinery guarantee holds by construction: every composer plus `review`, `package-change`, `export-design`, and `audit-against-system` carries the silent freshness stage (fingerprint comparison via `lib/cds_hash.py`, silent regeneration, halt only on `STYLESHEETS_REGEN_FAILED:{inner}`), and no skill, command, or agent text instructs the human to run a regeneration command.

One authoring verb — compose — covers Shells, Pages, and Views. `review` opens any generated output (Shell, Page HTML, View, isolated Section, isolated Component) in the harness built by `tools/build-review-harness.py`; the copied change request routes to the owning composer. `package-change` bundles any of the three composer outputs and excludes `.review.html`. Halt codes use the entity vocabulary (`PAGE_UNKNOWN`, `SECTION_TYPE_UNKNOWN`, `SHELL_UNKNOWN`).

## 3. Agents

`cds-ui-author` wraps exactly the eight user-facing skills, with two disciplines: studio (all UI flows through the compose skills) and app-repo direct-build (consult `apply-design-system` → build with system tokens/classes → `audit-against-system` before done). `cds-code-companion` is unchanged in role: non-UI code that binds against generated UI.

## 4. Machinery

`tools/build-review-harness.py`, `lib/cds_hash.py`, `validation/lint-elements.py`, `validation/customizable-design-elements.schema.json`, `tools/migrate-elements.py`, and `tools/check-values-parity.py` survive as-is (only prose comments naming renamed skills were updated). The `shell_component:` frontmatter key is retained: under the current model it accurately marks Components that realize a Shell's Sections, and `compose-shell` consults it.

Environment contract: `CUSTOMIZABLE_DESIGN_SYSTEM_{ELEMENTS, INSTALL_MODE, STYLESHEETS_DIR, MOCKS_DIR, SHELLS_DIR, EXTENSIONS_DIR, ASSETS_DIR, DESIGN_MD_PATH, PACKAGE_DIR}`. The two variables retired with the deleted in-app composer are not part of the contract; values present in a user's settings are ignored.

## 5. Verification record

| Check | Result |
|---|---|
| Retired-vocabulary sweep (the 12-pattern grep covering the previous generation's entity names, the deleted composer and its env vars, the renamed CSS machinery, the shipped-shells catalog path, and the invented layout terms) over the plugin | clean |
| "pane" / "chrome" as design prose (token names `--pane-*`, `--app-shell-*` excluded) | absent |
| `family:` frontmatter key | replaced by `page_family:` on every catalog and rule entry |
| Every Section resolves a Shape (eager `shape:` or a `rules/shape-selection/` entry) | yes — 22 eager, 17 lazy with matching rule files |
| Shells catalog | absent — no shells directory exists under `reference/libraries/` |
| Command and skill directory listings | exactly the approved surface (9 commands; 9 user-facing skills + generate-css) |
| Deterministic test suite (`bash test/run-tests.sh`) | exit 0 |

## 6. Test-suite retargeting record

Assertions were retargeted to the current model (catalog paths `pages/`, no shells catalog, the renamed skill directories, the current command list); no assertion was weakened. Checks whose subject no longer exists under the current model are deleted and recorded here:

- (none deleted — every check's subject survives under the current model)
