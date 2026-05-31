# Shapes

Shapes are spatial composition patterns for the grouped components that fill a single landing-page section — each shape is independent of what content fills it.

All shapes resolve their spacing, container widths, radii, breakpoints, motion, and accessibility contracts against `foundations/` (layout, responsive, motion, accessibility) and the component specs in `components.md`. Where a shape names a measurement below, it is a definitive determination consistent with those foundations: the 12-column grid above the 700px breakpoint dropping to 2 columns (and to a single column below 480px), section padding from the `--section-pad-*` scale, gaps from the `--sp-*` scale, and radii from the `--radius-*` scale.

## Part A — Catalog

| #   | Shape                              | One-line description |
|-----|------------------------------------|----------------------|
| S0  | Standalone heading strip           | Just an H2 (and optional eyebrow) acting as a section label, no content beneath |
| S1  | Centered text + visual below       | Headline + subhead + CTAs centered; visual (video/screenshot) sits below |
| S2  | Two-column text/visual             | Text + CTAs on one side, single visual on the other |
| S3  | Centered text + embedded affordance| Centered headline; interactive element (chat input, install snippet, prompt chips) sits where the visual would |
| S4  | Static card grid                   | N cards in M columns, identical card structure (icon/title/blurb/optional CTA) |
| S5  | Tagged card grid                   | S4 plus an eyebrow tag/pill above each card title |
| S6  | Tabs with one panel per tab        | Tab strip + a large panel that swaps; each tab gets a full visual |
| S7  | Alternating image+text rows        | Horizontal rows; image-left/text-right alternates each row |
| S8  | Horizontal carousel                | Card row with prev/next arrows; more items than fit on screen |
| S9  | Marquee strip                      | Continuously scrolling horizontal row (logos/icons); may duplicate items |
| S10 | Numbered step row                  | 3-column (occasionally more) row with explicit step ordering |
| S11 | 3-up stacked pull-quotes           | Three quote blocks stacked vertically, no card framing, attribution under each |
| S12 | Quote swiper with logos            | Rotating quote in a viewport; logo carousel beneath rotates in sync |
| S13 | Single hero quote                  | One large quote, often with metric, treated as a near-hero element |
| S14 | Accordion list                     | Collapsible items, each header expands to reveal answer; vertical stack |
| S15 | Tier card row + segment toggle     | Horizontal row of 2-4 tier cards; segment toggle above swaps tier set |
| S16 | Rate table                         | Rows of usage rates (Input / Output / Cache write / Cache read) in tabular form |
| S17 | Banner strip                       | Narrow full-width strip: one headline + 1-2 CTAs, no visual |
| S18 | Full-width CTA panel               | Tall full-width band: headline + subhead + CTAs; theme (light/dark) is variable |
| S19 | CTA panel + newsletter form        | S18 plus inline email-capture form with submit and status |
| S20 | Path picker (2-card fork)          | Two large parallel cards representing exclusive paths |
| S21 | Pictogram + nested sub-cards       | Animated pictogram as anchor; sub-cards below, each with own "learn more" |
| S22 | Pill/tag cloud columns             | 3-5 vertical columns of category pills, each column has a header |
| S23 | Lead card + companion carousel     | One featured large card; secondary cards in a carousel beside it |
| S24 | Resource grid with source tags     | Card grid; each card carries a source-type tag (Docs / Blog / Video / etc.) |
| S25 | Two-column prompt/artifact panel   | Left column = mock user prompt; right column = mock generated artifact |
| S26 | Download/install button strip      | Horizontal row of platform-specific install buttons (macOS / Windows / iOS / etc.) |
| S27 | Footer navigation grid             | Multi-column nav grid + legal/copyright row |
| S28 | Sub-hero with video + CTA pair     | Mid-page hero-like restatement: video on one side, headline + CTA on the other |

---

## S0 — Standalone heading strip

Just an H2 (and optional eyebrow) acting as a section label, no content beneath.

- **Slots:** one H2; optional eyebrow above the H2.
- **Layout:** single-row block; vertical stack of optional eyebrow over the H2.
- **Allowed variants:** with eyebrow / without eyebrow.

**Determinations**
- The strip spans the marketing medium container (1192px max) and is left-aligned, matching the reading-axis of the sections it labels.
- Vertical padding uses `--section-pad-small` (64–96px clamp); the eyebrow-to-H2 gap is `--sp-0-75` (12px).

---

## S1 — Centered text + visual below

Headline + subhead + CTAs centered; visual (video/screenshot) sits below.

- **Slots:** headline; subhead; one or more CTAs; one visual (video or screenshot) below.
- **Layout:** vertical stack, all centered horizontally — text block above visual.
- **Allowed variants:** visual = video or screenshot.

**Determinations**
- CTA count is 1–2; the first is a primary button, the optional second a tertiary/text button beside it (`--sp-1`, 16px, gap). Above 2 CTAs, fall back to S3 or S17.
- The visual sits at a fixed 16:9 aspect ratio, capped at the full marketing primary container (1440px), with `--sp-4` (52–64px clamp) between the text block and the visual.
- Below the 700px breakpoint the CTA pair stacks vertically full-width; the visual stays 16:9 and reflows to container width.

---

## S2 — Two-column text/visual

Text + CTAs on one side, single visual on the other.

- **Slots:** text column (headline + subhead + CTAs); visual column (single image/screenshot/video).
- **Layout:** horizontal two-column split — text and visual side by side.
- **Allowed variants:** text-left/visual-right and the mirror; visual = image, screenshot, or video.

**Determinations**
- Column ratio is 50/50 on the 12-column grid (each column spans 6). The grid gutter (32px) separates the columns.
- Below the 700px breakpoint the columns stack to a single column with the text block first, then the visual; the grid drops to 2 columns and the two slots each take the full row.
- The visual is centered vertically against the text column and capped at the column width; it carries no fixed aspect ratio so source media of any ratio fits.

---

## S3 — Centered text + embedded affordance

Centered headline; interactive element (chat input, install snippet, prompt chips) sits where the visual would.

- **Slots:** centered headline (optional subhead/CTAs); one embedded interactive affordance (chat input, install/code snippet, prompt chips).
- **Layout:** vertical stack, centered — text above the affordance, replacing what would otherwise be a visual.
- **Allowed variants:** affordance = chat input, install/code snippet, or prompt chips.

**Determinations**
- Exactly one affordance per shape. When more than one affordance is needed, repeat the shape as separate sections rather than stacking affordances.
- CTAs, when present, sit below the affordance (the affordance is the section's primary action). The affordance is centered, capped at the marketing small container (960px), with `--sp-3` (40–48px clamp) between the heading block and the affordance.

---

## S4 — Static card grid

N cards in M columns, identical card structure (icon/title/blurb/optional CTA).

- **Slots:** N cards, each with icon, title, blurb, and optional CTA.
- **Layout:** grid of M columns by ⌈N/M⌉ rows; uniform cell structure.
- **Allowed variants:** with or without per-card CTA; with or without icon.

**Determinations**
- Default column count is 3 (M = 3) on desktop, dropping to 2 columns below the 700px breakpoint and 1 column below 480px. N is content-driven; the last row left-aligns any remainder.
- Grid gap is the 32px grid gutter on both axes. Cards use the Full promo card or Feature card spec from `components.md` (`--radius-xl` outer, 32px inner padding).
- Cards animate in with the `--card-index` stagger (motion.md §15.4), suppressed under `prefers-reduced-motion: reduce`.

---

## S5 — Tagged card grid

S4 plus an eyebrow tag/pill above each card title.

- **Slots:** N cards each with eyebrow tag/pill, title, blurb, optional icon, optional CTA.
- **Layout:** grid (inherits S4); tag/pill sits above the card title inside each card.
- **Allowed variants:** inherits S4 variants; adds tag/pill style.

**Determinations**
- Tags use the Outline pill badge spec (12px caption, sentence case, `--radius-xs` corners). Styling is uniform across cards — one consistent neutral pill — rather than color-per-category, so the grid reads as one set.
- The tag sits `--sp-0-75` (12px) above the title. All other layout inherits S4.

---

## S6 — Tabs with one panel per tab

Tab strip + a large panel that swaps; each tab gets a full visual.

- **Slots:** tab strip (one tab label per panel); per-tab panel containing a full visual plus accompanying copy.
- **Layout:** horizontal tab strip above a single full-width panel that swaps on selection.
- **Allowed variants:** count and position of tabs; visual-only vs. visual + text panels.

**Determinations**
- Tabs are top-oriented and horizontal. Tab count is 2–5; beyond 5 the strip becomes a horizontal scroll row rather than wrapping.
- The first tab is selected by default. The strip uses the Pill-tab strip component (`role="tablist"` + `role="tab"` + `aria-selected` + `aria-controls`, per components.md §14 Pill-tab strip), with the panel as `role="tabpanel"`.
- Panel swaps use the standard cross-fade; honor `prefers-reduced-motion: reduce` by swapping instantly.

---

## S7 — Alternating image+text rows

Horizontal rows; image-left/text-right alternates each row.

- **Slots:** per-row image and accompanying text block (headline, blurb, optional CTA).
- **Layout:** vertical stack of horizontal rows; first row image-left/text-right, then alternating.
- **Allowed variants:** start side (image-left or image-right) for row 1.

**Determinations**
- Row count is content-driven, 2 or more. Each row is a 50/50 split on the 12-column grid with the 32px gutter.
- Below the 700px breakpoint every row collapses to a single column with image above text, regardless of the desktop side — alternation is dropped on narrow widths so reading order stays consistent top-to-bottom.
- Row-to-row gap is `--sp-5` (64–80px clamp).

---

## S8 — Horizontal carousel

Card row with prev/next arrows; more items than fit on screen.

- **Slots:** N card items; prev/next arrow controls; optional pagination indicator.
- **Layout:** single horizontal row of cards exceeding viewport width, with scroll/paging affordances.
- **Allowed variants:** with or without pagination dots; auto-advance off/on.

**Determinations**
- Cards are a fixed width sized so roughly 3 fit within the marketing primary container at desktop, with the next card peeking ~10% to signal overflow. Inter-card gap is `--sp-1-5` (24px).
- Scroll snaps card-by-card (`scroll-snap-type: x mandatory`, `scroll-snap-align: start`). Auto-advance is off by default; when on, it pauses on hover and on focus within the carousel, and is suppressed under `prefers-reduced-motion: reduce`.
- Prev/Next controls carry `aria-label` and are disabled (with `aria-disabled`) at the start/end. Below 700px the row is finger-scrollable and the arrows hide.

---

## S9 — Marquee strip

Continuously scrolling horizontal row (logos/icons); may duplicate items.

- **Slots:** N logo/icon items in a single horizontal row.
- **Layout:** single full-width row with continuous horizontal scroll; items may duplicate to fill loop.
- **Allowed variants:** scroll direction; pause-on-hover; duplicated vs. unique item set.

**Determinations**
- The item set duplicates to fill at least two viewport widths so the loop is seamless. Default scroll direction is right-to-left.
- Scroll completes one full loop in ~40s (a calm, non-distracting speed); item-to-item spacing is `--sp-4` (52–64px clamp). The strip pauses on hover.
- The animation is purely decorative: it is gated behind `prefers-reduced-motion: no-preference` and the strip renders as a static, wrapped row under reduced motion.

---

## S10 — Numbered step row

3-column (occasionally more) row with explicit step ordering.

- **Slots:** ordered steps (typically 3), each with a step number, title, and blurb.
- **Layout:** horizontal row of columns (typically 3); explicit ordinal numbering on each step.
- **Allowed variants:** step count = 3 by default, occasionally more; numbering style (digit vs. ordinal).

**Determinations**
- Default step count is 3; columns sit on the 12-column grid (4 columns each). When step count exceeds 3, the row wraps onto additional grid rows rather than scrolling, keeping each step at the same column width.
- Below the 700px breakpoint steps stack to a single column in numeric order. Numbering uses leading digits (1, 2, 3) by default.
- The numbered list is semantically an ordered list (`<ol>`) so the step sequence is conveyed without relying on the visual numbers alone.

---

## S11 — 3-up stacked pull-quotes

Three quote blocks stacked vertically, no card framing, attribution under each.

- **Slots:** three quote blocks; per-quote attribution (name/role/org).
- **Layout:** vertical stack of three quote blocks; no card framing or surface around each quote.
- **Allowed variants:** with or without per-quote logo; with or without metric callout.

**Determinations**
- Three is the default; the shape accepts 2–4 quotes using the same stacked treatment if a section needs a different count.
- Quotes are centered within the marketing small container (960px) with `--sp-5` (64–80px clamp) between blocks. Attribution sits directly beneath each quote in tertiary ink.

---

## S12 — Quote swiper with logos

Rotating quote in a viewport; logo carousel beneath rotates in sync.

- **Slots:** rotating quote viewport (one quote at a time with attribution); paired logo carousel beneath.
- **Layout:** quote block stacked above logo carousel; both rotate in sync.
- **Allowed variants:** auto-advance off/on; with or without metric per quote.

**Determinations**
- Quote count and logo count are equal and paired one-to-one (each quote is bound to its source's logo); the logo carousel advances to the same index as the quote.
- Auto-advance is off by default; when on, it pauses on hover/focus and is suppressed under reduced motion, falling back to manual prev/next. Advance interval is ~7s when auto-advance is on.

---

## S13 — Single hero quote

One large quote, often with metric, treated as a near-hero element.

- **Slots:** one large quote; optional metric; attribution.
- **Layout:** single dominant block treated near-hero in scale.
- **Allowed variants:** with or without metric.

**Determinations**
- The quote is capped at the marketing small container (960px) with `text-wrap: balance` and runs no longer than ~240 characters; longer testimonials use S11 instead.
- When present, the metric sits above the quote as an oversized display number (Primary Sans, weight 600–700), with attribution below the quote. Vertical padding uses `--section-pad-large` (128–200px clamp) to give the block its near-hero scale.

---

## S14 — Accordion list

Collapsible items, each header expands to reveal answer; vertical stack.

- **Slots:** N collapsible items, each with header and revealed body.
- **Layout:** vertical stack of accordion rows.
- **Allowed variants:** single-open vs. multi-open expansion; default-open first item or none.

**Determinations**
- Default behavior is multi-open (each item toggles independently) with all items closed at load. Item count is content-driven, 2 or more.
- Items are separated by a 1px hairline (`--border-subtle`) rather than card framing; the stack is capped at the marketing small container (960px). Headers carry `aria-expanded` and `aria-controls` per accessibility.md §18.3, and the expand/collapse uses a max-height transition gated by reduced motion.

---

## S15 — Tier card row + segment toggle

Horizontal row of 2-4 tier cards; segment toggle above swaps tier set.

- **Slots:** segment toggle (e.g., Individual ↔ Team); 2–4 tier cards.
- **Layout:** segment toggle anchored above; horizontal row of 2–4 tier cards below.
- **Allowed variants:** tier count 2, 3, or 4; toggle segment count.

**Determinations**
- The segment toggle is centered above the row and uses the Pill-tab strip component as a `role="radiogroup"` (it filters the tier set in place rather than swapping distinct panels).
- One tier may be marked featured: it paints a 1px accent border and a "featured" pill at its top, and sits in the visual center of the row. Tier cards use the Pricing card spec from `components.md`.
- Below the 700px breakpoint the tier row stacks to a single column with the featured tier first.

---

## S16 — Rate table

Rows of usage rates (Input / Output / Cache write / Cache read) in tabular form.

- **Slots:** column headers for rate categories; one row per priced unit; cells for rate values.
- **Layout:** tabular grid with row headers and rate columns.
- **Allowed variants:** column set may include Input, Output, Cache write, Cache read.

**Determinations**
- Rendered as a semantic `<table>` with `<th scope>` on the row and column headers. Rate values are right-aligned; the leading row-header column is left-aligned.
- Rates display with an explicit currency symbol and per-unit suffix in each cell. Rows render in the order the content supplies them (no automatic re-sort). The column set is extensible — additional rate categories append as further columns.
- Below the 700px breakpoint the table becomes horizontally scrollable within its container rather than reflowing cells.

---

## S17 — Banner strip

Narrow full-width strip: one headline + 1-2 CTAs, no visual.

- **Slots:** one headline; 1–2 CTAs.
- **Layout:** narrow full-width horizontal strip; no visual.
- **Allowed variants:** CTA count = 1 or 2.

**Determinations**
- The strip resolves its background through the active theme's `--surface-secondary` so it reads as a distinct band against the page ground, in either light or dark mode.
- Headline and CTAs sit on one row, headline left and CTAs right, within the marketing medium container; vertical padding uses `--section-pad-small` (64–96px clamp). Below 700px the CTAs wrap beneath the headline.

---

## S18 — Full-width CTA panel

Tall full-width band: headline + subhead + CTAs; theme (light/dark) is variable.

- **Slots:** headline; subhead; one or more CTAs.
- **Layout:** tall full-width band; vertically centered content block.
- **Allowed variants:** theme = light or dark.

**Determinations**
- CTA count is 1–2 (a primary button plus an optional tertiary peer). Content is centered both horizontally and vertically.
- The band height comes from `--section-pad-large` (128–200px clamp) top and bottom against a centered content block, giving the tall full-width feel without a fixed pixel height.

---

## S19 — CTA panel + newsletter form

S18 plus inline email-capture form with submit and status.

- **Slots:** inherits S18 slots; adds inline email-capture form (input + submit) and status message slot.
- **Layout:** inherits S18 layout; newsletter form sits inline within the band.
- **Allowed variants:** inherits S18 theme variants.

**Determinations**
- The form sits below the CTAs as the section's final affordance (the CTAs lead; the form captures intent for those who scroll to it). Input and submit sit on one row at desktop and stack below 480px.
- The form uses the Standard text input + Primary button specs; required-field and email-format validation follow accessibility.md §18.6, with the status message rendered in the status slot under `aria-live="polite"`.

---

## S20 — Path picker (2-card fork)

Two large parallel cards representing exclusive paths.

- **Slots:** exactly two large cards, each representing an exclusive path; per-card headline, blurb, and CTA.
- **Layout:** horizontal pair of equally-sized large cards.
- **Allowed variants:** with or without per-card visual/illustration.

**Determinations**
- Count is fixed at two. The cards are a 50/50 split on the 12-column grid with the 32px gutter, each using the Full promo card spec.
- Below the 700px breakpoint the cards stack to a single column in source order (the first-listed path renders on top).

---

## S21 — Pictogram + nested sub-cards

Animated pictogram as anchor; sub-cards below, each with own "learn more".

- **Slots:** one animated pictogram anchor; multiple sub-cards beneath, each with its own "learn more" CTA.
- **Layout:** anchor pictogram above; sub-card group below.
- **Allowed variants:** sub-card count; pictogram motion style.

**Determinations**
- The pictogram is centered above the group at a fixed 1:1 aspect ratio. Its motion is decorative and gated behind `prefers-reduced-motion: no-preference`, rendering as a static glyph under reduced motion.
- Sub-cards follow the S4 grid (3 columns default, 2 below 700px, 1 below 480px) with the 32px gutter; the "learn more" CTA is a tertiary/text button at the foot of each card. The pictogram-to-sub-card gap is `--sp-4` (52–64px clamp).

---

## S22 — Pill/tag cloud columns

3-5 vertical columns of category pills, each column has a header.

- **Slots:** 3–5 columns; per-column header; per-column list of category pills.
- **Layout:** 3–5 vertical columns side by side.
- **Allowed variants:** column count 3, 4, or 5.

**Determinations**
- Columns sit on the 12-column grid (evenly dividing the row by column count) with the 32px gutter. Below the 700px breakpoint the columns stack to a single column, header then pills, in source order.
- Pills within a column render in the order the content supplies them (no automatic re-sort). Each pill is a non-interactive Outline pill badge by default; when a pill filters or navigates, it becomes a `<button>`/`<a>` with the foundation focus ring, per the badge's interactive variant in `components.md`.

---

## S23 — Lead card + companion carousel

One featured large card; secondary cards in a carousel beside it.

- **Slots:** one featured lead card; companion carousel of secondary cards.
- **Layout:** horizontal arrangement — lead card on one side, carousel beside it.
- **Allowed variants:** lead-card side (left or right); carousel scroll vs. paginate.

**Determinations**
- The lead card spans grid columns 1–6 and the companion carousel spans 7–12, giving a 50/50 footprint with the lead at full height and the carousel showing secondary cards with a peek of the next.
- The companion carousel inherits S8 behavior (snap, prev/next, reduced-motion handling). Below the 700px breakpoint the lead card stacks above the carousel, which becomes finger-scrollable.

---

## S24 — Resource grid with source tags

Card grid; each card carries a source-type tag (Docs / Blog / Video / etc.).

- **Slots:** N cards, each carrying a source-type tag (Docs / Blog / Video / etc.), title, blurb, optional thumbnail.
- **Layout:** grid (S4-style) with source tag per card.
- **Allowed variants:** source-tag set is extensible (Docs / Blog / Video / etc.).

**Determinations**
- Inherits the S4 grid (3 columns default, 2 below 700px, 1 below 480px) and uses the Catalog card spec from `components.md`.
- The source tag sits in the card's top-left corner as a small label badge (per the Catalog card). Tag styling is uniform — one neutral badge treatment across all source types — rather than color-per-source, so the grid reads as one set; the tag's text carries the source-type distinction.

---

## S25 — Two-column prompt/artifact panel

Left column = mock user prompt; right column = mock generated artifact.

- **Slots:** left column with a mock user prompt; right column with the mock generated artifact.
- **Layout:** horizontal two-column split, fixed left/right roles.
- **Allowed variants:** artifact type (text/code/image).

**Determinations**
- The prompt/artifact roles are fixed: prompt always left, artifact always right (the left-to-right order mirrors the cause-then-effect reading). Columns are 50/50 on the 12-column grid with the 32px gutter.
- Exactly one prompt/artifact pair per shape; when several examples are needed, repeat the shape as separate sections rather than stacking pairs.
- The artifact renders per its type: text in body type, code in the Code block component, image in a contained tile. Below the 700px breakpoint the columns stack with prompt above artifact.

---

## S26 — Download/install button strip

Horizontal row of platform-specific install buttons (macOS / Windows / iOS / etc.).

- **Slots:** one button per platform (macOS / Windows / iOS / etc.).
- **Layout:** single horizontal row of platform buttons.
- **Allowed variants:** platform set is extensible.

**Determinations**
- Buttons render in a fixed source-defined order (not OS-detected reordering), so the layout is stable across visitors. The detected platform may be visually emphasized (primary fill) while the rest are secondary, but their position does not move.
- Buttons sit on one centered row with `--sp-1` (16px) gap; below the 700px breakpoint they wrap to multiple centered rows rather than scrolling.

---

## S27 — Footer navigation grid

Multi-column nav grid + legal/copyright row.

- **Slots:** multiple nav columns (per-column header + links); legal/copyright row.
- **Layout:** multi-column grid above a legal/copyright row.
- **Allowed variants:** number of nav columns; with or without social/utility row.

**Determinations**
- Default is 4–6 nav columns on the 12-column grid, collapsing to 2 columns below 700px and 1 below 480px. The shape uses the Footer component spec from `components.md` §12.7 (column headings as `<h3>`, `<footer role="contentinfo">`).
- The legal/copyright row sits full-width beneath the grid, separated by `--sp-4` (52–64px clamp), and carries the copyright line plus legal links (and a locale/language selector when present) per the Footer slot definitions.

---

## S28 — Sub-hero with video + CTA pair

Mid-page hero-like restatement: video on one side, headline + CTA on the other.

- **Slots:** video on one side; headline plus a CTA pair on the other.
- **Layout:** horizontal two-column split — video and text/CTA columns side by side.
- **Allowed variants:** video-left/text-right and the mirror.

**Determinations**
- The CTA pair is exactly two CTAs (a primary button plus a tertiary peer); when only one action is needed, use S2 instead.
- Columns are 50/50 on the 12-column grid with the 32px gutter; the video sits at a fixed 16:9 aspect ratio capped at its column width. Below the 700px breakpoint the columns stack with the video above the text/CTA column, and the CTA pair stacks full-width.

---

## Shape-set conventions

- Per-shape slot and layout detail is definitive at the level stated above. Column counts, padding, theme constraints, responsive collapse, and per-shape bounds resolve against `foundations/` (the `--section-pad-*` and `--sp-*` scales, the 12-column grid, the 480 / 700 / 1024 / 1440 breakpoints) and the component specs in `components.md`.
- Light vs. dark theme is a per-shape variable only where the shape names it (S18 explicitly, S19 by inheritance, S17 via its `--surface-secondary` band). Every other shape inherits the surrounding section's theme.
- "Card grid" shapes (S4, S5, S24) share one column policy: 3 columns at desktop, 2 below the 700px breakpoint, 1 below 480px, with the 32px grid gutter on both axes and the `--card-index` stagger on entry.
- S10 step rows wrap onto additional grid rows when the step count exceeds 3 and stack to a single column below the 700px breakpoint, as stated in the S10 determinations.
