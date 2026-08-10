---
kind: component
name: pricing-card
page_family: landing
aliases: [pricing card, tier card, plan card, subscription card]
status: stable
slots:
  - { name: pictogram, required: false, accepts: [svg-glyph] }
  - { name: title, required: true, accepts: [heading] }
  - { name: tagline, required: false, accepts: [text] }
  - { name: price, required: false, accepts: [text] }
  - { name: price-note, required: false, accepts: [text] }
  - { name: cta, required: false, accepts: [button] }
  - { name: inherits-line, required: false, accepts: [text] }
  - { name: feature-list, required: true, accepts: [text] }
sizing:
  padding: "--sp-1-5"
  pictogram: "--icon-size-feature on the --icon-viewbox-xl drawing grid"
  title-gap: "--sp-1-5 between the pictogram and the title"
  price-gap: "--sp-1 between the tagline and the price"
  cta-gap: "--sp-1-5 between the price block and the CTA"
  feature-list-divider: "a 1px top rule with --sp-1-5 of padding above the feature list"
  feature-row-gap: "--sp-0-75 between adjacent feature rows"
  check-gap: "--sp-0-75 between a feature's check glyph and its text"
behavior:
  - "static at rest; the card does not hover or animate"
  - "the CTA spans the card's full inner width so every tier presents the same commitment affordance"
accessibility:
  - "the feature list is a real <ul>; each check glyph is aria-hidden because the row's presence is the affirmative"
  - "the featured tier's emphasis is carried by an accessible name, not by the border alone"
  - "the price and its qualifying note are one announced unit, so a discounted headline price is never heard without its condition"
token_bindings:
  - --surface-raised
  - --border-subtle
  - --border-strong
  - --text-primary
  - --text-secondary
  - --text-tertiary
  - --accent-primary
  - --icon-size-feature
  - --radius-lg
  - --sp-0-75
  - --sp-1
  - --sp-1-5
composite: true
---

# Pricing card

One tier of an offering, stated top to bottom in the order a reader decides in: what it is, what it costs, how to take it, and what it includes.

The card composes a button (`libraries/components/button.md`) for its CTA and the system check glyph (`libraries/components/icon-glyphs.md`) for its feature rows. Several cards in a row are arranged by the pricing-tiers Shape (`libraries/shapes/pricing-tiers.md`), which owns the segment toggle above them.

## Anatomy

Top to bottom, each part supplied-or-absent except the title and the feature list:

1. **pictogram** — one mark identifying the tier, so tiers are distinguishable before a word is read.
2. **title** — the tier's name.
3. **tagline** — one line saying who the tier is for.
4. **price** — the headline figure at display scale.
5. **price-note** — the conditions attached to that figure: billing period, what a discount depends on, the alternative rate.
6. **cta** — one full-width action.
7. **inherits-line** — a single line naming the tier this one builds on, when the feature list states only the difference.
8. **feature-list** — the included capabilities, one per row, each affirmed by a check glyph.

## Variants

- `tier`: `default` (ground `--surface-raised` with a `1px solid --border-subtle` hairline) | `featured` (a `1px solid --border-strong` outline plus the `foundations/layout.md` §11.8 faint-elevation shadow, lifting the emphasized tier one step above its peers).
- `feature-list-mode`: `complete` (the list states everything the tier includes) | `incremental` (the `inherits-line` names the tier beneath and the list states only what this tier adds).

## Choosing the featured tier

Exactly one tier in a row carries `featured`. It is a composition decision made per row — the emphasized tier is whichever the offering wants chosen, not a fixed position — and the geometry is otherwise unchanged, so the cards still align on their titles, prices, and CTAs. A row with no featured tier is valid; a row with two is not, because the emphasis then marks nothing.

## Determinations

- Padding `var(--sp-1-5)`, radius `var(--radius-lg)`.
- The pictogram sits at the card's block-start edge at `--icon-size-feature`, painting via `currentColor`, `var(--sp-1-5)` above the title. Either every tier in a row carries a pictogram or none does.
- Title at the display-small role, ink `var(--text-primary)`. Tagline directly beneath at the compact body size, ink `var(--text-secondary)`.
- Price at the display role, ink `var(--text-primary)`, `var(--sp-1)` beneath the tagline. The price note sits directly beneath it at the caption size in `var(--text-tertiary)` and takes as many lines as its conditions need — the note is not a footnote, it is part of the price.
- The CTA spans the card's full inner width, `var(--sp-1-5)` beneath the price block. It is a primary button on the `featured` tier and a secondary button on `default` tiers, so the emphasized tier carries the dominant action.
- A `1px solid var(--border-subtle)` rule separates the CTA from the feature list, with `var(--sp-1-5)` of padding above the list.
- The inherits-line, when present, sits directly beneath that rule at the compact body size, weight 700, ink `var(--text-primary)` — it is a heading for the list, not a feature in it.
- Each feature row is a check glyph at the inline-start and its text beside it, `var(--sp-0-75)` apart, with `var(--sp-0-75)` between adjacent rows. Text wraps to the row's own hanging indent so continuation lines align with the first line, not with the glyph.
- The check glyph is `var(--accent-primary)` on every row. Absence is not drawn: a capability a tier lacks is omitted from its list, never listed with a cross. Cross-tier absence is what the comparison matrix is for (`libraries/shapes/comparison-matrix.md`).
- Cards in a row stretch to a common height and anchor their feature lists to a common block-start edge, so the lists begin on one line across the row however long the taglines run.

## Accessibility

- The feature list is a `<ul>` with one `<li>` per capability. Each check glyph carries `aria-hidden="true"` — the row's presence in the list is the affirmative, and a screen reader announcing "check" before every item adds nothing.
- The price and its note are one unit for assistive technology: the note is associated with the price rather than floating after it, so a discounted headline figure is never announced without the condition that produces it.
- The `featured` tier's emphasis reaches a non-visual reader: the card carries an accessible name or a visually-hidden line naming it as the emphasized tier. A border alone is invisible to a screen reader and to a high-contrast rendering that flattens it.
- Each CTA's accessible name identifies its tier, since several identical CTA labels in a row are indistinguishable out of context.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
