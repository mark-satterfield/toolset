# Shape-set conventions

Shapes are content-free slot arrangements for one Section — spatial composition patterns independent of what content fills them. These conventions bind every Shape in this library.

## Definitive detail and foundations resolution

Per-Shape slot and layout detail is definitive at the level each entry states. Column counts, padding, theme constraints, responsive collapse, and per-Shape bounds resolve against `foundations/` — the `--section-pad-*` and `--sp-*` scales and the 12-column grid (`foundations/layout.md` §11), the breakpoint set (`foundations/responsive.md` §17.1), motion (`foundations/motion.md`), and accessibility (`foundations/accessibility.md`) — and the component specs in the components library.

## Theme and ground

No Shape sets its own theme or Section ground. Every Shape inherits the surrounding Section's theme and takes the Section's scheduled `surface-primary`/`surface-secondary` ground from `rules/page-constraints/ground-alternation.md`. A Section that must read as a distinct theme (e.g. a dark band) is a named theme island declared on the Page, not a Shape-level choice.

## Interactive and animated Shapes are self-contained

Shape-level behavior — the logo-marquee scroll, card-carousel paging/prev-next, quote-swiper rotation, tabbed-panels tab switching, accordion expand/collapse — is NOT provided by the generated component stylesheet or any shared script. Each such Shape declares `self_contained: true` and its fragment carries its own scoped `<style>` and, where the behavior cannot be achieved in pure CSS, a scoped `<script>` written as an IIFE that scopes itself to its own instance(s) so multiple copies on one page never collide. That script implements the ARIA keyboard contract for the pattern from `foundations/accessibility.md` (e.g. tablist arrow-key navigation, accordion `aria-expanded` toggling), and any motion is gated behind `@media (prefers-reduced-motion: no-preference)` with a static fallback. A fragment whose behavior is defined nowhere is broken — it must work standalone.

## Card-grid column policy

"Card grid" Shapes (card-grid, tagged-card-grid, resource-grid) share one column policy: 3 columns at desktop, 2 below the tablet breakpoint, 1 below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1), with the grid gutter (`foundations/layout.md` §11.6) on both axes and the `--card-index` stagger on entry.

## Step rows

numbered-steps step rows wrap onto additional grid rows when the step count exceeds 3 and stack to a single column below the tablet breakpoint, per the numbered-steps determinations.

## Universal Section slots

Every Shape accepts two optional Section-level slots ahead of its own: `eyebrow` — a short label line above the Section's heading — and `media` — one image, illustration, or embed belonging to the Section as a whole. Both are supplied-or-absent: a Shape renders the slot when the content carries it and renders nothing when it does not, and neither slot changes the Shape's layout contract. The universal slots are declared once in `libraries/FORMAT.md`; a Shape entry names them only to state a placement that differs from the default.

Default placement is the heading stack: the eyebrow sits directly above the Section's heading at the caption role, and the media sits after the heading stack and before the Shape's own content. A Shape whose composition requires otherwise — a per-card tag inside tagged-card-grid and resource-grid, the subjects line in article-header, a hero whose media is already a declared column — states its placement in its own Determinations.

An eyebrow is content, not decoration: it appears because the brief supplies one and is omitted because the brief does not. Splitting a supplied eyebrow into its own Section is a composition error — the eyebrow, the heading, and the content they introduce are one Section. The standalone `section-header` Section remains available for a label that genuinely introduces a *run* of following Sections rather than the content beneath it.

## Heading alignment registers

Heading alignment follows the Section's content, not a free per-Section choice. Compose each Section in one register.

**Left register is the default:** the lead heading aligns to the start, matching its content's reading axis — use it whenever the content reads left (accordion, rate-table, alternating-rows, card-grid, tag-columns, resource-grid, and the standalone heading-strip).

**Centered register** centers the lead heading and its content together as one column — reserve it for heroes and full-width editorial / CTA / quote blocks (centered-stack, centered-affordance, stacked-quotes, feature-quote, cta-panel, cta-newsletter) and for short, symmetric content (a centered numbered-steps row, a symmetric 2–3 brief-card grid).

A centered lead heading must **never** sit above left-reading long-form content (an accordion, a data table, a paragraph stack): when the content reads left, the whole Section — heading included — is left. Sub-headings (card titles, column headers, per-row / per-step titles, H3 and below) inherit their Section's register and never fight it.
