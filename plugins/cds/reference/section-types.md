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

**Default + alternate shapes.** Visual = video → centered-stack (alt sub-hero-split); visual = screenshot → split-text-media (alt centered-stack); visual = code/install snippet → centered-affordance (alt centered-stack); visual = chat input / live affordance → centered-affordance. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T2 — Trust Strip

**Purpose.** Validation via customer/brand logos (no quotes).

**`content_meta` fields consulted.** `item_count` (logos-only set: ≥ 10 vs. ≤ 8).

**Default + alternate shapes.** items ≥ 10, logos only → logo-marquee (alt card-grid); items ≤ 8, logos only → card-grid (alt logo-marquee). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T3 — Validation Block

**Purpose.** Validation via customer quotes (with or without logos).

**`content_meta` fields consulted.** `item_count`; `has_metric_per_item`; presence of logos alongside metrics.

**Default + alternate shapes.** count = 1, big metric → feature-quote (alt stacked-quotes); count = 3, qualitative → stacked-quotes; count ≥ 5, with metrics + logos → quote-swiper (alt stacked-quotes). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T4 — Capability Showcase

**Purpose.** What the product can do (features, surfaces, tools).

**`content_meta` fields consulted.** `item_count`; `has_visual_per_item`; `copy_density_per_item`; `taxonomy_type` (categorical-pill case).

**Default + alternate shapes.** count = 3, short blurbs, no big visual → card-grid (alt tagged-card-grid); count = 4, distinct categories → tagged-card-grid (alt card-grid); count = 2–4, substantial copy + substantial visual per item → alternating-rows (alt tabbed-panels); count = 5–6, distinct visual per item → tabbed-panels (alt alternating-rows); count ≥ 10 → card-carousel (alt tag-columns); items are categorical pills, no visuals → tag-columns (alt card-grid). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T5 — Workflow / Process

**Purpose.** How the product is used, step by step.

**`content_meta` fields consulted.** Step count (mapped to `item_count`).

**Default + alternate shapes.** step_count = 3 → numbered-steps; step_count ≠ 3 → tabbed-panels (alt = a vertical numbered list, or split into two T5 sections). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T6 — Use-Case Routing

**Purpose.** Which audience/role/job this is for.

**`content_meta` fields consulted.** `item_count`; `taxonomy_type` (role / discipline); presence of sub-items per category.

**Default + alternate shapes.** count = 3–4, role/discipline tagged → tagged-card-grid (alt card-grid); count ≥ 5 categories with sub-items → tag-columns. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T7 — Path Fork

**Purpose.** Binary fork in the funnel (self-serve vs assisted).

**`content_meta` fields consulted.** `item_count` (= 2 by definition for the binary fork).

**Default + alternate shapes.** count = 2 → two-path-fork. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T8 — Interactive Demo

**Purpose.** Let the visitor see/try the product output.

**`content_meta` fields consulted.** Demo format (prompt → artifact, vs. multi-surface with one screenshot per surface).

**Default + alternate shapes.** format = prompt → artifact → prompt-artifact (alt tabbed-panels); format = multi-surface (one screenshot per surface) → tabbed-panels (alt alternating-rows). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T9 — Pricing

**Purpose.** Investment tiers or usage rates.

**`content_meta` fields consulted.** Pricing model (subscription tiers vs. usage rates); `has_segment_toggle`.

**Default + alternate shapes.** model = subscription tiers, segments present → pricing-tiers; model = usage rates → rate-table (alt pricing-tiers). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T10 — Trust Detail

**Purpose.** Security, governance, deployment, controls.

**`content_meta` fields consulted.** Composite signal — multiple controls + visual.

**Default + alternate shapes.** composite (multiple controls + visual) → pictogram-subcards (alt card-grid). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T11 — FAQ

**Purpose.** Anticipated operational/technical questions.

**`content_meta` fields consulted.** None; T11 always uses the accordion shape regardless of content properties.

**Default + alternate shapes.** any → accordion. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T12 — News / Updates

**Purpose.** Recent releases, changelog, announcements.

**`content_meta` fields consulted.** `item_count`; `has_emphasis_item` (one featured + secondary cards).

**Default + alternate shapes.** count = 3 → card-grid (alt card-carousel); count ≥ 4 → card-carousel (alt lead-plus-carousel); one featured + secondary cards → lead-plus-carousel (alt card-carousel). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T13 — Resource Directory

**Purpose.** Docs, blog posts, guides — content surface to deepen engagement.

**`content_meta` fields consulted.** `has_source_tag_per_item`.

**Default + alternate shapes.** items have source-type tags → resource-grid (alt tagged-card-grid). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T14 — Cross-Promo

**Purpose.** Surface another product or feature inline.

**`content_meta` fields consulted.** Format (narrow banner vs. event/register card with thumbnail).

**Default + alternate shapes.** format = narrow banner → banner-strip; format = event/register card with thumbnail → embedded inside T10 (alt banner-strip). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T15 — Sub-Hero

**Purpose.** Mid-page restatement of value prop + secondary CTA.

**`content_meta` fields consulted.** Composition signal — video + text + CTA.

**Default + alternate shapes.** video + text + CTA → sub-hero-split (alt centered-stack). See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T16 — Final CTA

**Purpose.** Closing conversion attempt.

**`content_meta` fields consulted.** `has_newsletter_capture` (bool) and `has_download_upgrade_path` (bool). These two T16-only booleans drive the shape pick. T16 may also be omitted entirely on browse-mode pages — see the decision table.

**Default + alternate shapes.** `has_newsletter_capture = true` → cta-newsletter (alt cta-panel dark); `has_download_upgrade_path = true` → cta-panel light (alt install-buttons); omitted on browse-mode page → none. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T17 — Footer

**Purpose.** Global navigation, legal, copyright.

**`content_meta` fields consulted.** None; T17 always uses footer-grid.

**Default + alternate shapes.** always → footer-grid. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---

## T18 — Section Header / Eyebrow

**Purpose.** Standalone label preceding another content unit.

**`content_meta` fields consulted.** None; T18 always uses heading-strip.

**Default + alternate shapes.** always → heading-strip. See `../skills/compose-page/reference/landing-sections-shape-rules.md`.

---
