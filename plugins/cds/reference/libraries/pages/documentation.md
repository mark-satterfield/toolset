---
kind: page
name: documentation
page_family: docs
aliases: [documentation page, docs page, reference page, legal page, terms page, policy page]
status: stable
sections:
  - { section: doc-header, required: true, notes: "always first" }
  - { section: doc-body, required: true, notes: "always last" }
constraints: []
---

# Documentation Page

Long-form reference content: legibility and stability. Closest in style to editorial, with optional side navigation. This Page is content Sections only, in the fixed order above: title → body; the top-nav and site-footer Sections, and any outer offset, belong to the user's Shell. In-page anchor links scroll smoothly.

## Theme

`editorial` only — no theme rotation. Any footer treatment belongs to the user's Shell. Long-form pages use zero radius: structure relies on whitespace and hairlines.

## Register rules

### Layout

- Reading column: `--column-reading` (calibrates to 640px), centered, or left-aligned with a sticky sidebar to the right.
- An optional `--docs-outer-offset` inset (`foundations/layout.md` §11.2; calibrates to 316px per side at the widest viewport) frames the content region when the user's Shell applies it.

### Navigation

- Optional in-page anchor links; anchor navigation scrolls smoothly.

### Typography (editorial scale, `foundations/typography.md` §13.5)

- Title: Editorial-Display-2 (calibrates to 64px desktop, weight 700, line-height 100%).
- Section h2: Headline 5, margin `calc(2 * var(--sp-1)) 0 var(--sp-0-5)` (`foundations/layout.md` §11.5; calibrates to 32px 0 8px).
- Body paragraph: Body 2 with the `.serif` modifier (weight 400, line-height 155%, margin `--sp-1`).
- Ordered list: Editorial Serif at the Body 2 size, weight 400, line-height `--lh-140` (calibrates to 23.8px) — a declared departure from the Body 2 `.serif` role's 500 / 155%, as no §13.5 role defines 400-weight serif list text. Decimal markers at every level — no alphabetic nesting.
- Inline `<strong>`: the surrounding family at weight 600.
- Defined terms: `<strong>` with bare quote marks in running text.
- Effective-date stamp and "Previous Version" link: Text Label.

### Components

- Hand-numbered h2 headings ("1. Section name.", "11. Next section.").
- A single hard 1px rule at `--border-strong` between the metadata row and the body — the only line work on the page.
- Language picker (single-option dropdown by default).
- No cards, no badges, no shadows.

### Motion (documentation register, `foundations/motion.md` §15.3)

- Body content does not animate; link colors may transition (200ms).

### Responsive

- Reading column scales to full content width below 700px.
- When the user's Shell applies an outer offset, it reduces to the standard page gutter below the desktop breakpoint.

### Do not

- No `text-transform: uppercase` on all-caps disclaimers — the source text is set upper-case.
- No shadows or boxes.
- No state colors anywhere in the body.
