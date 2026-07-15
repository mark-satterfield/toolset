---
kind: page-constraint
name: variety-principle
page_family: landing
status: stable
applies_to: { page_families: [landing], pages: [] }
check: |
  Reject a Shape candidate whose rendered dimensions would repeat the
  immediately preceding Section's combination — same structural pattern and
  same alignment and same density. Theme and background are not variety
  dimensions and are never grounds for rejection under this constraint.
---

# The Variety Principle

**No two adjacent Sections may look alike.** This is the landing page's identity. Across the page, vary these dimensions Section-to-Section:

| Dimension | Values to draw from |
|---|---|
| Surface treatment | solid or textured |
| Width | `u-container` (page width, default) or `u-container-full` (full-bleed) (`foundations/layout.md`) |
| Headline measure | any `ch` measure (`foundations/typography.md`) |
| Body measure | any `ch` measure, independent of the headline |
| Type role | any type role in `foundations/typography.md` |
| Alignment | any alignment register (shape-set conventions) |
| Density | sparse → packed |
| Structural pattern | any Shape in the library |
| Section padding | the `--section-pad-*` scale |
| Radius (where containers round) | the `--radius-*` scale |

**Combine freely.** Every Section is a fresh composition decision; no combination repeats across adjacent Sections. Unless a Shape is intentionally centered, alternate its alignment — a two-column Shape mirrors its text/visual sides relative to the previous two-column Section.

**Theme and background are NOT variety dimensions.** The principal theme stays constant for the whole page; grounds follow `ground-alternation`; theme islands are declared on the Page.

## As a validator

Reject a Shape candidate whose rendered dimensions would repeat the immediately preceding Section's combination (same structural pattern + same alignment + same density). On rejection the rule engine tries the next candidate; on exhaustion the composer fallback-generates a layout that satisfies the variety dimensions.
