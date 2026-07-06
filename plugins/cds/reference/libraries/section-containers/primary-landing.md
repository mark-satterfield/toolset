---
kind: section-container
name: primary-landing
family: landing
aliases: [landing page, primary landing page, product landing page, marketing landing page]
status: stable
default_shell: marketing
sections:
  - { id: T1, required: true, notes: "always first; alternation index 1" }
  - { id: T2, required: false }
  - { id: T3, required: false }
  - { id: T4, required: false }
  - { id: T5, required: false }
  - { id: T6, required: false }
  - { id: T7, required: false }
  - { id: T8, required: false }
  - { id: T9, required: false, notes: "theme island: clarity" }
  - { id: T10, required: false }
  - { id: T11, required: false }
  - { id: T12, required: false }
  - { id: T13, required: false }
  - { id: T14, required: false, notes: "may embed inside T10 — see t14 composition notes" }
  - { id: T15, required: false }
  - { id: T16, required: false, notes: "omitted entirely when page_meta.buying_mode == browse; dark variant is a named theme island" }
  - { id: T18, required: false, notes: "standalone label preceding another content unit; may appear multiple times" }
constraints: [ground-alternation, variety-principle, eyebrow-scope]
register:
  type_scale: marketing
  motion_register: landing
---

# Primary Landing Page

The longest Section Container in the system: introduces the product, demonstrates it, and closes on a conversion moment. The `sections` list is the typical order when a Section is present — which Sections appear is a content decision; the order above governs when they do.

The Shell supplies topbar and footer; this container is content Sections only.

## Theme islands

Pricing (T9) → `clarity`. A dark Final CTA (T16) → its declared island. Islands apply on top of the scheduled ground per `ground-alternation`. The hero uses `default`; feature blocks stay on the principal theme — grounds alternate per `ground-alternation`, never as a theme rotation.

## Register rules

### Layout

- Container: `--container-marketing-primary` (`.u-container`; calibrates to 1440px); side gutters on the 32–64px clamp (`foundations/layout.md` §11).
- Section padding: `--section-pad-main` default; `--section-pad-large` for the hero; `--section-pad-page-top` above the fold only.
- 12-column grid above 700px (`foundations/layout.md` §11.6).

### Navigation

- Fixed topbar with a five-trigger dropdown nav and a brand CTA on the right.
- No hide-on-scroll: the topbar stays anchored.

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

- Navigation drops to the drawer below the tablet breakpoint.
- Feature cards stack vertically below the tablet breakpoint.
- Section padding reduces to the `--section-pad-main` mobile floor (calibrates to 56px).

### Do not

- No photography in feature cards.
- The hero h1 does not end with a period.
- No fixed-width box on the hero — it inherits the full container.
