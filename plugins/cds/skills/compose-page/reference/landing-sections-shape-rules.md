# Landing-section shape rules

## Scope

This file's composition rules apply to **landing pages only**. The named-shape catalog and the `pick_shape` decision rules are scoped to landing pages; other page types are supplied via the plugin reference or the project extensions dir.

---

## Part D — pick_shape function

```text
pick_shape(section_type, content_meta, page_meta) -> Shape[]
```

```text
section_type: T# from the catalog above

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

page_meta: {
  buying_mode:               "commit" | "browse"
  position_in_page:          "top" | "mid" | "late"
}

returns: ordered Shape[]   # primary first, then valid alternates
```

`content_meta` fields are the secondary signals that disambiguate when one section type has multiple valid shapes (the common case — most section types have 2-4 valid shapes). The function consults the Part C decision table.

---

## Part C — Decision table: (section_type + content_meta) → shapes

| Section type        | Content property                                            | Primary shape | Alternates |
|---------------------|-------------------------------------------------------------|---------------|------------|
| T1 Hero             | visual = video                                              | centered-stack            | sub-hero-split |
| T1 Hero             | visual = screenshot                                         | split-text-media            | centered-stack |
| T1 Hero             | visual = code/install snippet                               | centered-affordance            | centered-stack |
| T1 Hero             | visual = chat input / live affordance                       | centered-affordance            | — |
| T2 Trust Strip      | items ≥ 10, logos only                                      | logo-marquee            | card-grid |
| T2 Trust Strip      | items ≤ 8, logos only                                       | card-grid            | logo-marquee |
| T3 Validation       | count = 1, big metric                                       | feature-quote           | stacked-quotes |
| T3 Validation       | count = 3, qualitative                                      | stacked-quotes           | — |
| T3 Validation       | count ≥ 5, with metrics + logos                             | quote-swiper           | stacked-quotes |
| T4 Capability       | count = 3, short blurbs, no big visual                      | card-grid            | tagged-card-grid |
| T4 Capability       | count = 4, distinct categories                              | tagged-card-grid            | card-grid |
| T4 Capability       | count = 2–4, substantial copy + substantial visual per item | alternating-rows            | tabbed-panels |
| T4 Capability       | count = 5–6, distinct visual per item                       | tabbed-panels            | alternating-rows |
| T4 Capability       | count ≥ 10                                                  | card-carousel            | tag-columns |
| T4 Capability       | items are categorical pills, no visuals                     | tag-columns           | card-grid |
| T5 Workflow         | step_count = 3                                              | numbered-steps           | — |
| T5 Workflow         | step_count ≠ 3                                              | tabbed-panels | a vertical numbered list, or split into two T5 sections. |
| T6 Use-Case Routing | count = 3–4, role/discipline tagged                         | tagged-card-grid            | card-grid |
| T6 Use-Case Routing | count ≥ 5 categories with sub-items                         | tag-columns           | — |
| T7 Path Fork        | count = 2                                                   | two-path-fork           | — |
| T8 Demo             | format = prompt → artifact                                  | prompt-artifact           | tabbed-panels |
| T8 Demo             | format = multi-surface (one screenshot per surface)         | tabbed-panels            | alternating-rows |
| T9 Pricing          | model = subscription tiers, segments present                | pricing-tiers           | — |
| T9 Pricing          | model = usage rates                                         | rate-table           | pricing-tiers |
| T10 Trust Detail    | composite (multiple controls + visual)                      | pictogram-subcards           | card-grid |
| T11 FAQ             | any                                                         | accordion           | — |
| T12 News            | count = 3                                                   | card-grid            | card-carousel |
| T12 News            | count ≥ 4                                                   | card-carousel            | lead-plus-carousel |
| T12 News            | one featured + secondary cards                              | lead-plus-carousel           | card-carousel, 3-card strip and carousel), |
| T13 Resource Directory | items have source-type tags                              | resource-grid           | tagged-card-grid |
| T14 Cross-Promo     | format = narrow banner                                      | banner-strip           | — |
| T14 Cross-Promo     | format = event/register card with thumbnail                 | embedded inside T10 | banner-strip |
| T15 Sub-Hero        | video + text + CTA                                          | sub-hero-split           | centered-stack |
| T16 Final CTA       | `has_newsletter_capture = true`                             | cta-newsletter           | cta-panel (dark) |
| T16 Final CTA       | `has_download_upgrade_path = true`                          | cta-panel (light)   | install-buttons |
| T16 Final CTA       | omitted (browse-mode page)                                  | (none)        | — |
| T17 Footer          | always                                                      | footer-grid           | — |
| T18 Section Header  | always                                                      | heading-strip            | — |

> **T16 note:** The T16 rows key on the explicit `content_meta` booleans `has_newsletter_capture` and `has_download_upgrade_path` rather than on an audience facet.

---
