# CDS Plugin Audit (Phase 0)

This document merges the findings of seven parallel per-file source audits covering every source file in the cds plugin — composer skills and their skill-local references, support skills, agents, commands, the shared reference tree (entities and foundations), the machinery (seed YAML, hasher, schema, linter, test suite, manifest) — plus one external file, the live SkillSpoke elements YAML. Every finding comes from direct source reading of the audited files; the plugin README was treated as non-evidence throughout.

---

## 1. File verdicts

Paths are relative to the plugin root (`plugins/cds/`) except the external SkillSpoke YAML. Verdict tally: 37 keep, 9 rework, 2 split, 1 external keep, 0 kill.

### Composers

| File | Verdict | Behavior |
|---|---|---|
| `skills/compose-page/SKILL.md` | keep | The standalone-mock composer: fixed-order discovery (routing gate, iteration/update checks, page type, surface kind, content mode, stylesheet freshness), pipeline emitting one self-contained HTML file plus two sidecars and a state record. |
| `skills/compose-page/reference/landing-sections-shape-rules.md` | rework | Landing-only `pick_shape` decision table (T1–T18 × content_meta → Shape[]); content sound, structure broken (missing Parts A/B, D before C, three corrupted cells). |
| `skills/compose-app-surface/SKILL.md` | keep | The in-app composer: triggers only on explicit app-embedding signals, emits framework-native code that links (never inlines) the stylesheet set, plus a wiring diff and a state record — no sidecars. |
| `skills/compose-app-surface/reference/app-shapes.md` | split | 1472-line skill-local catalog conflating four concerns: shell layouts A1–A5, ~13 page shapes, cross-context component compositions, and skill-pipeline policy; carries frozen pixel captures. |

### Support skills

| File | Verdict | Behavior |
|---|---|---|
| `skills/generate-stylesheets/SKILL.md` | keep | Deterministically emits tokens.css + components.css + themes.css + manifest.json from the elements YAML plus the reference tree; semantic-hash fingerprints; data-driven variant emission. |
| `skills/apply-design-system/SKILL.md` | keep | Read-only vocabulary service for non-UI code authors; returns a six-section cited response (class names, tokens, event hooks, ARIA, pointers, halts); emits nothing. |
| `skills/audit-against-system/SKILL.md` | keep | THE compliance gate: audits a target against compliance.md rules filtered by caller-declared rendering context; flags undefined-in-reference patterns rather than passing them. |
| `skills/package-change/SKILL.md` | keep | Assembles an approved mock or surface into one self-describing hand-off bundle (README, spec/, design/, styles/, assets/, state/, optional update/) driven by the state record. |
| `skills/setup/SKILL.md` | keep | User-invoked-only env-var walkthrough writing CUSTOMIZABLE_DESIGN_SYSTEM_* into settings JSON; idempotent; never edits YAML content or generates anything. |

### Agents

| File | Verdict | Behavior |
|---|---|---|
| `agents/cds-ui-author.md` | rework | Sub-agent routing all UI emission through the composer skills and self-auditing before done; frontmatter and body contradict each other on tools and skill scope. |
| `agents/cds-code-companion.md` | keep | Sub-agent for non-UI code binding against generated surfaces; loads vocabulary via apply-design-system, audits UI-adjacent assertions; lists halt codes its skills can never emit. |

### Commands

| File | Verdict | Behavior |
|---|---|---|
| `commands/setup.md` | keep | Thin dispatcher for the setup skill; the only sanctioned entry point (skill is disable-model-invocation). |
| `commands/generate-stylesheets.md` | rework | Thin dispatcher parsing --full/--incremental; contradicts the skill on the determinism contract (stale "YAML bytes" wording vs the skill's semantic-content keying). |
| `commands/compose-page.md` | keep | Thin dispatcher for compose-page; restates discovery order, sidecars, extensions overlay, auto-regen, update mode. |
| `commands/compose-app-surface.md` | keep | Thin dispatcher for compose-app-surface; requires explicit app-embedding signal, otherwise routes to compose-page. |
| `commands/apply-design-system.md` | keep | Thin dispatcher; $ARGUMENTS is the one-sentence problem statement; surfaces the six-section response. |
| `commands/audit-against-system.md` | keep | Thin dispatcher; target plus --inline/--report; restates that this command IS the compliance gate. |
| `commands/package-change.md` | keep | Thin dispatcher; resolves the state record, packages the bundle, lists the five halt codes. |

### Reference: entities

| File | Verdict | Behavior |
|---|---|---|
| `reference/components.md` | rework | 1596-line component-family catalog (§12 chrome + §14 flat catalog, ~40 H2s) with strong a11y contracts; dead self-references, broken section ordering, and two competing token vocabularies. |
| `reference/page-types.md` | split | Six page types each bundling frame, content structure, and style rules; every H2 is literally "§20"; carries the Variety Principle and the alternation schedule; conflates shell/content/style per enhancement #14. |
| `reference/section-types.md` | rework | The T1–T18 landing section-type catalog plus content_meta schema and default/alternate shape mappings; schema incomplete relative to its own consumers; two mappings break the shape vocabulary. |
| `reference/shapes.md` | rework | 30 content-independent shapes with Slots/Layout/Variants/Determinations and load-bearing shape-set conventions; several shapes embed content assumptions; token pixel values frozen in prose everywhere. |

### Reference: foundations

| File | Verdict | Behavior |
|---|---|---|
| `reference/foundations/overview.md` | keep | Philosophy + seven-layer resolution architecture (palette → role → theme → mode → page type → section wrapper → element); one internal count/list contradiction. |
| `reference/foundations/layout.md` | keep | Geometry laws: two-anchor clamp interpolation, section-wrapper-vs-reading-column distinction (encodes enhancement #1), mobile_floor; minor self-violations. |
| `reference/foundations/typography.md` | rework | Three font role slots plus three type scales; the editorial scale's per-breakpoint columns contradict layout.md §11.1; auth-scale line-heights frozen as absolutes. |
| `reference/foundations/motion.md` | keep | YAML-sourced motion tokens, four entrance patterns with exact CSS templates, the non-negotiable reduced-motion gating law, per-surface motion registers. |
| `reference/foundations/imagery.md` | keep | Icon/mascot/photography/feature-tile rules; documents data-driven .feature-tile--N/.ground--N emission; one hand-picked vw clamp defect. |
| `reference/foundations/responsive.md` | keep | Five-breakpoint model; mostly a cross-reference file; introduces a tokenless 316px outer gutter and the +5% mobile line-height rule found nowhere else. |
| `reference/foundations/accessibility.md` | keep | Contrast floors, focus-ring styles, keyboard patterns, three-axis readability floor; declared focus tokens disagree with the file's own rule table. |
| `reference/foundations/implementation.md` | rework | The emission playbook (mode resolution, two-tier palette emission, theme wrappers, geometry/motion tokens, pre-paint JS); section §6 sits after §9 and cited "§6 tables" no longer exist. |
| `reference/compliance.md` | rework | Three audit layers (§21 adoption checklist, §22 implementation checklist, §23 nineteen build-blocking rules) with [scope:] tags; cites dead table structures and embeds a "Scope ambiguities" self-critique. |

### Machinery

| File | Verdict | Behavior |
|---|---|---|
| `setup/customizable-design-elements.yaml` | keep | The project-seed elements file (schema 1.1.0): $conventions, three-tier color catalog, typefaces/fonts, ~44 roles, 8 themes, geometry, motion, assets.logo; descriptions swept. |
| `lib/cds_hash.py` | keep | Single shared fingerprint implementation: semantic YAML hash (comments/descriptions excluded, key order load-bearing), reference-tree and extensions-tree hashes, `inputs` JSON. |
| `validation/customizable-design-elements.schema.json` | keep | JSON Schema 2020-12 for the elements YAML; encodes Conventions, Color/Func, Palette, Role, Theme/Alias, Geometry (incl. mobile_floor and the container invariant), Motion, Assets.logo. |
| `validation/lint-elements.py` | keep | Tier-2 property linter: schema, var-chain integrity, tier purity, alias rules, from_palette, required-role coverage, description-discipline enforcement. |
| `test/README.md` | keep | Documents the three-tier test model (structural checks, YAML lint, render proof); tier-1 check enumeration is under-inclusive as prose. |
| `test/run-tests.sh` | keep | Deterministic gate over the three tiers; a missing render proof can never pass silently; uses one `2>/dev/null`. |
| `test/assemble.py` | rework | Render-proof gallery viewer; its chrome stylesheet consumes retired `--role-*` variables that never resolve, so the gallery chrome permanently paints hardcoded fallbacks instead of theme-following. |
| `test/check-plugin.py` | keep | Tier-1 runner: dynamic discovery of checks/check_*.py, dotted-leader PASS/FAIL, exit 1 on any failure. |
| `test/checks/check_schema.py` | keep | Validates the schema document itself (Draft 2020-12 check_schema, $schema/$id identity). |
| `test/checks/check_structure.py` | keep | Plugin structural contract: manifests, command/skill frontmatter, skill-path resolution, marketplace entry. |
| `test/checks/check_links.py` | keep | Dead-link scan over all plugin markdown, deliberately loose base resolution to avoid false positives. |
| `test/checks/check_consistency.py` | keep | Halt-code propagation (command Notes ⊆ skill Halt conditions) and env-var near-duplicate detection. |
| `test/checks/check_reference.py` | keep | Reference-tree integrity vs the live YAML: shape headers, component headers, `--role-` prefix ban, from_palette existence, scope-tag vocabulary. |
| `test/checks/check_reference_prose.py` | keep | "Reference is source, not a PM board" guard: fails PM headings and deferral/history lexicon in reference trees; operationalizes enhancement #15's rule. |
| `test/checks/check_semantic_hash.py` | keep | Verifies the semantic hash's invariance (prose-only edits) and sensitivity (value edits) with synthetic YAML. |
| `test/checks/check_shape_alignment.py` | keep | Shape-name integrity: bans retired S# indices, checks fragment basenames and data-shape attributes against the shapes.md Part A catalog. |
| `test/checks/check_token_coverage.py` | keep | Closed-token-graph check: every var(--token) in generated components.css must be defined somewhere in the generated set. |
| `test/checks/check_topbar_nav.py` | keep | Enforces the §12.1 right-aligned nav cluster on the rendered landing sample (a recurring compose regression). |
| `test/checks/check_nav_dropdown.py` | keep | ARIA-correctness guard for nav dropdowns (aria-haspopup ⇒ aria-expanded + role=menu panel) on the rendered landing sample. |
| `.claude-plugin/plugin.json` | keep | Plugin manifest: name cds, version 0.3.1, non-empty description. |

### External

| File | Verdict | Behavior |
|---|---|---|
| `/Users/msat1971/projects/SkillSpoke/app/SkillSpoke/.customizable-design-elements.yaml` (external) | keep | Live SkillSpoke selections (schema 1.0.0): colors, typefaces, font bindings, 43 roles, 8 themes only — no geometry or motion; ~30% of the file is commented-out mirror dark-mode blocks. |

### 1.1 Behavior notes

Details a rebuild must know, beyond the one-line distillations:

**`compose-page/SKILL.md`.** Discovery is a fixed-order checklist: (1) routing gate STOPping `WRONG_SKILL:compose-app-surface` on app-embedding language; (2) state-record lookup at the resolved output path for iteration plus a distinct brownfield UPDATE-path check; (3–7) page type (ask, don't infer), surface kind, content mode, assets, mandatory/forbidden elements; (8) stylesheet freshness via cds_hash.py semantic fingerprints, auto-invoking generate-stylesheets on mismatch (never halting for staleness). The pipeline builds the working catalog as plugin reference ∪ extensions dir (project entry overrides plugin wholesale by name), derives section sequence and per-section shape via the skill-local pick_shape rules with the Variety Principle deferred to page-types.md §20, renders one self-contained HTML file, and on UPDATE parses the existing artifact into a region map, recomposes only localized regions, and splices them back byte-for-byte-preserving. It emits two sidecars (wireframe.txt, decisions.md) keeping the HTML metadata-free, and writes a YAML state record (mode generate|update, update_source, per-section preserved, sidecar paths; last 10 retained) that package-change consumes. Step 4 prose embeds several defect-born hard rules: topbar layout per §12.1, nav dropdowns per §12.2, never re-declare geometry tokens in page blocks, section wrapper width ≥ page width, entrance motion never wrapped in `prefers-reduced-motion: no-preference`, logo asset-pair mode.

**`compose-app-surface/SKILL.md`.** Mirrors compose-page's extensions overlay, freshness step, update mechanics, and state-record schema near-verbatim (see finding 1), resolves shell + page shape against skill-local app-shapes.md, requires `$CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK` (STOP `FRAMEWORK_UNSET`), emits framework-native code that links the stylesheet set, and generates a wiring diff citing the reference — never inspected host code. It emits NO wireframe/decisions sidecars — an asymmetry with compose-page. Its pipeline has a numbering defect: the Update-path block sits unnumbered between steps 5 and 6. Compliance gate is [scope: app-embedded]+[scope: both] with explicit negative checks (no theme controllers, mode resolvers, inlined CSS, route bootstrapping, agent metadata).

**`landing-sections-shape-rules.md`.** Declares the typed `pick_shape(section_type, content_meta, page_meta) -> Shape[]` signature and the Part C decision table. Structure is broken: Part D precedes Part C; "the catalog above" (missing Parts A/B) is a dead reference to content that moved to the shared section-types.md/shapes.md; three cells are corrupted (T5 alternates as prose, T12 trailing fragment, T14 primary "embedded inside T10" — an instruction, not a shape name).

**`app-shapes.md`.** Conflates (1) shell layouts A1–A5 with pane tokens, HTML skeletons, and collapse ladders; (2) ~13 descriptively-named page shapes; (3) cross-context component compositions that are components.md territory; (4) a "Mocks vs app-embedded rendering" policy section that is skill-pipeline policy, whose "Catalog notes" allowance (mocks may carry a footnote naming catalog entries) tensions with compose-page's metadata-free-HTML boundary. It declares its catalog disjoint from shapes.md and defines the extension naming law A6…A26 → AA1. The quickstart page shape and the field-group composition are frozen pixel captures of specific reference products (~1347px viewport stated outright; 711×762 panel; 208×72 field cells; 9.6px radius; raw Tailwind utility chains; 0.5px borders) contradicting the file's own claim that measurements "resolve against the foundations"; the field-group entry mixes two token vocabularies; one example row leaks project data ("Narrowing job seeker ICP for lean startup", line 788).

**`generate-stylesheets/SKILL.md`.** Colors/fonts come from the YAML; geometry and motion come from the reference with optional per-key YAML override blocks; the only foundation-fixed tokens are typography weight/line-height/tracking. components.css emits one class per family, data-driven feature-tile/ground variants (no hardcoded count), layout utilities, logo asset-pair CSS only when configured, and entrance keyframes animated in the base rule and disabled only under `prefers-reduced-motion: reduce`. manifest.json records three cds_hash.py fingerprints plus per-file SHAs and plugin version. Incremental mode skips writes when input SHAs match.

**`package-change/SKILL.md`.** Resolves the target's state record (strict output_path match for mocks; feature/output match for surfaces), confirms stylesheet freshness (auto-regen, `STYLESHEETS_REGEN_FAILED:{inner}` on failure), and writes `<change-slug>-<timestamp>/`: README index; spec/ (derived build-spec.md that cites rather than restates the reference, plus the two sidecars); design/ (mock.html or surface/ code + .diff wiring); styles/ (the four-file set); assets/; state/; and update/ (original snapshot + change.diff) only when mode == update. Generates nothing new about the design.

**`cds-ui-author.md`.** Frontmatter declares tools Read/Glob/Grep/WebFetch and skills compose-page, compose-app-surface, audit-against-system, package-change; the body's "Tool / skill scope" says tools are Read/Glob/Grep only and skills are only the three composition/audit skills; the description also never mentions package-change. Either frontmatter or body is stale.

**`components.md`.** The §14 intro claims "The 32 H2s below" carry row data from a source table — the table does not exist and ~40 §14 H2s exist; §14.1 points to "the component table at the top of §14", likewise absent. §12.5.1 (Workspace switcher) and §12.5.2 (Account row) physically sit at lines 1453–1584, after all §14 content. Marketing/editorial components bind semantic role vars (--surface-primary, --text-tertiary) while app-surface components are raw Tailwind class captures with a parallel undefined token set (--bg-300, --text-500, bg-fill-field, shadow-field-ring, cds-reset, duration-snap…). The Toggle switch spec (§14/§14.3: ~32×18–36×20 track, --switch-active-bg) contradicts the Setting card's embedded switch (43×24 track, --switch-track/--fill-accent). Application stat card (--surface-raised) and Stat tile (--bg-300) are near-duplicate components naming the same ground differently.

**`page-types.md`.** All six H2 headings are literally "§20". The Primary Landing entry carries the Variety Principle, the deterministic surface-primary/secondary alternation schedule (which shapes.md hard-depends on), and a Section-sequence table duplicating the entire T1–T18 catalog verbatim. Every "Required Structure" list mixes frame elements (topbar, footer) with content sections while the alternation rule declares the topbar "not a section" and excludes the footer — the frame/content boundary is asserted in one paragraph and erased in every structure list. Draft residue survives: "swaw", "varienty" (line 38), "not not all sections" (line 51).

**`section-types.md`.** Holds "Part B — Catalog" whose Part A lives in shapes.md — leftovers of one split document. Six section types consult signals (T1 visual type, T3 logos-presence, T5 step count, T8 demo format, T9 pricing model, T14 format) that are not fields of its own content_meta schema. T16 maps to "cta-panel dark"/"cta-panel light", directly contradicting shapes.md:314 where dark is a named theme island and explicitly not a shape variant.

**`shapes.md`.** Declares no shape sets its own theme or ground — every shape takes the scheduled ground from the alternation schedule that lives only inside page-types.md's Primary Landing entry. Determinations restate token pixel values in prose everywhere (--sp-4 "(52–64px clamp)", --column-medium "(960px)"), so a YAML override silently invalidates the prose. Despite the "independent of content" claim, rate-table hardcodes the Input/Output/Cache-write/Cache-read column set (LLM-API pricing), prompt-artifact assumes an AI product, install-buttons names OS platforms, pricing-tiers names "Individual ↔ Team", resource-grid names "Docs/Blog/Video". The self-containment mandate (scoped `<style>` + IIFE `<script>` per interactive shape, lines 188/468) is load-bearing and must survive any restructure.

**`typography.md`.** The editorial scale's Mobile/Tablet/Desktop columns structurally contradict layout.md §11.1's two-anchor interpolation law ("do not author per-breakpoint values for type") — the marketing scale complies, the editorial scale does not. The authentication scale freezes size×ratio products as absolutes (67.2px = 56×1.2, 19.6px = 14×1.4). Display-1/Display-2 names exist in both the marketing and editorial scales with different families and mechanics.

**`implementation.md` / `compliance.md`.** implementation.md's §6 (theme contracts) sits after §9 at the end of the file, while compliance.md §21/§22 and §8.2 cite "the §6 tables" and "the overview.md §4 tables" — neither location contains tables anymore (values moved to the YAML), so the generation instructions point at dead structures. compliance.md ends with a "Scope ambiguities" self-critique — editorial commentary embedded in a normative reference, the exact pattern enhancement #15 prohibits.

**`setup/customizable-design-elements.yaml` (seed).** Themes that don't flip on mode carry a fully commented-out dark block as a template — roughly a third of the 1770-line file, invisible to the semantic hash but an exact duplicate of the light bindings that will drift silently. The panels palette keeps a commented-out pastel alternative block; its live keys are positional letters a–g. `containers.conversion-card: 448px` is an element width filed in a scale whose own comment says a container is never below page width. Likely inherited contrast bug: light modes of clarity/default/punctuation/statement bind tile-ink-1/2 to near-black ink over tile-ground-1/2 = stronger-indigo/slate (dark grounds) — leftovers from when panels were pastels; no committed check can catch this (contrast is left to the render-proof eyeball).

**`lib/cds_hash.py`.** The semantic hash serializes with `sort_keys=False` — key order is deliberately load-bearing because the generator emits tokens in YAML order; reorderings and value edits change the hash, comment/description edits do not. "No extensions" hashes as the stable empty-string SHA so absence is deterministic.

**`assemble.py`.** The chrome stylesheet (lines 135–154) references `var(--role-surface-primary)` etc. — but roles are emitted bare per $conventions and check_reference bans `--role-` tokens in generated CSS, so these vars never resolve and the gallery chrome permanently paints its hardcoded fallbacks (#fff/#111/…) instead of re-skinning with the selected theme. The reference-tree guard deliberately does not scan test tooling, so this dead vocabulary survives.

---

## 2. Term registry and collisions

### 2.1 Collisions

**shape** — In `shapes.md:3` a shape is a content-independent spatial composition pattern for one landing-page section (30-entry Part A catalog). In `app-shapes.md` "shape" spans two more things: letter-coded shell layouts (A1–A5) and descriptively-named page shapes that fill a shell's main pane, with the catalog declared "non-interchangeable" with shapes.md (app-shapes.md:3). The word therefore spans two disjoint catalogs — and the single extensions `shapes/` dir serves both with no declared mechanism for an extension shape to state which catalog it belongs to (compose-page/SKILL.md:40-41; compose-app-surface/SKILL.md:41). Additionally, several shapes.md entries violate the file's own content-independence claim (rate-table, prompt-artifact, install-buttons, pricing-tiers, resource-grid).

**section** — Four live meanings plus a proposed fifth. (a) A landing-page vertical band typed T1–T18 (section-types.md:3; landing-sections-shape-rules.md:45-84). (b) In compose-app-surface, a region inside an existing in-app page — same word, different container model (compose-app-surface/SKILL.md:30). (c) In page-types.md:42, a full-width unit counted by the alternation index — the topbar is explicitly "not a section" and the footer is excluded, yet every Required Structure list numbers topbar and footer alongside content sections. (d) In the project YAML, the DOM subtree a theme wraps (`<section class="default">`, yaml:841-843). (e) Enhancement #14 proposes a Section that is themable and inherits a Shape — matching none of the above exactly. Non-landing content units (article header, featured grid, publication list) are called "sections" with no T-number, leaving the term untyped outside landing pages.

**page type vs page shape** — page-types.md:3 defines six page-level presets that in practice prescribe frame (topbar/footer), content structure, and style rules together. app-shapes.md:284-287 defines "page shape" as what fills a shell's main pane — a different axis sharing the word "page". overview.md:46 uses "page type" as a surface classification (marketing/editorial/legal/auth/app shell). Enhancement #14 proposes "Page Type" alias "Section Container" (content only) — the current page types include the shell too.

**shell** — app-shapes.md:5-7 defines shell layouts A1–A5 as whole-viewport partitionings for authenticated app screens. apply-design-system/SKILL.md:33 and page-types.md use "shell"/"Application Shell" as a page-type/rendering context. Enhancement #14 proposes a user-predefined Shell as the reusable wrapper (nav + content container + footer) for multiple pages — nothing in the plugin models that; the two existing senses cover only the app side.

**surface** — (a) A paintable ground role (--surface-primary/secondary/tertiary/raised/muted; overview.md:181, yaml:459-500). (b) A whole page classification ("marketing surface", motion register "by surface"; motion.md:53-61). (c) The compose-app-surface artifact kind — a new in-app page/section/component (commands/compose-app-surface.md:2; package-change). The role-slot sense and the page-classification sense coexist across the foundations with no disambiguating qualifier.

**container** — (a) A geometry width token (--container-{key}) whose invariant is "≥ the page width, never below it" (layout.md:27-38; yaml:1656-1659). (b) `--container-conversion-card` = 448px, an element width carrying the container- prefix while layout.md:48 insists it is not a container — a self-contradiction the schema descriptions repeat. (c) Enhancement #14's "Container" is a containment concept (Sections, Section Containers, Shells contain things), which will collide with the width-token sense in any rebuild.

**section wrapper** — overview.md:47 defines it by theme and rhythm (the block carrying a theme class); layout.md:27-38 defines it by width law (max-width ≥ page width, never a reading column). Same term, two axes of the same object, defined in two files.

**mode** — Four senses. (a) A theme's light/dark binding block, schema-restricted to light|dark (yaml:848-858; schema.json:570-593). (b) The runtime data-mode UI universe light|dark|system discovered by assemble.py (assemble.py:76-89) — two different "mode" universes. (c) State-record mode generate|update (package-change/SKILL.md:14). (d) Install mode global|project (setup/SKILL.md:29-32).

**ground** — (a) The ground/ink pairing vocabulary throughout components.md (a surface role + the ink painted on it, components.md:168-179). (b) The `.ground--<suffix>` shape-agnostic class emitted per tile-ground role (generate-stylesheets/SKILL.md:41). (c) The "ground-role" recorded per section in the wireframe sidecar = the alternation-schedule assignment (compose-page/SKILL.md:51-52). Related but not identical objects sharing one word.

**panels / panel-N** — In the YAML, `panels` is the Tier-2 semantic palette of saturated tile grounds keyed a–g (yaml:263-289). Enhancement #8 uses "panel-N" for the ad-hoc composer-minted card roles the item complains about — a different thing; shapes.md:112 now explicitly bans "ad-hoc panel-N roles".

**cta-panel dark/light** — section-types.md T16 names them as shape picks (section-types.md:203-209); shapes.md:314 rules that a dark CTA band "is a named theme island … not a shape variant". A direct cross-file contradiction in the shape vocabulary.

**Footer / T17** — Simultaneously a landing content section type (T17, always footer-grid, section-types.md:213-219) and a frame element excluded from the alternation schedule that carries a per-page theme island (page-types.md:42,47). The double identity is the single clearest symptom of the missing Shell concept from enhancement #14.

**eyebrow** — shapes.md:471 makes eyebrows deny-by-default at section level, authorized only in heading-strip and per-card tags. page-types.md:160,195 requires a "subjects (eyebrow)" line in the editorial article header — a non-landing eyebrow the shapes rule does not govern; the term is double-scoped.

**reading column** — 640px in the Editorial and Documentation page types (page-types.md:164,351) vs --column-medium (960px) in four shapes (shapes.md:97,217,244,259) — two canonical widths for the same concept across two files with no stated relationship. layout.md:40-47 holds the actual token ladder (1192/960/640).

**Search input vs Search field** — Two distinct components with near-identical names: general-purpose `<input type=search>` (components.md:558-570) vs the in-list filter with wrapper-owned chrome (components.md:1033-1076). The file explicitly distinguishes them; the names invite confusion.

**Toggle switch** — Two incompatible specs in one file: §14/§14.3 (~32×18–36×20 track, --switch-active-bg/--surface-tertiary/--surface-raised, components.md:661-673, 898-922) vs the Setting card's embedded switch (43×24 track, 20px thumb, --switch-track/--fill-accent/--switch-knob, components.md:1402).

**Application stat card vs Stat tile** — Stat tile calls itself "a smaller variant of the application stat card" yet is a separate H2 with its own props and near-duplicate dimension blocks; they name the same ground differently (--surface-raised vs --bg-300) (components.md:465-487 vs 926-976).

**Display-1 / Display-2** — Exist in both the marketing scale (Serif, two-anchor clamp) and the editorial scale (Sans, three breakpoints) with different families and mechanics (typography.md:94-142).

**§14 source table** — components.md:284 and :833 reference a one-row-per-component table that the "32 H2s below" supposedly carry as row data; the table does not exist and ~40 H2s do — a dead self-reference, and the count is stale.

**iteration vs update** — Not a collision but a deliberate, load-bearing distinction the rebuild must preserve: iteration starts from a prior CDS state record at the same output_path; update (brownfield) starts from external files (repo/Figma) (compose-page/SKILL.md:29-30).

### 2.2 Full registry

| Term | Meaning | Locations |
|---|---|---|
| mock | Self-contained standalone HTML file (stylesheets inlined, theming scripts, no metadata); not production code | compose-page/SKILL.md:3,9; package-change/SKILL.md:16 |
| mock harness | Wrapper turning an app-embedded surface into a reviewable standalone mock | app-shapes.md:1140 |
| page type | Named page classification with composition/audit rules (six in page-types.md; surface classification in overview.md) | page-types.md:3; overview.md:46; audit-against-system/SKILL.md:26 |
| page shape | Descriptively-named composition filling a shell's main pane; reusable across shells | app-shapes.md:284-287 |
| surface kind | compose-page: page / section / component; compose-app-surface: page route / in-app section / shell component | compose-page/SKILL.md:32; compose-app-surface/SKILL.md:30 |
| section | See collision entry — landing band / in-app region / alternation unit / theme-wrapped subtree | section-types.md:3; page-types.md:42; yaml:841-843 |
| section type | T#-coded catalog entry a landing section instantiates; primary key of pick_shape | section-types.md:3; landing-sections-shape-rules.md:16,43 |
| shape | Named layout template for a section's slots (landing) / shell + page-shape (app) — see collision | shapes.md:3; app-shapes.md:3; compose-page/SKILL.md:41 |
| pick_shape | Deterministic (section_type, content_meta, page_meta) → ordered Shape[] decision table | landing-sections-shape-rules.md:9-43 |
| content_meta | Typed 10-field per-section signal record disambiguating shape choice | landing-sections-shape-rules.md:18-29; section-types.md:30-49 |
| page_meta | Page-level shape-selection signals: buying_mode (commit\|browse), position_in_page (top\|mid\|late) | landing-sections-shape-rules.md:31-34 |
| buying_mode | commit\|browse posture; browse-mode pages omit T16 entirely | landing-sections-shape-rules.md:32,82 |
| content mode | Drafted (skill generates fill-in scaffold) vs supplied (caller provides content) | compose-page/SKILL.md:33; compose-app-surface/SKILL.md:28 |
| iteration | Modifying a prior CDS artifact starting from its state record | compose-page/SKILL.md:29; compose-app-surface/SKILL.md:26 |
| UPDATE path (brownfield) | Starting from existing external artifacts: region map → localized recompose → splice/diff, rest byte-for-byte intact | compose-page/SKILL.md:30,44; compose-app-surface/SKILL.md:27,45 |
| state record | Per-run YAML ({timestamp}-{basename}.yaml) in the install-mode-resolved state dir: brief_snapshot, sections, sidecar paths, mode, update_source, preserved flags; last 10 kept | compose-page/SKILL.md:57; package-change/SKILL.md:14 |
| sidecar | `<basename>.wireframe.txt` (ASCII layout map) + `<basename>.decisions.md` (derivation log), never inlined into the HTML; compose-page only | compose-page/SKILL.md:50-54; package-change/SKILL.md:17 |
| bundle | Timestamped hand-off dir from package-change: README + spec/ + design/ + styles/ + assets/ + state/ + optional update/ | package-change/SKILL.md:37-60 |
| build spec | spec/build-spec.md synthesized from the state record, reference-anchored (cites rather than restates) | package-change/SKILL.md:32 |
| wiring diff | Unified diff making a new surface reachable (nav/route/parent), citing the reference, never inspected host code | compose-app-surface/SKILL.md:44 |
| extensions dir | $CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR with shapes/, page-types/, section-types/ *.md; matching basename overrides plugin entry wholesale | compose-page/SKILL.md:21,40-41; generate-stylesheets/SKILL.md:17 |
| stylesheet set | tokens.css + components.css + themes.css + manifest.json; mocks inline it, app surfaces link it | generate-stylesheets/SKILL.md:9; compose-page/SKILL.md:15,45 |
| manifest.json | Freshness/provenance: generated_at, three input fingerprints, per-file SHAs, plugin version | generate-stylesheets/SKILL.md:44-67 |
| semantic hash | SHA-256 of the YAML's meaning — comments/descriptions excluded, key order included (load-bearing) | lib/cds_hash.py:14-21,75-87; generate-stylesheets/SKILL.md:63 |
| reference tree / extensions tree | The plugin's reference/ dir and a project's extensions dir, each tree-hashed; no-extensions = empty-string SHA sentinel | lib/cds_hash.py:23-37; generate-stylesheets/SKILL.md:15,17 |
| determinism contract | Same inputs → byte-identical CSS; keyed on (YAML semantic content, reference tree bytes) — command wording is stale ("bytes") | generate-stylesheets/SKILL.md:88; commands/generate-stylesheets.md:21 |
| elements YAML | User-owned design config at $CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS: palette, typefaces, roles, $conventions, themes, geometry/motion overrides, assets | generate-stylesheets/SKILL.md:14 |
| $conventions | Machine-readable naming patterns turning YAML paths into CSS var names — single source of truth for token naming | yaml:15-30; schema.json:54-150 |
| token | A CSS custom property in tokens.css; families: colors, typefaces/fonts, geometry, motion, foundation-fixed typography | generate-stylesheets/SKILL.md:34-40 |
| role / role variable | Semantic binding a theme fills and components consume via var(); emitted BARE (--surface-primary) per role_var_pattern | overview.md:43,177-183; compliance.md:94; yaml:452-838 |
| scope (semantic\|component) | Role attribute: any component may consume vs tied to one component | schema.json:455-459 |
| family | Role grouping (surface, text, border, accent, nav, footer, hero, button, tile, state, status…) | schema.json:481-483 |
| from_palette | Constraint restricting which palette a theme may bind a role to; linter-enforced | schema.json:489-496; lint-elements.py:158-174; compliance.md:34 |
| palette / swatch | Flat dictionary of named colors; one named entry; components may never name one | overview.md:42,128,183 |
| primitive palette | Tier-1 raw hex, named for what the color IS; Ramp or Discrete | yaml:32-43; overview via implementation.md:35-68 |
| semantic palette | Tier-2 usage-named palette of { var: } aliases to primitives; holds no hex | yaml:243-407 |
| Ramp / Discrete | Ordered 000–1000 stepwise progression / unordered named set | yaml:66-241; schema.json:247-290 |
| common_colors | Foundational colors outside any palette (white, black) | yaml:46-55 |
| Func | Exactly-one-property CSS function object (var, calc, color-mix…) | schema.json:215-236 |
| ramp | 21-step progression white→black with stable step names; contrast progression is load-bearing | overview.md:131-134 |
| accent family | One hue family in four slots: primary, interactive, hover, dark-mode | overview.md:137-145 |
| panel ground | Saturated swatch reserved for feature blocks/tiles/badges — never body type or default surfaces | overview.md:147-149 |
| state swatch | Component-scoped colors (error-*, required, focus-blue); deliberately no success-green/warning-yellow | overview.md:152-161 |
| selection tint | Global ::selection via selection-bg (50% accent mix); a system signature | overview.md:163-173; yaml:586-589 |
| theme | Named wrapper class binding every role slot to a swatch per mode; self-contained | overview.md:44; implementation.md:303-307; yaml:839-1610 |
| alias theme | { alias: target }, no bindings; selector grafted onto every target rule; never chains | implementation.md:160-178; lint-elements.py:141-156 |
| named theme island | Per-section theme override (Pricing→clarity, Footer→deep, dark Final CTA) declared in page-type notes | page-types.md:36,47; shapes.md:467 |
| interjection | Theme used as a contrast band in a light page's scroll rhythm | SkillSpoke yaml:1069-1073,1284-1288 |
| scroll rhythm | Vertical alternation ordering of themes down a page | SkillSpoke yaml:1073 |
| mode | See collision — binding mode / UI mode / state-record mode / install mode | yaml:848-858; assemble.py:76-89; package-change/SKILL.md:14; setup/SKILL.md:29-32 |
| mode marker | data-mode on the document root (or local wrapper), set pre-paint by inline script | implementation.md:5,251-263 |
| binding | One (theme, mode, role) → ColorValue assignment | yaml:866-1610; schema.json:539-559 |
| compatibility alias | Optional brand-named legacy tokens (--p-burnt-orange → …); not part of the contract | overview.md:102; implementation.md:71-93 |
| configurable element set | YAML-defined token family (geometry:, motion:) emitted as global tokens, not theme-bound | overview.md:52-53; layout.md:3; motion.md:3 |
| geometry token | --sp-*, --radius-*, --section-pad-*, --container-*, --column-*, --{component}-{property} | overview.md:53; implementation.md:221-239 |
| geometry component | Per-component sizing block; the system, not the page, owns component dimensions | yaml:1673-1687; schema.json:668-675 |
| motion token | --ease-*, --duration-*, --{pattern}-* | motion.md:3-18 |
| entrance pattern | reveal/.reveal-word, card/.card-stagger, fade/.content-fade, fade-up/.content-fade-up — emitted keyframes + classes | motion.md:8-18,63-125; yaml:1689-1753 |
| gating law | Entrance motion animates in the base rule, disabled ONLY under prefers-reduced-motion: reduce | motion.md:19; compliance.md:80 |
| motion register | Per-surface motion intensity budget, liveliest (landing) to near-zero (docs) | motion.md:53-61 |
| mobile_floor | Per-token minimum emitted as :root re-declaration inside @media (max-width) | layout.md:74-87; schema.json:641-651 |
| viewport anchors | The 320px/1440px interpolation endpoints for every responsive clamp | layout.md:9-21 |
| breakpoint | Five discrete ranges (<480, 480–700, 700–1024, 1024–1440, >1440) governing layout behavior only | responsive.md:5-11 |
| inner reading column | --column-{key} (1192/960/640) capping a single content block inside a page-width section | layout.md:28,40-47 |
| element width | Fixed width of an individual component (448px conversion card) — not a container | layout.md:48 |
| layout utility | .u-container (page-width wrapper), .u-container-full (full-bleed), .u-reading (inner column) | generate-stylesheets/SKILL.md:41; page-types.md:23 |
| register (left/centered) | Section-wide heading-alignment mode; sub-headings inherit, never fight it | shapes.md:472 |
| affordance | Embedded interactive element (chat input, snippet, chips); exactly one per centered-affordance | shapes.md:87-98 |
| Determinations | Per-entry definitive measurements/behaviors beyond static layout | shapes.md:5,51; app-shapes.md:320-323 |
| slot | Named content position within a shape | shapes.md:47 |
| self-contained shape fragment | Interactive shapes carry their own scoped `<style>` + IIFE `<script>` implementing the ARIA contract | shapes.md:188,468 |
| alternation index | 1-based position among content sections assigning surface-primary (odd) / surface-secondary (even) | page-types.md:42-47 |
| Variety Principle | No two adjacent landing sections may look alike across ~10 dimensions — never varying theme or background | page-types.md:13-38; compose-page/SKILL.md:17,41 |
| ground / ink | Pairing vocabulary: ground = surface/background role, ink = text/glyph color painted on it | components.md:168-179,624-639 |
| tile-ground-N / tile-ink-N | Numbered feature-tile role pairs; open number space; variant classes emitted per declared pair | yaml:745-810; components.md:459; imagery.md:41-56 |
| feature tile | 16:9/1:1 tinted tile hosting a centered currentColor SVG; .feature-tile--N + .ground--N per role | imagery.md:29-56; generate-stylesheets/SKILL.md:41 |
| ground (.ground--N) | Shape-agnostic background/ink pairing any card-grid may opt into; shares tile declarations | generate-stylesheets/SKILL.md:41; shapes.md:107,112 |
| mascot | Brand's decorative animated illustration bound through --accent-heroes via currentColor; max one per page | imagery.md:15; motion.md:147 |
| logo mode (currentColor / asset-pair) | Default single recoloring glyph vs declared light/dark image pair swapped in CSS by mode — the one supported exception | generate-stylesheets/SKILL.md:41; implementation.md:23; compliance.md:76; yaml:1755-1769 |
| code theme (fixed-dark) | The one sanctioned theme-system escape: code blocks stay dark in both modes with fixed hex | components.md:649; implementation.md:25; compliance.md:71,90 |
| button slot family | --button-{primary\|secondary\|brand}-bg/text + tertiary border; binding is mode-driven | implementation.md:317; overview.md:181 |
| weight oscillation | Button label weight flips 480↔500 across modes to compensate perceptual weight | implementation.md:331-343 |
| focus ring | Three :focus-visible styles: default 2px --focus-ring offset 1px; inset -2px; chromatic --input-focus-ring | accessibility.md:12-28; implementation.md:313 |
| three-axis floor | Readable text satisfies color (AA), weight (≥600 below 14px), size (≥12px/13px) simultaneously | accessibility.md:45-52 |
| type family role | --font-sans / --font-serif / --font-mono with fallback stacks; typefaces project-supplied | typography.md:5-21 |
| type scale | Marketing (clamp), editorial (three-breakpoint), authentication-card ladders | typography.md:94-162 |
| typeface / font | Physical family record vs usage-named binding aliasing a typeface + fallback stack | SkillSpoke yaml:404-443 |
| drift rule | Change values only in the YAML and regenerate; never edit the emitted CSS | implementation.md:102,180,245 |
| scope tag | [scope: both\|standalone\|app-embedded] on every compliance item | compliance.md:5-80; check_reference.py |
| compliance gate | The completion check rooted in compliance.md; audit-against-system IS the gate and has none of its own | audit-against-system/SKILL.md:55 |
| rendering context | app-embedded vs standalone — caller-declared, never inferred from host code | audit-against-system/SKILL.md:24; apply-design-system/SKILL.md:24 |
| undefined-in-reference | Audit finding class for patterns the reference does not define — a finding, not a pass | audit-against-system/SKILL.md:35 |
| UI category | apply-design-system classification selecting reference files (navigation, shell, modal, form…) | apply-design-system/SKILL.md:25 |
| halt code / STOP | Uniform failure surface "STOP: {skill}: {code}: {summary}"; agents propagate verbatim | generate-stylesheets/SKILL.md:77-84; check_consistency.py:9-16 |
| install mode | global vs project — decides settings/YAML/state locations | setup/SKILL.md:29-32 |
| shell layout | Letter-coded A1–A5 whole-viewport partitioning; extension naming law A6…A26 → AA1 | app-shapes.md:5-7,14-281,1471 |
| rail / mini-rail / list-column / detail-viewport / info-panel / bottom-strip / form-sidebar / canvas-or-gallery | Named shell panes: 256px rail, 56px icon rail, 280px list, fluid detail, 320px info, 64px strip, 320px sidebar, fluid gallery | app-shapes.md:22-30,74-78,120-122,158-162,227-231 |
| cross-context component composition | Multi-component arrangement that is not a full page shape (modal-with-form, checkbox tree, field-group rows, destructive zone…) | app-shapes.md:1144-1461 |
| destructive zone | Divider-delimited (hairline, no card chrome) section hosting one Destructive button; confirm modal on click | app-shapes.md:1335-1366 |
| Topbar / primary-nav / conversion-cta | Fixed banner header; logo left, nav + 1–2 conversion actions right; blends via --nav-bg | components.md:7-38 |
| Dropdown panels | Flat (200px) / Mega (656–864px) / Lift-and-scale (256px) role=menu panels below topbar triggers | components.md:41-76 |
| Mobile drawer | Full-viewport dialog the topbar collapses into; clip-path wipe, staggered items, focus trap | components.md:79-110 |
| Sticky header | Editorial header hiding on downward scroll; suppressed while focused | components.md:114-147 |
| App shell left rail | Fixed 256px nav column: workspace-switcher, section headers, 36px item rows | components.md:151-197 |
| Workspace switcher / Account row | Rail-top combobox control (232×32 / 32×32) and bottom-of-rail identity button | components.md:1453-1584 |
| Skip links / Footer (component) | Off-screen anchors z-index 101; multi-column contentinfo with editorial/marketing/auth ground variants | components.md:201-247,251-278 |
| Button base (§14.1) | Shared contract: 40px min-height, 8/9.6px radius, transition set, disabled/loading/icon-only rules | components.md:825-861 |
| h-control | 32px compact control-height utility (destructive-inline, Filter chip, Period picker) | components.md:345,995,1093 |
| icon-button base | Shared 32×32 outer / 20×20 glyph geometry; AAA hosts should ship ≥44×44 | components.md:781,1209-1216 |
| cds-reset | Utility class neutralizing inherited styles on app-surface skeletons — used but never defined in components.md | components.md:1016-1018,1114-1115,1427 |
| Theme Roles Used | Per-component facet listing which role tokens the component binds | components.md:284 and every §14 entry |
| Cross-component foundation references | Closing consolidation mapping shared contracts to foundations/ locations | components.md:1588-1596 |
| T1–T18 | Hero, Trust Strip, Validation, Capability, Workflow, Use-Case Routing, Path Fork, Interactive Demo, Pricing, Trust Detail, FAQ, News, Resource Directory, Cross-Promo, Sub-Hero, Final CTA, Footer, Section Header | section-types.md:53-229 |
| heading-strip, centered-stack, split-text-media, centered-affordance, card-grid, tagged-card-grid, tabbed-panels, alternating-rows, card-carousel, logo-marquee, numbered-steps, stacked-quotes, quote-swiper, feature-quote, accordion, pricing-tiers, rate-table, banner-strip, cta-panel, cta-newsletter, two-path-fork, pictogram-subcards, tag-columns, lead-plus-carousel, resource-grid, prompt-artifact, install-buttons, footer-grid, sub-hero-split | The 30-shape landing catalog (Part A), each with Slots/Layout/Variants/Determinations | shapes.md:43-461 |
| component family | Named group in components.md yielding one kebab-case class per family | generate-stylesheets/SKILL.md:41; check_reference.py:143-158 |
| render proof | The non-optional third test tier: generated artifacts in gitignored visual-proof-out/, judged by eye | test/README.md:26-64; run-tests.sh:34-43 |
| deep (wrapper/theme) | Local dark-theme wrapper context (Hero promo sub-panel, consent banner, marketing footer) | components.md:264,484,496-500,719 |
| signals / status | Semantic palettes: form/interaction state feedback vs badge grounds by meaning | SkillSpoke yaml:377-399 |

---

## 3. Hardcoded values inventory

### 3.1 Derived (frozen captures the rebuild must re-express as relationships)

| Value | Location | Kind | Context |
|---|---|---|---|
| ~1347px | app-shapes.md:374 | dimension | Quickstart page shape openly states its values are "representative for a desktop viewport (~1347px wide)" — an admitted screenshot-capture baseline all following absolutes derive from |
| 711×762px | app-shapes.md:381,386,405 | dimension | Templates panel container — should be a fluid track of the main pane; frozen from the 1347px capture; also baked into grid-cols-[1fr_711px] |
| 678px | app-shapes.md:388 | dimension | Search input width = 711px minus 2×16px padding — a frozen consequence stated as an absolute |
| ~333×79px | app-shapes.md:389-390 | dimension | Template card size = half of 678px inner width minus 12px gap; frozen instead of 1fr |
| ~328px; 328×66; 266×48 | app-shapes.md:380,395-396 | dimension | Quickstart left column, prompt-strip wrapper, textarea — the leftover of viewport minus 711px panel |
| 208×72px cells; 96px postal basis; 32rem 2-col cap | app-shapes.md:1265-1267,1282,1329 | dimension | Field-group form: text mandates "natural flex sizing (no fixed basis)" yet pins each cell at 208×72 — a captured measurement contradicting the fluid rule |
| 9.6px (rounded-[0.6rem]) | app-shapes.md:1268,1275 | dimension | Input radius — non-token Tailwind arbitrary value captured from a product; recurs at components.md:546,843-847,882 and page-types.md:486 |
| 44px input / 42px combobox heights | app-shapes.md:1268-1269 | dimension | 2px difference is a capture artifact, not a design choice |
| 0.5px solid borders | app-shapes.md:386,390,650,1384 | dimension | Sub-pixel Tailwind border-0.5 from the captured product; the same role elsewhere uses 1px (layout.md:176-179 prescribes alpha-thinned 1px instead) |
| 44px group summary / 40px tool rows | app-shapes.md:1420-1421 | dimension | Tool-permission editor row heights — should derive from a list-row density token |
| 10 template cards; 3 KPI cards; 4 KPI tiles; 2 charts | app-shapes.md:389,296,334,452 | count | Instance counts from captured screenshots frozen as structural rules |
| --border-subtle/--surface-raised/--typeface-sans vs hsl(var(--border-300)) | app-shapes.md:1268 vs 1272-1278 | color | Field-group form mixes a foreign token vocabulary with CDS role tokens in one entry |
| 1440px content / 64px padding isolation wrapper | compose-page/SKILL.md:55; commands/compose-page.md:20 | dimension | Section/component-mock wrapper — should derive from --container-marketing-primary and the spacing scale |
| 26px (violation exemplar) | audit-against-system/SKILL.md:33; compliance.md:79 | dimension | Canonical violation example (.topbar-logo img { height: 26px }) — an anti-pattern illustration, itself a frozen reference-site capture |
| 40px topbar logo height | components.md:12; yaml:1683 | dimension | Comment says the glyph "tracks the bar height" and the schema's own example shows value var(--topbar-height) — yet the seed freezes 40px, decoupled from the 84px bar |
| 36px topbar action height | components.md:28; yaml:1684 | dimension | Sized to sit inside the 84px bar; a frozen consequence of bar height |
| 200px / 656–864px / 256px dropdown widths | components.md:52-56 | dimension | The mega range especially reads as measured capture that should derive from the container/grid columns |
| 40×40 hamburger; 16×1 + 8×1 lines | components.md:95 | dimension | Line lengths look like pixel captures; plausibly ratios of the 40px button |
| 256px rail width | components.md:156,166; app-shapes.md:29,74 | dimension | Fixed pane width belonging to the layout pane system (also intrinsic in yaml:1687 — the same value classified both ways across slices) |
| 232px / 225px / 30px switcher widths | components.md:1470-1471 | dimension | 232 = 256px rail minus 2×12px padding; frozen consequences captured as absolutes |
| weight 460 | components.md:340 | other | Destructive button font weight — a capture of a specific brand's variable-font axis setting |
| 254×176 / 242×176 / 210×144, max-w 500, gap 48 | components.md:481-483,944-946 | dimension | Stat card/tile frame sizes — explicit W×H pairs measuring a reference product; the spec itself already describes flex-1-up-to-max-w behavior |
| 96–128px = calc(--card-padding-md × 2) | components.md:743,749 | dimension | Article-hero tile padding stated as both derivation and frozen result |
| 216px marginalia rail (35ch content is intrinsic) | components.md:522-528 | dimension | Rail width is a capture that should derive from the 12-column grid |
| 30×30 SVG arrow | components.md:763; imagery.md:12 | dimension | Odd non-scale size measured from the reference site |
| 105–180px / 104–201px chip width ranges | components.md:997,1093 | dimension | Documenting min/max of observed content strings; content-driven width needs no pixel range |
| 20×20 circle, 1.5/1px borders, 1×16 connector, ≥1400/≥1536px reveals | components.md:1142-1155 | dimension | Stepper geometry; 1400/1536 are viewport captures not in responsive.md's breakpoint set |
| 2px dots, 4px centers | components.md:1242 | dimension | Kebab glyph measured detail |
| 69px / 81px+ editor-card heights | components.md:1311-1312,1361,1367 | dimension | Rendered-output measurements (line-height + padding sums) — the clearest frozen-consequence dimensions in the file |
| 43×24 track, 20px thumb, ~16px translate | components.md:1402 | dimension | Setting-card switch — derived from --cds-switch-h but contradicting the §14/§14.3 switch geometry |
| 48px height, 232px width, 32×32 avatar, 40px strip | components.md:1539-1554 | dimension | Account row — 232px again the rail-minus-padding consequence |
| 8 footer columns (Products/Models/Solutions/Platform/Resources/Help/Company/Terms) | components.md:256 | count | Column NAMES enumerate a specific reference site's IA, not a system default |
| 640px reading column | page-types.md:164,180,351,368 | dimension | Typography foundations elsewhere use ch measures — plausibly should be a ch measure or derive from container (layout.md:46 classifies the token itself as intrinsic; the per-page restatements are the frozen part) |
| 316px documentation offset | page-types.md:366; responsive.md:11 | dimension | Arithmetic residue of centering a 640px column inside a captured container width — textbook frozen relational dimension; tokenless, appears nowhere else |
| 23.8px list line-height | page-types.md:384 | dimension | 17px × 1.4 frozen as an absolute; should be the 140% ratio |
| 84px (5.25rem) auth topbar | page-types.md:468; implementation.md:233-238 | dimension | Captured computed value not tied to a spacing token |
| 64px icon rail; 280–320px list column; 960–1100px detail card | page-types.md:539-540,558-560 | dimension | App-shell pane widths frozen from a reference app |
| cols 1–9/10–13; 1–10/11–13 | page-types.md:260,278-279 | dimension | Frozen grid spans from a reference layout (13 implies grid-line notation) |
| five-trigger nav | page-types.md:88 | count | Nav item count is content, frozen from the reference site's nav |
| 56px mobile section padding | page-types.md:126 | dimension | Flattens the --section-pad-* clamp scale to one absolute (the layout.md:80-87 mobile_floor version is intrinsic; this restatement is frozen) |
| weight 330 | page-types.md:443,475 | other | Auth ultralight headline — font-file-specific captured value |
| scale 1.005 × 1.015 | page-types.md:496 | other | Primary CTA hover transform — captured computed values |
| -0.08px / 0.15px letter-spacing | page-types.md:387,296; typography.md:141-142 | dimension | Sub-pixel captured computed styles against the em-based --track-* tokens |
| 96px → 48px tile padding | page-types.md:227 | dimension | Should ride the --section-pad scale |
| 32px auth-card radius | page-types.md:461 | dimension | Pixel and "top of the radius scale" both asserted; only one should be canonical |
| 700px / 480px breakpoints restated inline | shapes.md:5 and ~20 repeats; page-types.md:82,224,318 | dimension | Restated in nearly every shape determination instead of referenced from responsive.md |
| 32px gutter restated | shapes.md:81,111,155,345,373,415… | dimension | Foundation token frozen into prose in ~10 shapes |
| 960px beside --column-medium | shapes.md:97,217,244,259 | dimension | Token pixel restated in prose in 4 shapes; if the YAML overrides the token, the prose lies |
| --sp-*/--section-pad-* pixel restatements | shapes.md:54,66,97,157,170,186,217,245,304,318,360,431,445 | dimension | 12/16/24/40–48/52–64/64–80/64–96/128–200px restated beside every token use |
| ~3 cards + ~10% peek | shapes.md:170 | dimension | Relation is right; the 1440px container anchor is frozen |
| Input/Output/Cache write/Cache read | shapes.md:27,281,285 | other | rate-table default columns — LLM-API pricing content frozen into a content-independent shape |
| macOS / Windows / iOS | shapes.md:37,421,424 | other | install-buttons platform set — content, though marked extensible |
| --section-pad clamp ranges restated | page-types.md:81 | dimension | 192–240/128–200/96–128px restated in landing layout rules |
| 1400px --container-editorial | layout.md:38; page-types.md:179,277; yaml:1662; responsive.md:10-11 | dimension | Second near-page width 40px under the marketing width with no stated reason; likely a frozen reference-site capture (ref-pages slice and machinery classify unclear; foundations classifies derived) |
| 1192px --column-wide | layout.md:44; implementation.md:232; yaml:1669 | dimension | Page width minus gutters frozen as an absolute — the classic captured dimension |
| 960px --column-medium | layout.md:45 | dimension | Plausibly a fraction of page width frozen as px (yaml slice classifies the token intrinsic as a reading measure) |
| 448px --container-conversion-card | layout.md:48; responsive.md:20; yaml:1663; page-types.md:460,505 | dimension | Element width mislabeled with the container- prefix, filed inside the containers scale that declares "≥ page width" |
| clamp(32px, 4vw, 64px) .u-container padding | layout.md:55; responsive.md:18 | dimension | Hand-picked vw middle term violating the file's own §11.1 derived-middle-term law |
| clamp(48px, 8vw, 128px) .feature-tile padding | imagery.md:39 | dimension | Same violation; min/max also outside the --sp-* scale |
| 96px 0 48px; 24px; 16px 0; 32px 0 8px; 12px editorial rhythm | layout.md:111-117 | dimension | "Exact pixel margins" that should derive from the type scale/line-height |
| 1.57% / 1.18% shadow opacities | layout.md:160-168 | color | Sub-integer opacities verbatim from a reference site's computed styles |
| editorial Mobile/Tablet/Desktop type triples | typography.md:119-142 | dimension | Three-breakpoint per-role sizes contradicting the two-anchor clamp law; the tablet column should fall out of interpolation |
| 67.2 / 19.6 / 22.4 / 28 / 21 / 24 / 16 / 16.8px auth line-heights | typography.md:148-161 | dimension | Frozen size×ratio products; should be --lh-* ratio tokens |
| 250/500/750/1000ms editorial stagger | motion.md:58 | duration | Frozen per-index delays that should derive from base × index like the reveal pattern |
| icon viewboxes 18/20/30/32; containers 20/24/32/40px; 16px rail icons | imagery.md:8-12 | dimension | Plausibly should derive from the spacing scale / button geometry |
| card padding 24–48px | responsive.md:19; compliance.md:51 | dimension | Disagrees with layout.md's --sp-2 card-padding default (28–32px); unclear which token this maps to |
| (100vw − 320px) / 1120 in every clamp | yaml:1633-1654 | dimension | The §11.1 interpolation repeated verbatim in ~10 tokens; 1120 = 1440 − 320 — a page-width change silently desynchronizes every clamp |
| max-width:1440px .galwrap | assemble.py:145 | dimension | Duplicates containers.marketing-primary in viewer tooling; drifts if the YAML page width changes |
| top:41px .gal-label | assemble.py:151 | dimension | Frozen consequence of the galbar's computed height; breaks if bar chrome changes |
| 4 feature-tile variant pairs (1,2,3,accent) | SkillSpoke yaml:742-808 | count | The role count freezes the tile variants the project can express (a data decision, but flagged by items #4/#6 as previously mirrored in hardcoded plugin classes) |

### 3.2 Unclear

| Value | Location | Kind | Context |
|---|---|---|---|
| --container-marketing-primary / --column-reading names in emission rules | generate-stylesheets/SKILL.md:41 | other | The marketing-specific container name is hardwired as the universal section-wrapper width regardless of page family |
| 448px auth card max-width | page-types.md:460,505 | dimension | Captured from a reference login card; held on every breakpoint (also listed in 3.1 as the misfiled container token) |
| 42–72 / 30–44 / 32–52 / 64 / 56→36px headline clamps | page-types.md:95-98,194,292,381,475,506 | dimension | Type-scale choices, but restated per page type rather than referencing typography tokens |
| grid spans 1–6, 7–12, 1–9, 10–13, 1–10, 11–13 | layout.md:124-130 | count | '13' entries read as grid-line numbers in a table labeled "Column Span" for a 12-column grid — notation inconsistency |
| --focus-offset-inner -2px / --focus-offset-outer 4px vs table offsets 1px/2px | accessibility.md:16-28 | dimension | The declared focus tokens and the file's own rule table disagree; 4px is used nowhere |

### 3.3 Intrinsic (genuine design choices, shipped defaults)

| Value | Location | Kind | Context |
|---|---|---|---|
| 320px / 1440px (20rem / 90rem) anchors | layout.md:11-12; typography.md:96 | dimension | The two viewport interpolation anchors; structural law |
| 1440px --container-marketing-primary | layout.md:37; yaml:1661; page-types.md:80; shapes.md:67,170 | dimension | "The page width"; the root dimension others should derive from |
| 640px --column-reading | layout.md:46; compliance.md:50,69 | dimension | Deliberate reading-comfort measure, enforced as "the only acceptable body width" in §23 #8 |
| 64/96, 96/128, 128/200, 192/240px section-padding scale | layout.md:69-72 | dimension | Designed rhythm scale at the anchors |
| 56px @ max-width 480px mobile floor | layout.md:80-87; yaml:1652; compliance.md:52,73 | dimension | Mobile floor for major section padding; "no exceptions" per §23 #12 |
| 4…96px spacing scale (--sp-0-25…--sp-6) | layout.md:96-105; yaml:1627-1638 | dimension | The shared spacing scale |
| 12-col / 2-col grid, 700px switch, 32px gutter | layout.md:121 | count | Grid model, declared structurally fixed |
| 4/8/12/16/16–24/16–32px radius scale | layout.md:134-141; yaml:1641-1647 | dimension | xs..2xl; 32px top reserved for the conversion card |
| 1px solid rgba(ink, 0.15–0.3) hairline | layout.md:176-179 | dimension | Alpha-thinned substitute for 0.5px borders — deliberate rendering choice |
| weights 300/330/400/430/480/500/600/700 | typography.md:53-88; implementation.md:335-339 | other | Variable-axis weight slots incl. the oscillation intermediates |
| 21-step type ladder, 10px Micro → 80px Display XXL | typography.md:67,100-142 | dimension | The full ladder across marketing and editorial scales |
| underline 0.08em thickness, 0.18/0.2em offset | typography.md:167-168,131 | dimension | Relational em geometry — the correct derived form |
| 20/30/35/40ch max-widths | typography.md:100,107,112,134; overview.md:149; components.md:522 | dimension | Character-count measures, relational by construction |
| 7 cubic-bezier easing curves | motion.md:29-37; yaml:1704-1722 | other | Easing defaults; NOTE --ease-out-quart and --ease-out-power2 are byte-identical (0.165, 0.84, 0.44, 1) under two names |
| 100–1000ms duration ladder | motion.md:41-50; yaml:1704-1722 | duration | Mapped to interaction types |
| reveal 0.75s/60ms/0.5em; card 0.4s/80ms/16px; fade 0.4s+0.3s; fade-up 0.5s/32px | motion.md:70-123; yaml:1731-1753 | duration | Entrance-pattern defaults, also inline var() fallbacks |
| 0.01ms reduced-motion reset | motion.md:132-139 | duration | Standard technique |
| 16:9 / 1:1 tile aspect ratios | imagery.md:16,35; shapes.md:67,460 | other | Feature-tile and hero visual aspects |
| srcset 500/800/1080/native | imagery.md:27 | dimension | Photography responsive breakpoints |
| 480/700/1024/1440px breakpoint set | responsive.md:5-11; app-shapes.md:29,80,166,236,378 | dimension | Five-range model; 1440 coincides with the upper anchor and page width |
| 17px minimum body size | responsive.md:27; compliance.md:42 | dimension | Body-type floor on every breakpoint |
| +5% mobile line-height | responsive.md:29 | other | Relational compensation rule |
| 7:1 / 4.5:1 contrast; weight ≥600 below 14px; 12/13px size floor | accessibility.md:5-7,49-51 | other | WCAG thresholds and the three-axis floor |
| --focus-width 2px | accessibility.md:16-28 | dimension | Focus ring width (offsets disputed — see 3.2) |
| 84px topbar / 64px mobile floor | components.md:17,23; yaml:1682 | dimension | Tokenized as geometry.components.topbar.height with mobile_floor; YAML-overridable |
| 600ms/200ms dropdown motions | components.md:63-64; page-types.md:117; motion.md:48 | duration | Curves inlined rather than referencing named eases (vocabulary inconsistency) |
| 800/400ms drawer wipe, 80ms stagger, 320ms delay | components.md:99-101 | duration | Mobile drawer timing |
| 8px down / 4px up scroll thresholds | components.md:147 | dimension | Sticky-header hide/reveal |
| 36px rail rows, 8px pad, 40px icon slot, 12px gap, 8px radius | components.md:172-177,197 | dimension | Rail nav-row geometry (40px slot is itself a sum) |
| z-index 100 / 101 | components.md:21,93,246 | count | Stacking ladder: topbar 100, drawer/skip links 101 |
| 40px button min-height, 8/9.6px radius, 8px 16px padding | components.md:843-847 | dimension | Button base (9.6px flagged as capture oddity in 3.1) |
| 36px / 32px destructive heights | components.md:340,345; app-shapes.md:1398 | dimension | Unexplained deviation from the 40px button base |
| 12/16/24/32px feature-card padding ladder | components.md:379-381 | dimension | small→x-large mapped to section density |
| 44px input height, 12px padding | components.md:546; page-types.md:486 | dimension | 44px justified by WCAG 2.5.5 AAA |
| 0.5rem/0.75rem badge padding, 12px caption, 4rem min-width | components.md:598,614 | dimension | Pill badge geometry |
| ~600px dialog, 16px radius, 50% backdrop, <700px full-screen | components.md:683-687 | dimension | Centered dialog |
| 75rem/90vw/90vh lightbox caps, 5–10px blur, 90% opacity | components.md:701-705 | dimension | The only permitted backdrop blur |
| exactly 3 related-rail items | components.md:758,765 | count | Host-supplied; columns collapse when fewer |
| 32×32 outer / 20×20 glyph icon buttons | components.md:781,1211-1215,1264,1320 | dimension | Repeated in four components with the ≥44×44 AAA hedge |
| 32px chip height (h-control), 6px gap | components.md:995-996,1093 | dimension | Filter chip / Period picker |
| 200ms leading-edge debounce | components.md:1076 | duration | Search-field live filter |
| >48 chars / max-w 32rem truncation | components.md:1268 | count | Read-only identifier row |
| ~7 workspaces search threshold | components.md:1516 | count | Switcher panel shows a Search field above it |
| 1.5s Copied revert | components.md:655,1271 | duration | Code block and identifier row |
| 320px --info-panel-width; 64px bottom strip; 280px --list-column-width; 320px --form-sidebar-width (280px floor) | app-shapes.md:75,121,161,228,236 | dimension | Shell pane tokens, tokenized and cross-referenced |
| 56px icon-only rail | app-shapes.md:29,160 | dimension | Reused consistently as a system constant |
| 520px --modal-width, 80vh cap, 12px radius | app-shapes.md:756,1166-1168 | dimension | Centered modal, capped at calc(100vw − 32px) |
| 48px empty-state circle, 1px --border-300 ring | app-shapes.md:528 | dimension | Empty-state icon frame |
| 32px vs 36px destructive heights | app-shapes.md:1398 | dimension | destructive-inline one step below primary |
| 150ms hover / 200ms modal fade | app-shapes.md:56,1109,1193 | duration | Reduced-motion suppressed |
| 12:00 / 17:59 / 18:00 greeting cutoffs | app-shapes.md:322 | other | Greeting page-shape time-of-day logic |
| 8px active-pill radius | app-shapes.md:56 | dimension | Should plausibly reference a --radius-* token |
| --sp-* values given with token names | app-shapes.md:77,121,163,323,1217 | dimension | Properly tokenized spacing |
| retain last 10 state records | compose-page/SKILL.md:57; compose-app-surface/SKILL.md:47 | count | Retention policy |
| pick_shape thresholds (≥10, ≤8, =3, 2–4, 5–6, ≥5, =2) | landing-sections-shape-rules.md:51-82 | count | Genuine decision-table heuristics |
| ~40s marquee loop; ~7s quote auto-advance; ~240-char quote cap | shapes.md:186,231,244 | duration/count | Shape behavior choices |
| per-shape count bounds (3 cols; 2–5 tabs; 2–4 tiers/quotes; 3–5 tag cols; 4–6 footer cols) | shapes.md:110,140,216,269,371,444 | count | Genuine composition choices |
| 600ms landing dropdown; 300ms editorial topbar hide | page-types.md:117,188,218 | duration | Page-type motion values |
| 44px/12px auth input | page-types.md:486 | dimension | Height and horizontal padding |
| light-mode default + top-right toggle | commands/compose-page.md:20 | other | Isolation-wrapper theming behavior |
| two-space indent, trailing newline | setup/SKILL.md:50 | other | settings.json serialization |
| ask once | generate-stylesheets/SKILL.md:24; package-change/SKILL.md:26 | count | One interactive ask before OUTPUT_PATH_UNRESOLVABLE |
| 3 CSS files + manifest | generate-stylesheets/SKILL.md:9,43-44 | count | The architectural partition of the output |
| color: var(--text-primary) ink fallback | generate-stylesheets/SKILL.md:41 | color | Role reference, not a literal |
| tile-ground-4..N example range | generate-stylesheets/SKILL.md:41 | count | Illustrative; the skill mandates "Hardcode no count or suffix list" |
| react-tsx, vue-sfc, plain-html | setup/SKILL.md:38 | other | FRAMEWORK examples, not an enum |
| 2-level state paths | package-change/SKILL.md:14 | other | Fixed state-record directory layout |
| 21-step ramps 000–1000 | yaml:66-177; SkillSpoke yaml:55-166 | count | Ramp resolution choice |
| 7 panel grounds (a–g); 3+accent tile pairs | yaml:283-289,751-810; SkillSpoke yaml:272-278 | count | Data decisions per enhancement #6 |
| all seed/project ramp and discrete hex values | yaml:44-241; SkillSpoke yaml:44-241 | color | Tier-1 primitives are BY DESIGN the only place hex lives (full inventory in §7) |
| 50% selection-bg color-mix | yaml:586-589; SkillSpoke yaml:579-582; compliance.md:40 | other | Selection tint ratio |
| 50% modal wash; 40% link rest opacity | compliance.md:75; typography.md:157 | color | Fixed alpha ratios |
| weights 300–900 / 300–700, opsz 7–72 | yaml:414-433; SkillSpoke yaml:412-425 | other | Intrinsic axes of the chosen typefaces |
| font fallback stacks | SkillSpoke yaml:435,439,443 | other | system-ui / Georgia / ui-monospace stacks |
| 8 themes (2 dual-mode, 1 alias, 5 light-only) | SkillSpoke yaml:858-1609; yaml:839-1610 | count | The theme roster |
| 480 / 500 button weights per mode | implementation.md:335-339 | other | The oscillation table |
| ["light","dark","system"] fallback | assemble.py:89 | count | Mode-list fallback, stated as the foundations contract |
| 999 sort sentinel; PAD=28; 2000-char slice | assemble.py:228; check-plugin.py:36; check_topbar_nav.py:73 | count | Tooling constants |
| 480px mobile_floor max_width | yaml:1652,1682 | dimension | The narrow-viewport breakpoint both floors share |
| #2C84DB focus-blue | SkillSpoke yaml:230 | color | Chromatic focus/switch fill, deliberately mode-invariant |
| #F46C5D / #E35849 / #E05446 / #DE5D4E | SkillSpoke yaml:181-184 | color | The SkillSpoke brand accent (burnt-orange) |

---

## 4. Halt-code inventory

| Code | Trigger | Where defined | Inconsistencies |
|---|---|---|---|
| `WRONG_SKILL:{name}` | Request carries app-embedding language — caller must re-invoke compose-app-surface | compose-page/SKILL.md:28,70 | — |
| `STYLESHEETS_REGEN_FAILED:{inner-code}` | Stylesheet set stale/missing and the auto-invoked generate-stylesheets itself halted; inner code surfaced verbatim | compose-page/SKILL.md:36,61; compose-app-surface/SKILL.md:36,52; package-change/SKILL.md:66 | — |
| `SHAPE_RULES_PENDING:{page-type}` | Requested page type's shape rules present in neither plugin reference nor project extensions | compose-page/SKILL.md:41,62 | Listed by cds-code-companion (agents/cds-code-companion.md:31-38) although neither of its two skills can emit it — unreachable |
| `APP_SECTION_RULES_PENDING:{section-type}` | Section-level shape rules for in-app sections defined nowhere | compose-app-surface/SKILL.md:41,54 | Same unreachable listing in cds-code-companion |
| `MISSING_SPEC` | generate-stylesheets: a REFERENCE file lacks a value the emitted CSS needs (never for an omitted YAML override). apply-design-system: reference does not cover the category. audit: reference too thin to evaluate. Composers: a required spec too thin and absent from both sources | generate-stylesheets/SKILL.md:75; apply-design-system/SKILL.md:55; audit-against-system/SKILL.md:40; compose-page/SKILL.md:63; compose-app-surface/SKILL.md:55 | — |
| `MISSING_COMPONENT:{name}` | Required component not defined | compose-page/SKILL.md:64; compose-app-surface/SKILL.md:41,53 | Wording drift: compose-page cites only components.md; compose-app-surface correctly says "neither reference nor extensions" |
| `UPDATE_SOURCE_UNREADABLE` | Brownfield source cannot be read/parsed into a region map | compose-page/SKILL.md:44,65; compose-app-surface/SKILL.md:45,56 | — |
| `UPDATE_TARGET_AMBIGUOUS` | Update request cannot be localized to specific region(s) | compose-page/SKILL.md:44,66; compose-app-surface/SKILL.md:45,57 | — |
| `OUTPUT_PATH_UNRESOLVABLE` | No output path provided or discoverable (after one ask, where interactive) | compose-page/SKILL.md:67; compose-app-surface/SKILL.md:58; generate-stylesheets/SKILL.md:72; package-change/SKILL.md:65 | Also listed unreachably by cds-code-companion |
| `PRECONDITION_FAILED` | compose-page: compliance rule unsatisfiable without violating a spec. compose-app-surface: request doesn't fit Application Shell rules. generate-stylesheets: YAML fails schema validation. audit: target unreadable past recovery. setup: settings.json is malformed JSON (no repair attempted) | compose-page/SKILL.md:56,68; compose-app-surface/SKILL.md:59; generate-stylesheets/SKILL.md:73; audit-against-system/SKILL.md:41; setup/SKILL.md:47,55 | One code, five materially different meanings across five skills |
| `ELEMENTS_YAML_UNSET` | $CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS not set or file missing | compose-page/SKILL.md:69; compose-app-surface/SKILL.md:60; generate-stylesheets/SKILL.md:71; audit-against-system/SKILL.md:42; package-change/SKILL.md:68 | — |
| `FRAMEWORK_UNSET` | $CUSTOMIZABLE_DESIGN_SYSTEM_FRAMEWORK not set and not supplied after asking once | compose-app-surface/SKILL.md:18,35,51 | Listed unreachably by cds-code-companion |
| `ELEMENTS_VERSION_MISMATCH` | YAML $schema_version major differs from the validation schema's $id major | generate-stylesheets/SKILL.md:74 | — |
| `STATE_RECORD_NOT_FOUND` | No state record matches the packaging target | package-change/SKILL.md:64 | — |
| `ASSETS_UNRESOLVABLE` | An asset path recorded in the state record cannot be found | package-change/SKILL.md:67 | — |
| (unnamed setup STOPs) | Shipped-template copy destination cannot be created; user declines to supply an elements path | setup/SKILL.md:56-57 | Two halts carry NO code, breaking the otherwise-uniform `STOP: {skill}: {code}` contract |

Enforcement mechanism: `test/checks/check_consistency.py:9-16,44` requires every backticked UPPER_SNAKE code in a command's `## Notes` to appear (by base name, `:{...}` suffixes ignored) in the same-named skill's `## Halt conditions`. The reference tree and foundations define no halt codes; `STYLESHEETS_STALE` (named in the enhancement doc) no longer exists — superseded by auto-regeneration plus `STYLESHEETS_REGEN_FAILED`.

---

## 5. Enhancement items #1–15 status

Reconciliation rule applied: not-assessable-from-my-files is a non-vote; on substantive disagreement the more specific/negative finding wins, with both cited.

| # | Title | Resolved status | Evidence summary |
|---|---|---|---|
| 1 | Section containers can render narrower than the page | **partial** | Core law implemented: layout.md §11.2 mandates section wrappers ≥ page width, .u-container defaults to --container-marketing-primary, --column-* demoted to inner blocks (foundations); composers enforce it (compose-page/SKILL.md:47) and generate-stylesheets emits the utilities accordingly. Residual defects override the implemented votes: page-types.md still hardcodes divergent section-level containers (1440px landing :80 vs 1400px editorial/index :179,:277) with no stated relationship (ref-pages slice), and `containers.conversion-card: 448px` — an element width — sits inside the containers scale, violating the invariant on its face (machinery, yaml:1663). |
| 2 | Comment/description discipline (type vs. instance) | **partial** | The seed template and project YAML are swept, and the rule is enforced twice (lint-elements.py DESCRIPTIONS hard-fail; check_reference_prose.py) — machinery and project-yaml slices report implemented. Residue overrides: change-narration in components.md:24 ("is exactly what audit-against-system now flags") and the stale "32 H2s" count (:284); compliance.md's embedded "Scope ambiguities" self-critique (:84-90); the commented-out pastel alternative block in both YAMLs (seed :268-280; project :257-270) is contents/history kept in-file. |
| 3 | Extensibility — extensions dir for shapes/page-types/section-types | **partial** | The mechanism is fully implemented in the skills: both composers read $CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/{shapes,page-types,section-types}/ overriding by name, halts fire only when an entry is in NEITHER source, and cds_hash.py fingerprints the extensions tree (composers, support, machinery slices). But the reference catalogs themselves remain closed lists that never mention the extension path ("The framework recognizes six page types", page-types.md:3; fixed T1–T18 and 30-shape tables — ref-pages slice: absent), components.md has no extension hook, and a project extension shape has no declared mechanism to state which catalog (landing vs app) it belongs to (composers notes). |
| 4 | Reference-as-source consistency (role_var_pattern; data-driven tile variants) | **partial** | Reference and seed fixed: role tokens are bare per compliance.md:94 and the seed's $conventions (yaml:19), imagery.md:41-48 and generate-stylesheets make tile variants fully data-driven, and check_reference's ROLE-PREFIX rule bans `--role-` regressions (foundations: implemented). Two contradictions override: the live SkillSpoke YAML still declares `role_var_pattern: --role-{role key}` (line 19) which nothing exercises — the stated convention is dead in the consuming project (project-yaml slice); and assemble.py's gallery chrome still consumes `--role-surface-primary` etc. (assemble.py:135-154), a broken remnant the guard deliberately does not scan (machinery slice). The enhancement doc's own citation "components.md §16.4" does not match the file (no §16 exists). |
| 5 | Mock output — two companion sidecar files | **implemented** | compose-page Step 4a emits `<basename>.wireframe.txt` ("T# · section-type · shape · ground-role" blocks) and `<basename>.decisions.md` (per-section shape choice, pick_shape trigger, alternates rejected, ground reasoning) as SEPARATE files beside metadata-free HTML, with paths in the state record (compose-page/SKILL.md:50-54,57); package-change copies both into the bundle spec/ (package-change/SKILL.md:17,47-48). Caveat carried to §6: compose-app-surface emits no sidecars. |
| 6 | Tile-ground role count is a data decision | **implemented** | tile-ground-N/tile-ink-N are ordinary role pairs, themes bind role numbers freely to any panels key (SkillSpoke yaml:742-808, clarity light tile-ground-1→panels-a :901, dark →panels-d :947), the generator emits one .feature-tile--N and .ground--N per declared pair with no hardcoded count (generate-stylesheets/SKILL.md:41; imagery.md:44-55; components.md:459; seed yaml:745-750). All assessing slices concur. |
| 7 | Multi-color logo support (asset-pair) | **implemented** | assets.logo mode: asset-pair is a formally supported configuration end-to-end: seed YAML + schema oneOf (yaml:1755-1769; schema.json:772-802), implementation.md:23 and compliance.md §23 #15 sanction it, generate-stylesheets emits the CSS-only mode swap, compose-page renders the .logo-light/.logo-dark element pair (SKILL.md:47), components.md §12.1 documents it. The live SkillSpoke YAML declares no assets.logo block (project-yaml: absent) — a project choice, not a plugin gap. |
| 8 | card-grid grounds vs feature-tile grounds | **partial** | Colored card-grids are now first-class via SHARED grounds: shapes.md:107,112 makes .ground--N a first-class card-grid variant and explicitly bans ad-hoc panel-N; generate-stylesheets emits .ground--N per tile-ground role (support: implemented). But the item asked for a decision on a dedicated "card ground" role set, and none exists anywhere: no card-ground family in the seed or project YAML (machinery, project-yaml: absent), components.md's Catalog/Pricing cards bind only --surface-raised + --border-subtle and tile-ground-* stays exclusive to the Editorial featured tile (ref-components: absent, lines 423,441,459). The resolution shipped is reuse, not the requested first-class role set. |
| 9 | Stylesheets regenerate automatically on YAML change | **implemented** | Both composers and package-change run "stylesheet freshness (auto-regenerate, never halt for staleness)": semantic fingerprints via cds_hash.py vs manifest.json, self-invoked generate-stylesheets on mismatch, only inner failure halts (STYLESHEETS_REGEN_FAILED) (compose-page/SKILL.md:36; compose-app-surface/SKILL.md:36; package-change/SKILL.md:31). The sub-point is proven mechanically: the semantic hash excludes comments/descriptions and check_semantic_hash.py verifies prose-invariance and value-sensitivity (lib/cds_hash.py:60-87; check_semantic_hash.py:84-116). `STYLESHEETS_STALE` no longer exists. |
| 10 | A "package the change" skill | **implemented** | skills/package-change/SKILL.md exists and covers the full requested contract: stylesheets + manifest, mock HTML or surface code + wiring diffs, a derived build-spec.md (the developer instructions), the #5 sidecars, ancillary assets, the state record, and a brownfield update/ folder with original snapshot + change.diff (support slice, entire file; composers confirm the state-record hooks that feed it). |
| 11 | Brownfield / update mode | **implemented** | Both composers carry a discovery-level UPDATE-path check and a pipeline update path: parse existing artifacts (repo files or Figma refs) into a region map, recompose only targeted regions, splice back byte-for-byte (compose-page) or emit region-scoped diffs (compose-app-surface); UPDATE_SOURCE_UNREADABLE / UPDATE_TARGET_AMBIGUOUS halts; state records carry mode=update, update_source, per-section preserved; package-change ships update/original + change.diff (compose-page/SKILL.md:30,44; compose-app-surface/SKILL.md:27,45; package-change/SKILL.md:34,57-59). |
| 12 | Additional constraints (project stack; motion defaults) | **partial** | Motion half implemented: motion.md §15.0 codifies exactly the requested landing/marketing orchestration (one orchestrated page-load, animation-delay staggered reveals, scroll triggering, one high-impact moment), the entrance patterns are emitted with correct reduce-only gating, and the Application Shell keeps motion calm (page-types.md:593-598). The stack constraint (Tailwind / shadcn-ui / NativeWind / ag-grid / Zustand / Motion) has NO deliberate trace in any file — setup's FRAMEWORK examples are react-tsx/vue-sfc/plain-html only (setup/SKILL.md:38); the raw Tailwind chains in app-shapes.md and components.md are capture leakage, not a stack commitment (composers, ref-components slices). |
| 13 | Nav menu / dropdown support | **implemented** | components.md §12.2 fully specifies dropdown panels (flat/mega/lift-and-scale, ARIA menu pattern, keyboard, touch) and §12.1 wires primary-nav items as trigger+panel; compose-page renders them and drafted mode asks which nav items carry dropdowns (compose-page/SKILL.md:45); accessibility.md:34 and motion.md:48,61 carry the contracts; check_nav_dropdown.py enforces the ARIA correctness on the rendered sample. The "we only have links" worry is resolved. |
| 14 | Pages not defined correctly (Building Blocks vocabulary) | **absent** | The proposed vocabulary (Section / Section Container / Shell / Shape / UI Object, with user-predefined Shells) exists nowhere. overview.md still models page type → section wrapper → element with no shell/section-container layer (foundations); page-types.md conflates frame with content in every Required Structure list while the alternation rule contradicts them, and the footer holds a double identity (content section T17 AND excluded frame element) (ref-pages); components.md is a flat catalog with no page-assembly model (ref-components); the seed reuses "container" for a width token that will collide with #14's containment concept (machinery). Only fragments exist: app-side shell layouts/page shapes (app-shapes.md:1-10,284-287) and section-scoped themes (project yaml:858) — and compose-page's fallback is inverted vs the proposal (STOP SHAPE_RULES_PENDING instead of improvise) (composers). |
| 15 | Add more options / fill gaps; remove PM commentary | **partial** | The PM-commentary rule is enforced mechanically (check_reference_prose.py hard-fails Known gaps/TODO/history markers in reference trees — machinery) and no "Known gaps" prose survives in any audited reference file. Catalogs are broad (30 shapes; ~40 §14 components; 2–4 shapes per landing section type; 5 shells + ~13 page shapes + 6 compositions). Remaining gaps override: T7/T11/T17/T18 map to exactly one shape with no alternate (section-types.md:119,159,219,229); landing-sections-shape-rules.md shows an incomplete sweep (dead catalog reference, Part D before C, three corrupted cells); compliance.md's "Scope ambiguities" block is exactly the embedded self-commentary the item forbids (compliance.md:84-90). |

---

## 6. Structural findings

1. **The two composer SKILLs duplicate four whole subsystems near-verbatim, and one drift already exists.** The extensions-overlay paragraph, the stylesheet-freshness step, the update-path mechanics, and the state-record step are near-verbatim copies between compose-page/SKILL.md and compose-app-surface/SKILL.md; any change must be made twice. The drift: compose-page's MISSING_COMPONENT halt text cites only components.md while compose-app-surface's correctly cites "neither reference nor extensions" (compose-page/SKILL.md:64 vs compose-app-surface/SKILL.md:41,53).

2. **Sidecar asymmetry: the derivation log exists only for standalone mocks.** compose-page emits wireframe + decisions sidecars (SKILL.md:50-54); compose-app-surface emits none — so the composition reasoning is lost exactly where a developer hand-off needs it most (compose-app-surface/SKILL.md:47).

3. **landing-sections-shape-rules.md is an orphaned, partially corrupted fragment.** It presents Part D before Part C and references "the catalog above" (Parts A/B) which is absent — the T# definitions moved to the shared section-types.md, leaving a dead reference (line 16). Three cells are corrupted: T5 alternates carry prose ("a vertical numbered list, or split into two T5 sections.", :63), T12 carries a trailing ")" fragment (:75), and T14's primary is "embedded inside T10" — an instruction, not a shape name (:78).

4. **app-shapes.md conflates four concerns and contradicts itself.** Shell layouts, page shapes, component compositions, and skill-pipeline policy live in one 1472-line file. Its preamble claims all measurements "resolve against the foundations", yet the quickstart page shape anchors to a ~1347px captured viewport (:374) and the field-group composition mandates "natural flex sizing (no fixed basis)" while pinning cells at 208×72px (:1265-1267). It mixes a foreign token vocabulary (--border-subtle/--surface-raised/--typeface-sans, :1268) with CDS role tokens (--border-300/--bg-200, :1272-1278) in one entry, uses raw Tailwind arbitrary classes (grid-cols-[1fr_711px], rounded-[0.6rem], border-0.5, :405-430) beside BEM skeletons, and leaks project data ("Narrowing job seeker ICP for lean startup", :788) into a brand-neutral spec.

5. **app-shapes.md's "Mocks vs app-embedded" section is skill policy in a catalog file — and it tensions with compose-page.** Lines 1131-1140 restate/extend pipeline rules belonging in the two SKILL.md files; its "Catalog notes" allowance (mocks may carry a footnote naming catalog entries) conflicts with compose-page's absolute "no agent-side metadata in the HTML" boundary.

6. **The two shape catalogs are declared disjoint but share one extension dir and parallel halt codes with no routing.** app-shapes.md:3 declares its catalog non-interchangeable with shapes.md, yet the single extensions `shapes/` dir serves both composers and a project extension shape has no declared mechanism to state which catalog it extends (composers notes; compose-page/SKILL.md:40-41).

7. **Token-vocabulary schism in components.md.** Marketing/editorial components bind semantic roles (--surface-primary, --text-tertiary, --border-subtle) while ~11 app-surface components are raw Tailwind class captures with a parallel token set (--bg-000/300/400, --text-100..500, --border-200/300, bg-fill-field, shadow-field-ring, --brand-000, --accent-100, --switch-track, --fill-accent, cds-reset, duration-snap, ease-overshoot) — many used but never defined or cross-referenced in the file; Application stat card (--surface-raised) and Stat tile (--bg-300) name the same ground differently (ref-components notes; components.md:465-487 vs 926-976, 959, 1016, 1419).

8. **components.md has a dead self-reference and broken ordering.** The §14 intro describes a "source table" whose row data "The 32 H2s below" carry — no table exists and ~40 H2s do (:284); §14.1 points to "the component table at the top of §14", likewise absent (:833). §12.5.1/§12.5.2 physically sit after all §14 content (:1453-1584), breaking the §12 block.

9. **Two incompatible switch specs in one file.** Toggle switch / §14.3 (~32×18–36×20 track, --switch-active-bg/--surface-tertiary/--surface-raised) vs the Setting card's embedded switch (43×24 track, 20px thumb, --switch-track/--fill-accent/--switch-knob) (components.md:661-673,898-922 vs 1402).

10. **The T1–T18 catalog exists in three places.** section-types.md Part B table, page-types.md's "Section sequence" table (:54-73, verbatim), and the shape mappings a third time in landing-sections-shape-rules.md — three sources of truth for one catalog (ref-pages notes).

11. **page-types.md's section numbering is destroyed and it carries draft residue.** All six page-type H2 headings are literally "§20"; typos/unfinished prose survive in a normative reference ("swaw this is on the left", "varienty" :38; "not not all sections" :51).

12. **"Part A — Catalog" (shapes.md:7) and "Part B — Catalog" (section-types.md:5) are leftovers of one split document.** Neither file contains its counterpart part; assemble.py and check_shape_alignment.py parse "Part A" by name, coupling tooling to the leftover.

13. **Direct shape-vocabulary contradiction: T16 vs cta-panel.** section-types.md picks "cta-panel dark"/"cta-panel light" as shapes (:203-209) while shapes.md:314 rules a dark CTA band is a named theme island and explicitly NOT a shape variant.

14. **content_meta is incomplete relative to its own consumers.** T1 visual type, T3 logos-presence, T5 step count, T8 demo format, T9 pricing model, T14 format are all consulted by the mappings but are not fields of the 10-field schema; T1 states none of the schema fields branch it. Fixed-vs-resolved-at-build layout is never declared — it is only implicit that layout resolves at build via the shape pick (section-types.md:30-49,53-59 et al.).

15. **The background-alternation schedule — which 29 shapes depend on — lives only inside ONE page type's subsection.** shapes.md:303,314,467 cite the schedule; it exists only inside Primary Landing Page in page-types.md, so the ground rule dangles for the five other page types (ref-pages notes).

16. **The footer's double identity is the clearest symptom of the missing Shell concept.** Content section T17 (always footer-grid) AND frame element excluded from the alternation schedule carrying a per-page theme island (section-types.md:213-219; page-types.md:42,47).

17. **shapes.md freezes token values as pixel prose everywhere, and several shapes embed content.** ~20 restatements of 700px/480px breakpoints, ~10 of the 32px gutter, four of --column-medium's 960px, and the full --sp-*/--section-pad-* ladders in prose — a YAML override silently invalidates all of it. rate-table's Input/Output/Cache-write/Cache-read columns, prompt-artifact's AI pairing, install-buttons' OS list, pricing-tiers' "Individual ↔ Team", and resource-grid's "Docs/Blog/Video" violate the file's own content-independence claim (shapes.md:27,281,285,406-432).

18. **shapes.md's self-containment mandate is load-bearing and must survive any restructure.** Interactive/animated shapes carry their own scoped `<style>` and IIFE `<script>` implementing the ARIA contract; a fragment deferring behavior to "the stylesheet" is broken (shapes.md:188,468).

19. **implementation.md's section order is broken and compliance.md cites dead structures.** §6 (theme contracts) sits after §9 at the end of the file while compliance.md §21/§22 and implementation.md §8.2 cite "the §6 tables" and "the overview.md §4 tables" — neither location contains tables anymore (values moved to the YAML), so the generation instructions point at structures that no longer exist (compliance.md:19-20,33).

20. **Foundations carry five internal contradictions.** overview.md:181 counts "three button variants" then lists four; accessibility.md's declared focus tokens (--focus-offset-outer: 4px, -inner: -2px) disagree with its own rule table (1px/-2px/2px — 4px used nowhere, :16-28); responsive.md:19 + compliance.md §22 #19 say card padding 24–48px while layout.md's --sp-2 card-padding default is 28–32px; typography.md's editorial scale ships three-breakpoint values while layout.md §11.1 forbids per-breakpoint type authoring; layout.md §11.6's grid-placement table mixes column-span and grid-line notation ("10–13", "11–13" in a 12-column grid) under one "Column Span" header.

21. **Two utility rules violate the system's own no-hand-picked-vw law.** .u-container padding-inline clamp(32px, 4vw, 64px) (layout.md:55) and .feature-tile padding clamp(48px, 8vw, 128px) (imagery.md:39) both hand-pick vw middle terms against §11.1's derived-middle-term law.

22. **motion.md and the seed YAML define two identical easing curves under two names.** --ease-out-quart and --ease-out-power2 are byte-identical cubic-bezier(0.165, 0.84, 0.44, 1) (motion.md:29-37; yaml:1704-1722).

23. **--container-conversion-card is a naming residue of the pre-#1 model, contradicted twice.** The token carries the container- prefix while layout.md:48 insists it is an element width; in the seed it sits inside the containers scale two lines below the comment asserting a container is "never below the page width" (yaml:1656-1663) — the schema descriptions repeat the contradiction.

24. **assemble.py's gallery chrome consumes the retired --role-* vocabulary and therefore never theme-follows.** Roles are emitted bare and check_reference bans --role- in reference docs and generated CSS, but the ban deliberately excludes test tooling — so the chrome's vars never resolve and the gallery permanently renders its hardcoded fallback colors (assemble.py:135-154; check_reference.py:161-189).

25. **The live SkillSpoke YAML still declares the dead role_var_pattern.** `--role-{role key}` (line 19) is used nowhere in the file — all bindings use --color-* semantic tokens — matching enhancement #4's inconsistency from the project side (project-yaml notes).

26. **Likely inherited contrast bug in the seed from the panels pastel→stronger flip.** Light modes of clarity/default/punctuation/statement bind tile-ink-1/2 to near-black ink over tile-ground-1/2 = panels-a/g = stronger-indigo (#2B3A6B) / stronger-slate (#3D4A6B) — dark ink on dark grounds; the inks read as leftovers from when panels-a/g were pastels. No committed check can catch this; contrast is left to the render-proof eyeball (machinery notes; seed yaml:268-289,904,950).

27. **~500 lines of commented-out mirror dark-mode blocks per non-flipping theme (both YAMLs).** A deliberate documented convention, invisible to the semantic hash — but the blocks are exact duplicates of the light bindings that will drift silently when light bindings change (seed ~30% of 1770 lines; SkillSpoke yaml:1128-1173 et al.).

28. **Command/skill and agent internal contradictions in the support layer.** commands/generate-stylesheets.md:21 keys determinism on "(elements YAML bytes, reference tree bytes)" — the stale pre-semantic-hash wording vs the skill's semantic keying (SKILL.md:88). agents/cds-ui-author.md's frontmatter (tools incl. WebFetch; skills incl. package-change) contradicts its body's "Tool / skill scope" (Read/Glob/Grep only; three skills). agents/cds-code-companion.md lists five halt codes neither of its two skills can emit. setup has two coded-halt gaps (finding in §4).

29. **apply-design-system promises an "Event hooks" section sourced verbatim from components.md** — whether components.md actually defines event hooks is unverified and an empty-section risk (support notes).

30. **The test suite is hardwired to the monorepo layout and violates the errors-visible rule once.** Every check computes repo_root three levels above test/ and re-derives `<root>/plugins/cds`, so the suite only runs in the toolset marketplace tree; run-tests.sh line 35 uses `2>/dev/null`. Minor prose drift: test/README.md enumerates 8 of the 11 actual checks; lint-elements.py prints its checks in the order 1,2,4,0,3,5,6.

31. **Cross-file artifacts the audit confirms exist (dependencies of the skills' claims):** lib/cds_hash.py, validation/customizable-design-elements.schema.json, setup/customizable-design-elements.yaml, test/checks/check_token_coverage.py, compliance.md §23 rules #15/#18/#19, layout.md §11.2/§11.3, motion.md §15.4/§15.5, implementation.md §8.4, components.md §12.1/§12.2, and skills/compose-page/reference/landing-sections-shape-rules.md — all present. The enhancement doc's citation of "components.md §16.4" is the one dangling reference (no §16 exists).

32. **Residual a11y-claim confusion in components.md.** The repeated hedge "host-project implementations targeting WCAG 2.5.5 AAA should ship at ≥44×44px to clear the WCAG 2.1 AA tap-target floor" conflates the AAA target size with an AA floor (components.md:781,1211).

33. **Naming and data hygiene in the YAML layer.** `--color-common_colors-black` mixes an underscore into otherwise kebab-case var names; green/red ramps omit `name` on their 000/1000 entries while neutral/blue name all 21; panels keys are opaque letters a–g with a shadow alternate configuration kept commented out; the statement theme uniquely binds accent-primary → --color-accent-interactive (deliberate max-contrast choice, but the only accent-key crossing) (project-yaml notes).

34. **The schema restricts YAML binding modes to light|dark while the runtime mode universe is light|dark|system.** Two different "mode" universes: binding modes (schema.json:570-593) vs the data-mode values assemble.py discovers and the switcher wires (assemble.py:76-89) — reconcilable but undeclared.

---

## 7. Values-parity baseline

Canonical inventory of the live SkillSpoke elements YAML (`/Users/msat1971/projects/SkillSpoke/app/SkillSpoke/.customizable-design-elements.yaml`, schema 1.0.0). Every value below must survive the rebuild.

### Conventions

`color_var_pattern` `--color-{palette key}-{color key}`; `typeface` `--typeface-{typeface key}`; `font` `--font-{font key}`; `role` `--role-{role key}` (NOTE: the role pattern is dead — nothing uses `--role-*`).

### common_colors (Discrete, 2)

white `#FFFFFF`, black `#000000`

### Primitive RAMPS (21 steps each, keys 000/050/…/950/1000)

**neutral** (warm): `#FFFFFF #FAF9F5 #F5F4ED #F0EEE6 #E8E6DC #DEDCD1 #D1CFC5 #C2C0B6 #B0AEA5 #9C9A92 #87867F #73726C #5E5D59 #4D4C48 #3D3D3A #30302E #262624 #1F1E1D #1A1918 #141413 #000000`

**blue** (cool): `#FFFFFF #F8F9FC #F1F4F9 #EAEEF5 #E0E6F1 #D4DCEB #C4CFE4 #B2C1DB #9CAFD0 #6A9BCC #6B86B6 #5371A9 #3D5C95 #3D4A6B #2B3A6B #1D2F50 #162541 #111E35 #0D192E #0A1426 #000000`

**green** (cool): `#FFFFFF #F7FAF9 #F1F5F3 #E9F0ED #DFE8E5 #D2DFDB #BCD1CA #AFC6BE #98B6AC #7FA397 #629987 #497E6E #2F6959 #255649 #1D453A #15372E #102C24 #0B231D #081E18 #061813 #000000`

**red** (warm rose): `#FFFFFF #FCF8F9 #F9F2F3 #F5EBED #F0E1E4 #EAD6DA #E2C7CC #D9B5BC #CDA0AA #BF8895 #B17080 #A1586B #8C4156 #743446 #6B1F2A #5A1F3D #3D1823 #32121B #2B0F17 #230B12 #000000`

(green/red 000 and 1000 entries omit `name`, inconsistent with neutral/blue which name every step.)

### Primitive DISCRETES

**burnt-orange** (4): primary `#F46C5D`, interactive `#E35849`, hover `#E05446`, dark `#DE5D4E`

**pastel** (10): oat `#E3DACC`, peach `#EBC9B7`, coral `#EBCECE`, fig `#C46686`, olive `#788C5D`, mineral `#629987`, cactus `#BCD1CA`, sky `#6A9BCC`, heather `#CBCADB`, plum `#827DBD`

**stronger** (7): indigo `#2B3A6B`, violet `#4B2E6B`, crimson `#6B1F2A`, umber `#7A4A28`, wine `#5A1F3D`, espresso `#3E2418`, slate `#3D4A6B`

**saturated** (5): error-light `#B53333`, error-dark `#DF6666`, error-fill `#BF4D43`, required `#8A2424`, focus-blue `#2C84DB`

### Semantic palettes (alias targets)

**accent** (4): primary/interactive/hover/dark → burnt-orange same-key.

**panels** (7 live): a→stronger-indigo, b→stronger-violet, c→stronger-crimson, d→stronger-umber, e→stronger-wine, f→stronger-espresso, g→stronger-slate. Commented alternate: a–j → pastel oat/peach/coral/fig/olive/mineral/cactus/sky/heather/plum.

**buttons** (16): primary-bg-brand→blue-750, primary-bg-frost→blue-050, primary-bg-ink→common_colors-black, primary-bg-light→neutral-050, primary-txt-frost→blue-050, primary-txt-brand-ink→blue-950, primary-txt-light→neutral-050, primary-txt-ink→neutral-950, secondary-bg-pale→blue-150, secondary-bg-light→blue-200, secondary-bg-brand→blue-750, secondary-bg-slate→neutral-700, secondary-txt-slate→blue-650, secondary-txt-frost→blue-050, secondary-txt-light→neutral-050, tertiary-border→neutral-400.

**backgrounds** (19): pure→neutral-000, ivory→neutral-050, linen→neutral-100, cream→neutral-150, beige→neutral-200, sand→neutral-250, tan→neutral-300, charcoal→neutral-700, graphite→neutral-750, dark→neutral-800, deeper→neutral-850, near-black→neutral-900, ink→neutral-950, brand-navy→blue-750, brand-deep→blue-800, brand-midnight→blue-850, brand-night→blue-900, brand-ink→blue-950, absolute-black→neutral-1000.

**text** (14): ivory→neutral-050, tan→neutral-300, warm-gray→neutral-400, gray→neutral-450, dim→neutral-600, deep-gray→neutral-650, graphite→neutral-750, dark→neutral-800, ink→neutral-950, black→common_colors-black, frost→blue-050, powder→blue-400, cornflower→blue-500, brand-ink→blue-950.

**borders** (12): soft→neutral-300, tan→neutral-350, warm-gray→neutral-400, gray→neutral-450, mid→neutral-500, dim→neutral-550, deep→neutral-600, charcoal→neutral-700, dark→neutral-800, pale→blue-300, royal→blue-600, powder→blue-400.

**signals** (5): focus→saturated-focus-blue, error→saturated-error-fill, error-text→saturated-error-light, error-text-dark→saturated-error-dark, required→saturated-required.

**status** (3): positive→pastel-mineral, caution→pastel-peach, critical→saturated-error-fill.

### Typefaces & fonts

host-grotesk "Host Grotesk" variable w300–900 italic:true; literata "Literata" variable w300–900 opsz 7–72 italic:true; red-hat-mono "Red Hat Mono" variable w300–700 italic:false.

Fonts: sans→host-grotesk / "system-ui, sans-serif"; serif→literata / "Georgia, serif"; mono→red-hat-mono / "ui-monospace, monospace".

### Roles (43, all type:color, all required:true)

**Semantic (19):** surface-primary/secondary/tertiary/raised/muted (family surface, from backgrounds; surface-primary constraint "AAA contrast against text-primary on every theme"); text-primary/secondary/tertiary/inverse (family text, from text; text-primary AAA vs surface-primary, text-tertiary AA); border-subtle/strong (borders); accent-primary/interactive (accent); accent-heroes (from_palette [accent, text] — the only list-valued from_palette); selection-bg (accent; fallback color-mix 50% accent-primary/transparent); focus-ring (borders); error-text, error-fill, field-required (family state, signals).

**Component (24):** input-focus-ring (input), nav-bg/nav-text (topbar), footer-bg/footer-text (footer), hero-bg/hero-text (hero), button-primary-bg/-text, button-secondary-bg/-text, button-tertiary-border (buttons), switch-active-bg (switch, signals), tile-ground-1/2/3/accent + tile-ink-1/2/3/accent (feature-tile; grounds from panels except tile-ground-accent from accent; inks from text), status-positive/caution/critical-bg (badge, status).

### Themes (8) — light/dark bindings (semantic-token form)

**clarity** (dual-mode). LIGHT: surfaces ivory/pure/linen/pure/linen; text ink/graphite/dim/frost; borders tan/charcoal; accent primary/interactive/primary; focus-ring gray; btn-primary brand/frost; btn-secondary pale/slate; tertiary-border; switch focus; selection accent-primary; input-focus focus; nav ivory/ink; footer brand-navy/powder; hero pure/ink; error error-text-dark/error; required; tiles 1:a/ink 2:g/ink 3:d/ivory accent:accent-primary/ivory; status positive/caution/critical. DARK: surfaces brand-midnight/brand-deep/brand-deep/brand-midnight/brand-deep; text frost/powder/cornflower/brand-ink; borders royal/pale; accent dark/hover/frost; focus powder; btn-primary frost/brand-ink; btn-secondary brand/frost; selection accent-dark; nav brand-midnight/frost; footer brand-navy/powder; hero brand-midnight/frost; error error-text/error; tiles 1:d/ivory 2:a/ivory 3:e/ivory accent:accent-dark/ivory.

**default** (dual-mode; principal). LIGHT: surfaces linen/ivory/cream/pure/cream; text ink/graphite/dim/frost; borders warm-gray/charcoal; accent primary/interactive/primary; focus gray; btn-primary brand/frost; btn-secondary light/slate; nav linen/ink; footer brand-navy/powder; hero ivory/ink; selection accent-primary; error error-text-dark/error; tiles as clarity-light. DARK: surfaces brand-ink/brand-night/brand-deep/brand-midnight/brand-night; text frost/powder/cornflower/brand-ink; borders royal/pale; accent dark/hover/frost; focus powder; btn-primary frost/brand-ink; btn-secondary brand/frost; nav brand-ink/frost; hero brand-ink/frost; footer brand-navy/powder; selection accent-dark; error error-text/error; tiles as clarity-dark.

**editorial**: alias of default, no bindings.

**punctuation** (light-only; dark mirrors, commented): surfaces cream/beige/sand/ivory/beige; text ink/graphite/dim/frost; borders gray/charcoal; focus-ring dim; nav cream/ink; hero cream/ink; btn-secondary light/slate; else as default-light pattern (footer brand-navy/powder, tiles a/g/d/accent).

**statement** (light-only): surfaces beige/sand/tan/ivory/sand; text black/dark/deep-gray/frost; borders mid/dark; accent-primary→accent-INTERACTIVE (unique), accent-interactive interactive, heroes primary; focus deep; btn-primary INK/light (max-contrast); selection accent-interactive; nav beige/black; hero beige/black; tiles a/ink g/ink d/ivory accent-primary/ivory.

**feature-dark** (light-only): surfaces dark/graphite/charcoal/dark/graphite; text ivory/tan/warm-gray/ink; borders mid/soft; accent dark/hover/ivory; focus soft; btn-primary light/ink; btn-secondary slate/light; nav dark/ivory; hero dark/ivory; error error-text; tiles d/a/e all ivory ink, accent:accent-dark/ivory.

**code** (light-only): surfaces deeper/dark/charcoal/deeper/dark; text ivory/tan/gray/ink; borders dim/soft; accent dark/hover/ivory; focus warm-gray; btn-primary light/ink; btn-secondary slate/light; nav deeper/ivory; hero deeper/ivory; tiles d/a/e ivory, accent dark/ivory.

**deep** (light-only): surfaces ink/near-black/dark/deeper/near-black; text ivory/tan/gray/ink; borders deep/soft; accent dark/hover/ivory; focus soft; footer brand-navy/powder; btn-primary light/ink; btn-secondary slate/light; nav ink/ivory; hero ink/ivory; tiles d/a/e ivory, accent dark/ivory.

**Constant across ALL themes/modes:** switch-active-bg=signals-focus, input-focus-ring=signals-focus, footer-bg=brand-navy, footer-text=powder, field-required=signals-required, error-fill=signals-error, status positive/caution/critical.

### Scope of this file

No dimensions, spacing, typography sizes, geometry, or motion live in the SkillSpoke YAML — it is colors, typefaces, font-role bindings, roles, and themes only. The plugin's frozen-dimension problem cannot originate here; all sizes live in plugin references or generated stylesheets. Theme roles semantic in nature: `interjection` (punctuation = light interjection, feature-dark = dark interjection, code = deeper-dark interjection) and `scroll rhythm` ordering are documented in the theme comments (yaml:1069-1073, 1284-1288, 1391-1396) and are part of the design intent this baseline carries.
