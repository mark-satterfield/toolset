# CDS Model Mapping (Phase 1) — Entity Dispositions under Building Blocks

Companion to `plugin-audit.md` (Phase 0). This document rules on every current entity: what it becomes under the Building Blocks model, which vocabulary collisions are resolved and how, and where each audit finding gets fixed. The Building Blocks document (`cdc-building-blocks.md`) is the vocabulary authority; the plugin source is the behavioral authority; where they conflict, Building Blocks wins on names and model, the plugin wins on proven machinery.

---

## 1. Target model

Six internal terms, exactly as Building Blocks defines them:

- **Element** — concept only; never named in configuration.
- **Component** — smallest CDS-aware unit; five contracts (slots, sizing, behavior, accessibility, token bindings).
- **Shape** — content-free slot arrangement for one Section. An abstract layout contract.
- **Section** — a themable content container. `deterministic` (layout fixed at definition) or `dynamic` (Shape assigned at build by the rule engine).
- **Section Container** — an ordered list of Sections forming a page region or a complete page. User-facing alias: **Page Type**.
- **Shell** — the outermost frame; wraps a Section Container with persistent furniture (topbar/footer for marketing, rail/panes for app).

Plus two rule kinds:

- **Shape Selection Rule** — per-Section-type: content signals → ordered eligible Shapes.
- **Page-Level Aesthetic Constraint** — post-selection validator over the accumulating page (rejection loop: candidate → validate → reject → next → exhausted → fallback).

```
Layer 4  Skills (verbs)      compose-page · compose-app-surface · generate-stylesheets ·
                             package-change · export-design · apply/audit · setup
Layer 3  Build pipeline      Shell → Section Container → per-Section resolution
                             (deterministic | dynamic → rules → constraints → fallback)
Layer 2  Building Blocks     libraries/{components,shapes,sections,section-containers,shells}
                             rules/{shape-selection,page-constraints} · aliases.md
Layer 1  Design tokens       elements YAML → roles → themes → generated stylesheets (KEPT)
```

**Fallback semantics (decision).** Building Blocks specifies: rule engine → constraint validation → if all candidates exhausted, the agent generates a fitting layout. This replaces the current halt-on-missing behavior *for Sections whose type is known*: `SHAPE_RULES_PENDING` fires only when the Section type itself is absent from plugin+extensions. A known Section type whose candidates are all rejected falls back to agent generation, and the decisions sidecar records that the layout was fallback-generated. The plugin's "no best guess" principle survives at the catalog boundary (unknown entries still halt), not at the composition boundary.

---

## 2. Library format

One `.md` file per entry. Typed YAML frontmatter + body. The same format in the plugin (`reference/libraries/`) and in project extensions.

```
reference/
  libraries/
    components/<name>.md          kind: component
    shapes/<name>.md              kind: shape
    sections/<id>-<name>.md       kind: section
    section-containers/<name>.md  kind: section-container
    shells/<name>.md              kind: shell
  rules/
    shape-selection/<section-id>.md   kind: shape-selection-rule
    page-constraints/<name>.md        kind: page-constraint
  foundations/                    (kept; dimensional re-expression pass applied)
  compliance.md                   (kept; restructured citations)
  aliases.md                      (the alias table, §4 below)
```

Frontmatter (common): `kind`, `name`, `id` (stable; T# preserved for landing Sections), `family` (landing | editorial | docs | auth | app | shared), `aliases` (user-facing names), `status` (stable | draft). Kind-specific: Sections add `mode: deterministic|dynamic`, `content_contract` (the completed content_meta fields); Shapes add `slots`, `variants`, `self_contained: true` where the scoped-style/IIFE mandate applies (audit finding 18 — preserved verbatim); Components add the five contracts; Shells add `furniture` (component refs) and `content_slot` (what Section Containers it accepts); Section Containers add `sections` (ordered Section refs with per-position notes) and `constraints` (page-constraint refs).

**Extensions.** `$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR` mirrors `libraries/` + `rules/` exactly; basename match overrides wholesale (unchanged mechanism). Catalog membership is declared by `kind` + `family` frontmatter, not by directory guessing — this dissolves audit finding 6 (an extension shape states what it extends).

**IDs.** Landing Sections keep T1–T16, T18 (T17 retires — see §5 Footer ruling). New families get prefixed IDs (E# editorial, D# docs, A# app, X# auth) so the wireframe sidecar convention (`ID · section · shape · ground`) generalizes. Retired IDs are never reused.

---

## 3. Dispositions

### 3.1 Per current entity file

| Current | Disposition | Becomes |
|---|---|---|
| `reference/shapes.md` (30 shapes) | **adopt** | One Shape file each. Strip content assumptions (§3.3); delete token-pixel prose restatements (reference tokens only — finding 17); formalize Slots/Layout/Variants/Determinations into frontmatter+body; keep self-containment mandate. |
| `reference/section-types.md` (T1–T18) | **adopt** | One Section file each (landing family, `mode: dynamic`), with the content contract completed (finding 14: add visual_type, logos_presence, step_count, demo_format, pricing_model, format). T17 retires to Shell furniture. |
| `reference/page-types.md` (6 page types) | **split 3 ways** | (a) Section Containers — the ordered content sequences, alias "Page Type"; (b) Shells — topbar/footer frame rules per family; (c) Page-Level Aesthetic Constraints — Variety Principle + alternation schedule promoted to first-class constraint entries (finding 15: scoped per Section Container, no longer trapped inside one page type). Per-page-type style rules (type scale, motion register) become `register` properties on the Section Container referencing foundations. |
| `skills/compose-page/reference/landing-sections-shape-rules.md` | **absorb** | One shape-selection rule file per landing Section. Fix the three corrupted cells (finding 3): T5 alternates normalized to shape names; T12 fragment repaired; T14 "embedded inside T10" moves to the T14 Section definition as a composition note, not a shape pick. Parts framing dropped; dead "catalog above" reference dissolves (the catalog is the sections/ library). |
| `skills/compose-app-surface/reference/app-shapes.md` | **split 4 ways** | (a) A1–A5 → Shell files (app family; naming law A6…A26→AA1 kept); (b) ~13 page shapes → Section Containers (app family) when they order multiple content regions (dashboard, quickstart, overview), Shapes (app family) when they arrange slots within one region (empty state, settings form, command palette) — ruled per entry at migration; (c) cross-context compositions → Component files (composite components, merged into the components library); (d) "Mocks vs app-embedded rendering" policy → absorbed into the shared pipeline doc (§6); the "Catalog notes" footnote allowance is **discarded** (contradicts the metadata-free boundary; sidecars carry that information). |
| `reference/components.md` (~40 components) | **adopt** | One Component file each. §12 chrome (topbar, dropdowns, drawer, sticky header, rail, switcher, account row, skip links, footer) tagged as Shell furniture. Token-vocabulary schism resolved (§5 ruling 7); duplicates merged (§5 rulings 15–17); dead self-references and broken ordering dissolve with the file split (finding 8). |
| `reference/foundations/*` + `compliance.md` | **adopt with pass** | Structure kept. Dimensional re-expression per audit §3.1 (derived values become relationships whose defaults reproduce today's rendering); the five internal contradictions (finding 20), two vw-law violations (21), duplicate easing (22), and conversion-card misfiling (23 — element widths get an `elements:` geometry group, `--container-conversion-card` renamed with a compatibility emission) fixed; implementation.md/compliance.md dead citations (19) repointed at the new structure. |
| Machinery (YAML schema, cds_hash, linter, tests) | **keep + evolve** | Schema 2.0 with mechanical migration (§7). Semantic hash, state records, env config, halt contract, test harness all survive. |
| Composer SKILLs | **rework** | Shared pipeline extracted (finding 1): discovery stages, extensions overlay, freshness/auto-regen, update path, state records, sidecars defined once in a shared pipeline reference both skills cite. Sidecars become a pipeline output for BOTH composers (finding 2 resolved: compose-app-surface emits them too). |
| Agents, commands | **rework** | cds-ui-author frontmatter/body reconciled (finding 28); cds-code-companion's unreachable halt listings removed; command determinism wording fixed to semantic keying. |

### 3.2 Nothing is discarded outright

The audit found 0 kill verdicts; every current entry's content survives somewhere. "Discard" applies only to: the Catalog-notes footnote allowance, the three corrupted rule cells (repaired, not carried), draft residue ("swaw", "varienty", "not not"), the dead §14 source-table references, and the commented-out mirror/pastel blocks (replaced by schema features, §7).

### 3.3 Content-embedded shapes (finding 17)

rate-table's LLM-pricing columns, prompt-artifact's AI pairing, install-buttons' OS list, pricing-tiers' "Individual ↔ Team", resource-grid's "Docs/Blog/Video" move from the Shape definition into `content_defaults` — declared example content in frontmatter that drafted-mode scaffolds offer and supplied content overrides. The Shape's layout contract becomes genuinely content-free; the useful defaults are values, preserved.

---

## 4. Alias table (user-facing ↔ internal)

Users and prompts keep real-world words; skills translate at the boundary. Shipped as `reference/aliases.md`, extensible per project.

| User says | Internal |
|---|---|
| page type, kind of page | Section Container |
| landing page / blog index / blog post / pricing page / docs page / sign-in page | named Section Container (+ its family's default Shell) |
| page, full page | Shell + Section Container assembled |
| nav, nav bar, top nav, menu bar | Shell furniture: topbar component |
| footer | Shell furniture: footer component |
| section, band, stripe, block | Section |
| layout, arrangement, template | Shape |
| app screen, app page | app Shell + Section Container |
| sidebar, rail | Shell pane (app Shell) |
| widget, control | Component |
| wireframe, layout map | wireframe sidecar |
| why did it choose…, reasoning | decisions sidecar |
| theme, skin, color scheme | theme (unchanged) |
| light/dark mode | color-mode (§5 ruling 8) |

---

## 5. Vocabulary rulings (the 18 collisions)

1. **shape** — One meaning: a content-free slot arrangement for one Section. The app catalog's other two senses are renamed: A1–A5 are **Shells**; "page shapes" are Section Containers or app-family Shapes per §3.1(b). Catalog membership is frontmatter (`family`), never implied by the word.
2. **section** — One meaning: the Building Blocks Section. Landing bands, in-app regions, alternation units, and theme-wrapped subtrees are all the same object viewed from different layers; the definitions merge into the Section kind. Non-landing content units (article header, featured grid, publication list) get Section definitions with E#/D# IDs — the term is never untyped again.
3. **page type / page shape** — "Page Type" survives only as the user-facing alias of Section Container. "page shape" is retired.
4. **shell** — Building Blocks Shell only. The "Application Shell" page type dissolves into the A1–A5 Shell definitions.
5. **surface** — The role sense (`--surface-*`) keeps the word exclusively. The page-classification sense is retired in favor of `family`; motion registers re-key "by family". `compose-app-surface` keeps its name as a user-facing verb (alias), described internally as the app render target.
6. **container** — The model concept is always the two-word **Section Container**. Width tokens keep their `--container-*` names (values preserved); `conversion-card` leaves the containers scale for the new `elements:` group.
7. **components token schism** — Semantic roles win. The parallel captured vocabulary (`--bg-000..400`, `--text-100..500`, `--border-200/300`, `bg-fill-field`, `shadow-field-ring`, `cds-reset`, `duration-snap`, `ease-overshoot`, raw Tailwind chains) is retired: each app-surface component is re-expressed against the semantic role set at migration, with a recorded old→new token map per component; any capture token with no semantic equivalent surfaces as a role-gap decision rather than being silently invented.
8. **mode** — Always qualified: **color-mode** (binding: light|dark; runtime: light|dark|system — the relationship declared in the schema, finding 34), **run-mode** (generate|update), **install-mode** (global|project).
9. **ground** — One definition: the surface role a Section or tile paints, `.ground--N` utilities included; the wireframe-sidecar "ground-role" and the ground/ink pairing both reference it.
10. **panels / panel-N** — The palette keeps `panels`; ad-hoc `panel-N` roles stay banned (shapes ruling preserved).
11. **cta-panel dark/light** — shapes.md wins: `cta-panel` is the Shape; darkness is a theme island. The T16 rule re-expresses as shape=cta-panel + theme directive (finding 13 closed).
12. **Footer / T17** — The footer is Shell furniture, period. T17 retires from the Section catalog; the footer-grid Shape becomes the footer component's layout spec. The alternation schedule's "excluded frame" language becomes structural truth instead of a special case (finding 16 closed).
13. **eyebrow** — One Component definition; the landing deny-by-default rule becomes a landing-family page constraint; the editorial article-header eyebrow is that Section's declared slot. One term, scoped by family.
14. **reading column** — One token ladder in layout.md is canonical; every per-page restatement (640px, 960px) becomes a token reference. Editorial's 640 = `--column-reading`.
15. **Search input vs Search field** — Renamed `search-input` and `list-filter`.
16. **Toggle switch** — One component, one token set; the §14 spec is canonical, the Setting card embeds it (size variants allowed, contradicting geometry reconciled at migration with the render proof as arbiter).
17. **Application stat card / Stat tile** — One component with a size variant; one ground role (semantic, per ruling 7).
18. **Display-1/Display-2** — Scale-qualified names: the marketing scale keeps Display-1/2; the editorial scale's entries rename to Editorial-Display-1/2 (and the editorial scale itself is re-derived under the two-anchor law during the foundations pass, finding 20).

**Preserved distinction:** iteration (from prior CDS state record) vs update (from external files) — load-bearing, unchanged.

---

## 6. Pipeline and rules

**One shared build pipeline**, defined once and cited by both composers (finding 1):

1. Resolve Shell (named, or the family default for the requested Section Container).
2. Resolve Section Container (plugin ∪ extensions; alias table applied to the user's words).
3. Per Section in order: deterministic → populate; dynamic → shape-selection rules → constraint validation (rejection loop) → apply winner, or fallback-generate on exhaustion (§1).
4. Render per target: standalone HTML (inline stylesheets, theming scripts) or framework-native code (linked stylesheets, wiring diff).
5. Emit sidecars (wireframe + decisions) for **both** targets (finding 2), write the state record.

**Render targets** (capability 2/3/5): `shell-only` (frame with placeholder content region), `container-only` (today's no-nav/no-footer case, formalized), `assembled` (default), `spa` (one Shell, N Section Containers, client-side switcher in the mock — the same mechanism as the mode toggle).

**Rules as data.** Shape-selection rule files carry the typed content contract and the decision table (pick_shape semantics preserved, thresholds preserved as values). Page-constraint files carry: the alternation schedule (generalized: per-family defaults + per-container overrides — finding 15), the Variety Principle's ~10 dimensions, the eyebrow deny-by-default rule, and future constraints. The composer executes; no rule lives in skill prose.

---

## 7. Machinery evolution

- **Schema 2.0** (mechanical migration ships with it, values-parity check in the tests): adds `dark: mirror` (replacing ~500-line commented mirror blocks — finding 27); an `elements:` geometry group (ruling 6); declared color-mode universes (finding 34); `$conventions.role` corrected to the bare emission truth (`--{role key}`), retiring the dead `--role-` pattern in both YAMLs (finding 25, enhancement #4).
- **Halt codes:** `PRECONDITION_FAILED`'s five meanings split into distinct codes; setup's two uncoded halts get codes; unreachable listings removed from cds-code-companion; `MISSING_COMPONENT` wording unified ("neither reference nor extensions"). Codes re-keyed to the new vocabulary where they name entities (e.g. `SECTION_TYPE_UNKNOWN:{id}` per §1's fallback decision).
- **Tests:** check_shape_alignment re-anchored from "Part A" parsing to the libraries tree; assemble.py chrome rewritten to bare role tokens (finding 24); the `2>/dev/null` removed (finding 30); new checks per the plan's Phase 5 (per-kind frontmatter schema, alias integrity, rule dry-runs, constraint rejection-loop cases, values parity, derivation-formula calibration against the captured pixel values).
- **Contrast bug** (finding 26): the seed's tile-ink-1/2-on-dark-grounds bindings are corrected in the seed template; the SkillSpoke YAML gets the same fix flagged in the migration notes (a value *correction*, listed explicitly, not silent).

---

## 8. Findings → work packages

A = libraries + pipeline rebuild · B = Shell composition targets · C = SPA mode · D = packaging rework · E = export-design · F = agent no-mock path · G = artwork intake · H = artwork generation. (Plan §Phase 4.)

| Findings | Fixed in |
|---|---|
| 1, 2, 5, 6, 10, 12, 13, 14, 15, 16, 17, 18 (preserved), 3 | A — shared pipeline + libraries migration |
| 4 (split), 7, 8, 9, 32 | A — components/app-shapes migration |
| 11 | dissolves with page-types split (A) |
| 19, 20, 21, 22, 23 | A — foundations pass |
| 24, 30 | A — test tooling |
| 25, 26, 27, 33, 34 | Schema 2.0 + YAML migration (A) |
| 28, 29 | A — skills/agents/commands rework (29: verify components' event-hook coverage during migration; fill or drop the promised section) |
| 31 | no action (confirmations) |
| Sidecar asymmetry (2) | A (pipeline), surfaced in D's bundle |
| Dimensional re-expression (audit §3.1, all rows) | A — intrinsic/derived classification workflow, calibrated against captured values |

Enhancement items closing with the rebuild: #1 (page-types divergent containers dissolve with the split; conversion-card refiled), #2 (residue swept in migration; prose linter extended to libraries), #3 (catalogs open by construction — closed lists gone), #4 (convention corrected), #8 (card-ground decision: rulings 7/9 make `.ground--N` the first-class shared mechanism; a dedicated card-ground role family remains available as a YAML data decision, not a plugin change), #12 (stack constraint recorded as a `compose-app-surface` framework profile, not capture leakage), #14 (the whole point), #15 (single-shape section types get alternates during catalog fill; corrupted cells repaired).
