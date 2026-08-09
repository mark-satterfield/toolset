---
kind: page
name: primary-landing
page_family: landing
aliases: [landing page, primary landing page, product landing page, marketing landing page]
status: stable
sections:
  - { section: hero, required: true, notes: "always first; alternation index 1" }
  - { section: trust-strip, required: false }
  - { section: validation-block, required: false }
  - { section: capability-showcase, required: false }
  - { section: workflow-process, required: false }
  - { section: use-case-routing, required: false }
  - { section: path-fork, required: false }
  - { section: interactive-demo, required: false }
  - { section: pricing, required: false, notes: "theme island: clarity" }
  - { section: trust-detail, required: false }
  - { section: faq, required: false }
  - { section: news-updates, required: false }
  - { section: resource-directory, required: false }
  - { section: cross-promo, required: false, notes: "may embed inside trust-detail — see cross-promo composition notes" }
  - { section: sub-hero, required: false }
  - { section: final-cta, required: false, notes: "omitted entirely when page_meta.buying_mode == browse; takes the footer ground with a light hairline seam — see the Section entry" }
  - { section: section-header, required: false, notes: "standalone label preceding another content unit; may appear multiple times" }
constraints: [ground-alternation, variety-principle]
---

# Primary Landing Page

The longest Page in the system: introduces the product, demonstrates it, and closes on a conversion moment. The `sections` list is the typical order when a Section is present — which Sections appear is a content decision; the order above governs when they do.

This Page is content Sections only; topbar and footer belong to the user's Shell.

## Theme islands

Pricing (pricing) → `clarity`. Final CTA (final-cta) → the island the Shell's footer wears, so the closing Section and the footer share one ground across the seam (`libraries/sections/final-cta.md`). Islands apply on top of the scheduled ground per `ground-alternation`. The hero uses `default`; feature blocks stay on the principal theme — grounds alternate per `ground-alternation`, never as a theme rotation.

## Register rules

### Layout

- Container: `--container-marketing-primary` (`.u-container`; calibrates to 1440px); side gutters on the 32–64px clamp (`foundations/layout.md` §11).
- Section padding: `--section-pad-main` default; `--section-pad-large` for the hero; `--section-pad-page-top` above the fold only.
- 12-column grid above 700px (`foundations/layout.md` §11.6).

### Typography (marketing scale, `foundations/typography.md` §13.4)

- Hero h1: Display-1 (`text-wrap: balance`, `max-width: 20ch`).
- Section h2: H2.
- Body: Body 1 on light grounds; Body 2 inside cards.
- Card titles: H3.

### Components

- Pill-tab strips for in-Section navigation.
- Feature cards with left or top hairline anchors.
- Full promo cards with 1px outer border and transparent inner fill.
- Primary button for the principal conversion CTA (the loud action); secondary button for secondary conversion CTAs (the quiet alternative).

### Motion (landing register, `foundations/motion.md` §15.3)

- Hero word-by-word reveal driven by the `--reveal-*` properties.
- Card-grid stagger on viewport entry; IntersectionObserver-driven fades.
- Dropdowns open over 600ms.
- One mid-page Section carries the scroll-driven panel that grows from inset to full-bleed.

### Responsive

- Feature cards stack vertically below the tablet breakpoint.
- Section padding reduces to the `--section-pad-main` mobile floor (calibrates to 56px).

### Do not

- No photography in feature cards.
- The hero h1 does not end with a period.
- No fixed-width box on the hero — it inherits the full container.
