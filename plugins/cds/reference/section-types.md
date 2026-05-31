# Section types

Section types are purpose-defined units of a landing page; many section types map to many shapes and a single section type can map to multiple shapes — see `../skills/compose-page/reference/landing-sections-shape-rules.md` for the picker.

## Part B — Catalog

| #   | Section type            | Purpose |
|-----|-------------------------|---------|
| T1  | Hero                    | Primary value prop + first CTA |
| T2  | Trust Strip             | Validation via customer/brand logos (no quotes) |
| T3  | Validation Block        | Validation via customer quotes (with or without logos) |
| T4  | Capability Showcase     | What the product can do (features, surfaces, tools) |
| T5  | Workflow / Process      | How the product is used, step by step |
| T6  | Use-Case Routing        | Which audience/role/job this is for |
| T7  | Path Fork               | Binary fork in the funnel (self-serve vs assisted) |
| T8  | Interactive Demo        | Let the visitor see/try the product output |
| T9  | Pricing                 | Investment tiers or usage rates |
| T10 | Trust Detail            | Security, governance, deployment, controls |
| T11 | FAQ                     | Anticipated operational/technical questions |
| T12 | News / Updates          | Recent releases, changelog, announcements |
| T13 | Resource Directory      | Docs, blog posts, guides — content surface to deepen engagement |
| T14 | Cross-Promo             | Surface another product or feature inline |
| T15 | Sub-Hero                | Mid-page restatement of value prop + secondary CTA |
| T16 | Final CTA               | Closing conversion attempt |
| T17 | Footer                  | Global navigation, legal, copyright |
| T18 | Section Header / Eyebrow| Standalone label preceding another content unit |

---

## `content_meta` schema (full)

The `content_meta` object carries the secondary signals that disambiguate the shape choice when a section type maps to multiple shapes. Field types:

```text
content_meta: {
  item_count:                int           # number of items in this section
  has_visual_per_item:       bool          # each item has a substantial image/screenshot/video
  has_metric_per_item:       bool          # each item carries a quantified result (e.g., "13% lift")
  copy_density_per_item:     "short" | "medium" | "long"   # blurb size
  taxonomy_type:             "discipline" | "role" | "workload" | "surface" | null
  has_source_tag_per_item:   bool          # items belong to typed sources (docs/blog/etc.)
  has_segment_toggle:        bool          # e.g., Individual ↔ Team toggle for pricing
  has_emphasis_item:         bool          # one item is meant to lead the rest
  has_newsletter_capture:    bool          # T16 only — closing form captures email for newsletter
  has_download_upgrade_path: bool          # T16 only — closing path is platform download + paid upgrade
}
```

`has_newsletter_capture` and `has_download_upgrade_path` are only consulted for T16 Final CTA — see T16 below.

---

## T1 — Hero

**Purpose.** Primary value prop + first CTA.

**`content_meta` fields consulted.** None of the listed `content_meta` fields branch T1's shape pick directly; the branching signal is the visual type carried by the section (video / screenshot / code-or-install snippet / chat input or live affordance).

**Default + alternate shapes.** Visual = video → S1 (alt S28); visual = screenshot → S2 (alt S1); visual = code/install snippet → S3 (alt S1); visual = chat input / live affordance → S3. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T2 — Trust Strip

**Purpose.** Validation via customer/brand logos (no quotes).

**`content_meta` fields consulted.** `item_count` (logos-only set: ≥ 10 vs. ≤ 8).

**Default + alternate shapes.** items ≥ 10, logos only → S9 (alt S4); items ≤ 8, logos only → S4 (alt S9). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T3 — Validation Block

**Purpose.** Validation via customer quotes (with or without logos).

**`content_meta` fields consulted.** `item_count`; `has_metric_per_item`; presence of logos alongside metrics.

**Default + alternate shapes.** count = 1, big metric → S13 (alt S11); count = 3, qualitative → S11; count ≥ 5, with metrics + logos → S12 (alt S11). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T4 — Capability Showcase

**Purpose.** What the product can do (features, surfaces, tools).

**`content_meta` fields consulted.** `item_count`; `has_visual_per_item`; `copy_density_per_item`; `taxonomy_type` (categorical-pill case).

**Default + alternate shapes.** count = 3, short blurbs, no big visual → S4 (alt S5); count = 4, distinct categories → S5 (alt S4); count = 2–4, substantial copy + substantial visual per item → S7 (alt S6); count = 5–6, distinct visual per item → S6 (alt S7); count ≥ 10 → S8 (alt S22); items are categorical pills, no visuals → S22 (alt S4). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T5 — Workflow / Process

**Purpose.** How the product is used, step by step.

**`content_meta` fields consulted.** Step count (mapped to `item_count`).

**Default + alternate shapes.** step_count = 3 → S10; step_count ≠ 3 → S6 (alt = a vertical numbered list, or split into two T5 sections). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T6 — Use-Case Routing

**Purpose.** Which audience/role/job this is for.

**`content_meta` fields consulted.** `item_count`; `taxonomy_type` (role / discipline); presence of sub-items per category.

**Default + alternate shapes.** count = 3–4, role/discipline tagged → S5 (alt S4); count ≥ 5 categories with sub-items → S22. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T7 — Path Fork

**Purpose.** Binary fork in the funnel (self-serve vs assisted).

**`content_meta` fields consulted.** `item_count` (= 2 by definition for the binary fork).

**Default + alternate shapes.** count = 2 → S20. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T8 — Interactive Demo

**Purpose.** Let the visitor see/try the product output.

**`content_meta` fields consulted.** Demo format (prompt → artifact, vs. multi-surface with one screenshot per surface).

**Default + alternate shapes.** format = prompt → artifact → S25 (alt S6); format = multi-surface (one screenshot per surface) → S6 (alt S7). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T9 — Pricing

**Purpose.** Investment tiers or usage rates.

**`content_meta` fields consulted.** Pricing model (subscription tiers vs. usage rates); `has_segment_toggle`.

**Default + alternate shapes.** model = subscription tiers, segments present → S15; model = usage rates → S16 (alt S15). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T10 — Trust Detail

**Purpose.** Security, governance, deployment, controls.

**`content_meta` fields consulted.** Composite signal — multiple controls + visual.

**Default + alternate shapes.** composite (multiple controls + visual) → S21 (alt S4). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T11 — FAQ

**Purpose.** Anticipated operational/technical questions.

**`content_meta` fields consulted.** None; T11 always uses the accordion shape regardless of content properties.

**Default + alternate shapes.** any → S14. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T12 — News / Updates

**Purpose.** Recent releases, changelog, announcements.

**`content_meta` fields consulted.** `item_count`; `has_emphasis_item` (one featured + secondary cards).

**Default + alternate shapes.** count = 3 → S4 (alt S8); count ≥ 4 → S8 (alt S23); one featured + secondary cards → S23 (alt S8, with "3-card strip and carousel" as a tentative unbound alternate). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T13 — Resource Directory

**Purpose.** Docs, blog posts, guides — content surface to deepen engagement.

**`content_meta` fields consulted.** `has_source_tag_per_item`.

**Default + alternate shapes.** items have source-type tags → S24 (alt S5). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T14 — Cross-Promo

**Purpose.** Surface another product or feature inline.

**`content_meta` fields consulted.** Format (narrow banner vs. event/register card with thumbnail).

**Default + alternate shapes.** format = narrow banner → S17; format = event/register card with thumbnail → embedded inside T10 (alt S17). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T15 — Sub-Hero

**Purpose.** Mid-page restatement of value prop + secondary CTA.

**`content_meta` fields consulted.** Composition signal — video + text + CTA.

**Default + alternate shapes.** video + text + CTA → S28 (alt S1). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T16 — Final CTA

**Purpose.** Closing conversion attempt.

**`content_meta` fields consulted.** `has_newsletter_capture` (bool) and `has_download_upgrade_path` (bool). These two T16-only booleans drive the shape pick. T16 may also be omitted entirely on browse-mode pages — see the decision table.

**Default + alternate shapes.** `has_newsletter_capture = true` → S19 (alt S18 dark); `has_download_upgrade_path = true` → S18 light (alt S26); omitted on browse-mode page → none. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T17 — Footer

**Purpose.** Global navigation, legal, copyright.

**`content_meta` fields consulted.** None; T17 always uses S27.

**Default + alternate shapes.** always → S27. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T18 — Section Header / Eyebrow

**Purpose.** Standalone label preceding another content unit.

**`content_meta` fields consulted.** None; T18 always uses S0.

**Default + alternate shapes.** always → S0. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## Known gaps

- Which `content_meta` fields branch each section type is expressed indirectly via the Part C decision table. Per-type field requirements (which fields are required vs. optional vs. ignored) are not declared explicitly — the listings above are derived from the decision-table rows.
- T8 demo "format" and T9 pricing "model" are dimensions used in the decision rows but are not part of the `content_meta` schema; they need their own field definitions in a future revision.
- T1 hero "visual = …" categories (video / screenshot / code-or-install / chat-input) are likewise outside the `content_meta` schema.
- T14 cross-promo's alternate "embedded inside T10" is not a shape — it is a composition note. Carry forward in landing-sections-shape-rules.md.
