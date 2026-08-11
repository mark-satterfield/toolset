---
kind: component
name: media-header-card
aliases: [tinted header card, model card, illustrated card, banner card, header-image card]
status: stable
slots:
  - { name: media-header, required: true, accepts: [svg-glyph, image] }
  - { name: title, required: true, accepts: [heading] }
  - { name: title-badge, required: false, accepts: [inverted-pill-badge, outline-pill-badge] }
  - { name: tags, required: false, accepts: [outline-pill-badge] }
sizing:
  header-aspect: "16 / 9 at the card's full inline width, bleeding to the card's edges"
  header-radius: "--radius-lg on the block-start corners only; the card's own radius on the block-end corners"
  body-padding: "--sp-1"
  title-gap: "--sp-0-5 between the title row and the tag run"
  tag-gap: "--sp-0-25 between adjacent tags"
behavior:
  - "the whole card is one target; hover raises it one elevation step over --duration-150"
  - "static media at rest — an animated header honors the animated-media contract (foundations/imagery.md §16.5)"
accessibility:
  - "the card's target is a single link whose accessible name is the title; the media header is decorative and aria-hidden"
  - "the title is the card's heading at the level its surrounding run establishes"
  - "tags are content, not controls"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --tile-ground-1, --tile-ink-1, --radius-lg, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5, --sp-1]
composite: false
---

# Media header card

A card opening with a full-bleed tinted band carrying one centered mark, then a title with an optional inline badge, then a wrapping run of tags describing what the subject is for. The band gives each card in a run its own identity while the bodies stay uniform.

The band's ground is a theme-bound `tile-ground-*` role constrained to the `panels` palette (`foundations/imagery.md` §16.4) — the author picks a ground number, the theme decides the color, and the mark inside inherits the paired `tile-ink-*` so it recolors with the band.

Distinct from the editorial featured card (`libraries/components/editorial-featured-card.md`), which pairs an illustration tile with a dek and a date for a piece of writing. This card describes a thing you can use, and its tags are its capabilities.

## Variants

- `header-content`: `mark` (default — one centered glyph on the tinted ground) | `image` (a photographic or screenshot fill, `.webp` per `foundations/imagery.md` §16.3).
- `target`: `whole-card` (default — the card is one link) | `inert` (the card is a container with no target of its own).

## Determinations

- Card: ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-lg)`, body padding `var(--sp-1)`.
- The media header bleeds to the card's inline edges at a 16:9 ratio and takes the card's radius on its block-start corners only, so the band and the card read as one object.
- The mark inside the band is centered on both axes and drawn on the `--icon-viewbox-xl` grid, painting via `currentColor` so it inherits the band's `tile-ink-*`.
- Title at the body size, weight 700, ink `var(--text-primary)`. The optional badge sits inline after the title on the same line, separated by `var(--sp-0-5)`, and wraps with it.
- The tag run is a wrapping row of hairline pill badges with `var(--sp-0-25)` between adjacent tags, `var(--sp-0-5)` below the title row. Tags wrap onto as many rows as they need; the cards in a run align on their title, not on their last tag row.
- Hover raises the card one elevation step (`foundations/layout.md` §11.8) over `var(--duration-150)` `var(--ease-in-out)`. Nothing inside the card moves.

## Accessibility

- In the `whole-card` variant the card's target is a single `<a>` whose accessible name is the title; the link is stretched over the card's box rather than the whole card being wrapped, so the tags and badge stay outside the link's name. The media header carries `aria-hidden="true"` — it identifies, it does not inform.
- The title is a heading at the level the surrounding run establishes, so a run of cards reads as a list of peers rather than a nesting.
- Tags are plain text content. A tag that filters the run is a filter chip (`libraries/components/filter-chip.md`), not a badge.
- Focus paints the foundation ring on `:focus-visible` around the whole card, not around the invisible link box (`foundations/accessibility.md` §18.2).
- Reduced motion suppresses the hover raise (WCAG 2.3.3).
