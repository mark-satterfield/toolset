# Landing-section shape rules

## Scope

This file's composition rules apply to **landing pages only**. The S0–S28 shape catalog and the `pick_shape` decision rules are scoped to landing pages and have no claim to coverage of other page types. See `## Known gaps` for the page types not yet covered.

---

## §19.1 Variety Principle

This document is a **style guide**, not a content guide. What content goes into a page and in what order is a marketing / product / business-analyst decision — outside this document's scope. What follows is the style rule for how a long, multi-section page (landing, marketing hub, anything that scrolls through several grounds) composes itself so that the page reads as varied and intentional rather than flat or templated.

Do not let two adjacent sections look alike. Treat the choice of every style dimension as a fresh composition decision per section, and vary across these dimensions section-to-section:

| Dimension | Draw from |
|---|---|
| Theme state | Any of the 8 themes (§6) |
| Surface treatment | Solid or textured |
| Width | `container` (1440px), `container-small` (960px), or full-bleed |
| Density | Sparse → packed |
| Alignment | Left-aligned with right-side artifact / centered headline + symmetric grid / asymmetric split / sticky-pane / tabbed-pane / marginalia rail |
| Structural pattern | N-up comparison grid, hairline-divided row stack, logo grid, poster surface holding one artifact, editorial split (light half + dark half within one section), sticky-pane, tabbed-pane, marginalia rail, centered headline + body + CTA, multi-column features, horizontal slider |
| Section padding | `small`, `main`, `large`, or `page-top` (§11.3) |
| Radius | Vary per surface role (§11.7); do not default everything to one radius |
| Text measure | Independent for headline and body (§13) |

Combine freely. Treat each section as its own composition. **Do not map "this kind of content uses this kind of section."** Pick the composition; let the content fill it.

For every asymmetric move on the page (offset artifact, unbalanced split, edge-anchored block), place a symmetric move (uniform N-up grid, centered comparison) elsewhere on the page. Alternate the two registers down the page so the rhythm reads as composed rather than accidental.

---

## §19.2 First and second section background rules

The first section of any long page uses the default page background for the current mode. The second section is **one step lighter in both modes** — moving toward white regardless of which mode the page is in. This subtle stratification lifts the second section off the page ground and signals that section grounds shift down the page.

Sections carry **themes**, not ramp steps — each theme supplies its own `--surface-primary`. "One step lighter" means choosing the next theme up the lightness order, never naming a neutral step.

| Mode | First section theme | Second section theme (one step lighter) |
|---|---|---|
| Light | `default` (principal light ground) | `clarity` (pure-white ground) |
| Dark | `default` (dark ground) | `code` or `feature-dark` |

Beyond the second section, the Variety Principle in §19.1 governs. There is no fixed sequence.

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
| T1 Hero             | visual = video                                              | S1            | S28 |
| T1 Hero             | visual = screenshot                                         | S2            | S1 |
| T1 Hero             | visual = code/install snippet                               | S3            | S1 |
| T1 Hero             | visual = chat input / live affordance                       | S3            | — |
| T2 Trust Strip      | items ≥ 10, logos only                                      | S9            | S4 |
| T2 Trust Strip      | items ≤ 8, logos only                                       | S4            | S9 |
| T3 Validation       | count = 1, big metric                                       | S13           | S11 |
| T3 Validation       | count = 3, qualitative                                      | S11           | — |
| T3 Validation       | count ≥ 5, with metrics + logos                             | S12           | S11 |
| T4 Capability       | count = 3, short blurbs, no big visual                      | S4            | S5 |
| T4 Capability       | count = 4, distinct categories                              | S5            | S4 |
| T4 Capability       | count = 2–4, substantial copy + substantial visual per item | S7            | S6 |
| T4 Capability       | count = 5–6, distinct visual per item                       | S6            | S7 |
| T4 Capability       | count ≥ 10                                                  | S8            | S22 |
| T4 Capability       | items are categorical pills, no visuals                     | S22           | S4 |
| T5 Workflow         | step_count = 3                                              | S10           | — |
| T5 Workflow         | step_count ≠ 3                                              | S6 | a vertical numbered list, or split into two T5 sections. |
| T6 Use-Case Routing | count = 3–4, role/discipline tagged                         | S5            | S4 |
| T6 Use-Case Routing | count ≥ 5 categories with sub-items                         | S22           | — |
| T7 Path Fork        | count = 2                                                   | S20           | — |
| T8 Demo             | format = prompt → artifact                                  | S25           | S6 |
| T8 Demo             | format = multi-surface (one screenshot per surface)         | S6            | S7 |
| T9 Pricing          | model = subscription tiers, segments present                | S15           | — |
| T9 Pricing          | model = usage rates                                         | S16           | S15 |
| T10 Trust Detail    | composite (multiple controls + visual)                      | S21           | S4 |
| T11 FAQ             | any                                                         | S14           | — |
| T12 News            | count = 3                                                   | S4            | S8 |
| T12 News            | count ≥ 4                                                   | S8            | S23 |
| T12 News            | one featured + secondary cards                              | S23           | S8, 3-card strip and carousel), |
| T13 Resource Directory | items have source-type tags                              | S24           | S5 |
| T14 Cross-Promo     | format = narrow banner                                      | S17           | — |
| T14 Cross-Promo     | format = event/register card with thumbnail                 | embedded inside T10 | S17 |
| T15 Sub-Hero        | video + text + CTA                                          | S28           | S1 |
| T16 Final CTA       | `has_newsletter_capture = true`                             | S19           | S18 (dark) |
| T16 Final CTA       | `has_download_upgrade_path = true`                          | S18 (light)   | S26 |
| T16 Final CTA       | omitted (browse-mode page)                                  | (none)        | — |
| T17 Footer          | always                                                      | S27           | — |
| T18 Section Header  | always                                                      | S0            | — |

> **T16 note:** The T16 rows key on the explicit `content_meta` booleans `has_newsletter_capture` and `has_download_upgrade_path` rather than on an audience facet.

---

## Known gaps

- This file carries composition rules for landing pages. Composition rules for other page types — Editorial Detail, Resource Index, Documentation, Conversion/Authentication, Application Shell — are not present here yet; add a page-type rules file (or extend this one) to enable them.
- The function consults the Part C decision table. `content_meta` fields are the secondary signals that disambiguate when one section type has multiple valid shapes (the common case — most section types have 2-4 valid shapes).
- T5 Workflow step_count ≠ 3 fallback: the "or split into two T5 sections" portion of the fallback is a composition instruction outside the Shape[] return type and needs a downstream decision (which shape is the canonical non-3 fallback).
- T12 News "one featured + secondary cards" lists "3-card strip and carousel" as a tentative alternate that is not yet bound to a shape ID.
- T14 Cross-Promo "format = event/register card with thumbnail" primary reads `embedded inside T10` — this is not a shape ID but a composition caveat; the table cannot strictly answer this row with a shape until the rule is restated.
- Variety Principle §19.1 references "§6 themes", "§11.3 section padding", "§11.7 surface role / radius", and "§13 text measure" — those numbered references point into the larger style guide and are not resolved inside this file.
- §19.2 section grounds are expressed as **themes** (`default`, `clarity`, `code`, `feature-dark`), not ramp steps — each theme supplies its own `--surface-primary`. The theme names are authoritative; the §6 theme namespace itself is not redefined here.
- Per-shape layout detail (column counts, padding, alignment, responsive-collapse, the S10 step-count overflow rule, and S18/S19 theme variants) is pinned per shape in `../../../reference/shapes.md`; this file defers to those determinations for composition.
