# Shape-set conventions

Shapes are content-free slot arrangements for one Section — spatial composition patterns independent of what content fills them. These conventions bind every Shape in this library.

## Definitive detail and foundations resolution

Per-Shape slot and layout detail is definitive at the level each entry states. Column counts, padding, theme constraints, responsive collapse, and per-Shape bounds resolve against `foundations/` — the `--section-pad-*` and `--sp-*` scales and the 12-column grid (`foundations/layout.md` §11), the breakpoint set (`foundations/responsive.md` §17.1), motion (`foundations/motion.md`), and accessibility (`foundations/accessibility.md`) — and the component specs in the components library.

## Theme and ground

No Shape sets its own theme or Section ground. Every Shape inherits the surrounding Section's theme and takes the Section's scheduled `surface-primary`/`surface-secondary` ground from `rules/page-constraints/ground-alternation.md`. A Section that must read as a distinct theme (e.g. a dark band) is a named theme island declared on the Section Container, not a Shape-level choice.

## Interactive and animated Shapes are self-contained

Shape-level behavior — the logo-marquee scroll, card-carousel paging/prev-next, quote-swiper rotation, tabbed-panels tab switching, accordion expand/collapse — is NOT provided by the generated component stylesheet or any shared script. Each such Shape declares `self_contained: true` and its fragment carries its own scoped `<style>` and, where the behavior cannot be achieved in pure CSS, a scoped `<script>` written as an IIFE that scopes itself to its own instance(s) so multiple copies on one page never collide. That script implements the ARIA keyboard contract for the pattern from `foundations/accessibility.md` (e.g. tablist arrow-key navigation, accordion `aria-expanded` toggling), and any motion is gated behind `@media (prefers-reduced-motion: no-preference)` with a static fallback. A fragment whose behavior is defined nowhere is broken — it must work standalone.

## Card-grid column policy

"Card grid" Shapes (card-grid, tagged-card-grid, resource-grid) share one column policy: 3 columns at desktop, 2 below the tablet breakpoint, 1 below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1), with the grid gutter (`foundations/layout.md` §11.6) on both axes and the `--card-index` stagger on entry.

## Step rows

numbered-steps step rows wrap onto additional grid rows when the step count exceeds 3 and stack to a single column below the tablet breakpoint, per the numbered-steps determinations.

## Eyebrows are deny-by-default

Enforced as the landing-family page constraint `rules/page-constraints/eyebrow-scope.md`. A section-level eyebrow — a short label line above a Section's heading — is authorized in exactly two places: the optional eyebrow in heading-strip (the standalone heading strip), and the per-card tag/pill inside tagged-card-grid and resource-grid. No other Shape carries a section-level eyebrow. A hero (centered-stack, split-text-media, centered-affordance, sub-hero-split), a card-grid heading (card-grid), a workflow (numbered-steps), a CTA panel (banner-strip, cta-panel, cta-newsletter), and every other Shape begin directly with the heading — no kicker above it. When a label genuinely must precede a content unit, model it as its own heading-strip Section rather than decorating an adjacent Section's heading.

## Heading alignment registers

Heading alignment follows the Section's content, not a free per-Section choice. Compose each Section in one register.

**Left register is the default:** the lead heading aligns to the start, matching its content's reading axis — use it whenever the content reads left (accordion, rate-table, alternating-rows, card-grid, tag-columns, resource-grid, and the standalone heading-strip).

**Centered register** centers the lead heading and its content together as one column — reserve it for heroes and full-width editorial / CTA / quote blocks (centered-stack, centered-affordance, stacked-quotes, feature-quote, cta-panel, cta-newsletter) and for short, symmetric content (a centered numbered-steps row, a symmetric 2–3 brief-card grid).

A centered lead heading must **never** sit above left-reading long-form content (an accordion, a data table, a paragraph stack): when the content reads left, the whole Section — heading included — is left. Sub-headings (card titles, column headers, per-row / per-step titles, H3 and below) inherit their Section's register and never fight it.
